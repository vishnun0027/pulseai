# PulseAI Project Guidelines

## Architecture
- PulseAI is a polyglot pipeline: `agent/` (Rust telemetry collector) -> `ingestion/` (Go HTTP + Redis Streams) -> `ai/` (Python IsolationForest + ADWIN + SHAP) -> `dashboard/` (FastAPI + SSE UI), with `correlation/` and `alerts/` consuming Redis events.
- Shared defaults live in `config/settings.toml`; environment-specific secrets belong in `.env` or environment variables. Never hardcode credentials.
- Cross-service contracts matter here: if you change telemetry payloads, Redis channel names, DB schema, or API response fields, update every dependent service and the relevant docs together.

## Working In This Repo
- Start by identifying the service boundary you are changing and keep edits local unless the task explicitly changes a shared contract.
- Avoid editing generated or build-output paths such as `agent/target/`, compiled binaries, `.venv/`, or other artifacts.
- Prefer small, surgical changes that preserve the current module layout and naming.

## Build, Run, And Validation
- Full stack: `docker compose up --build`
- Python setup: `uv sync`
- Dashboard local dev: `uv run uvicorn dashboard.main:app --port 8000 --reload`
- AI worker local dev: `uv run python ai/consumer.py`
- Go services local dev: `cd ingestion && go run .`, `cd correlation && go run .`, `cd alerts && go run .`
- Rust agent local dev: `cd agent && cargo run`
- There are no committed automated tests yet, so after changes run the smallest relevant validation for the touched area, such as `cargo check`, `go build ./...`, or a Python import/compile smoke check.

## Code Conventions
- Python code favors small module-focused files, FastAPI route handlers, async DB helpers in `storage/db.py`, and Pydantic models in `storage/models.py`.
- Go services use straightforward `main.go` entrypoints and standard-library HTTP wiring; keep handlers simple and metrics concerns in the dedicated metrics files.
- Rust agent code is split into focused modules under `agent/src/` with explicit payload structs and a `tokio` loop in `main.rs`.
- Preserve existing JSON field names and public API shapes unless the task specifically requires a contract change.

## Key Docs
- Start with `README.md` for the service map and local development commands.
- Use `docs/TECHNICAL_DEV_GUIDE.md` for detailed architecture, data flow, schema, and deployment context.
- Check each service folder's `README.md` for component-specific notes before making deeper changes.

## Known Gotchas
- `docker-compose.yml` expects a real `DB_PASSWORD` in `.env`; `ALERT_WEBHOOK_URL` is optional.
- The README quick start still mentions `cd anomaly-system`; use the actual workspace root, `pulseai`.
