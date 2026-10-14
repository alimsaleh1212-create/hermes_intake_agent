# Two-layer LLM fallback: Hermes-native, plus a direct call to the secondary

Fallback swaps the **LLM**, not the agent. Hermes' own `fallback_providers` moves a run from the primary (Groq `openai/gpt-oss-120b`) to the secondary (OpenRouter `nvidia/nemotron-3-super-120b-a12b:free`) on 401/403/404, on 429/5xx, and on empty replies. Hermes doesn't fall back on a timeout, can't see JSON that fails our Pydantic schema, and is no help when its own gateway is down, returns an HTTP error or ends a run as failed. In those cases (Layer 2) the service calls the secondary LLM directly through `LLMClient` with a strict `json_schema`, bypassing Hermes. With `HERMES_ENABLED=false`, the same `LLMClient` runs primary then secondary by itself, which is the plan's escape hatch if Hermes setup stalls.

## Considered Options

- **Agent-level fallback** (a second agent behind the first): rejected. What fails is a model or provider, not the agent, and duplicating the agent hides which model answered.
- **Hermes-only fallback**: rejected. It doesn't cover timeouts, schema-invalid output, gateway errors or an unreachable gateway.

## Consequences

- A timeout or invalid JSON goes straight to the secondary, with no retry on the primary. The Hermes config sets `api_max_retries: 0` and `auto_recovery_cycles: 0`, so a 429 or 5xx moves to Hermes' native fallback at once and each run stays inside the 60 s budget (Hermes' default waits can last 600 s). Retrying a hung provider would cost another 60 seconds on camera.
- Layer 2 also covers gateway HTTP errors and failed runs, not only an unreachable gateway.
- `model_used` and `fallback_used` come from the gateway's Runs API (`runtime` field), because `/v1/chat/completions` only echoes the requested model.
- Groq's free tier allows 8K tokens per minute, so Intakes sent close together can trigger a fallback nobody asked for. The e2e test spaces its runs out.
