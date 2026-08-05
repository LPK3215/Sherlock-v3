# 实时业务后端验收记录

## 范围

本记录只验收 Sherlock-v3 后端中的实时业务扩展,不重复验收 Sherlock-v3 原有管理、知识库和普通聊天基础功能。

架构结论:实时模块位于 `backend/package/yuxi/realtime`,与 Sherlock-v3 FastAPI、AgentRun、模型、Tools、Skills、MCP、权限和持久化共用一个后端进程。

## 验收结果

| 能力 | 结果 | 证据 |
|---|---|---|
| 实时 Agent 模型注册/绑定 | 通过 | `test_realtime_agent_capabilities_e2e.py` |
| Agent Prompt 绑定 | 通过 | `test_realtime_agent_capabilities_e2e.py` |
| 标准 AgentRun 创建/事件流 | 通过 | 同上 |
| 文件 Tool | 通过 | 同上 |
| Skill 激活与执行 | 通过 | 同上 |
| MCP Tool | 通过 | 同上 |
| 上下文压缩/工具结果回写 | 通过 | 同上 |
| 摄像头/屏幕帧输入 | 通过 | `realtime_browser_e2e.mjs` |
| 文字输入、STT、TTS | 通过 | `realtime_browser_e2e.mjs` |
| 插话取消旧 Run | 通过 | `realtime_stage4_controls_e2e.mjs`、数据库 Run 状态 |
| 审批中断数据生成 | 后端通过 | Redis Run 事件含 `ask_user_question_required` 与完整 questions |
| 审批 resume Run | 后端逻辑已实现,浏览器闭环待验收 | `agent_run_service` resume 路径 |

## 关键运行命令

```text
pytest backend/test/e2e/test_realtime_agent_capabilities_e2e.py -q
pnpm --dir user-app lint
```

浏览器专项必须使用 Playwright 官方镜像、loopback proxy、fake media 和 camera/microphone 权限;直接从测试容器访问 `localhost:3000` 不代表 user-app。

## 当前未完成

审批卡片、断线恢复、Stable 提交和 resume Run 仍需在真实 WebRTC 浏览器条件下取得完整证据。后端本身已确认能创建 interrupted Run 和 questions。
