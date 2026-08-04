# 实时用户端验收记录

## 范围

`user-app` 是专门的实时用户端,调用同一个 Yuxi 后端,不承载独立后端。重点验收视频、语音、文字和媒体控制的组合场景。

## 已验证能力

| 场景 | 结果 | 证据 |
|---|---|---|
| 页面打开、登录、Agent 选择 | 通过 | Playwright 浏览器现场运行 |
| WebRTC 建连 | 通过（正确 proxy/fake media 条件） | `realtime_browser_e2e.mjs` |
| 文字消息 | 通过 | 浏览器专项 |
| TTS 音频返回 | 通过 | Piper 入站音频 |
| STT 语音识别 | 通过 | Whisper 真实 WAV |
| 摄像头共享并被 Agent Tool 识别 | 通过 | `CAMERA RED 742 / 229` |
| 屏幕共享并被 Agent Tool 识别 | 通过 | `SCREEN GREEN 915 / 431` |
| 插话后新消息 | 通过 | 旧 Run 取消,新 Run 完成 |
| 多种 UI/事件日志 | 已接入 | `ClientApp` / `EventStreamPanel` |
| 审批卡片首次显示 | 待完成 | 后端事件正确,浏览器闭环仍需证据 |
| 审批断线恢复与 resume | 待完成 | active-run 轮询已实际返回 200,完整点击闭环待完成 |

## 组合业务清单

需要在真实浏览器最终确认:纯文字、纯语音、视频+文字、视频+语音、屏幕+文字、屏幕+语音、上传/发送文字与媒体同时进行、插话、断线重连、审批恢复。

## 测试注意事项

Playwright 容器不能把自身 `localhost:3000` 当作 user-app;必须使用 loopback proxy。Chromium 必须启用 fake media 参数和 camera/microphone 权限,否则会报 `WebRTC not supported or suppressed`。
