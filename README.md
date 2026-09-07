# Sherlock-v3

> 基于 Pipecat 的 AI 实时语音对话系统，支持摄像头、屏幕共享和可拖拽布局。

## 项目简介

Sherlock-v3 是一个基于 Pipecat 框架构建的 AI 实时语音对话系统，采用 SmallWebRTC 传输方式（无需 Daily API Key），使用 Cascade 管线模式（STT → VLM → TTS）实现实时语音对话。

### 核心能力

- **实时语音对话** — 本地 Whisper STT + OpenAI 兼容 VLM + 本地 Piper 中文 TTS
- **视频输入** — 摄像头 + 屏幕共享
- **可拖拽布局** — 自定义界面布局
- **事件日志面板** — 实时调试和监控

## 项目结构

```
Sherlock-v3/
├── web-bot-official/     ★ 核心项目 — 唯一需要操作的目标
│   ├── bot.py            — 后端管线（Python Pipecat，仅 172 行）
│   └── src/              — 前端（Next.js 15 + Tailwind CSS v4 + Voice UI Kit）
├── ai-video-call-core/   ☆ 参考项目 1 — 多供应商模型配置、双管线切换
└── my-video-ai/          ☆ 参考项目 2 — 标准 Pipecat 项目结构
```

### 核心项目 web-bot-official

- **来源**：Pipecat 官方示例 `gemini-live-starters/web-bot`
- **传输方式**：SmallWebRTC（本地不需要 Daily API Key）
- **管线模式**：仅 Cascade（STT → VLM → TTS）
- **当前模型组合**：本地 Whisper + OpenAI 兼容 VLM + 本地 Piper 中文 TTS
- **前端**：Next.js 15 + Tailwind CSS v4 + Voice UI Kit
- **后端**：Python (Pipecat)
- **API**：`POST /start`（Next.js rewrite 代理到 bot 服务）

## 技术栈

| 层级 | 技术 |
|---|---|
| 后端 | Python、Pipecat、SmallWebRTC |
| STT | 本地 Whisper |
| VLM | OpenAI 兼容端点 |
| TTS | 本地 Piper 中文 TTS |
| 前端 | Next.js 15、Tailwind CSS v4、Voice UI Kit |

## 快速开始

```bash
# 进入核心项目
cd web-bot-official

# 安装后端依赖
pip install -r requirements.txt

# 安装前端依赖
cd src && npm install

# 启动开发服务器
npm run dev
```

## 贡献指南

1. Fork 本仓库
2. 创建特性分支：`git checkout -b feature/your-feature`
3. 提交更改：`git commit -m 'feat: add your feature'`
4. 推送分支：`git push origin feature/your-feature`
5. 提交 Pull Request

## 许可证

[MIT License](./LICENSE) © 2026 LPK3215

## 作者

**LPK3215** — Email: 17538703215@163.com

## 致谢

本项目基于 [Pipecat](https://github.com/pipecat-ai/pipecat) 开源框架。
