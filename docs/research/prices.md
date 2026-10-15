# Published paid prices (for `est_cost_usd`). Retrieved 2026-10-14

| Model | Input $/1M | Output $/1M | Source |
|---|---|---|---|
| Groq `openai/gpt-oss-120b` | **0.15** | **0.60** | https://console.groq.com/docs/model/openai/gpt-oss-120b and https://console.groq.com/docs/models (both list "$0.15 input / $0.60 output") |
| OpenRouter `nvidia/nemotron-3-super-120b-a12b` (paid variant; the price of the `:free` sibling) | **0.08** | **0.45** | https://openrouter.ai/api/v1/models (`pricing.prompt="0.00000008"`, `pricing.completion="0.00000045"`, per token) |

## Details
- **Groq gpt-oss-120b** also lists cached input at **$0.075/1M**. That isn't needed (we don't use the cache). Context is 131,072 and max output is 65,536.
  - groq.com/pricing did not render model prices for the fetcher. The two console docs pages above are the primary source.
- **Nemotron 3 Super (paid)** has per-endpoint prices from https://openrouter.ai/api/v1/models/nvidia/nemotron-3-super-120b-a12b/endpoints:
  - DekaLLM (fp8): $0.08 / $0.45
  - DeepInfra (bf16): $0.085 / $0.40
  - The model-level price on OpenRouter (the "from" price) is **$0.08 in / $0.45 out**. Use this value, and note in the UI that it is the OpenRouter listed price.
  - The `:free` variant is served only by provider "Nvidia" at $0 / $0, with a 262,144 context.
- NVIDIA's own build.nvidia.com price was not needed, because a paid OpenRouter variant exists.

## Config-ready price table (USD per token)
```python
PRICES = {
    "openai/gpt-oss-120b":                    {"in": 0.15e-6, "out": 0.60e-6},   # Groq, 2026-10-14
    "nvidia/nemotron-3-super-120b-a12b:free": {"in": 0.08e-6, "out": 0.45e-6},   # OpenRouter paid variant, 2026-10-14
}
# est_cost_usd = tokens_in*in + tokens_out*out ; cost_usd = 0 on free tiers
```
Caveats:
- Reasoning tokens (gpt-oss and Nemotron both reason) are billed as output and are included in `completion_tokens`.
- OpenRouter's `usage.cost` is the actual charge, which is 0 on `:free`.
