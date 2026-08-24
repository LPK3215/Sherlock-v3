from __future__ import annotations

import inspect as py_inspect
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import get_args, get_origin


def _resolve_injected_arg_keys(func: Callable) -> frozenset[str]:
    """解析函数签名中的运行时注入参数名。

    langchain 在构建 StructuredTool 时用 `signature(fn)`（默认不 eval 字符串注解）
    识别注入参数；工具文件一旦使用 `from __future__ import annotations`，注解会变成
    字符串，导致 `ToolRuntime` 等注入类型识别失败，真实调用时出现
    `missing required positional argument: 'runtime'`。这里用 `eval_str=True` 重新解析。
    """
    try:
        sig = py_inspect.signature(func, eval_str=True)
    except (TypeError, ValueError):
        return frozenset()

    from langchain_core.tools import InjectedToolArg
    from langchain_core.tools.base import _DirectlyInjectedToolArg

    keys: set[str] = set()
    for name, param in sig.parameters.items():
        annotation = param.annotation
        if isinstance(annotation, type) and issubclass(annotation, _DirectlyInjectedToolArg):
            keys.add(name)
            continue
        args = get_args(annotation)
        if args and any(
            isinstance(arg, InjectedToolArg)
            or (isinstance(arg, type) and issubclass(arg, InjectedToolArg))
            for arg in args[1:]
        ):
            keys.add(name)
    return frozenset(keys)


@dataclass
class ToolExtraMetadata:
    """附加元数据（用装饰器注册）"""

    category: str = ""  # 分类: buildin, knowledge, mysql, subagents, debug
    tags: list[str] = field(default_factory=list)
    display_name: str = ""  # 显示名称（给人看的名字）
    icon: str = ""
    config_guide: str = ""  # 配置说明（给人看的使用前配置提示）


# 全局注册表: tool_name -> ToolExtraMetadata
_extra_registry: dict[str, ToolExtraMetadata] = {}

# 全局工具实例列表（由 @tool 装饰器自动收集）
_all_tool_instances: list = []


def get_extra_metadata(tool_name: str) -> ToolExtraMetadata | None:
    """获取工具附加元数据"""
    return _extra_registry.get(tool_name)


def get_all_extra_metadata() -> dict[str, ToolExtraMetadata]:
    """获取所有附加元数据"""
    return _extra_registry.copy()


def get_all_tool_instances() -> list:
    """获取所有工具实例（由 @tool 装饰器自动收集）"""
    return _all_tool_instances


# 基于 langchain.tool 的拓展装饰器
def tool(
    category: str = "",
    tags: list[str] = None,
    display_name: str = "",
    icon: str = "",
    config_guide: str = "",
    name_or_callable: str | Callable | None = None,
    description: str | None = None,
    args_schema: type | None = None,
    return_direct: bool = False,
):
    """基于 langchain.tool 的拓展装饰器，同时注册元数据

    使用方式:
    @tool(category="buildin", tags=["计算"], display_name="计算器")
    def calculator(a: float, b: float, operation: str) -> float:
        ...

    或者保留原有的 name_or_callable 和 description 参数来自定义工具名称和说明。
    """
    from langchain.tools import tool as langchain_tool

    # 先应用 langchain tool 装饰器
    langchain_decorator = langchain_tool(
        name_or_callable=name_or_callable,
        description=description,
        args_schema=args_schema,
        return_direct=return_direct,
    )

    def decorator(func: Callable) -> Callable:
        # 应用 langchain 装饰器
        tool_obj = langchain_decorator(func)

        # 注册附加元数据
        tool_name = tool_obj.name
        _extra_registry[tool_name] = ToolExtraMetadata(
            category=category,
            tags=tags or [],
            display_name=display_name,
            icon=icon,
            config_guide=config_guide,
        )

        # 自动收集工具实例
        tool_obj.handle_tool_error = True
        # 修复 langchain 对字符串注解的注入参数识别（见 _resolve_injected_arg_keys）
        fn = getattr(tool_obj, "coroutine", None) or getattr(tool_obj, "func", None)
        if fn is not None:
            injected_keys = _resolve_injected_arg_keys(fn)
            if injected_keys:
                tool_obj._injected_args_keys = injected_keys
        _all_tool_instances.append(tool_obj)

        return tool_obj

    return decorator
