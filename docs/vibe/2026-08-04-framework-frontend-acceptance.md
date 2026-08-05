# Sherlock-v3 框架前端验收记录

## 范围

`web` 是 Sherlock-v3 官方管理/框架前端,继续保留官方 Agent 管理、模型管理、Tools、Skills、MCP、知识库和普通文字聊天能力。本阶段不修改其基础业务,只确认实时后端接入没有破坏它。

## 当前结论

| 项目 | 结果 | 说明 |
|---|---|---|
| 框架前端仍可独立部署 | 通过 | Compose `web` 服务运行,共享唯一 `api` |
| 官方登录/Agent 管理/模型管理 | 保留 | 本项目不重复验收官方基础功能 |
| 官方普通聊天 | 保留 | 未被实时模块替换或删除 |
| 与实时后端共存 | 通过 | 两者调用同一个 Sherlock-v3 API |
| 框架前端内嵌实时入口 | 通过 | `/agent` 进入管理端原生 Vue `/agent/realtime`,不嵌入 `user-app` |

## 第四阶段进展

- 已新增 `/agent/realtime` 原生 Vue 页面,由 `/agent` 官方聊天页面的“实时通话”按钮进入。
- 真实浏览器专项 smoke 已通过:管理端原生页面完成 WebRTC 建连、文字发送、屏幕共享开关、麦克风静音/恢复。
- 后端日志确认管理端会话进入统一实时 pipeline,并成功初始化 Whisper STT 与 Piper TTS;兼容审批 payload 的修复后 smoke 复跑通过。
- 已修复管理端实时接口缺少 Sherlock-v3 Authorization 导致的 401。
- 已修复 ICE candidate 在后端 `pc_id` 返回前提前 PATCH 导致的 404 竞态。
- 管理端页面已具备文字、摄像头、屏幕共享、音频接收、审批基础交互、插话和自动重连代码;STT/TTS/审批完整闭环仍需使用音频 fixture 和审批 Agent 做专项验收。

## 当前边界

当前成品是“一套 Sherlock-v3 后端 + 两套前端”:框架管理前端负责官方管理与普通聊天,`user-app` 负责实时语音/视频/屏幕交互。两者共享认证、Agent、模型和 AgentRun 数据。

## 第四阶段实现边界

`web` 自己实现 Vue 实时页面和媒体控制,通过 `/api/realtime/*` 调用唯一 Sherlock-v3 后端;`user-app` 保持独立用户端。两套前端共享认证、Agent、模型和 AgentRun 数据,不互相嵌入或复制。
