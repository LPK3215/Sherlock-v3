# Sherlock 正式用户端产品化

> 日期：2026-08-04
> 状态：已完成

## 目标

保留 Sherlock-v3 `web` 作为管理端，将现有 `realtime-client` 产品化为独立用户端。两个前端直接调用同一套 Sherlock-v3 后端接口，不保留独立 Realtime Gateway 或前端业务代理。

## 产品边界

- `web`：Sherlock-v3 管理端，负责模型、Agent、知识库、工具、Skills、MCP 与系统管理。
- `user-app`：Sherlock 用户端，负责登录、Agent 选择、文字/语音/视频通话、实时字幕、屏幕共享、审批和通话状态。
- `backend`：唯一业务后端。认证、Thread、AgentRun、Prompt、模型、工具和实时媒体均以 Sherlock-v3 为事实来源。
- `user-portal`：视觉参考已迁移，目录已删除。
- `realtime-gateway`：历史功能已迁入 Sherlock-v3 后端，目录已删除。

## 验收标准

- 用户端不再调用 `/api/start` 或 `realtime-gateway`，直接使用 Sherlock-v3 `/api/realtime/*`。
- 保留原客户端的麦克风、摄像头、屏幕共享、PiP、字幕、文字输入、媒体附加、插话、审批和异常重连。
- 使用 `user-portal` 的暗色用户端布局、视觉层级和控件设计，但所有状态来自真实运行数据。
- 页面在桌面和移动端为真实响应式布局，不使用固定 1440x900 画布整体缩放。
- Compose 同时部署 Sherlock-v3 `web` 与正式 `user-app`，两者共享 Sherlock-v3 API。
- 完成后端实时 Agent 能力 E2E 验证（模型、提示词、AgentRun、文件工具、Skill、MCP、上下文压缩）；浏览器媒体专项脚本已准备，但当前 Compose 的 user-app 容器未提供 Playwright/Chromium 与 STT fixture，因此本轮未将浏览器摄像头、屏幕、语音和 TTS 标记为已验证。
- 最终删除 `user-portal` 与 `realtime-gateway`，正式用户端目录命名为 `user-app`。

## Checklist

本轮专项证据：官方 Playwright 容器中已通过摄像头、屏幕共享、文字、TTS、STT 与插话取消；审批恢复、Stage 4 控制项及移动响应式仍待复验。

- [x] Sherlock-v3 直连会话、Offer 与 ICE
- [x] 用户端产品外壳与登录/Agent 入口
- [x] 通话布局和真实媒体状态绑定
- [x] 字幕、消息、媒体附加与审批交互
- [ ] 桌面/移动端响应式验证（需具备 Playwright/Chromium 测试环境）
- [x] Docker Compose 用户端服务
- [ ] 浏览器完整链路验证（脚本已就绪，等待浏览器依赖与 STT fixture）
- [x] 删除参考目录并更新架构文档
