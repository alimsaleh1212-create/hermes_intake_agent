"""Estimated Cost: tokens priced at the providers' published paid rates."""

from collections.abc import Mapping

from app.core.config import ModelPrice


def estimate_cost_usd(
    prices: Mapping[str, ModelPrice], model: str, tokens_in: int, tokens_out: int
) -> float:
    """Return what these tokens would cost at paid rates (0.0 for unknown models).

    Args:
        prices: Per-model prices in USD per million tokens.
        model: The model ID that answered.
        tokens_in: Prompt tokens.
        tokens_out: Completion tokens (reasoning tokens included).
    """
    price = prices.get(model)
    if price is None:
        return 0.0
    return (
        tokens_in * price.input_per_mtok + tokens_out * price.output_per_mtok
    ) / 1_000_000
