# AI Video Call Core

一个基于 Pipecat 1.7 的 AI 视频通话核心项目。浏览器显示全屏本地摄像头，麦克风、摄像头、屏幕共享和通话控件悬浮在画面上；同一个页面可在原生实时多模态和级联多模态之间切换。

## 两种架构

| 页面选择 | 实际管线 | 视频进入模型的方式 | 配置入口 |
|---|---|---|---|
| `实时直连 / Google` | Gemini Live 原生处理音频、图像和语音输出 | 摄像头/屏幕约 1fps 连续直传 | `REALTIME_GOOGLE_*` 或 `GOOGLE_API_KEY` |
| `实时直连 / OpenAI` | OpenAI Realtime 原生处理音频、图像和语音输出 | 摄像头/屏幕约 1fps 连续直传 | `REALTIME_OPENAI_*` 或 `OPENAI_API_KEY` |
| `级联 / Google` | 独立 STT → Gemini VLM → 独立 TTS | 视觉问题触发工具，抓取当前摄像头或屏幕帧 | `CASCADE_STT_*`、`CASCADE_VLM_*`、`CASCADE_TTS_*` |
| `级联 / OpenAI` | 独立 STT → OpenAI VLM → 独立 TTS | 同上 | 同上 |
| `级联 / Qwen / OpenAI 兼容` | 独立 STT → OpenAI-compatible VLM → 独立 TTS | 同上 | `CASCADE_VLM_API_KEY/BASE_URL/MODEL` |

Pipecat 是音视频传输、实时事件和模型服务的编排框架，不是模型本身。Realtime 模型原生接收流式音频和图像；普通多模态模型放在 Cascade 中，由 Pipecat 串联 STT/VLM/TTS，并通过 `UserImageRequestFrame` 获取当前画面。两条代码路径可按每次通话切换，无需重启服务。是否真实可用仍取决于所配置端点的模型能力和真实端到端验收结果。

## 核心功能

- 全屏、镜像的本地摄像头预览。
- 透明悬浮的麦克风、摄像头、屏幕共享、呼叫和挂断按钮。
- Realtime/Cascade 切换，以及 Google、OpenAI、OpenAI-compatible VLM 选择。
- Cascade 的 STT、VLM、TTS 可以分别选择不同供应商和地址。
- 语音输入、键盘文字输入、用户转录和 AI 输出记录。
- AI 语音返回浏览器，并支持用户开口打断。
- Realtime 连续视觉输入；Cascade 按需获取摄像头或共享屏幕快照。
- 页面显示实际音频、摄像头、屏幕、视觉请求和 AI 音频帧计数。
- 后端日志记录 profile、管线、客户端、画面捕获、转录和媒体帧计数。

暂不包含管理员端、账号、数据库、计费、持久化聊天记录和数字人视频输出。

## 启动

环境要求：Python 3.11+、uv、Node.js 20+、Chrome 或 Edge。

后端：

```powershell
cd server
uv sync
Copy-Item .env.example .env
notepad .env
.\run.ps1
```

前端：

```powershell
cd client
npm install
npm run dev
```

打开 `http://localhost:5180`，允许摄像头和麦克风权限，选择模式和模型后点击绿色电话按钮。连接期间不能切换 profile；挂断后可以重新选择。

不要把密钥发到聊天中，只写入本机 `server/.env`。Google/OpenAI 原生服务允许模型留空并使用 Pipecat 1.7 默认值；OpenAI-compatible 服务必须明确填写 key、base URL 和 model。

## 凭证配置

使用原生 Realtime 模型：

```dotenv
AI_MODE=realtime
REALTIME_PROVIDER=openai
OPENAI_API_KEY=你的Key
```

切换为 Gemini Live 时：

```dotenv
REALTIME_PROVIDER=google
GOOGLE_API_KEY=你的Key
```

使用 ModelScope/Qwen-VL，并用 OpenAI 提供语音识别和合成：

```dotenv
AI_MODE=cascade
CASCADE_VLM_PROVIDER=openai-compatible
CASCADE_VLM_API_KEY=你的ModelScopeKey
CASCADE_VLM_BASE_URL=https://api-inference.modelscope.cn/v1
CASCADE_VLM_MODEL=Qwen/Qwen3-VL-8B-Instruct
CASCADE_VLM_ADAPTER=qwen

CASCADE_STT_PROVIDER=openai
CASCADE_TTS_PROVIDER=openai
OPENAI_API_KEY=你的OpenAIKey
```

VLM 端点必须同时支持 OpenAI Chat Completions、图片内容和工具调用。Qwen 模型使用 Pipecat 官方 `QwenLLMService` 适配器，它会处理 Qwen 不接受 `developer` 角色的差异；模型名包含 `qwen` 时会自动选择，也可通过 `CASCADE_VLM_ADAPTER` 明确指定。若没有 OpenAI 语音服务，可把 `CASCADE_STT_PROVIDER` 和 `CASCADE_TTS_PROVIDER` 分别设为 `openai-compatible`，并为两者填写各自的 `API_KEY/BASE_URL/MODEL`。它们不要求和 VLM 使用同一个供应商。

Google Cloud STT/TTS 需要 `GOOGLE_CREDENTIALS_JSON` 或 `GOOGLE_APPLICATION_CREDENTIALS`；Gemini API Key 不能替代服务账号。不要提交 `.env` 或服务账号文件。

## 如何验证

### 1. 不需要 Key 的代码验证

```powershell
cd server
uv run python -m unittest discover -s tests -v
uv run ruff format --check .
uv run ruff check .
uv run pyright

cd ..\client
npm run lint
npm run build
```

单测会验证 profile、四类独立配置、兼容端点传递、两种管线顺序，以及视觉工具确实产生带当前连接 ID 的 `UserImageRequestFrame`。这仍只能证明本地组装正确，不能证明云模型已经回答。

### 2. 浏览器媒体与请求验证

接通后查看页面顶部诊断条：

- `麦克风` 持续增加，证明后端收到了真实音频帧。
- `摄像头` 按约 1fps 增加，证明后端收到了真实视频帧。
- 开启屏幕共享后 `屏幕` 增加，证明共享画面已进入后端。
- profile 变为绿色，证明后端确认的 profile 与页面选择一致。
- `AI 语音` 增加，证明模型/TTS 的音频已返回浏览器。
- Cascade 中问视觉问题后 `视觉请求` 增加，证明模型调用了当前画面工具。

后端同时应出现这些日志：

```text
Selected pipeline | profile=...
Selected models | ...
Client connected | profile=...
Video capture started | camera=1fps screen=1fps
Media diagnostics | audio_in_frames=... camera_frames=...
Transcript | role=user ...
Transcript | role=assistant ...
```

### 3. 真实端到端验收

有真实 Key 后对需要使用的 profile 分别做一次通话：

1. 说一句话，确认用户文本出现且 AI 有文字和语音返回。
2. 输入一条文字消息，确认 AI 仍同时返回文字和语音。
3. 问“我手里拿的是什么”，确认回答与当前摄像头一致。
4. 共享一个包含明显文字的窗口，问“共享画面写了什么”。
5. AI 说话时再次开口，确认可以打断。

没有真实 Key、没有 `AI 语音` 帧、没有模型文本时，不能宣称模型闭环通过。

## Pipecat Eval

Cascade 可以先跑快速文字场景：

```powershell
cd server
$env:AI_LANGUAGE="en"
.\run.ps1 -t eval --port 7860 --runner-body evals\cascade-openai.json
```

另一个终端：

```powershell
cd server
uv run pipecat eval run evals\cascade_text.yaml -v
```

Realtime 必须跑音频场景，将 runner body 换成 `evals\realtime-openai.json`，场景换成 `evals\realtime_audio.yaml`。音频场景第一次会下载本地 Kokoro/Moonshine 模型；自然语言 `eval:` 默认还需要本地 Ollama judge，或者按 Pipecat Eval 文档配置其他 judge。

## 常见问题

- `missing required environment configuration`：当前选择的 profile 缺少 `.env` 项。
- `CASCADE_VLM_BASE_URL` 或 `CASCADE_VLM_MODEL` 缺失：选择了 Qwen/OpenAI 兼容模式，但兼容端点配置不完整。
- Qwen 能文字聊天但视觉请求为 0：该模型没有按工具协议调用视觉工具；确认端点和具体模型支持 OpenAI 工具调用。
- 本地预览有画面但 `摄像头` 为 0：WebRTC 未成功接通后端，检查后端日志和浏览器控制台。
- Cascade 能聊天但视觉请求为 0：模型没有调用视觉工具；确认问题明确依赖当前摄像头或共享屏幕。
- Cascade Google 启动失败：Gemini API Key 不能代替 Google Cloud STT/TTS 服务账号。
- 公网无法获取媒体：生产环境必须使用 HTTPS，`localhost` 是开发例外。
- 跨网络 WebRTC 失败：为 SmallWebRTC 配置 TURN，或生产环境切换 Daily。
- 画面快速变化未被识别：当前视觉采样是约 1fps，不是逐帧视频分析。
