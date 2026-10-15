# Coding standards

The judgement rules for this repo. Black, ruff (including Google docstrings and type annotations) and `tests/test_layering.py` enforce the mechanical ones; this file covers what they cannot check. It is applied at review. Vocabulary follows `GLOSSARY.md`.

## Privacy and logging

- Never log Transcript text (raw or redacted), model prompts or model output. Log only the Intake ID, status, cost, duration and errors.
- Secrets live only in the uncommitted `.env` and are `SecretStr` in settings. Never print or log them, and never read `.env` values into output, tests or docs.
- Add every new setting to `app/core/config.py` and to `.env.example`.

## Error strings

- An error string stored on an Intake (`error`, `fallback_reason`) or written to a log must not contain Transcript text, prompt text or model output. Provider and gateway bodies can echo prompts, so name the model and a category (`timeout`, `invalid_output`, `provider 429`), or a status and message from the gateway's own `error` field.
- Exception messages that wrap validation errors may quote input. Log the exception type, or a fixed category, instead.

## Layering intent

- The path is route, then service, then repository, then database. Routes call services only. Services hold the use cases and never write SQL. Only `app/db/` knows SQLAlchemy, and only the repository opens sessions.
- The reason: each layer can be swapped or faked at one seam, and a privacy or transaction rule has one place to live. `tests/test_layering.py` checks imports; it cannot check that logic sits in the right layer, so reviewers do.

## Dependency injection

- Collaborators come from `app/deps.py` providers, and each provider calls one factory per concern (`app/<concern>/factory.py`). `deps.py` imports only factories (which re-export their concern's types), settings and schemas, and never constructs the repository or the service.
- To change or add a collaborator, change that concern's factory. Do not edit `deps.py` or `main.py` to do it.
- The reason: tests swap a collaborator with `app.dependency_overrides`, and parallel work on different concerns does not collide in shared wiring files.

## Lifespan ownership

- The lifespan creates the async engine, the shared httpx client and the Slack client once, and closes them at shutdown. Nothing else creates or closes these.
- Request code and agents receive the shared client through `deps.py`. They do not build their own clients or sessions.

## Test seams

- Test first, at the agreed seams: the HTTP API, `IntakeAgent`, the guardrail functions, the dashboard fetch boundary and e2e. Assert behavior through those interfaces, not private functions or internal collaborators.
- API tests use the real Postgres from testcontainers (Docker must be running). Agent tests fake the transport (`httpx.MockTransport`), not the agent's collaborators.
- E2E tests are marked `e2e`, are excluded by default, and hit real models. Run them only on purpose.

## Git

- Conventional Commits (`feat:`, `fix:`, `docs:`, `chore:`, `ci:` and so on), one concern per commit.
