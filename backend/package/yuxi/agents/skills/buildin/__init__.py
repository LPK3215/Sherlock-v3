from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BuiltinSkillSpec:
    slug: str
    source_dir: Path
    description: str = ""
    version: str = "1.0.0"
    tool_dependencies: tuple[str, ...] = ()
    mcp_dependencies: tuple[str, ...] = ()
    skill_dependencies: tuple[str, ...] = ()


_SKILLS_ROOT = Path(__file__).resolve().parent

BUILTIN_SKILLS: list[BuiltinSkillSpec] = [
    BuiltinSkillSpec(
        slug="image-gen",
        source_dir=_SKILLS_ROOT / "image-gen",
        description="在 Agent 沙盒中生成图片并保存到 outputs，默认支持 Qwen-Image，也可接入其它图片生成接口。",
        version="2026.06.02",
        tool_dependencies=("present_artifacts",),
    ),
    BuiltinSkillSpec(
        slug="deep-research",
        source_dir=_SKILLS_ROOT / "deep-research",
        description="深度研究编排方法论：澄清范围、拆解规划、并行调度子智能体调研、对抗式核验、综合成带引用的结构化报告。",
        version="2026.06.05",
        tool_dependencies=("tavily_search",),
    ),
    BuiltinSkillSpec(
        slug="knowledge-base",
        source_dir=_SKILLS_ROOT / "knowledge-base",
        description="使用 Yuxi 知识库进行检索、打开文档、文档内定位和查看思维导图。",
        version="2026.06.24",
        tool_dependencies=(
            "list_kbs",
            "query_kb",
            "find_kb_document",
            "open_kb_document",
            "get_mindmap",
            "search_file",
        ),
    ),
    BuiltinSkillSpec(
        slug="mysql-reporter",
        source_dir=_SKILLS_ROOT / "mysql-reporter",
        description="基于 MySQL 数据库生成查询报表和可视化图表，适合分析业务指标、统计趋势，并用 Charts MCP 展示结果。",
        version="2026.06.05",
        mcp_dependencies=("mcp-server-chart",),
    ),
    BuiltinSkillSpec(
        slug="junior-math-learning",
        source_dir=_SKILLS_ROOT / "junior-math-learning",
        description="学生拍题助手:理解多模态题目,自主分析讲解,按需使用知识库和学习记录工具。",
        version="2026.08.04",
        tool_dependencies=(
            "save_wrong_question",
            "list_wrong_questions",
            "update_wrong_question",
            "delete_wrong_question",
            "query_kb",
            "open_kb_document",
        ),
        skill_dependencies=("knowledge-base",),
    ),
    BuiltinSkillSpec(
        slug="legal-matter-analysis",
        source_dir=_SKILLS_ROOT / "legal-matter-analysis",
        description="法律事务通用分析:识别合同、法规和事实整理任务,按需组合法律子技能与资料工具。",
        version="2026.08.04",
        tool_dependencies=(
            "list_kbs",
            "query_kb",
            "find_kb_document",
            "open_kb_document",
            "search_file",
            "save_legal_matter",
            "list_legal_matters",
            "update_legal_matter",
            "delete_legal_matter",
        ),
        skill_dependencies=("knowledge-base", "legal-contract-analysis", "legal-fact-organizer"),
    ),
    BuiltinSkillSpec(
        slug="legal-contract-analysis",
        source_dir=_SKILLS_ROOT / "legal-contract-analysis",
        description="合同和协议分析:提取条款、解释权利义务、标注常见风险并区分事实与分析。",
        version="2026.08.04",
        tool_dependencies=("ocr_parse_file", "search_file", "open_kb_document"),
    ),
    BuiltinSkillSpec(
        slug="legal-fact-organizer",
        source_dir=_SKILLS_ROOT / "legal-fact-organizer",
        description="法律事实整理:建立事件时间线、证据清单和待补充信息,不把用户陈述自动认定为事实。",
        version="2026.08.04",
        tool_dependencies=("ocr_parse_file",),
    ),
    BuiltinSkillSpec(
        slug="visual-observation",
        source_dir=_SKILLS_ROOT / "visual-observation",
        description="视觉观察总流程:读取当前图片、摄像头或屏幕画面,区分直接观察与推断,按需核验并在确认后保存摘要。",
        version="2026.08.04",
        tool_dependencies=("save_visual_observation", "list_visual_observations"),
    ),
    BuiltinSkillSpec(
        slug="visual-identification",
        source_dir=_SKILLS_ROOT / "visual-identification",
        description="识别当前画面中的物体、植物、动物、商品或设备,表达候选结果、依据和不确定性。",
        version="2026.08.04",
        skill_dependencies=("visual-observation",),
    ),
    BuiltinSkillSpec(
        slug="visual-research",
        source_dir=_SKILLS_ROOT / "visual-research",
        description="对视觉识别结果进行按需搜索或知识库核验,保留来源并避免把候选识别说成专业鉴定。",
        version="2026.08.04",
        tool_dependencies=("query_kb", "open_kb_document", "search_file"),
        skill_dependencies=("visual-observation", "knowledge-base"),
    ),
    BuiltinSkillSpec(
        slug="career-work",
        source_dir=_SKILLS_ROOT / "career-work",
        description="职场与个人工作总流程:整理工作事项、会议和面试信息,生成行动项并按需保存用户确认的记录。",
        version="2026.08.04",
        tool_dependencies=("save_career_record", "list_career_records"),
    ),
    BuiltinSkillSpec(
        slug="career-document",
        source_dir=_SKILLS_ROOT / "career-document",
        description="处理简历、求职材料、会议纪要和职业文档,区分原文事实、建议和待确认信息。",
        version="2026.08.04",
        skill_dependencies=("career-work",),
    ),
    BuiltinSkillSpec(
        slug="career-planning",
        source_dir=_SKILLS_ROOT / "career-planning",
        description="把用户明确的职业目标拆成可执行的阶段、行动项和复盘记录,不替用户做未经确认的承诺。",
        version="2026.08.04",
        skill_dependencies=("career-work",),
    ),
]
