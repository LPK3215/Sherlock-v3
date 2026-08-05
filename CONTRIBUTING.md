# Contributing to Sherlock-v3

感谢你关注 Sherlock-v3。欢迎提交 Issue、改进文档、修复 Bug 或贡献新功能。

更完整的开发文档可参考 [docs/develop-guides/contributing.md](docs/develop-guides/contributing.md)。

## 开始之前

- 提交前请先搜索现有 [Issues](https://github.com/LPK3215/Sherlock-v3/issues)
- 对于较大的功能改动,建议先开 Issue 讨论方案
- 保持改动聚焦,避免在一次 PR 中混入无关重构

## 开发方式

本项目通过 Docker Compose 进行开发,推荐直接在容器环境中调试。

```bash
docker compose up -d
docker ps
docker logs api-dev --tail 100
```

项目中的 API 和前端服务支持热重载,本地修改代码后通常无需重启容器。

## 提交流程

1. 创建功能分支
2. 在对应目录完成开发与测试
3. 提交清晰的 Commit Message
4. 发起 Pull Request,并说明修改内容、原因和验证方式
5. 提交前完成 PR 模板中的检查项

## 代码要求

- 保持实现简单直接,避免过度设计
- 只修改当前任务所需内容,不顺手做额外重构
- 更新相关文档和必要的 [变更记录](docs/develop-guides/changelog.md)
- 后端使用 Python 3.12+ 风格,测试脚本放在 `backend/test`
- 前端使用 `pnpm`,API 接口统一放在 `web/src/apis`
- 样式使用 `less`,优先复用 `web/src/assets/css/base.css` 中的颜色变量

## 提交前检查

```bash
make format
docker compose exec -T api uv run pytest
pnpm --dir web run lint
pnpm --dir user-app run lint
```

## 问题反馈

- Bug 反馈/功能讨论:<https://github.com/LPK3215/Sherlock-v3/issues>
