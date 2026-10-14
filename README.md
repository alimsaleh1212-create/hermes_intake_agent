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

Files for the setup wizard: the skill is `app/agents/assets/client-intake/SKILL.md` (install to `~/.hermes-intake/skills/client-intake/SKILL.md`) and the config is `app/agents/assets/hermes-config.yaml.template` (install to `~/.hermes-intake/config.yaml`; secrets, `API_SERVER_ENABLED=true` and `API_SERVER_PORT=8643` go in `~/.hermes-intake/.env`).

## Security & least privilege

**Hermes has no tools.** The config template sets `platform_toolsets.api_server: []` and `agent.disabled_toolsets`, so even a successful prompt injection cannot act: the model can only return text, which is schema-validated and then approved by a person in Slack. The template also sets `api_max_retries: 0` and `auto_recovery_cycles: 0` so Hermes cannot exceed the 60 s budget.

Redaction, flagging and the API key sit between the Client and the model:

- **Redaction first.** The raw Transcript never leaves the submit call. Email addresses, phone numbers and street addresses are replaced with placeholders such as `[EMAIL_1]` before anything else happens, so only the Redacted Transcript reaches the model, the database and the logs.
- **Injection Flag.** A keyword check on the Redacted Transcript sets `injection_flagged`. The Intake is still processed, but the flag shows in the dashboard and in the Slack message so a reviewer looks closer. The Transcript is also wrapped in `<transcript>` tags and the prompt says it is data, never instructions.
- **API key.** `POST /intakes` requires the `X-API-Key` header to match `INTAKE_API_KEY`; if the key is unset on the server every submission is rejected. The read endpoints are open (they hold only Redacted data).
- **CORS.** Only the origins in `CORS_ORIGINS` (the dashboard) may call the API from a browser, with `GET`, `POST` and the `Content-Type` and `X-API-Key` headers.
- **No Transcript logging.** Logs carry Intake IDs, status, cost and duration, and only exception type names, never Transcript text or model output.
- **Least privilege.** Hermes has no tools (above), the output must pass the Intake Output schema, a person approves in Slack, and Slack callbacks are accepted only with a valid signature and a fresh timestamp. The container runs as a non-root user and the database is in an EU region.

## Setup wizard

[`scripts/setup_wizard.sh`](scripts/setup_wizard.sh) walks you through the steps only a human can do. It opens each URL, captures each value (secrets are read hidden and never printed) and updates `.env` in place without touching other keys.

```bash
scripts/setup_wizard.sh local    # stages 1-3: dedicated Hermes home + gateway on 8643, Groq + OpenRouter keys, OpenRouter privacy
scripts/setup_wizard.sh deploy   # stages 4-8: Slack app, Supabase, GCP VM + Caddy, Vercel dashboard, optional cloudflared tunnel
```

**Separate Hermes home.** The Intake service has its own Hermes: home `~/.hermes-intake` (Hermes picks its home from the `HERMES_HOME` environment variable, `hermes_constants.get_hermes_home`), its own `.env`, config and skills, and its gateway on `127.0.0.1:8643` (`API_SERVER_PORT` in that `.env`) as the systemd user unit `hermes-intake-gateway`. A personal Hermes in `~/.hermes` (default port 8642, unit `hermes-gateway`) is never read, written or restarted by the wizard. Use `INTAKE_HERMES_HOME` / `INTAKE_HERMES_PORT` to move it. Logs: `journalctl --user -u hermes-intake-gateway`.

The local stages are enough to start the e2e before any deploy. Re-running is safe: existing values and generated keys are reused.

## Deploy

Local: `cp .env.example .env`, fill it in, then `docker compose --profile dev up -d --build`. This starts Postgres (`db`, published on `127.0.0.1:5432` only) and the `api`, which runs `alembic upgrade head` and then uvicorn on `127.0.0.1:8000`. Check with `curl 127.0.0.1:8000/health`. Stop with `docker compose --profile dev down` (add `-v` to drop the database volume).

The image is built with uv in two stages, runs as a non-root user (uid 10001) and has a healthcheck on `/health`. `.dockerignore` keeps `.env` out of the image. The `api` service uses host networking so it can reach the Intake Hermes gateway at `127.0.0.1:8643` on the host.

Server (one VM, Hermes on the host, API in Docker, Caddy in front):

1. Install Docker, Caddy and Hermes (as a non-root service user; see the setup wizard). Copy the repo to `/opt/hermes_intake_agent` and create `.env` there.
2. Set `DATABASE_URL` to the Supabase (EU region) connection string on port **5432** (direct or session). Do **not** use the 6543 transaction pooler. Use the `postgresql+asyncpg://` scheme. Do not use the `dev` profile on the server, so no local `db` starts.
3. Hermes: run `scripts/setup_wizard.sh local` as the service user (it installs the user unit `hermes-intake-gateway`), or, for a system-wide unit, copy `deploy/hermes-intake-gateway.service` and replace `__SERVICE_USER__` and `__HOME__` with the user who installed Hermes and their home directory. Never add an `ExecStopPost` kill.
4. API: `sudo cp deploy/intake-compose.service /etc/systemd/system/ && sudo systemctl enable --now intake-compose`. The container itself has `restart: unless-stopped`, and the unit re-runs `docker compose up -d` on boot.
5. Caddy: put your free hostname in `deploy/Caddyfile`, copy it to `/etc/caddy/Caddyfile` and run `sudo systemctl reload caddy`. Caddy gets the HTTPS certificate automatically and proxies to `127.0.0.1:8000`.
6. Dashboard: deploy `dashboard/` to Vercel and add its origin to `CORS_ORIGINS`.

Syntax checks: `systemd-analyze verify deploy/*.service` and `caddy validate --config deploy/Caddyfile`.

## E2E runbook

### Automated e2e (real stack)

`tests/e2e/` drives the real compose stack (`dev` Postgres + API) and real Groq and OpenRouter calls. It is excluded from the default `uv run pytest`.

```bash
cp .env.example .env     # real keys (the wizard fills this in); no stray lines
uv run pytest -m e2e tests/e2e -s
```

- The suite builds and starts compose itself, runs `down -v` at the end (`E2E_KEEP_STACK=1` keeps it), and needs ports 5432 and 8000 free.
- It generates a throwaway `INTAKE_API_KEY` and `SLACK_SIGNING_SECRET` per run and passes them through the process environment, so `.env` is never edited.
- Mode: with the Intake Hermes gateway up at the configured `HERMES_BASE_URL` (default `127.0.0.1:8643`) it runs through Hermes; otherwise it falls back to `HERMES_ENABLED=false` (direct Groq then OpenRouter). Force one with `HERMES_ENABLED=true|false`. The first line of output says which mode ran.
- It submits the three demo Transcripts `E2E_SUBMIT_GAP` seconds apart (default 30, Groq free tier allows 8K tokens per minute), so a run takes about 2 to 3 minutes.
- It checks: valid Intake Output and primary model; Mike's Roofing has 3 Current Systems and 1 Issue (the assertion is strict, and the model may disagree: report the real counts rather than loosening it); PII placeholders with no raw values in API responses, database or API logs; `injection_flagged`; a signed Slack Approve gives `approved` and `approved_by`; and a forced Fallback (invalid Groq key, or in Hermes mode an unreachable gateway so Layer 2 answers) gives `fallback_used=true` with the OpenRouter model.

### Manual Slack click-through (on the VM)

1. Check `.env` on the VM has `SLACK_BOT_TOKEN`, `SLACK_SIGNING_SECRET`, `SLACK_CHANNEL_ID` and `INTAKE_API_KEY`, and that the Slack app's Interactivity URL is `https://<your-host>/slack/actions`. Then `docker compose up -d --build`.
2. Submit: `curl -X POST https://<your-host>/intakes -H "X-API-Key: $INTAKE_API_KEY" -H 'Content-Type: application/json' -d "$(jq -n --rawfile t transcripts/mikes_roofing.txt '{client_name:"Mike'"'"'s Roofing",transcript:$t}')"`.
3. Within about a minute the message appears in the Slack channel with Approve and Request changes buttons.
4. Click Approve. The message should update to show who approved, and `GET /intakes/<id>` (or the dashboard) shows `approved` with `approved_by` set.
5. Click again: nothing changes (a decision is final). If the click shows a Slack error, check the signing secret and that Caddy proxies `/slack/actions`.
