<div align="center">
<h1>Sherlock-v3</h1>

<p><strong>A multimodal agent platform for real-world workflows</strong><br/>Knowledge bases, knowledge graphs, real-time voice, and visual interaction</p>

[![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat&logo=docker&logoColor=ffffff)](https://www.docker.com/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-0.7.1-blue.svg)](backend/package/pyproject.toml)
[![Docs](https://img.shields.io/badge/docs-VitePress-646CFF)](https://lpk3215.github.io/Sherlock-v3/)
[![GitHub](https://img.shields.io/badge/GitHub-Sherlock--v3-181717?logo=github)](https://github.com/LPK3215/Sherlock-v3)

[[Documentation]](https://lpk3215.github.io/Sherlock-v3/) · [[中文 README]](README.md)

</div>

## Project Foundation and Open-Source Notice

Sherlock-v3 is an independently developed multimodal agent platform integrating RAG retrieval, knowledge graphs, LangGraph agent orchestration, and real-time voice and visual interaction. Copyright and license notices for third-party dependencies are retained as required; the project's centralized license information is in [LICENSE](LICENSE).

Apart from the license file, project documentation does not repeat third-party attributions.

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

## Project Structure

```text
Sherlock-v3/
├── backend/
│   ├── package/        # Python core package and dependency configuration
│   ├── server/         # FastAPI, agents, and task services
│   └── test/           # unit, integration, and e2e tests
├── web/                # Vue administration console
├── user-app/           # Next.js/React user application
├── docker/             # images, data volumes, and sandbox provisioner
├── docs/               # VitePress project documentation
├── scripts/            # initialization, version, and evaluation scripts
├── docker-compose.yml  # development service orchestration
└── docker-compose.prod.yml
```

## Development Checks

Run backend tests and frontend checks with the repository's Docker and package tooling:

```bash
# Full backend test suite
docker compose exec -T api uv run --group test pytest test

# Run tests by layer
docker compose exec -T api uv run --group test pytest test/unit
docker compose exec -T api uv run --group test pytest test/integration
docker compose exec -T api uv run --group test pytest test/e2e -m e2e

# Backend formatting and frontend checks
make format
pnpm --dir user-app run lint
```

See the [testing guide](docs/develop-guides/testing-guidelines.md) and [contribution guide](CONTRIBUTING.md) for the complete container-based verification workflow.

## Acknowledgements

This project uses and references LangGraph, DeepAgents, Pipecat, LightRAG, DeerFlow, RAGFlow, QwenPaw, and other open-source projects. Their maintainers and contributors are gratefully acknowledged; each dependency remains subject to its own license.

## Contributing

Please read the [contribution guide](CONTRIBUTING.md) before submitting an issue, documentation improvement, bug fix, or feature.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
