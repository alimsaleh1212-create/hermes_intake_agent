# Hermes Intake

FastAPI service that turns a Client's Transcript into an Intake Output via a Hermes Agent skill, with Slack Approval and a React dashboard. Vocabulary follows `GLOSSARY.md`; the spec is GitHub issue #1.

## Coding rules

- **Stack**: uv, Python 3.12, FastAPI, async SQLAlchemy, Alembic, pydantic-settings, httpx. Dashboard: React + Vite with npm (not pnpm).
- **Style**: type hints everywhere, Google docstrings, Black 88, ruff (`uv run black . && uv run ruff check .`).
- **Layering**: route → service → repository → database. Routes call services only; services never write SQL; only `app/db/` imports SQLAlchemy, and only `app/db/repository.py` opens sessions. `tests/test_layering.py` enforces this.
- **Dependency injection**: collaborators come from `app/deps.py` providers, which call one factory per concern (`app/<concern>/factory.py`). Change your concern's factory, not `deps.py` or `main.py`. Tests swap collaborators with `app.dependency_overrides`.
- **Lifespan** creates the async engine, the shared httpx client and the Slack client once, and closes them at shutdown.
- **Config**: every setting lives in `app/core/config.py` (case-insensitive env, `.env`); secrets are `SecretStr`. Add new keys to `.env.example` too. Secrets only in the uncommitted `.env`; never print or log them.
- **Privacy**: never log Transcript text (raw or redacted), model prompts or model output. Log only Intake ID, status, cost, duration and errors. Error strings stored on an Intake must not contain Transcript text.
- **Tests**: test-first at the agreed seams (HTTP API, `IntakeAgent`, guardrail functions, dashboard fetch boundary, e2e). API tests use the real Postgres from testcontainers (Docker must be running). E2E tests are marked `e2e` and excluded by default.
- **Git**: Conventional Commits.

## Agent skills

### Issue tracker

Issues and specs are tracked as GitHub Issues, using the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Uses the five default triage labels (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `GLOSSARY.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.

## Subagent models

- Implementation and merge subagents use Sonnet 5.5 (`model: "sonnet"`).
- Code review uses Opus 5.5.
