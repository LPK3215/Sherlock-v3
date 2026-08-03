# Sherlock-v3 项目结构说明

## 当前目录关系

```
Sherlock-v3/
├── client/                  ★ 正式前端
├── server/                  ★ 正式 Cascade 后端
```

### ★ 根目录正式项目（唯一操作目标）

- **来源**：Pipecat 官方示例 `gemini-live-starters/web-bot`
- **定位**：Sherlock-v3 的**开发底座**，根目录即正式项目
- **传输方式**：SmallWebRTC（本地不需要 Daily API Key）
- **管线模式**：仅 Cascade（STT → VLM → TTS）
- **当前模型组合**：本地 Whisper + OpenAI 兼容 VLM + 本地 Piper 中文 TTS
- **前端**：Next.js 15 + Tailwind CSS v4 + Voice UI Kit
- **后端**：Python (Pipecat)，`bot.py` 是轻量 Cascade 入口
- **核心能力**：实时语音对话 + 摄像头 + 屏幕共享 + 可拖拽布局 + 事件日志面板
- **API**：`POST /start`（Next.js rewrite 代理到 bot 服务）

---

## 开发流程规范

### 核心原则

1. **唯一操作目标**：根目录正式项目，所有业务代码位于 `client/` 和 `server/`
2. **单一后端**：只有 `server/` 包含 AI Pipeline
3. **冻结恢复点**：微信式视频通话模板代码保存在 Git 标签 `v0.1-cascade-demo`

### 日常开发流程

```
用户提出需求
    │
    ├─→ 涉及正式项目的功能开发
    │       └─→ 直接在此项目中编码、修改
    │
    └─→ 其他需求
            └─→ 直接修改根目录 client/ 或 server/
```

### 技术栈约定（正式项目）

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

### 关键文件清单

```
client/
├── app/
│   ├── page.tsx              # 首页入口
│   ├── layout.tsx            # 根布局
│   ├── globals.css           # 全局样式
│   ├── ClientApp.tsx         # 核心 UI 组件
│   ├── EventStreamPanel.tsx  # 事件日志面板
│   └── api/start/route.ts    # API 代理路由
└── package.json

server/
├── bot.py                    # Cascade 唯一入口
├── bot_cascade.py            # STT + VLM + TTS Pipeline
├── pyproject.toml
├── Dockerfile
├── pcc-deploy.toml
└── config.example.env
```

---

## 扩展方向（未来规划）

基于当前根目录正式项目，后续可扩展的方向包括但不限于：

- 替换/增强系统指令（System Instruction）
- 添加多模型支持（OpenAI、Qwen 等）
- 扩展 Pipeline 处理器（自定义中间件）
- 添加视觉工具调用（按需截图分析）
- 文档上传与处理
- 技能包系统
- 前端 UI 定制化

---

> **最后更新**：2026-08-03
> **维护者**：Sherlock-v3 开发团队
