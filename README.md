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

<!-- TODO(#10): link and summary of the setup wizard for human-only steps. -->

## Deploy

Local: `cp .env.example .env`, fill it in, then `docker compose --profile dev up -d --build`. This starts Postgres (`db`, published on `127.0.0.1:5432` only) and the `api`, which runs `alembic upgrade head` and then uvicorn on `127.0.0.1:8000`. Check with `curl 127.0.0.1:8000/health`. Stop with `docker compose --profile dev down` (add `-v` to drop the database volume).

The image is built with uv in two stages, runs as a non-root user (uid 10001) and has a healthcheck on `/health`. `.dockerignore` keeps `.env` out of the image. The `api` service uses host networking so it can reach the Hermes gateway at `127.0.0.1:8642` on the host.

Server (one VM, Hermes on the host, API in Docker, Caddy in front):

1. Install Docker, Caddy and Hermes (as a non-root service user; see the setup wizard). Copy the repo to `/opt/hermes_intake_agent` and create `.env` there.
2. Set `DATABASE_URL` to the Supabase (EU region) connection string on port **5432** (direct or session). Do **not** use the 6543 transaction pooler. Use the `postgresql+asyncpg://` scheme. Do not use the `dev` profile on the server, so no local `db` starts.
3. Hermes: `sudo hermes gateway install --system && sudo hermes gateway start --system`, or copy `deploy/hermes-gateway.service` (adjust `User` and paths). Never add an `ExecStopPost` kill.
4. API: `sudo cp deploy/intake-compose.service /etc/systemd/system/ && sudo systemctl enable --now intake-compose`. The container itself has `restart: unless-stopped`, and the unit re-runs `docker compose up -d` on boot.
5. Caddy: put your free hostname in `deploy/Caddyfile`, copy it to `/etc/caddy/Caddyfile` and run `sudo systemctl reload caddy`. Caddy gets the HTTPS certificate automatically and proxies to `127.0.0.1:8000`.
6. Dashboard: deploy `dashboard/` to Vercel and add its origin to `CORS_ORIGINS`.

Syntax checks: `systemd-analyze verify deploy/*.service` and `caddy validate --config deploy/Caddyfile`.

## E2E runbook

<!-- TODO(#11): how to run the e2e suite and the manual Slack click-through. -->
