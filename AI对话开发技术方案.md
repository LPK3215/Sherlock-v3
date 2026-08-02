# AI 对话开发技术方案

> 基于 Pipecat 框架构建实时多模态（语音 + 视频）AI 对话系统的完整技术方案。
>
> **覆盖范围**：框架原理 → 两种管线模式 → 所需模型 → 官方示例 → 参考项目 → 快速启动。

> **当前项目状态（2026-08-02）**：`web-bot-official` 只运行 Cascade 模式，
> 使用 SmallWebRTC。唯一有效配置文件是 `web-bot-official/server/.env`；
> 根目录 `.env` 和 `.env.example` 不会被该项目读取。Realtime 代码不在当前运行路径中。

---

## 一、核心框架：Pipecat

### 1.1 是什么

Pipecat 是一个由 [Daily.co](https://www.daily.co/) 开源的 Python 框架，专门用来构建**实时语音和多模态 AI 对话 Agent**。它负责编排 real-time media pipeline —— 把 WebRTC 音频/视频流传给 AI 模型，再把输出返回给用户。

### 1.2 官方资源

| 资源 | 地址 |
|------|------|
| 官网 | <https://www.pipecat.ai/> |
| GitHub 主仓库 | <https://github.com/pipecat-ai/pipecat> |
| 官方文档 | <https://docs.pipecat.ai/> |
| PyPI 包 | <https://pypi.org/project/pipecat-ai/> |
| GitHub 组织（所有仓库） | <https://github.com/pipecat-ai/> |

### 1.3 子项目 / 配套工具

| 项目 | GitHub | 用途 |
|------|--------|------|
| **Voice UI Kit** | <https://github.com/pipecat-ai/voice-ui-kit> | React 前端组件库，快速搭建 AI 语音界面 |
| **Client Web Transports** | <https://github.com/pipecat-ai/pipecat-client-web-transports> | 浏览器端 WebRTC Transport 层 |
| **官方示例集** | <https://github.com/pipecat-ai/pipecat/tree/main/examples> | 各种场景的示例代码 |
| **web-bot 示例** | <https://github.com/pipecat-ai/gemini-live-web-starter> | Gemini Live + Voice UI Kit 完整前后端示例 |
| **gemini-webrtc-simple** | <https://github.com/pipecat-ai/gemini-webrtc-web-simple> | 最简 Gemini Live WebRTC 示例 |
| **Voice UI Kit 文档** | <https://voiceuikit.pipecat.ai/> | Voice UI Kit 组件文档 |

### 1.4 安装方式

```bash
# 方式 1：uv（推荐）
uv add pipecat-ai[webrtc,silero,google,openai,runner]

# 方式 2：pip
pip install "pipecat-ai[webrtc,silero,google,openai,runner]"

# 方式 3：Pipecat CLI 脚手架（快速创建项目）
pip install pipecat-ai
pipecat init    # 交互式创建新项目
```

extras 说明：

| extra | 用途 |
|-------|------|
| `webrtc` | WebRTC 传输层（Daily / SmallWebRTC） |
| `silero` | Silero VAD 语音活动检测（免费本地） |
| `google` | Google AI 服务（Gemini Live / STT / TTS） |
| `openai` | OpenAI 服务（Realtime / STT / TTS / VLM） |
| `runner` | Pipecat Runner（进程管理） |
| `daily` | Daily.co 传输（已废弃，用 `webrtc` 替代） |

---

## 二、两种管线模式

Pipecat 支持两种根本不同的管线（Pipeline）架构：

```
┌─────────────────────────────────────────────────────────────────┐
│                      Pipeline 架构对比                            │
├──────────────────┬──────────────────────────────────────────────┤
│   Realtime (S2S) │              Cascade (级联)                    │
├──────────────────┼──────────────────────────────────────────────┤
│                  │                                                │
│  麦克风 ──→ [模型] ──→ 扬声器    │  麦克风 → [STT] → [VLM] → [TTS] → 扬声器 │
│  摄像头 ──→   ↑    │              摄像头 ───→  ↑                   │
│                  │                                                │
│  模型直接吃音视频，直接吐音频        │  三阶段流水线，每阶段独立可替换                │
├──────────────────┼──────────────────────────────────────────────┤
│  节点数: 5 个     │               节点数: 7 个                      │
├──────────────────┼──────────────────────────────────────────────┤
│  延迟: 极低 (~0.3s) │             延迟: 中等 (~1-2s)                 │
├──────────────────┼──────────────────────────────────────────────┤
│  灵活性: 低        │              灵活性: 极高                       │
│  (模型必须原生支持音视频)             │  (STT/VLM/TTS 任意混搭)                  │
├──────────────────┼──────────────────────────────────────────────┤
│  所需模型类型:     │               所需模型类型:                       │
│  Speech-to-Speech │              STT + 多模态VLM + TTS              │
│  原生多模态模型      │              三个独立模型/服务                     │
└──────────────────┴──────────────────────────────────────────────┘
```

### 2.1 Realtime 模式（S2S / Speech-to-Speech）

**核心特征**：模型本身能直接输入原始音频/视频，直接输出原始音频。不需要 STT（语音转文字）和 TTS（文字转语音）中间层。

**Pipeline 结构**：

```python
transport.input()       # WebRTC 输入（麦克风 + 摄像头）
    ↓
user_aggregator         # 用户帧聚合器（VAD 断句）
    ↓
LLM Service             # S2S 模型（Gemini Live / OpenAI Realtime）
    ↓
transport.output()      # WebRTC 输出（扬声器）
    ↓
assistant_aggregator    # 助手帧聚合器
```

**代码关键参数**：

```python
# server/bot.py 中的关键设置
from pipecat.services.gemini_live import GeminiLiveLLMService

llm = GeminiLiveLLMService(
    api_key=os.getenv("GOOGLE_API_KEY"),
    model="models/gemini-2.5-flash-native-audio-preview-12-2025",
    voice="Charon",                          # 输出语音
)

# Context 聚合器必须标记 realtime_service_mode=True
context = OpenAILLMContext(messages, tools)
context_aggregator = llm.create_context_aggregator(
    context,
    realtime_service_mode=True    # ← 关键：告诉框架这是 S2S 模型
)
```

**支持此模式的模型**：

| 模型 | 供应商 | 获取方式 | 费用 |
|------|--------|----------|------|
| **Gemini 2.5 Flash (native audio)** | Google | [Google AI Studio](https://aistudio.google.com/) | 有免费额度 |
| **OpenAI Realtime (gpt-4o-realtime)** | OpenAI | [OpenAI Platform](https://platform.openai.com/) | 付费 |

> **注意**：全世界的 Realtime S2S 模型仅 Google 和 OpenAI 两家提供（另有实验性的 MiniCPM-o）。普通多模态模型（如 Qwen-VL、GPT-4o、DeepSeek-VL）都不支持此模式。

### 2.2 Cascade 模式（级联 / STT+VLM+TTS）

**核心特征**：把语音对话拆成三个独立步骤——先听写，再看图理解，最后朗读回复。每步可独立换模型。

**Pipeline 结构**：

```python
transport.input()       # WebRTC 输入（麦克风 + 摄像头）
    ↓
STT Service             # 语音 → 文字
    ↓
user_aggregator         # 用户帧聚合器（断句）
    ↓
VLM Service             # 多模态视觉理解（文字 + 图片 → 文字）
    ↓
TTS Service             # 文字 → 语音
    ↓
transport.output()      # WebRTC 输出（扬声器）
    ↓
assistant_aggregator    # 助手帧聚合器
```

**代码关键参数**：

```python
# Pipecat 1.7 的 Cascade Context 聚合器
user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
    context,
    realtime_service_mode=False,
    user_params=LLMUserAggregatorParams(vad_analyzer=vad),
)

# Pipecat 1.7 使用 FunctionSchema / ToolsSchema 声明工具
tools = ToolsSchema(standard_tools=[FunctionSchema(...)])
llm.register_function("fetch_camera_image", fetch_camera_image)
```

**三阶段可用的模型/服务**：

#### STT（语音 → 文字）

| 方案 | 来源 | 实时性 | 费用 |
|------|------|:---:|------|
| **Google STT** | Google Cloud | ✅ | 有免费额度 |
| **OpenAI Whisper** | OpenAI API | ✅ | $0.006/分钟 |
| **Whisper.cpp** (本地) | GitHub 开源 | ✅ | 完全免费 |
| **FunASR / Paraformer** | 阿里达摩院 / 魔搭 | ✅ | 免费 |
| **Deepgram** | Deepgram API | ✅ | 有免费额度 |

#### VLM（多模态视觉理解）

| 方案 | 来源 | 视觉能力 | 费用 |
|------|------|:---:|------|
| **Qwen2-VL** | 阿里 / 魔搭社区 | ⭐⭐⭐⭐⭐ | 免费额度 |
| **InternVL2** | 上海 AI Lab / 魔搭 | ⭐⭐⭐⭐⭐ | 免费额度 |
| **GPT-4o / GPT-4.1** | OpenAI API | ⭐⭐⭐⭐⭐ | 付费 |
| **Gemini Flash** | Google API | ⭐⭐⭐⭐⭐ | 有免费额度 |
| **LLaVA** (本地) | Ollama / HuggingFace | ⭐⭐⭐ | 完全免费 |
| **DeepSeek-VL2** | DeepSeek / 魔搭 | ⭐⭐⭐⭐ | 免费 |

#### TTS（文字 → 语音）

| 方案 | 来源 | 音质 | 费用 |
|------|------|:---:|------|
| **Edge-TTS** | 微软（免费） | ⭐⭐⭐⭐ | 完全免费 |
| **CosyVoice** | 阿里 / 魔搭 | ⭐⭐⭐⭐⭐ | 免费 |
| **OpenAI TTS** | OpenAI API | ⭐⭐⭐⭐⭐ | 付费 |
| **Google TTS** | Google Cloud | ⭐⭐⭐⭐ | 有免费额度 |
| **ElevenLabs** | ElevenLabs API | ⭐⭐⭐⭐⭐ | 有免费额度 |

---

## 三、传输层（Transport）

### 3.1 两种 Transport 对比

| | Daily Transport | SmallWebRTC Transport |
|------|:---|:---|
| 协议 | WebRTC | WebRTC |
| 信令服务器 | 需要 Daily.co 服务 | 不需要（P2P） |
| API Key | `DAILY_API_KEY` | 不需要 |
| ICE/STUN/TURN | Daily 自动提供 | 需要自配 ICE Server |
| 房间管理 | Daily Room | 不涉及 |
| 适用场景 | 生产环境 | 本地开发 / 简单部署 |
| 登录屏障 | 需要注册 Daily.co | 无 |

### 3.2 前端对应 npm 包

| Transport | npm 包 |
|-----------|--------|
| Daily | `@pipecat-ai/daily-transport` |
| SmallWebRTC | `@pipecat-ai/small-webrtc-transport` |

**前端切换示例**（`ClientApp.tsx`）：

```tsx
// SmallWebRTC（当前使用，无需 Daily API Key）
<RTVIClientRenderer
  transportType="smallwebrtc"
  ...
/>

// Daily（需要 DAILY_API_KEY）
<RTVIClientRenderer
  transportType="daily"
  ...
/>
```

---

## 四、Voice UI Kit（前端组件库）

### 4.1 概览

| 信息 | 详情 |
|------|------|
| GitHub | <https://github.com/pipecat-ai/voice-ui-kit> |
| 文档 | <https://voiceuikit.pipecat.ai/> |
| npm | `@pipecat-ai/voice-ui-kit` |
| 框架 | React 组件库 |

### 4.2 主要组件

| 组件 | 用途 |
|------|------|
| `<RTVIClientRenderer>` | 核心渲染器，管理 WebRTC 连接 + AI 对话状态 |
| `<ConversationPanel>` | 对话气泡面板，显示聊天记录 |
| `<EventStreamPanel>` | 实时事件日志，调试用 |
| `<MicrophoneButton>` | 麦克风控制（开始/停止说话） |
| `<ConnectButton>` | 连接/断开按钮 |

### 4.3 前端依赖

```json
{
  "@pipecat-ai/voice-ui-kit": "^0.11.0",
  "@pipecat-ai/small-webrtc-transport": "^1.10.0",
  "@pipecat-ai/daily-transport": "^1.6.0",
  "next": "^15.0.0",
  "tailwindcss": "^4.0.0"
}
```

---

## 五、官方示例项目结构

### 5.1 web-bot 示例（Gemini Live + Voice UI Kit）

> **仓库**：<https://github.com/pipecat-ai/gemini-live-web-starter>
>
> **本地副本**：`web-bot-official/`（本仓库已 clone 并适配）
>
> **边界说明**：上游官方 starter 验证的是 Gemini Live Realtime。当前仓库的
> Cascade Pipeline 是基于其 SmallWebRTC + Voice UI Kit 底座新增的实现，不能
> 通过只替换模型参数从官方 Realtime Pipeline 自动得到。

**目录结构**：

```
web-bot-official/
├── server/
│   ├── bot.py              # 后端 AI Pipeline 定义（172行）
│   ├── pyproject.toml      # Python 依赖
│   ├── env.example         # 环境变量模板
│   ├── Dockerfile          # Docker 部署
│   ├── pcc-deploy.toml     # Pipecat Cloud 部署配置
│   └── run.ps1             # Windows 启动脚本
│
├── client/
│   ├── app/
│   │   ├── ClientApp.tsx       # 前端主界面（282行）
│   │   ├── EventStreamPanel.tsx # 事件日志面板（185行）
│   │   └── api/start/route.ts  # API 代理路由
│   ├── package.json
│   └── next.config.ts
│
└── README.md
```

**技术组合（web-bot-official 当前）**：

| 层级 | 技术选型 |
|------|----------|
| 传输 | SmallWebRTC（已从 Daily 切换） |
| 管线模式 | **Cascade（STT + VLM + TTS）** |
| 模型 | Whisper + OpenAI 兼容 VLM + Piper 中文 TTS |
| VAD | Silero（本地，免费） |
| 前端 | Next.js 15 + Voice UI Kit |
| 后端 API | FastAPI（Pipecat Runner 内置） |

---

## 六、两种模式的完整启动方式

### 6.1 Realtime 模式（当前禁用）

`web-bot-official/server/bot.py` 会拒绝 `AI_MODE=realtime`。当前项目不需要
Google Gemini Live 或 OpenAI Realtime 权限。

### 6.2 Cascade 模式（当前唯一可用）

**当前组合**：
- STT：Whisper tiny，本地运行，不需要 API Key
- VLM：OpenAI 兼容接口，需要 `CASCADE_VLM_OPENAI_*`
- TTS：Piper 中文音色，本地运行，不需要 API Key

**唯一有效环境变量文件**：`web-bot-official/server/.env`

```env
# STT
AI_MODE=cascade

CASCADE_STT_PROVIDER=whisper
CASCADE_STT_WHISPER_MODEL=tiny
CASCADE_STT_WHISPER_DEVICE=cpu
CASCADE_STT_WHISPER_COMPUTE_TYPE=int8

CASCADE_VLM_PROVIDER=openai
CASCADE_VLM_OPENAI_BASE_URL=https://你的兼容端点/v1
CASCADE_VLM_OPENAI_API_KEY=你的密钥
CASCADE_VLM_OPENAI_MODEL=你的视觉模型

CASCADE_TTS_PROVIDER=piper
CASCADE_TTS_PIPER_VOICE=zh_CN-huayan-medium
```

**启动命令**：

```powershell
# 终端 1：后端
cd web-bot-official/server
uv sync
.\run.ps1

# 终端 2：前端
cd web-bot-official/client
npm install
npm run dev
```

打开 <http://localhost:3000>，允许麦克风权限后点击 Connect。

---

## 七、参考项目对照

本仓库内有三个项目，关系如下：

| 项目 | 定位 | 模式 | 使用策略 |
|------|------|:---:|------|
| `web-bot-official/` | **核心开发项目** | Cascade | 所有开发在此进行 |
| `ai-video-call-core/` | 参考项目（双模式实现） | Realtime + Cascade | 仅在用户点名时参考，借鉴 Cascade 实现 |
| `my-video-ai/` | 参考项目（CLI 脚手架生成） | Realtime | 仅在用户点名时参考 |

### 7.1 ai-video-call-core 关键参考价值

该项目的 Cascade 模式实现是后续开发的主要参考来源：

- `server/bot.py` → `build_cascade_services()` + `build_stt_service()` + `build_vlm_service()` + `build_tts_service()`
- `server/model_config.py` → 多供应商配置系统
- `server/profiles.py` → 管线模式切换 + Session Profile 解析

### 7.2 模型切换架构（参考 ai-video-call-core）

```
请求 body {mode: "cascade", provider: "openai-compatible"}
    ↓
parse_session_profile()  →  {mode: "cascade", provider: "openai-compatible"}
    ↓
load_model_config()      →  AIModelConfig (从环境变量加载所有配置)
    ↓
assemble_pipeline()     →  根据 mode 返回不同 pipeline 处理器列表
    ↓
build_cascade_services() →  build_stt_service() + build_vlm_service() + build_tts_service()
```

---

## 八、关键理解

### 8.1 代码 vs 模型 —— 成败的真正原因

> 当前曾经出现的问题不是模型权限，而是项目代码和 Pipecat 1.7 API 不兼容。

Pipecat 框架把所有 Pipeline、Transport、VAD 的技术细节都抽象好了。你的代码只是做"拼积木"：选什么 Service、用什么模式、配什么 Key。

当前 VLM 密钥已通过真实请求验证。Whisper 与 Piper 均为本地服务，不需要
额外密钥。框架版本、依赖 extra、Context/Tool Schema 和 WebRTC 会话生命周期
同样会决定项目是否可运行。

| 你想用 | 需要什么 |
|--------|----------|
| Realtime 模式 | 当前禁用，不需要准备对应权限 |
| Cascade 模式 | 当前配置只需要一个 OpenAI 兼容 VLM API Key；Whisper/Piper 在本地运行 |

### 8.2 技术壁垒的真实位置

| 看似有壁垒 | 实际没有壁垒 |
|------------|--------------|
| WebRTC 底层协议 | Pipecat 已完全封装 |
| Pipeline 帧流转 | 框架自动编排 |
| VAD 语音检测 | Silero 开箱即用 |
| 前端 AI 语音界面 | Voice UI Kit 组件化 |
| **模型获取** | **这是唯一的实际壁垒** |

### 8.3 开发策略：基石迭代法

以 `web-bot-official`（官方案例，已知能跑通）为基石：
1. ✅ 固定 SmallWebRTC Transport
2. ✅ 跑通 Cascade：Whisper + OpenAI 兼容 VLM + Piper 中文 TTS
3. ✅ 禁止入口回退到 Realtime
4. ⏳ 在当前稳定管线上继续添加业务功能

---

## 九、快速参考卡片

### 环境变量速查

| 变量 | 用途 | 必需？ |
|------|------|:---:|
| `AI_MODE=cascade` | 固定使用 Cascade | 是 |
| `CASCADE_VLM_OPENAI_API_KEY` | 当前 VLM 接口密钥 | 是 |
| `CASCADE_VLM_OPENAI_BASE_URL` | 当前 VLM 兼容端点 | 是 |
| `CASCADE_VLM_OPENAI_MODEL` | 当前视觉模型名称 | 是 |
| `NLTK_DISABLE_IMPORT_SECURITY` | Windows 下绕过 NLTK 安全检查 | Windows 必需 |
| `PYTHONUTF8` | Windows UTF-8 编码 | Windows 推荐 |

### 端口速查

| 服务 | 端口 |
|------|:---:|
| 后端 (Pipecat Bot) | 7860 |
| 前端 (Next.js Dev) | 3000 |

### 关键链接速查

| 资源 | 链接 |
|------|------|
| Pipecat 官网 | <https://www.pipecat.ai/> |
| Pipecat 文档 | <https://docs.pipecat.ai/> |
| Pipecat GitHub | <https://github.com/pipecat-ai/pipecat> |
| Voice UI Kit | <https://github.com/pipecat-ai/voice-ui-kit> |
| Voice UI Kit 文档 | <https://voiceuikit.pipecat.ai/> |
| web-bot 官方示例 | <https://github.com/pipecat-ai/gemini-live-web-starter> |
| Client Web Transports | <https://github.com/pipecat-ai/pipecat-client-web-transports> |
| Google AI Studio | <https://aistudio.google.com/> |
| 魔搭社区 | <https://modelscope.cn/> |
