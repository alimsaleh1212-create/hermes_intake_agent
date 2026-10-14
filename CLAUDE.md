# Hermes Intake

FastAPI service that turns a Client's Transcript into an Intake Output via a Hermes Agent skill, with Slack Approval and a React dashboard. Vocabulary follows `GLOSSARY.md`; the spec is GitHub issue #1.

## Working here

- **Stack**: uv, Python 3.12, FastAPI, async SQLAlchemy, Alembic, pydantic-settings, httpx. Dashboard: React + Vite with npm (not pnpm).
- **Plug-in points**: one factory per concern (`app/<concern>/factory.py`). Change your concern's factory, not `app/deps.py` or `app/main.py`.
- **Hermes, Slack or model-provider work**: read `docs/research/` first.
- **Standards**: `CODING_STANDARDS.md` is applied at review. Black, ruff and `tests/test_layering.py` enforce the mechanical rules.

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
