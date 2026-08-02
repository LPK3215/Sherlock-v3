# Pipecat AI 视频助手调研与使用指南

调研基线：Pipecat `v1.7.0`，官方仓库提交 `c49bf69`，检查日期 2026-08-02。

## 1. 结论

Pipecat 适合这个需求，而且是正确的框架选择。它已经提供实时音视频传输、音频/视频帧处理、模型服务适配、对话上下文、打断、转录事件和浏览器客户端 SDK，不需要自己重写 WebRTC 或实时流水线。

推荐的第一版组合是：

- 浏览器：React + Pipecat Client + Voice UI Kit
- 本地传输：SmallWebRTC
- 实时多模态模型：Gemini Live
- 后端：Pipecat Python pipeline
- 输入：麦克风、摄像头、屏幕共享
- 输出：AI 实时语音、字幕和事件

Pipecat 不是大模型，也不是 API Key 的替代品。当前组合仍需要后端的 `GOOGLE_API_KEY`。框架负责把浏览器媒体可靠地送入 Gemini Live，并把模型的语音和事件送回浏览器。

## 2. 哪些能力框架已经提供

Pipecat 直接提供：

- WebRTC 音频和视频收发。
- 浏览器麦克风、摄像头、扬声器和屏幕共享设备管理。
- 摄像头/屏幕视频抽帧并送入多模态模型。
- 实时 speech-to-speech，不需要单独拼 STT、LLM、TTS。
- 用户说话时打断 AI，避免必须等 AI 说完。
- 对话上下文、用户/助手转录、连接状态和错误事件。
- React hooks、视频组件和现成的 Voice UI Kit 控件。
- Gemini Live、OpenAI Realtime、Daily、SmallWebRTC 等服务适配。

仍然需要应用自己决定或提供：

- Gemini 或 OpenAI 的模型账号和 API Key。
- 产品提示词、业务工具调用、权限策略和数据保存规则。
- 公网 HTTPS、域名和生产级 STUN/TURN 或 Daily 基础设施。
- 如果需要上传静态图片，需要增加文件选择和上传界面。
- 如果 AI 自己需要以数字人视频出现，需要 Tavus、HeyGen、Simli、Anam 等 avatar 服务。

## 3. 实际数据流

```text
浏览器 microphone / camera / screen
        |
        | WebRTC
        v
SmallWebRTCTransport
        |
        v
transport.input()
        -> user context aggregator
        -> GeminiLiveLLMService
        -> transport.output()
        -> assistant context aggregator
        |
        v
浏览器播放 AI 语音、显示字幕和状态
```

后端必须启用 `audio_in_enabled`、`audio_out_enabled` 和 `video_in_enabled`。客户端连接后，还要调用摄像头和屏幕捕获 API。仅仅打开浏览器摄像头，不代表视频已经进入模型。

当前项目对摄像头和屏幕使用 `framerate=1`。这与官方 Gemini Live 视频示例一致：视频聊天仍可保持正常浏览器帧率，但送给模型做视觉理解的是约每秒一帧，适合看物体、读界面、看手势和排查屏幕问题，不适合逐帧分析高速运动。

## 4. 已核实的官方材料

本地已拉取五个官方仓库：

- `../pipecat-official`：Python 核心、服务、传输、测试和基础示例。
- `../pipecat-examples-official`：完整应用案例。
- `../pipecat-client-web-official`：JavaScript/React 客户端 SDK。
- `../pipecat-client-web-transports-official`：Daily、SmallWebRTC 等 Web 传输。
- `../voice-ui-kit-official`：官方 React UI 组件库。

最相关的官方后端案例：

- `../pipecat-official/examples/realtime/realtime-gemini-live-video.py`
- `../pipecat-official/examples/realtime/realtime-openai-live-video.py`
- `../pipecat-official/examples/function-calling/function-calling-google-video.py`
- `../pipecat-official/examples/video-processing/video-processing.py`
- `../pipecat-official/examples/vision/vision-gemini-flash.py`

最接近目标产品的完整前后端应用：

- `../pipecat-examples-official/gemini-live-starters/web-bot`

该应用使用 Next.js、Voice UI Kit、Daily 和 Gemini Live，包含麦克风、摄像头、屏幕共享、实时字幕与事件面板。其后端同时捕获 `camera` 和 `screenVideo`，频率为 1fps。

重点官方测试：

- `../pipecat-official/tests/test_smallwebrtc_transport.py`
- `../pipecat-official/tests/test_smallwebrtc_request_handler.py`
- `../pipecat-official/tests/test_gemini_live_user_audio.py`
- `../pipecat-official/tests/test_openai_realtime_audio_frames.py`
- `../pipecat-official/tests/test_openai_realtime_user_audio.py`
- `../pipecat-official/tests/test_runner_run.py`

当前检出的核心仓库规模：`src` 653 个文件、`tests` 207 个 Python 文件、`examples` 452 个文件，其中 Python 示例 380 个，约 3336 个 `test_*` 测试函数。这不是一个只有概念演示的小项目，核心传输和实时服务有相当完整的测试面。

官方文档入口：

- https://docs.pipecat.ai/
- https://docs.pipecat.ai/pipecat/features/gemini-live
- https://docs.pipecat.ai/api-reference/server/services/s2s/gemini-live
- https://docs.pipecat.ai/api-reference/server/services/transport/small-webrtc
- https://docs.pipecat.ai/client/concepts/media-management
- https://docs.pipecat.ai/api-reference/client/js/client-methods
- https://docs.pipecat.ai/client/voice-ui-kit
- https://github.com/pipecat-ai/pipecat
- https://github.com/pipecat-ai/pipecat-examples/tree/main/gemini-live-starters/web-bot

## 5. 当前可运行项目做了什么

项目目录是 `my-video-ai`，由 Pipecat 1.7.0 官方 CLI 生成，再按官方实时视觉示例补齐：

- `server/bot.py` 使用 `GeminiLiveLLMService`。
- pipeline 使用 realtime service mode。
- SmallWebRTC 同时启用音频输入、音频输出和视频输入。
- 客户端连接后，以 1fps 捕获摄像头和共享屏幕。
- `client/src/main.tsx` 默认启用麦克风和摄像头。
- `client/src/components/App.tsx` 提供麦克风、摄像头和屏幕共享按钮。
- 模型 Key 只从后端 `.env` 读取，不会进入浏览器 bundle。
- Windows 使用 `server/run.ps1`，规避 NLTK 对项目内 `.venv` 的误判，同时保留其安全检查。

已完成的验证：

- 后端 Ruff：通过。
- 后端 Pyright：0 error、0 warning。
- 后端 Python 编译：通过。
- 前端 ESLint：通过。
- 前端 TypeScript + Vite 生产构建：通过。
- 后端首页和 OpenAPI：HTTP 200，存在 `/start` 路由。
- 前端开发页：HTTP 200。

尚未声称通过的项目：真实 Gemini 视频通话。原因是当前没有配置 `GOOGLE_API_KEY`，不能用假的 Key 代替端到端验证。

## 6. 在当前 Windows 机器上启动

先创建服务端配置：

```powershell
cd "D:\Program Files (x86)\App_Cache\Temporary\桌面杂物\新建文件夹\my-video-ai\server"
Copy-Item .env.example .env
notepad .env
```

写入自己的 Key：

```dotenv
GOOGLE_API_KEY=你的真实Gemini_API_Key
```

不要把 Key 放进 `client/.env.local`。然后启动后端：

```powershell
.\run.ps1 --port 7861
```

第二个 PowerShell 窗口启动前端：

```powershell
cd "D:\Program Files (x86)\App_Cache\Temporary\桌面杂物\新建文件夹\my-video-ai\client"
npm run dev
```

当前机器的 `7860` 已被其他进程占用，因此 `client/.env.local` 已指向 `http://localhost:7861/start`。前端当前运行在 http://127.0.0.1:5175/；以后重新启动时，以 Vite 控制台显示的 Local URL 为准。

打开页面后：

1. 允许浏览器访问麦克风和摄像头。
2. 确认麦克风和摄像头按钮已打开。
3. 点击 Connect。
4. 需要分析桌面时，点击屏幕共享按钮并选择窗口或屏幕。
5. 正常说话，用户再次开口时应能打断 AI。

## 7. 怎么验证视觉真的生效

不要只问知识题。使用只能通过当前画面回答的问题：

- “我手里拿的是什么？它是什么颜色？”
- “读一下摄像头画面里的文字。”
- “我现在伸出了几根手指？”
- “看看我共享的窗口，这个错误提示是什么？”
- “告诉我这个页面上下一步应该点哪里。”

成功标准：

- 能听到 AI 的开场语音。
- 页面能显示用户和 AI 的实时转录或事件。
- AI 能描述当前摄像头或共享屏幕内容，而不是只回答常识。
- 用户说话时能打断 AI。
- 关闭摄像头或屏幕共享后，AI 不应声称仍能看到新画面。

## 8. 静态图片、视频理解和数字人不是同一件事

摄像头和屏幕共享已经实现。摄像头视频会被抽成图像帧送入模型。

静态图片文件上传尚未放进当前 UI，但框架已经有正式路径：服务端可使用 `LLMContext.create_image_message(...)` 把上传图片加入上下文；也可使用 `UserImageRequestFrame` 请求当前参与者图像。官方 `examples/vision/vision-gemini-flash.py` 和 `examples/function-calling/function-calling-google-video.py` 可直接参考。文件选择、大小限制和上传接口仍属于应用层。

当前项目是“AI 看你的画面并用语音回答”。如果目标是“屏幕上出现一个会说话的 AI 人物”，还需接入 avatar 服务。Pipecat 已有 Tavus、HeyGen、Simli、Anam、LemonSlice 等适配，但这是额外的视频输出服务和费用，不是 Gemini Live 摄像头输入本身。

## 9. SmallWebRTC 还是 Daily

SmallWebRTC 适合：

- 本地开发和快速验证。
- 单客户端或简单部署。
- 想尽量少依赖第三方房间服务。

Daily 更适合：

- 公网、多用户、复杂 NAT 和企业网络。
- 需要成熟的 TURN、房间、参与者和录制能力。
- 要接 Tavus 等依赖 Daily 房间的 avatar 或生产集成。

SmallWebRTC 并非只能演示，但生产环境必须正确部署信令、HTTPS、STUN/TURN、认证、限流和会话隔离。浏览器只有在 `localhost` 或安全的 HTTPS 上下文中才允许正常使用麦克风和摄像头。

## 10. 常见失败原因

- 浏览器权限被拒：在站点权限中重新允许麦克风和摄像头。
- 公网使用 HTTP：改成 HTTPS；localhost 是本地开发例外。
- `GOOGLE_API_KEY` 未填、无 Gemini Live 权限、账号地区或配额受限。
- 后端端口与 `VITE_BOT_START_URL` 不一致。
- 端口已经占用。当前项目后端已改用 7861。
- 跨网络连接失败：为 SmallWebRTC 配 TURN，或切换 Daily。
- 画面变化太快：模型收到的是约 1fps 抽帧，不是逐帧 30fps 视频。
- Key 被放进 Vite 环境变量：这会暴露给浏览器，必须移回后端 `.env`。
- 把视觉输入助手误认为数字人输出：后者需要独立 avatar 服务。

## 11. 模型选择

当前版本先用 Gemini Live，因为一个服务即可同时处理音频、视频、文本和语音输出，配置只需要一个 Google Key。Pipecat 1.7.0 当前默认 Gemini Live 模型为 `models/gemini-2.5-flash-native-audio-preview-12-2025`，默认声音为 `Charon`；项目没有硬编码旧模型名，因此会跟随框架的当前默认值。

OpenAI Realtime 也是可行替代。Pipecat 1.7.0 的当前默认是 `gpt-realtime-2`，并支持视频帧及 `video_frame_detail` 的 `auto`、`low`、`high` 设置。切换时应重新用 Pipecat CLI 生成对应模板或参照官方 `realtime-openai-live-video.py`，不要只替换一个类名后猜参数。
