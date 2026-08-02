# Sherlock-v3 项目结构说明

## 三个项目的关系

```
Sherlock-v3/
├── web-bot-official/     ★ 核心项目 — 唯一需要操作的目标
├── ai-video-call-core/   ☆ 参考项目 1 — 仅在被点名时才参考
└── my-video-ai/          ☆ 参考项目 2 — 仅在被点名时才参考
```

### ★ `web-bot-official/` — 核心项目（唯一操作目标）

- **来源**：Pipecat 官方示例 `gemini-live-starters/web-bot`
- **定位**：Sherlock-v3 的**开发底座**，所有新功能都在此基础上添加
- **传输方式**：SmallWebRTC（本地不需要 Daily API Key）
- **管线模式**：仅 Cascade（STT → VLM → TTS）
- **当前模型组合**：本地 Whisper + OpenAI 兼容 VLM + 本地 Piper 中文 TTS
- **前端**：Next.js 15 + Tailwind CSS v4 + Voice UI Kit
- **后端**：Python (Pipecat)，`bot.py` 仅 172 行
- **核心能力**：实时语音对话 + 摄像头 + 屏幕共享 + 可拖拽布局 + 事件日志面板
- **API**：`POST /start`（Next.js rewrite 代理到 bot 服务）

### ☆ `ai-video-call-core/` — 参考项目 1（仅被点名时参考）

- **来源**：用户自己编写，**可能有 bug**
- **参考价值**：多供应商模型配置、Realtime/Cascade 双管线切换、视觉工具调用（`fetch_camera_image`）、媒体诊断 Observer、Eval 测试框架
- **传输方式**：SmallWebRTC（无需 Daily）
- **AI 模型**：Gemini Live / OpenAI Realtime / Qwen-VL / OpenAI 兼容端点
- **前端**：Vite 8 + React 19 + Voice UI Kit
- **注意**：**仅在用户明确要求参考时才查看此项目，不要主动借鉴**

### ☆ `my-video-ai/` — 参考项目 2（仅被点名时参考）

- **来源**：Pipecat CLI 脚手架自动生成，用户在此基础上微调
- **参考价值**：标准 Pipecat 项目结构、`run.ps1` NLTK 规避脚本
- **传输方式**：SmallWebRTC（无需 Daily）
- **AI 模型**：仅 Gemini Live
- **前端**：Vite 8 + React 19 + Voice UI Kit（纯预制组件）
- **注意**：**仅在用户明确要求参考时才查看此项目，不要主动借鉴**

---

## 开发流程规范

### 核心原则

1. **唯一操作目标**：`web-bot-official/`，所有代码修改、功能添加都在此项目中进行
2. **参考项目隔离**：`ai-video-call-core/` 和 `my-video-ai/` 仅供思想参考，**不要主动查看或借鉴**
3. **点名机制**：只有当用户说"参考 ai-video-call-core 的 XXX"或类似表述时，才去查看对应的参考项目
4. **参考不等于照搬**：参考项目可能有 bug，仅借鉴思想和工具方向，不直接复制代码

### 日常开发流程

```
用户提出需求
    │
    ├─→ 涉及 web-bot-official/ 的功能开发
    │       └─→ 直接在此项目中编码、修改
    │
    ├─→ 用户点名参考 ai-video-call-core
    │       └─→ 查看对应模块，借鉴思想，在 web-bot-official 中实现
    │
    ├─→ 用户点名参考 my-video-ai
    │       └─→ 查看对应模块，借鉴思想，在 web-bot-official 中实现
    │
    └─→ 未点名参考项目
            └─→ 不查看、不借鉴，专注于 web-bot-official
```

### 技术栈约定（web-bot-official）

| 层级 | 技术 |
|------|------|
| 前端框架 | Next.js 15 (React 19) |
| UI 样式 | Tailwind CSS v4 |
| 实时通信 | `@pipecat-ai/client-js` + `@pipecat-ai/small-webrtc-transport` |
| UI 组件 | `@pipecat-ai/voice-ui-kit` |
| 后端 | Python 3.11+ (Pipecat) |
| AI 管线 | Cascade：Whisper STT + OpenAI 兼容 VLM + Piper 中文 TTS |
| 传输 | SmallWebRTC |
| 包管理 | npm (前端) / uv (后端) |

### 关键文件清单（web-bot-official）

```
web-bot-official/
├── client/
│   ├── app/
│   │   ├── page.tsx              # 首页入口
│   │   ├── layout.tsx            # 根布局
│   │   ├── globals.css           # 全局样式
│   │   ├── ClientApp.tsx         # 核心 UI 组件（282行）
│   │   ├── EventStreamPanel.tsx  # 事件日志面板（185行）
│   │   └── api/start/route.ts   # API 代理路由
│   ├── package.json
│   └── env.example
└── server/
    ├── bot.py                    # Cascade 唯一入口
    ├── bot_cascade.py            # STT + VLM + TTS Pipeline
    ├── pyproject.toml
    ├── Dockerfile
    ├── pcc-deploy.toml
    └── env.example
```

---

## 扩展方向（未来规划）

基于 `web-bot-official` 底座，后续可扩展的方向包括但不限于：

- 替换/增强系统指令（System Instruction）
- 添加多模型支持（OpenAI、Qwen 等）
- 扩展 Pipeline 处理器（自定义中间件）
- 添加视觉工具调用（按需截图分析）
- 文档上传与处理
- 技能包系统
- 前端 UI 定制化

---

> **最后更新**：2026-08-02
> **维护者**：Sherlock-v3 开发团队
