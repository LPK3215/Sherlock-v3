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

## 九、开发者的核心认知（2026-08-02 对话沉淀）

> 以下是对"这件事到底在做什么、为什么难"的元层理解，是工程实践后的认知总结，
> 不是技术细节，但对判断方向、避免自我怀疑有长期价值。

### 9.1 多模态 AI 的本质：两种范式

让文本类 AI 获得"看（图/视频）"和"听/说（语音）"能力，本质上只有两条路：

**范式一：模型原生多模态（模型本身支持）**
- 模型官方直接提供调用接口：文档里写明怎么传音视频、怎么设参数。
- 此时**不需要任何框架**，按官方 API 用即可（如 Gemini Live、GPT-Realtime）。
- 这是最优、最省力的方式——框架在这一范式里只是"传声筒"。

**范式二：中间件拼接（向下兼容）**
- 当模型只吃文本、但又必须让它支持音视频时，用工具做"输入/输出两侧转换"：
  - 输入端：语音→文本（STT）、图像/视频→文本描述（VLM 解析打包）
  - 输出端：文本→语音（TTS）
  - 中间：把解析后的参数传给文本模型，拿回结果
- 这就是 Cascade 模式的本质：**开头一个转换、结尾一个转换、中间一个模型**。

**结论**：两种范式覆盖了"AI 获取音视频能力"的全部可能。理解这一点后，
选型变清晰——有原生模型就用范式一，没有就退到范式二，框架价值在范式二才真正显现。

### 9.2 为什么"后端代码不多却反复出错"

核心认知纠偏：**前端不是"纯展示样式"，它是传输层客户端**。

前端实际要负责三件与后端强耦合的事，任何一件错就"页面能渲染、点按钮没反应"：

1. **建立传输连接**：WebRTC/Daily 的 transport 类必须和后端 `AI_MODE` 路由用的
   transport **完全匹配**，否则握手失败——不报错但也没流。
2. **按钮动作与模式匹配**：后端默认 cascade，前端若按 realtime 流程走 →
   请求发出去但后端未按预期回，前端卡在 loading。
3. **模式/provider 透传**：后端支持多种方式（如 cascade 内 whisper/minicpm/kokoro
   多种组合），前端若不把选中项作为参数发给 `/api/start`，后端就用默认，表现即"无实质操作"。

**真因往往不是"后端没实现"，而是"前后端边界对接没对上"**——即连接、轨道、路由、
模式透传这几处协议层问题，而不是核心业务逻辑（STT/VLM/TTS 那几行）的问题。

### 9.3 正确的验证顺序：先证明、再改

避免"越改越乱"的自我怀疑，按此顺序定位：

1. **绕开前端证明后端活着**：写终端自测脚本，直接跑三件套（STT→VLM→TTS），
   不经过 WebRTC。能出结果 = 后端功能 100% 没问题。
2. **证明前后端能连上**：用 curl 打 `POST /api/start`，看 200 还是 500，
   区分"前端没传到"还是"后端没起来"。
3. **读代码对齐前后端**：确认 `AI_MODE` 默认值、provider 是否透传、transport 是否匹配。
4. **前端只做"对接"不做"重做"**：把它当收发请求的客户端，正确发请求 + 建匹配
   transport + 透传模式 + 播返回流即可。

### 9.4 这件事的意义

不是为了"证明能做个语音助手"这么浅。真实价值：
- 吃透工业界真实在用的两种多模态架构范式（Realtime API vs Agent 工具链），
  这是可讲清楚的设计能力，而非"会调 SDK"。
- 亲手验证零成本方案（本地 whisper + 免费 VLM + 本地 TTS），证明范式二无需任何
  API Key 也能跑，是一种工程结论。
- 框架（Pipecat）的价值在范式二才显现——它管管线生命周期、帧调度、传输层，
  省下大量胶水代码。

> 认知领先于工程进度时，会自然产生"卡住了/没价值"的错觉。这是正常的
> "理解快于落地"阶段，不是方向错误。

### 9.5 实战验证结论（2026-08-02 已跑通）

经过按 9.3 顺序的验证，Cascade 全链路已被实测证明可用，澄清了此前所有疑虑：

**实际链路（已验证）**
```text
浏览器麦克风 → 本地 Whisper STT → OpenAI 兼容 VLM → 本地 Piper 中文 TTS → 浏览器扬声器
```

**已实测通过的关键事实**
- 中文文本链路：发送"请只回答：中文级联测试成功" → 页面收到同样内容；后端确认
  VLM 请求成功、返回中文，Piper 收到中文文本并合成音频，浏览器完成播放。
- Whisper 已实际处理浏览器音轨（非仅加载模型）：`STT audio: 2.82s / processing 1.81s`，
  CPU 推理正常，日志无 CUDA/cublas/Traceback/Pipeline ERROR。
- 前端控制台 `0 errors`；`/start`、SDP Offer、ICE 协商、WebRTC 数据通道全部通过。
- Python Ruff / 编译、前端 ESLint / TypeScript / Next.js 生产构建全部通过。
- 前端 3000、后端 7860 均返回 HTTP 200 并保持运行。

**曾踩的坑（即 9.2 所说"边界对接问题"的具体印证）**
1. 官方 starter 是 Gemini Live Realtime，Cascade 不能只换参数，需重排 STT/VLM/TTS/聚合器/工具。
2. 旧版 Pipecat API（`.service_name()`、旧工具格式）与 1.7.0 不兼容 → 已迁 `FunctionSchema`/`ToolsSchema`。
3. Whisper `device=auto` 误选 CUDA 报 `cublas64_12.dll` 缺失 → 显式 `device=cpu` 解决（非 Key 问题）。
4. Kokoro 中文音色在 Windows 下 espeak 不支持 `zh` → 改用本地 Piper `zh_CN-huayan-medium`。
5. Pipecat 默认空闲 5 分钟结束 Worker → 设 `idle_timeout_secs=None` 取消。
6. 前端旧属性 `textMode` → 当前需 `textRenderMode`。
7. 前端 `/start` 未传合法空 JSON body → 部分启动失败。
8. `web-bot-official` 不读根目录 `.env`，仅 `server/.env` 生效。

**结论印证 9.1 / 9.2**：后端核心功能早已具备，此前"点按钮没反应"确为前后端边界
对接问题（空请求体、属性名变更、transport 匹配、模式回退），而非功能缺失。修复后
项目即完整可用，剩余仅"真实中文麦克风识别准确度/听感"需使用者本人实测。

### 9.6 视觉链路实测打通（2026-08-02 截图验证）

截图证明摄像头→VLM→回答链路已真正串通，已进入"可交互多模态 Cascade 应用"阶段：

**已证明的视觉链路**
```text
浏览器摄像头 → 获取画面 → 传给 VLM → VLM 理解画面 → 返回回答 → 前端显示回答
```
证据：会话已连接（Disconnect）、实时摄像头预览、摄像头轨道启用（绿色）、模型识别出
办公室/天花板管道/日光灯/隔板/门/显示器、追问颜色能基于前帧回答（视觉上下文进入 VLM）、
多轮消息正常收发。

**准确边界区分**
- 当前实现是"按工具抓取摄像头帧"→ 压缩封装为图片参数 → VLM → 文字。属于 9.1 范式二
  （中间件拼接），**证明 AI 可"按需查看"画面，但不代表逐帧连续理解整段视频**。
- 截图时：麦克风静音（红）、摄像头开启、屏幕共享未开。
- 模型首次用英文、后用中文 → 输出语言未完全固定，可通过系统提示词统一中文。
- "你看起来是个男生"是模型基于外观的推测，非可靠身份判断，但证明人物画面已传入模型。

**按输入方式可分级确认**
- 键盘输入 → `文本 → VLM + 摄像头画面 → 文本回答`（已证）
- 麦克风说话且页面自动出现文字 → `语音 → Whisper STT → VLM + 画面 → 回答`
- 同时听到中文声音 → 完整链路 `麦克风 → Whisper → VLM + 图片 → Piper → 扬声器` 全部成立

**产品级确认清单（架构已证，转为体验验证）**
1. 对麦克风说未输入过的话，确认自动转写。
2. 确认 AI 回答从扬声器播放。
3. 拿新物体问颜色/数量，确认用最新画面。
4. 开屏幕共享，问屏幕内容。
5. 断开重连，确认可恢复。
6. 连续用超 5 分钟，确认不再自动结束（已设 `idle_timeout_secs=None`）。

**最终结论**：普通 Cascade 组合（Whisper + 视觉 VLM + Piper + 浏览器媒体传输）已实际获得
语音输入、视觉感知、语音输出能力——最初想证明的事已实现。`cascade_test.py` 现主要用于
故障诊断与自动回归，不再用于证明核心思路可行性。

---

## 十、快速参考卡片

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
