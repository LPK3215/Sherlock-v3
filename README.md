<div align="center">
<h1>Sherlock-v3</h1>

<p><strong>面向真实场景的多模态智能体平台</strong><br/>融合知识库、知识图谱、实时语音与视觉交互能力</p>

[![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat&logo=docker&logoColor=ffffff)](https://www.docker.com/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Docs](https://img.shields.io/badge/docs-VitePress-646CFF)](https://lpk3215.github.io/Sherlock-v3/)
[![GitHub](https://img.shields.io/badge/GitHub-Sherlock--v3-181717?logo=github)](https://github.com/LPK3215/Sherlock-v3)

[[项目文档]](https://lpk3215.github.io/Sherlock-v3/) · [[English README]](README.en.md)

</div>

## 项目基础与开源声明

Sherlock-v3 是在开源项目 Yuxi 的基础上进行二次开发的独立项目。项目复用了其部分智能体、知识库与平台能力,并围绕实时语音/视觉交互、领域业务能力和业务数据模型进行了扩展。Yuxi 及其他第三方依赖的版权和许可证信息按各自要求保留,本项目的集中许可证信息见 [LICENSE](LICENSE)。

除本节和许可证文件外,项目文档不重复展开上游项目归属;文档中的 `yuxi` 包名、环境变量和接口字段是当前运行时兼容契约,不代表项目品牌。

## 简介

Sherlock-v3 是一个基于大模型的多模态智能体平台。它将 **RAG 检索**、**知识图谱**、**LangGraph 智能体编排** 与 **实时语音和视觉交互** 集成到统一的 Docker Compose 工作区,并提供 Skills、MCP、子智能体、沙盒工具、引用来源和可交付产物等能力。平台同时包含管理端和面向实际使用场景的用户端。

导航:[项目介绍](https://lpk3215.github.io/Sherlock-v3/intro/project-overview) | [快速开始](https://lpk3215.github.io/Sherlock-v3/intro/quick-start) | [生产部署](https://lpk3215.github.io/Sherlock-v3/advanced/deployment) | [版本变更记录](https://lpk3215.github.io/Sherlock-v3/develop-guides/changelog)

## 技术栈

| 层 | 技术 |
| --- | --- |
| 前端 | Vue 3 · Vite · Pinia · Next.js/React 用户端 |
| 后端 | FastAPI · LangGraph · ARQ (异步 worker) |
| 存储 | PostgreSQL · Redis · MinIO · Milvus · Neo4j |
| 实时交互 | Pipecat · WebRTC · 语音识别/合成 · 视觉输入 |
| 文档解析 | MinerU · PaddleX · RapidOCR |
| 部署 | Docker Compose |

## 快速开始

**前置要求**:已安装 [Docker](https://docs.docker.com/get-docker/) 与 Docker Compose,并准备至少一个兼容 OpenAI 接口的大模型 API。

**1. 克隆代码并初始化**

```bash
git clone --branch business-mvp --depth 1 https://github.com/LPK3215/Sherlock-v3.git
cd Sherlock-v3

# Linux/macOS
./scripts/init.sh

# Windows PowerShell
.\scripts\init.ps1
```

**2. 使用 Docker 启动**

```bash
docker compose up --build
```

**3. 访问平台**

等待启动完成后,浏览器打开 `http://localhost:5173`;用户端默认位于 `http://localhost:3000`。具体配置与部署方式见[项目文档](https://lpk3215.github.io/Sherlock-v3/)。

## 致谢

本项目使用并参考了 LangGraph、DeepAgents、Pipecat、LightRAG、DeerFlow、RAGFlow、QwenPaw 及其他开源项目。感谢所有维护者和贡献者为本项目提供的基础能力与实践经验;各依赖的许可证以其项目声明为准。

## 参与贡献

欢迎提交 Issue、改进文档、修复 Bug 或贡献新功能。请先阅读[贡献指南](CONTRIBUTING.md),并在提交前完成相关测试。

## 许可证

本项目采用 MIT 许可证,详见 [LICENSE](LICENSE)。
