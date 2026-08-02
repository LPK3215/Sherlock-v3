# Sherlock-v3 项目结构说明

## 当前目录关系

```
Sherlock-v3/
├── web-bot-official/     ★ 核心项目 — 唯一需要操作的目标
└── ai-video-call-core/
    └── client/           ☆ 保留的微信式视频通话 UI 参考
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

### ☆ `ai-video-call-core/client/` — UI 参考

- **保留内容**：只有 Vite + React 前端
- **参考价值**：全屏摄像头、悬浮通话控件和微信式视频通话布局
- **边界**：不包含后端，不参与当前 Cascade 服务运行
- **使用方式**：仅在改造 `web-bot-official/client` 视觉布局时参考

---

## 开发流程规范

### 核心原则

1. **唯一操作目标**：`web-bot-official/`，所有代码修改、功能添加都在此项目中进行
2. **单一后端**：只有 `web-bot-official/server` 包含 AI Pipeline
3. **UI 隔离**：`ai-video-call-core/client` 只保留布局参考，不作为第二套应用运行
4. **冻结恢复点**：删除前的完整代码保存在 Git 标签 `v0.1-cascade-demo`

### 日常开发流程

```
用户提出需求
    │
    ├─→ 涉及 web-bot-official/ 的功能开发
    │       └─→ 直接在此项目中编码、修改
    │
    ├─→ 需要微信式视频通话布局
    │       └─→ 只参考 ai-video-call-core/client，在核心前端中实现
    │
    └─→ 其他需求
            └─→ 直接修改 web-bot-official
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
│   └── package.json
└── server/
    ├── bot.py                    # Cascade 唯一入口
    ├── bot_cascade.py            # STT + VLM + TTS Pipeline
    ├── pyproject.toml
    ├── Dockerfile
    ├── pcc-deploy.toml
    └── config.example.env
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
