# Sherlock-v3 项目结构说明

## 当前目录关系

```
Sherlock-v3/
├── backend/                 FastAPI 后端、worker 与领域能力
├── web/                     管理端 Vue 应用
├── user-app/                面向用户的实时交互应用
├── docs/                    VitePress 项目文档
├── scripts/                 初始化与辅助脚本
├── docker-compose.yml       开发环境服务编排
└── docker-compose.prod.yml  生产环境服务编排
```

## 项目边界

- `backend/` 是 API、异步 worker、智能体运行链路和领域业务的主要实现位置。
- `web/` 是管理员使用的 Vue 管理端。
- `user-app/` 是面向最终用户的实时语音、视频和屏幕交互应用。
- `docs/` 是开发、部署和使用文档,不承载运行时业务代码。

## 开发流程

1. 所有修改限定在当前 Sherlock-v3 仓库内,并遵循对应目录的职责边界。
2. API 和异步任务在 `backend/` 中维护,前端 API 声明位于 `web/src/apis/`。
3. Docker Compose 是本项目统一的开发与部署入口。
4. 修改后按影响范围运行相关测试、lint 和构建检查。

## 技术栈

| 层级 | 技术 |
|------|------|
| 管理端 | Vue 3 + Vite + Pinia |
| 用户端 | Next.js / React |
| 后端 | Python 3.12+ + FastAPI + LangGraph |
| 实时通信 | Pipecat + WebRTC |
| 存储 | PostgreSQL + Redis + MinIO + Milvus + Neo4j |
| 包管理 | pnpm (前端) / uv (后端) |

## 关键目录

```
backend/
├── package/yuxi/             # 后端 Python 包
├── test/                     # unit / integration / e2e 测试
└── pyproject.toml

web/
├── src/apis/                 # 前端 API 定义
├── src/components/           # 管理端组件
└── package.json

user-app/
├── app/                      # 用户端页面与路由
└── package.json
```

## 后续方向

- 持续完善实时语音、视频和屏幕交互体验。
- 扩展领域 Skill 与确认式业务工具。
- 完善知识库、知识图谱和智能体评估能力。
- 持续补充部署、运维和用户操作文档。
