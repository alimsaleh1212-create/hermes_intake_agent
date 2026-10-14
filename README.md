# Hermes Intake

A mini version of the agency's Hermes intake agent. A Client's first-call Transcript goes in. PII is redacted, injection attempts are flagged, and a Hermes Agent skill produces an Intake Output: Current Systems, an Architecture Doc, an Access Checklist and Feasibility Verdicts. A reviewer approves it in Slack, and a dashboard tracks every Intake with its model, Fallback, cost and duration.

Vocabulary: see [`GLOSSARY.md`](GLOSSARY.md). Decisions: [`docs/adr/`](docs/adr/).

## Quickstart

Requirements: [uv](https://docs.astral.sh/uv/), Docker (the tests start Postgres with testcontainers).

```bash
uv sync
cp .env.example .env          # then fill in the keys
uv run pytest                 # unit + API tests against a throwaway Postgres
```

Run the API locally against a Postgres on `DATABASE_URL`:

```bash
uv run alembic upgrade head
uv run uvicorn --factory app.main:create_app --reload
# open http://127.0.0.1:8000/docs and POST /intakes
```

Demo Transcripts live in [`transcripts/`](transcripts/): Mike's Roofing, one with PII, and one with an injection attempt.

## Architecture

Route → service → repository → database. Routes never touch the database, and only `app/db/` imports SQLAlchemy.

```
app/
├── main.py               # create_app() + lifespan (engine, httpx client, Slack client)
├── deps.py               # Depends() providers; each calls its concern's factory
├── core/config.py        # Settings (pydantic-settings), every config field
├── api/                  # routes: health, intakes, slack
├── services/             # IntakeService (submit, process, list, get, record_decision)
├── db/                   # models, session, repository (only layer touching the DB)
├── schemas/intake.py     # Intake Output + API request/response schemas
├── agents/               # IntakeAgent protocol, FakeAgent, direct + Hermes agents, factory
├── llm/                  # LLMClient protocol + factory (Groq then OpenRouter)
├── guardrails/           # Redactor + InjectionDetector protocols + factory
└── slack/                # SlackNotifier protocol, Slack client + notifier factory
alembic/                  # migrations (one creates the intakes table)
transcripts/              # demo Transcripts
dashboard/                # React (Vite) dashboard
```

Status lifecycle: `processing` → `awaiting_approval` → `approved` | `changes_requested`; any agent failure after both models → `failed`.

<!-- TODO(#4): models, Estimated Cost. -->

**Hermes agent and Fallback (#5).** With `HERMES_ENABLED=true` the service starts a run on the Hermes gateway (`POST /v1/runs`, then polls `GET /v1/runs/{id}`), sending the `client-intake` skill text as `instructions` and the Redacted Transcript in `<transcript>` tags. `model_used` and `fallback_used` come from the run's `runtime.model` (Layer 1, Hermes' own `fallback_providers`). If there is no answer in 60 s, the output fails Intake Output validation, the run fails, or the gateway is unreachable, the service calls the secondary model directly through `LLMClient` (Layer 2, `fallback_used=true`, no retry on the primary). See ADR 0001.

Files for the setup wizard: the skill is `app/agents/assets/client-intake/SKILL.md` (install to `~/.hermes/skills/client-intake/SKILL.md`) and the config is `app/agents/assets/hermes-config.yaml.template` (install to `~/.hermes/config.yaml`; secrets and `API_SERVER_ENABLED=true` go in `~/.hermes/.env`).

## Security & least privilege

**Hermes has no tools.** The config template sets `platform_toolsets.api_server: []` and `agent.disabled_toolsets`, so even a successful prompt injection cannot act: the model can only return text, which is schema-validated and then approved by a person in Slack. The template also sets `api_max_retries: 0` and `auto_recovery_cycles: 0` so Hermes cannot exceed the 60 s budget.

<!-- TODO(#3, #6): redaction before model/DB/logs, Injection Flag, transcript-as-data prompt, no Hermes toolsets, schema validation, API key, CORS, EU region, Slack signature checks. -->

## Setup wizard

<!-- TODO(#10): link and summary of the setup wizard for human-only steps. -->

## Deploy

<!-- TODO(#9): Docker, compose, systemd units, Caddy, Supabase port 5432 note, Vercel. -->

## E2E runbook

<!-- TODO(#11): how to run the e2e suite and the manual Slack click-through. -->
