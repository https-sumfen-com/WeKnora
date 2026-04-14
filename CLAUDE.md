# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

WeKnora (module `github.com/Tencent/WeKnora`, Go 1.24.11) is a multi-service LLM-powered knowledge management / RAG framework. Three deployable units cooperate at runtime:

- **`cmd/server`** — Go backend (Gin HTTP + `go.uber.org/dig` DI). Entry: `cmd/server/main.go`. Base path `/api/v1` on port 8080.
- **`docreader/`** — Python gRPC service (port 50051) for document parsing (PDF/Word/Excel/PPT/image/web). Started independently; the backend calls it over gRPC (`DOCREADER_ADDR`).
- **`frontend/`** — Vue 3 + Vite + TDesign SPA (port 5173 in dev). Builds to `frontend/dist`; Lite mode copies it to `web/` embedded in the Go binary.

There are two **editions** of the backend built from the same tree:
- **Standard** — multi-tenant, Docker Compose stack with Postgres/Redis/MinIO/Neo4j, external DocReader service.
- **Lite** — built with `-tags sqlite_fts5` and `EDITION=lite`; single binary, SQLite + in-memory queue, no shared space / multi-tenant features. See `docs/LITE.md`.

## Common Commands

All workflow commands go through the top-level `Makefile`. Run `make help` for the full annotated list.

### Daily development (fast mode — preferred)
```bash
make dev-start      # Start infra containers: postgres, redis, minio, neo4j, docreader, jaeger
make dev-app        # Run Go backend locally (new terminal)
make dev-frontend   # Run Vite dev server (new terminal)
make dev-stop       # Tear down infra
```
The dev-app target uses env vars that assume infra is reachable on localhost (see `docs/开发指南.md` for the VS Code launch config).

### Build / test / lint
```bash
make build          # go build -o WeKnora ./cmd/server
make test           # go test -v ./...
go test -run TestName ./path/to/pkg   # single test
make fmt            # go fmt ./...
make lint           # golangci-lint run
make deps           # go mod download
make docs           # regenerate Swagger from annotations (requires `make install-swagger` once)
```

### Database migrations (`migrations/`, golang-migrate)
```bash
make migrate-up
make migrate-down
make migrate-create name=add_foo_table
make migrate-force version=N       # use only when recovering from a broken migration
```

### Lite build
```bash
make build-lite     # builds frontend → web/, then Go binary WeKnora-lite with sqlite_fts5 tag
make run-lite       # build-lite + start using .env.lite
make package-lite   # distributable tarball
```
Set `SKIP_FRONTEND=1` to skip the frontend rebuild step.

### Docker / deployment
```bash
docker compose up -d                        # core services
docker compose --profile full up -d         # all optional services
docker compose --profile neo4j --profile minio up -d
make build-images                           # rebuild all images from source via scripts/build_images.sh
```

### DocReader (Python, separate tree)
`docreader/` is a `uv`-managed Python project with its own `Makefile`. It speaks gRPC on `:50051` (`grpc_health_probe` for health). Key env vars documented in `docreader/README.md` (OCR backend, VLM model, storage backends).

## Architecture

### Dependency injection wiring
The backend uses `go.uber.org/dig`. `main.go` calls `container.BuildContainer(runtime.GetContainer())` — **`internal/container/container.go` is the central wiring file**. Almost every new service, handler, or repository needs to be registered here. The container selects implementations based on env vars (e.g. `DB_DRIVER`, `RETRIEVE_DRIVER`, `STORAGE_TYPE`, `STREAM_MANAGER_TYPE`) and imports the corresponding `internal/application/repository/retriever/<backend>` package.

### Request flow
`router.NewRouter` (`internal/router/router.go`) takes a large `RouterParams` struct (all handlers + services injected by dig) and mounts everything under `/api/v1`. Handlers live in `internal/handler/` and delegate to services in `internal/application/service/` which use repositories in `internal/application/repository/`. The `internal/types/interfaces/` package holds the cross-package service interfaces.

### Key internal subsystems
- `internal/application/service/chat_pipeline/` — RAG / ReACT agent orchestration (query rewriting, retrieval, rerank, generation).
- `internal/agent/` — Agent engine, built-in tools, MCP integration.
- `internal/models/` — LLM / embedding / rerank / VLM / ASR provider abstraction (OpenAI / Ollama / DeepSeek / Qwen / Hunyuan / Novita / NVIDIA / etc.).
- `internal/datasource/connector/` — External data-source sync (Feishu, Notion).
- `internal/im/` — IM channel adapters (wecom, feishu, slack, telegram, dingtalk, mattermost, wechat).
- `internal/infrastructure/docparser/` — gRPC client to the `docreader` service.
- `internal/sandbox/` — sandboxed execution for agent skills.
- `internal/stream/` — streaming responses backed by memory or Redis (`STREAM_MANAGER_TYPE`).
- `internal/mcp/` — MCP client + built-in server wrapper.

### Retrieval / storage pluggability
A retriever is chosen per env var and the matching package is wired in the container:
`postgres` (pgvector) | `elasticsearch_v7` | `elasticsearch_v8` | `qdrant` | `milvus` | `weaviate` | `sqlite` (Lite only, via `sqlite_fts5` build tag + `sqlite-vec`) | `neo4j` (GraphRAG). Object storage backends: `local` / `minio` / `cos` / `tos` / `s3` / `oss`.

### Frontend
Vue 3 + Pinia + vue-router + TDesign. API client in `frontend/src/api/`, views in `frontend/src/views/`, i18n in `frontend/src/i18n/`. A Wails desktop wrapper lives in `frontend/src/wailsjs/` and `cmd/desktop/`.

### Auth
Two mechanisms live side-by-side: JWT `Authorization: Bearer <token>` for end-user sessions and tenant API keys `X-API-Key: sk-...` (see Swagger security definitions in `cmd/server/main.go`). API keys are encrypted at rest (AES-256-GCM). `DISABLE_REGISTRATION=true` locks down signup.

## Conventions

- **Module path:** `github.com/Tencent/WeKnora` — use this for all internal imports.
- **Commits:** Conventional Commits (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`…) per `README.md`.
- **Swagger annotations** in handler comments are the source of truth for `docs/swagger.{json,yaml}`; regenerate with `make docs` after changing handler signatures.
- When adding a handler or service, register it in `internal/container/container.go` **and** add it to `RouterParams` / the route table in `internal/router/router.go`.
- Build tags: `sqlite_fts5` gates the SQLite retriever used by Lite; the standard build omits it.

## Relevant documentation
- `docs/开发指南.md` — local dev environment walkthrough
- `docs/LITE.md` — Lite vs standard differences
- `docs/api/README.md` + `docs/swagger.yaml` — REST API reference
- `docs/MCP功能使用说明.md`, `docs/agent-skills.md` — agent / MCP subsystems
- `docs/使用其他向量数据库.md`, `docs/开启知识图谱功能.md` — retriever configuration
- `docreader/README.md` — docreader service env vars
