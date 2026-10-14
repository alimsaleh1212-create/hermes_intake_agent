"""The ``IntakeAgent`` contract: Redacted Transcript in, Intake Output and usage out."""

import time
from dataclasses import dataclass
from typing import Protocol

from app.core.errors import IntakeAgentError
from app.schemas.intake import IntakeOutput

__all__ = [
    "AgentResult",
    "AgentUsage",
    "IntakeAgent",
    "IntakeAgentError",
    "elapsed_ms",
]


def elapsed_ms(started: float) -> int:
    """Milliseconds since ``started`` (a ``time.monotonic()`` reading)."""
    return int((time.monotonic() - started) * 1000)


@dataclass(frozen=True)
class AgentUsage:
    """How an Intake Output was produced and what it cost.

    Attributes:
        model_used: The model that actually answered (from Hermes' ``runtime``
            field or the provider that ``LLMClient`` ended on).
        fallback_used: True when the secondary model produced the output.
        tokens_in: Prompt tokens.
        tokens_out: Completion tokens.
        duration_ms: Wall-clock time of the whole agent call.
        cost_usd: Actual cost (0 on free tiers).
        est_cost_usd: Estimated Cost at the providers' published paid prices.
        fallback_reason: Short code for why the primary was left (``timeout``,
            ``invalid_output``, ``provider 429`` ...). Never Transcript text.
    """

    model_used: str
    fallback_used: bool
    tokens_in: int
    tokens_out: int
    duration_ms: int
    cost_usd: float = 0.0
    est_cost_usd: float = 0.0
    fallback_reason: str | None = None


@dataclass(frozen=True)
class AgentResult:
    """A validated Intake Output and its usage."""

    output: IntakeOutput
    usage: AgentUsage


class IntakeAgent(Protocol):
    """Produces an Intake Output from a Redacted Transcript."""

    async def run(self, transcript_redacted: str) -> AgentResult:
        """Run the Intake.

        Args:
            transcript_redacted: The Redacted Transcript (never the raw one).

        Returns:
            The validated Intake Output with usage.

        Raises:
            IntakeAgentError: Every model failed.
        """
        ...
