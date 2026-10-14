# Hermes Agent: research notes (for tickets #5 Hermes adapter, #9/#10 deploy + wizard)

Retrieved 2026-10-14. Latest release is **v0.22.0** (2026-10-14). `main` is at commit `0e427d78`.
Written before the build; the "Gotchas found in this build" section at the end records what changed. Paths below say `~/.hermes` and port 8642 as the Hermes docs do; this project uses its own home `~/.hermes-intake` and port 8643 (see the gotchas).
Sources: the repo docs under `website/docs/` and the source code. Short names used below:
- [API] https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/features/api-server.md
- [PI] .../website/docs/developer-guide/programmatic-integration.md (section "Terminal run status")
- [FB] .../website/docs/user-guide/features/fallback-providers.md
- [CFG] .../website/docs/user-guide/configuration.md
- [PROV] .../website/docs/integrations/providers.md ("Cookbook: Together AI, Groq, Perplexity")
- [SK] .../website/docs/user-guide/features/skills.md, plus [CLI] .../user-guide/cli.md ("Persistent auto-load")
- [INST] .../website/docs/getting-started/installation.md; [MSG] .../user-guide/messaging/index.md ("Service Management")
- [SRC-RUNS] gateway/platforms/api_server_runs.py; [SRC-API] gateway/platforms/api_server.py; [SRC-TOOLS] hermes_cli/tools_config.py `_get_platform_tools`, model_tools.py `_select_tool_names`

## Install [INST]
```bash
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash   # Linux/macOS/WSL2
export PATH="$HOME/.local/bin:$PATH"   # launcher is ~/.local/bin/hermes; code is ~/.hermes/hermes-agent/
hermes doctor
```
- **Python:** the installer brings its own pinned uv and Python (via "PM"). "Current first-party installations run on **Python 3.14**". `pyproject.toml` allows `>=3.11,<3.15`. You do not need to install Python yourself.
- Needs git, curl, tar and sha256 tools. On minimal Debian/Ubuntu it also needs `libatomic1`, which the installer tries to install with `sudo -n`.
- `--non-interactive` skips the setup prompts. Do this in the wizard, then write the config files yourself.
- Install as the service user (not root). User data lives in `~/.hermes/` (`config.yaml`, `.env`, `skills/`, `logs/`).

## Enabling the API server [API]
Put these in `$HERMES_HOME/.env` (here `~/.hermes-intake/.env`; secrets go here, everything else in config.yaml):
```bash
API_SERVER_ENABLED=true
API_SERVER_KEY=<long random>        # required; connect() refuses to start without it [SRC-API L1560]
# API_SERVER_HOST=127.0.0.1 (default)   API_SERVER_PORT=8642 (default)
GROQ_API_KEY=...
OPENROUTER_API_KEY=...
```
Start it with `hermes gateway`. The log line is `[API Server] API server listening on http://127.0.0.1:8642`.
- **Auth:** `Authorization: Bearer <API_SERVER_KEY>` on every endpoint except `/health`.
- A bad key gets **401** `{"error":{"message":"Invalid gateway API key (API_SERVER_KEY)","type":"gateway_auth_error","code":"gateway_auth_failed"}}` [SRC-API L1553].
- Other errors use the OpenAI envelope `{"error":{"message","type","param","code"}}`.
- `max_concurrent_runs` defaults to 10. Past that, new runs get **429** `Too many concurrent runs (max N)`.
- **Health:** `GET /health` (also `/v1/health`) needs no auth and returns `{"status":"ok","platform":"hermes-agent","version":...}` [SRC-API L2427]. `GET /health/detailed` needs auth.

## Runs API: exact shapes [API] [PI] [SRC-RUNS]
**`POST /v1/runs`** (the docs say 202):
```json
{ "input": "<user message string>",            // required; a list of messages is allowed (the last item's content is used)
  "instructions": "<system prompt text>",      // optional -> agent ephemeral_system_prompt, LAYERED ON TOP of Hermes core prompt
  "session_id": "intake-<uuid>",               // optional; omit => session_id = run_id (fresh session)
  "model": "...", "provider": "...",           // optional per-request override; /v1/runs ALWAYS honours them
  "conversation_history": [...], "previous_response_id": "..." }   // optional, not needed
```
- Optional header `Idempotency-Key: <1-255 visible ASCII>`. A replay returns the same `run_id` with `Idempotency-Replayed: true`.
- **Response 202:** `{"run_id":"run_<hex>","status":"started","replayed":false}`. The doc example omits `replayed`.
- **400** for a missing `input` (`"Missing 'input' field"`) or invalid JSON.
- **There is no `skill` / `skills` field on /v1/runs.** The source reads only input, instructions, conversation_history, previous_response_id, session_id, model, provider, model_options, metadata and author.

**`GET /v1/runs/{run_id}`** (poll this):
```json
{ "object":"hermes.run", "run_id":"run_abc123", "status":"completed", "session_id":"...",
  "model":"hermes-agent",                       // ECHO of the request; do NOT use for model_used
  "output":"<final assistant text>",            // final answer (string)
  "usage":{"input_tokens":50,"output_tokens":200,"total_tokens":250,"cache_read_tokens":40,"cache_write_tokens":0},
  "runtime":{"provider":"openai","model":"gpt-5","route_source":"global"},   // provider/model that ACTUALLY served
  "completed":true, "partial":false, "interrupted":false,
  "created_at":..., "updated_at":..., "last_event":"run.completed" }
```
- "On a completed run, `runtime` is the provider/model pair that actually served the turn — after a fallback provider switch it names the fallback pair" [API].
  - `runtime` is set **only on completed** runs. Failed runs get `error` and no `runtime` or `usage` [SRC-RUNS `_finish`].
  - If the request named a model or provider, `runtime.requested = {provider, model}` is added.
- **Status values:** `queued` → `running` → terminal: `completed` | `failed` | `cancelled` | `interrupted`. Other values: `stopping`, and `waiting_for_approval` (tools only).
- A **failed** run carries `error` (a redacted string), `completed:false`, and sometimes `partial`, `turn_exit_reason`, or `output` with fallback text. An unknown id returns 404 `run_not_found`.
- Terminal statuses are "retained briefly" (TTL not documented), so poll promptly. `GET /v1/runs/{id}/events` is an SSE stream (`run.completed` carries the same `usage`/`runtime`). It is optional: **polling is sufficient**, and SSE isn't required.
- `POST /v1/runs/{id}/stop` returns `{"status":"stopping"}`. Use it after our 60 s timeout so we don't leak a running agent.
- Suggested adapter loop: POST → poll GET every 1 s until a terminal status, with the whole thing wrapped in `asyncio.timeout(60)`. On timeout, call stop and go to Layer 2.
  - `model_used = runtime.model`. `fallback_used = runtime.model != primary_model_id`.
- **Not confirmed:** the value of `runtime.provider` for the named custom Groq provider. `hermes_cli/runtime_provider.py` suggests named custom entries resolve to `"custom"`, and OpenRouter shows as `"openrouter"`. Decide "fallback used" from **`runtime.model`**, not from the provider.

## Invoking the `client-intake` skill
Hermes skills normally load through (a) `/skill-name` slash commands, or (b) the model calling the `skills_list`/`skill_view` tools.
- (a) is expanded by the messaging gateway (`gateway/run_inbound.py`), **not** by api_server. A `/client-intake ...` input to /v1/runs would most likely reach the model as literal text (inferred from the source, not tested).
- (b) is impossible with all toolsets disabled.

Options, in order of preference:
1. **`skills.auto_load: [client-intake]`** in config.yaml. "To have the same skills active at the start of every new session — CLI, TUI, gateway, cron and **API sessions** alike" [CLI]. Each run without a `session_id` is a new session, so the skill is loaded into the system prompt every time. *Check with one real run (spec's "short check").*
2. Fallback (the spec's plan B): send the SKILL.md body as `"instructions"` on every run. The docs confirm it is layered on Hermes' core prompt [API "System Prompt Handling"].

In both cases, put the transcript in `"input"` wrapped in `<transcript>` tags. Hermes passes no `response_format`, so validate the JSON from `output` ourselves.
- Token usage IS returned (`usage.input_tokens`/`output_tokens`), so a tokenizer estimate is not needed.
- Hermes' core prompt (SOUL.md and so on) adds input tokens, and that counts toward Groq's 8K TPM. Measure `usage.input_tokens` on the first run.

**SKILL.md format and install path** [SK]: `~/.hermes/skills/<category?>/client-intake/SKILL.md`. A flat `~/.hermes/skills/client-intake/SKILL.md` also works; the directory layout shows both.
```markdown
---
name: client-intake
description: Turn a redacted client call transcript into an Intake Output JSON.
version: 1.0.0
metadata:
  hermes:
    category: agency
---
# Client Intake
## When to Use ...   ## Procedure ...   ## Pitfalls ...   ## Verification ...
```
Check it with `curl -H "Authorization: Bearer $KEY" http://127.0.0.1:8643/v1/skills`, which should return `{"object":"list","data":[{name,description,category}...]}`. On Hermes 0.22.0 this endpoint returns 500 (see the gotchas), so check that `SKILL.md` exists on disk instead.

## config.yaml (`$HERMES_HOME/config.yaml`; the template is `app/agents/assets/hermes-config.yaml.template`)
```yaml
providers:                       # named custom OpenAI-compatible provider [PROV Groq recipe]
  groq:
    api: https://api.groq.com/openai/v1
    key_env: GROQ_API_KEY
    # request_timeout_seconds: 45   # optional provider-wide timeout [CFG "Provider Timeouts"]
model:
  provider: custom:groq
  default: openai/gpt-oss-120b
fallback_providers:              # top-level list, tried in order [FB]
  - provider: openrouter         # built-in provider, needs OPENROUTER_API_KEY in ~/.hermes/.env
    model: nvidia/nemotron-3-super-120b-a12b:free
platform_toolsets:
  api_server: []                 # explicit EMPTY list = no toolsets for the API server [SRC-TOOLS]
agent:
  disabled_toolsets: [terminal, file, web, browser, memory, skills, code_execution, delegation, cronjob, todo, vision, image_gen, tts, session_search, clarify, search, computer_use, connections]  # names from reference/toolsets-reference.md; belt and braces, applied LAST
  api_max_retries: 0             # default 3; 0 = first transient error hands off to fallback immediately [CFG]
  auto_recovery_cycles: 0        # default 5 (15/30/60/60/60 s waits) would blow our 60 s budget [CFG]
skills:
  auto_load: [client-intake]
gateway:
  api_server:
    max_concurrent_runs: 10
model_overrides:                 # added in this build, see the gotchas
  _default:
    supports_reasoning: false
```
- An explicit empty list disables everything. `_get_platform_tools`: "An explicit EMPTY list means none". `_select_tool_names` treats `[]` (not `None`) as "no tools".
- Verify with `GET /v1/toolsets`: every entry should show `"enabled": false`.
- The legacy `custom_providers:` list still works, but the `providers:` dict is the current format.

## When fallback (Layer 1) triggers [FB "When Fallback Triggers"]
- **HTTP 429** (after the retries run out), **HTTP 500/502/503** (after the retries run out). Retries = `agent.api_max_retries`, default 3.
- A rate limit carrying `Retry-After` is waited out, capped at 600 s per retry. That is another reason for `api_max_retries: 0`.
- **401/403:** immediately. **404:** immediately.
- **Invalid responses:** malformed or empty replies, "repeatedly". A 200 whose only text is a router connect-timeout message also counts.
- Fallback is **per turn**, and it fires at most once per turn. The next run starts on the primary again.
- If the fallback also fails, the run ends `failed` with `error`.
- There are no env vars for the fallback chain. It is configured in config.yaml only.
- **A slow but alive primary does NOT trigger fallback.** Only the stale-call detectors do (90 s non-stream / 180 s stream defaults). Our 60 s Layer-2 timeout covers that case.

## systemd [MSG "Service Management"]
```bash
hermes gateway install                 # user unit "hermes-gateway"; then: hermes gateway start
sudo loginctl enable-linger $USER      # survive logout/reboot without root restarts (recommended for headless VM)
# or system-wide boot unit that still runs as your user:
sudo hermes gateway install --system && sudo hermes gateway start --system
journalctl --user -u hermes-gateway -f # (system unit: journalctl -u hermes-gateway -f)
```
- The generated unit already has `Restart=always`, `KillMode=mixed` and `KillSignal=SIGTERM`. **Do not** add an `ExecStopPost=kill -9` drop-in (it causes a restart loop).
- Prefer `hermes gateway restart`, which drains in-flight runs.
- After editing config.yaml or .env, run `hermes gateway restart`.

## Open items to verify on the VM (could not confirm from the docs)
1. Whether `skills.auto_load` really injects into api_server runs, and whether a `/client-intake` prefix is ignored. (The service does not depend on it: it always sends the SKILL.md body as `instructions`, plan B above.)
2. The exact `runtime.provider` string for `custom:groq`.
3. Whether `usage` counts include the failed primary attempt after a fallback (probably only the successful calls).
4. The retention TTL of terminal run status.
5. Hermes core-prompt token overhead against the Groq 8K TPM free limit.

## Gotchas found in this build
- **Groq gpt-oss rejects `reasoning_effort`.** Hermes sends a default `reasoning_effort` on custom endpoints at `api.groq.com`, and Groq answers HTTP 400, so every run fell back. Fix: `model_overrides: {_default: {supports_reasoning: false}}` in `config.yaml` (it is in the template).
- **`GET /v1/skills` returns 500 on Hermes 0.22.0.** Do not treat it as a failed setup. The wizard accepts a 500 there when `$HERMES_HOME/skills/client-intake/SKILL.md` exists, and the service never calls the endpoint.
- **Isolate with `HERMES_HOME`, not `--profile`.** `--profile` lives under `~/.hermes/profiles`, so it still shares the personal home. The Intake service uses `HERMES_HOME=~/.hermes-intake` and gateway port 8643 (`API_SERVER_PORT` in that home's `.env`), run as the systemd user unit `hermes-intake-gateway` (`deploy/hermes-intake-gateway.service`).
- **The default retry settings allow 600 s waits.** `api_max_retries` (default 3) and `auto_recovery_cycles` (default 5) can sleep for minutes, past the 60 s budget. The template sets both to 0 (ADR 0001).
- **A personal `~/.hermes` can be on the same host.** It has its own config, `.env` and port 8642. The wizard must never replace, read or restart it, and refuses `INTAKE_HERMES_HOME` when it resolves to `~/.hermes`.
- **No documented endpoint names the gateway's configured model.** The run's `model` field only echoes the request (`hermes-agent`). The e2e preflight (`tests/e2e/preflight.py`) therefore reads `$INTAKE_HERMES_HOME/config.yaml` (default `~/.hermes-intake`) and `GET /v1/toolsets`.
