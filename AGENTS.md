# Repository Guidelines

## Project Structure & Module Organization

The Go service starts in `cmd/server`; domain and infrastructure code lives under `internal/`. The Vue 3/Vite UI is in `frontend/src`, with `components`, `views`, `stores`, `api`, and `utils`. `cli/` and `client/` are separate Go modules; Python services live in `docreader/` and `mcp-server/`. Put schema changes in `migrations/`, defaults in `config/`, deployment assets in `docker/`, `deploy/`, or `helm/`, and fixtures in `testdata/`.

## Build, Test, and Development Commands

- `make dev-start`: start development infrastructure.
- `make dev-app` / `make dev-frontend`: run the Go API and Vite UI in separate terminals.
- `make build` / `make test`: compile the server or run root Go tests.
- `make fmt && make lint`: format Go code and run `golangci-lint`.
- `cd frontend && npm ci && npm run build-with-types`: install locked UI dependencies, type-check, and build.
- `docker compose up -d`: launch the containerized stack.

## Coding Style & Naming Conventions

Format Go with `gofmt`/`gofumpt`; use tabs and short lowercase package names. Linting enforces `govet`, `revive`, and a 120-character line limit. TypeScript and Vue use two spaces and no semicolons. Name new components `PascalCase.vue`, functions/composables in `camelCase`, and import `frontend/src` through `@/`. Python uses four spaces, type hints, and `snake_case`.

## Testing Guidelines

Place Go tests beside code as `*_test.go` and favor table-driven cases. Frontend tests use Node's runner and `*.test.ts`; run `cd frontend && npm test`. Run mini-program tests with `cd miniprogram && npm test`, and Python `test_*.py` files with pytest from their service directory. Test nested Go modules with `cd cli && go test ./...` or `cd client && go test ./...`. There is no global coverage threshold; behavior changes still require focused regression tests.

## Commit & Pull Request Guidelines

Follow Conventional Commits: `feat(scope): ...`, `fix: ...`, `docs: ...`, or `refactor: ...`. PRs must explain the change, link issues with `Fixes #123`, list verification steps, and identify breaking changes. Add screenshots or recordings for UI changes. Run `make fmt && make lint && make test` plus affected package tests before submission.

## Security & Configuration

Copy `.env.example` or `.env.lite.example` for local setup. Never commit `.env`, credentials, private mini-program settings, generated artifacts, or production data. Report vulnerabilities through the process in `SECURITY.md` rather than a public issue.
