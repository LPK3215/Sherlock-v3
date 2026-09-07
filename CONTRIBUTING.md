# 贡献指南

感谢您关注 Sherlock-v3！请阅读以下指南参与贡献。

## 开发环境搭建

请先阅读 [README.md](./README.md) 中的"快速开始"部分，完成本地环境搭建。

## 分支策略

- `main` — 稳定发布分支
- `feature/*` — 新功能分支
- `fix/*` — Bug 修复分支

## 提交规范

| 前缀 | 用途 |
|---|---|
| `feat:` | 新功能 |
| `fix:` | Bug 修复 |
| `docs:` | 文档更新 |
| `refactor:` | 代码重构 |
| `chore:` | 构建/工具变更 |

## Pull Request 流程

1. Fork 本仓库
2. 从 `main` 分支创建特性分支
3. 编写代码并确保本地可正常运行
4. 提交 PR，描述变更内容和动机

## 注意事项

- 核心开发在 `web-bot-official/` 目录中进行
- `ai-video-call-core/` 和 `my-video-ai/` 是参考项目，仅在需要时参考
- 不要提交本地模型权重文件（.onnx, .bin, .gguf 等）
