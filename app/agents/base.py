"""The ``IntakeAgent`` contract: Redacted Transcript in, Intake Output and usage out."""

from dataclasses import dataclass
from typing import Protocol

from app.schemas.intake import IntakeOutput


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
    """

    model_used: str
    fallback_used: bool
    tokens_in: int
    tokens_out: int
    duration_ms: int
    cost_usd: float = 0.0
    est_cost_usd: float = 0.0


@dataclass(frozen=True)
class AgentResult:
    """A validated Intake Output and its usage."""

    output: IntakeOutput
    usage: AgentUsage


class IntakeAgentError(Exception):
    """Raised when no model could produce a valid Intake Output.

    The service turns this into a ``failed`` Intake with ``str(error)`` stored, so
    the message must never contain Transcript text.
    """


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
