# Sherlock User App

Sherlock 的独立用户端，直接使用 Yuxi API 提供登录、Agent 选择、文字、
语音、视频、屏幕共享、实时转写、审批和事件诊断。

## Start locally

先通过根目录 Compose 启动 Yuxi API，再运行：

```powershell
pnpm install
pnpm dev
```

打开 `http://localhost:3000`。`next.config.ts` 将 `/yuxi-api/*` 同源转发到
`YUXI_SERVER_URL`，实时会话与 WebRTC 信令均由 Yuxi 后端提供。

也可以在仓库根目录运行 `docker compose up -d user-app`。屏幕共享仅在桌面浏览器显示。
