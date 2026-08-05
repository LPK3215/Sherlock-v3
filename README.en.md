<div align="center">
<h1>Sherlock-v3</h1>

<p><strong>A multimodal agent platform for real-world workflows</strong><br/>Knowledge bases, knowledge graphs, real-time voice, and visual interaction</p>

[![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat&logo=docker&logoColor=ffffff)](https://www.docker.com/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Docs](https://img.shields.io/badge/docs-VitePress-646CFF)](https://lpk3215.github.io/Sherlock-v3/)
[![GitHub](https://img.shields.io/badge/GitHub-Sherlock--v3-181717?logo=github)](https://github.com/LPK3215/Sherlock-v3)

[[Documentation]](https://lpk3215.github.io/Sherlock-v3/) · [[中文 README]](README.md)

</div>

## Project Foundation and Open-Source Notice

Sherlock-v3 is an independent project developed on top of the open-source Yuxi project. It reuses selected agent, knowledge-base, and platform capabilities, while adding real-time voice and visual interaction, domain workflows, and business data models. Copyright and license notices for Yuxi and other third-party dependencies are retained as required; the project's centralized license information is in [LICENSE](LICENSE).

Apart from this section and the license file, project documentation does not repeat the upstream attribution. Runtime names such as the `yuxi` package, environment variables, and API fields are compatibility contracts and are not the product brand.

## Introduction

Sherlock-v3 is an LLM-powered multimodal agent platform. It combines **RAG retrieval**, **knowledge graphs**, **LangGraph agent orchestration**, and **real-time voice and visual interaction** in a Docker Compose workspace, with Skills, MCP, sub-agents, sandbox tools, citations, and deliverable artifacts. The repository includes both an administration console and a user-facing application.

See the [documentation](https://lpk3215.github.io/Sherlock-v3/) for the project overview, quick start, deployment guide, and changelog.

## Tech Stack

| Layer | Technologies |
| --- | --- |
| Frontend | Vue 3 · Vite · Pinia · Next.js/React user app |
| Backend | FastAPI · LangGraph · ARQ (async worker) |
| Storage | PostgreSQL · Redis · MinIO · Milvus · Neo4j |
| Realtime | Pipecat · WebRTC · speech recognition/synthesis · visual input |
| Document parsing | MinerU · PaddleX · RapidOCR |
| Deployment | Docker Compose |

## Quick Start

**Prerequisites**: [Docker](https://docs.docker.com/get-docker/), Docker Compose, and at least one OpenAI-compatible LLM API.

```bash
git clone --branch business-mvp --depth 1 https://github.com/LPK3215/Sherlock-v3.git
cd Sherlock-v3

# Linux/macOS
./scripts/init.sh

# Windows PowerShell
.\scripts\init.ps1
```

Start the services:

```bash
docker compose up --build
```

The administration console is available at `http://localhost:5173`; the user app is available at `http://localhost:3000`. See the [deployment documentation](https://lpk3215.github.io/Sherlock-v3/advanced/deployment) for details.

## Acknowledgements

This project uses and references LangGraph, DeepAgents, Pipecat, LightRAG, DeerFlow, RAGFlow, QwenPaw, and other open-source projects. Their maintainers and contributors are gratefully acknowledged; each dependency remains subject to its own license.

## Contributing

Please read the [contribution guide](CONTRIBUTING.md) before submitting an issue, documentation improvement, bug fix, or feature.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
