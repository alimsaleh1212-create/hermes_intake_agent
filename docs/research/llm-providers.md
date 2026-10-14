# Groq + OpenRouter OpenAI-compatible chat completions (ticket #4 LLMClient). Retrieved 2026-10-14

| | Groq | OpenRouter |
|---|---|---|
| URL | `POST https://api.groq.com/openai/v1/chat/completions` | `POST https://openrouter.ai/api/v1/chat/completions` |
| Auth | `Authorization: Bearer $GROQ_API_KEY` | `Authorization: Bearer $OPENROUTER_API_KEY` |
| Model | `openai/gpt-oss-120b` | `nvidia/nemotron-3-super-120b-a12b:free` |

## Strict structured output: same request shape on both
```json
{ "model": "...", "messages": [{"role":"system","content":"..."},{"role":"user","content":"<transcript>...</transcript>"}],
  "response_format": { "type": "json_schema",
    "json_schema": { "name": "intake_output", "strict": true,
      "schema": { "type":"object", "additionalProperties": false,
        "required": ["current_systems","architecture","access_checklist","feasibility"],
        "properties": {
          "current_systems": {"type":"array","items":{"type":"string"}},
          "architecture": {"type":"array","items":{"type":"object","additionalProperties":false,
              "required":["name","purpose"],"properties":{"name":{"type":"string"},"purpose":{"type":"string"}}}},
          "access_checklist": {"type":"array","items":{"type":"object","additionalProperties":false,
              "required":["system","access"],"properties":{"system":{"type":"string"},"access":{"type":"string"}}}},
          "feasibility": {"type":"array","items":{"type":"object","additionalProperties":false,
              "required":["integration","verdict","reason"],"properties":{"integration":{"type":"string"},
              "verdict":{"type":"string","enum":["yes","partial","no"]},"reason":{"type":"string"}}}} } } } },
  "stream": false }
```
(Field names follow spec #1. Adjust them to the Pydantic model from the contracts ticket.)

**Groq** (https://console.groq.com/docs/structured-outputs):
- Strict mode (`strict: true`) is supported on `openai/gpt-oss-20b`, **`openai/gpt-oss-120b`** and `qwen/qwen3.8-27b`.
- Strict-mode rules:
  - "All schema properties must be marked as `required`". Optional fields are not supported; use `["string","null"]` and still list the field as required.
  - Every object needs **`additionalProperties: false`**.
  - Supported types: string, number, boolean, integer, object, array, enum, `anyOf`, plus `$defs`/`$ref`.
- **"Streaming and tool use are not currently supported with Structured Outputs"**, so send `stream: false`.
- Strict uses constrained decoding. Best-effort mode returns **400** "Generated JSON does not match the expected schema". Treat any 400 as a failure and move to the next provider.

**OpenRouter** (https://openrouter.ai/docs/guides/features/structured-outputs):
- The request shape is the same. Enforcement depends on the provider.
- Add `"provider": {"require_parameters": true}` so routing only uses endpoints that support `response_format`.
- `nvidia/nemotron-3-super-120b-a12b:free` lists `response_format` and `structured_outputs` in `supported_parameters` (checked via `/api/v1/models/.../endpoints`).
- Still validate the reply with Pydantic, because "exact compliance isn't guaranteed on every endpoint".

## `usage` object
- **Groq** (https://console.groq.com/docs/api-reference):
  - `{"prompt_tokens","completion_tokens","total_tokens","queue_time","prompt_time","completion_time","total_time"}`
  - Also `x_groq: {"id": "req_..."}`.
  - *Unconfirmed:* `prompt_tokens_details` / `completion_tokens_details` may appear. Rely only on prompt and completion tokens.
- **OpenRouter** (https://openrouter.ai/docs/api/reference/overview):
  - `prompt_tokens`, `completion_tokens`, `total_tokens`
  - `cost` (credits; 0 on :free), `is_byok`
  - `prompt_tokens_details{cached_tokens,cache_write_tokens,audio_tokens,video_tokens}`
  - `completion_tokens_details{reasoning_tokens,...}`
  - `cost_details{upstream_inference_cost,...}`
- Map `tokens_in = prompt_tokens` and `tokens_out = completion_tokens` (reasoning is included in completion).

## Errors
**Groq** (https://console.groq.com/docs/errors):
- Shape: `{"error":{"message","type","code"?}}`.
- **Invalid key, observed live 2026-10-14:** HTTP **401** `{"error":{"message":"Invalid API Key","type":"invalid_request_error","code":"invalid_api_key"}}`
- Other codes: 400, 403, 404, 413, 422, 498 (flex capacity), 500/502/503.
- **429** for rate limits. `retry-after` is present only on 429. The `x-ratelimit-{limit,remaining,reset}-{requests,tokens}` headers are always sent (https://console.groq.com/docs/rate-limits).
- Limits table for gpt-oss-120b: 30 RPM, 1K RPD, **8K TPM**, 200K TPD. The page labels these as base limits, so the plan isn't clear.

**OpenRouter** (https://openrouter.ai/docs/api/reference/errors-and-debugging):
- Shape: `{"error":{"code":<int>,"message":"...","metadata":{...}?}}`.
- **Invalid key, observed live:** HTTP **401** `{"error":{"message":"User not found.","code":401}}`
- 402 (no credits), 403 (moderation/guardrail), 408 timeout, **429** (`metadata.error_type:"rate_limit_exceeded"`; may carry `Retry-After`; also `X-RateLimit-*` on platform limits), 502 (model down), 503 (no provider meets the routing requirements).
- **A 200 can carry an error.** A non-streaming body may contain only `{"error":...}` and no `choices`. Always check for `"error" in body` / missing `choices`.
- Free limits (https://openrouter.ai/docs/api/reference/limits): 20 RPM. 50 requests/day, or 1000/day once ≥$10 of credits has been bought.
- **Data-policy 404:** a free model whose only endpoint is filtered out by your privacy settings returns **404 "No endpoints found matching your data policy"**.
  - Source: third-party reports (e.g. https://www.truefoundry.com/blog/openrouter-free-models-whats-actually-free-and-what-it-costs-you). The official docs fetched did not quote the message.
  - Fix: at https://openrouter.ai/settings/privacy, allow free endpoints that may train on or log inputs. Wizard step.
  - Don't send `provider.data_collection:"deny"`; it would filter out the `:free` endpoint.

## OpenRouter recommended headers (optional, for app attribution)
`HTTP-Referer: <site url>` and `X-OpenRouter-Title: <app name>` (`X-Title` also accepted). Optionally `X-OpenRouter-Categories`.

## Mapping to the spec's fallback triggers (Layer 2 / direct mode)
Move to the next provider on any of these:
- httpx timeout or connect error
- status 401/403/404/408/429/5xx
- 400 (schema / unsupported parameter)
- a body with `error` or no `choices`
- empty `choices[0].message.content`
- `json.loads` or Pydantic validation failure

Do not retry within a provider.
