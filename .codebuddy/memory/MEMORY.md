# Sherlock-v3 长期记忆

## 项目关系（2026-08-02 确立）

三个项目目录：
- `web-bot-official/` — **唯一核心项目**，Pipecat 官方 web-bot 示例，所有开发在此进行
- `ai-video-call-core/` — 参考项目 1（用户自写，可能有 bug），**仅在用户点名时才参考**
- `my-video-ai/` — 参考项目 2（Pipecat CLI 脚手架生成），**仅在用户点名时才参考**

## 开发原则

1. 所有代码修改、功能添加都在 `web-bot-official/` 中进行
2. 参考项目仅在被用户明确点名时才查看，平时不要主动借鉴
3. 参考不等于照搬，仅借鉴思想和工具方向
4. 项目关系说明文档：`PROJECT_STRUCTURE.md`

## 核心开发策略（2026-08-02 确立）

**采用"基石迭代法"**：以官方 demo（web-bot-official，Daily + Gemini Live 固定组合）为开发基石，逐步添加多传输/多模型支持。每改一步验证一步。原因：官方 demo 已知能跑通，报错一定是自己改错；而用户自写项目（ai-video-call-core/my-video-ai）同时存在代码 bug、API Key、模型兼容性三个变量，排查成本极高，所以废弃不用。

## 技术栈（web-bot-official）

- 前端：Next.js 15 + Tailwind CSS v4 + Voice UI Kit + SmallWebRTC Transport
- 后端：Python 3.11+ + Pipecat + Gemini Live
- API：单一端点 `POST /api/start`（Next.js 代理到 bot 服务）
- 管线模式：Realtime（S2S），待开发 Cascade（STT+VLM+TTS）

## 关键文件

- 启动器：`web-bot-official/server/bot.py`（读 AI_MODE，代理到 realtime/cascade）
- Realtime 模式：`web-bot-official/server/bot_realtime.py`（Gemini Live S2S）
- Cascade 模式：`web-bot-official/server/bot_cascade.py`（STT+VLM+TTS 三阶段管线，每个组件支持多种 provider 切换）
- 前端核心：`web-bot-official/client/app/ClientApp.tsx`
- 前端日志：`web-bot-official/client/app/EventStreamPanel.tsx`
- API 路由：`web-bot-official/client/app/api/start/route.ts`
- 技术方案文档：`docs/AI对话开发技术方案.md`（Pipecat 框架全景 + 两种管线模式 + 模型清单 + 官方资源）

## Cascade 三件套 Provider 矩阵

| 组件 | 可用 Provider | 默认 | 费用 |
|------|------|:---:|:---:|
| STT | whisper / funasr / moonshine / openai | whisper (tiny) | 本地免费 |
| VLM | minicpm / openai | minicpm (MiniCPM-O-4.5-9B) | 免费公钥 |
| TTS | kokoro / piper / openai | kokoro (af_sky) | 本地免费 |

切换方式：改 `.env` 中的 `CASCADE_STT_PROVIDER` / `CASCADE_VLM_PROVIDER` / `CASCADE_TTS_PROVIDER`。
零成本方案：三件套全用本地/provider，不需要任何 API Key。
