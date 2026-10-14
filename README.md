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

<!-- TODO(#4, #5): two-layer Fallback summary (ADR 0001), models, Estimated Cost. -->

## Security & least privilege

<!-- TODO(#3, #5, #6): redaction before model/DB/logs, Injection Flag, transcript-as-data prompt, no Hermes toolsets, schema validation, API key, CORS, EU region, Slack signature checks. -->

## Setup wizard

[`scripts/setup_wizard.sh`](scripts/setup_wizard.sh) walks you through the steps only a human can do. It opens each URL, captures each value (secrets are read hidden and never printed) and updates `.env` in place without touching other keys.

```bash
scripts/setup_wizard.sh local    # stages 1-3: Hermes install/config/skill/gateway, Groq + OpenRouter keys, OpenRouter privacy
scripts/setup_wizard.sh deploy   # stages 4-8: Slack app, Supabase, GCP VM + Caddy, Vercel dashboard, optional cloudflared tunnel
```

The local stages are enough to start the e2e before any deploy. Re-running is safe: existing values and generated keys are reused.

## Deploy

<!-- TODO(#9): Docker, compose, systemd units, Caddy, Supabase port 5432 note, Vercel. -->

## E2E runbook

<!-- TODO(#11): how to run the e2e suite and the manual Slack click-through. -->
