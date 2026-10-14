"""``FakeAgent``: a deterministic ``IntakeAgent`` for tests and the walking skeleton."""

from app.agents.base import AgentResult, AgentUsage, IntakeAgentError
from app.schemas.intake import (
    AccessItem,
    ArchitectureComponent,
    FeasibilityVerdict,
    IntakeOutput,
)

FAKE_MODEL = "fake-model"

# Mike's Roofing-shaped output: 3 Current Systems, 1 Issue.
MIKES_ROOFING_OUTPUT = IntakeOutput(
    current_systems=["WordPress", "Google Ads", "Jobber"],
    architecture=[
        ArchitectureComponent(name="Landing page", purpose="Convert ad clicks"),
        ArchitectureComponent(name="GoHighLevel CRM", purpose="Track every lead"),
        ArchitectureComponent(name="Instant SMS reply", purpose="Answer new leads"),
        ArchitectureComponent(
            name="Missed-call text-back", purpose="Recover missed calls"
        ),
        ArchitectureComponent(name="Weekly report", purpose="Show lead volume"),
    ],
    access_checklist=[
        AccessItem(system="Google Ads", access="Admin access"),
        AccessItem(system="WordPress", access="Admin login"),
        AccessItem(system="Jobber", access="API key"),
        AccessItem(system="Domain registrar", access="DNS access"),
    ],
    feasibility=[
        FeasibilityVerdict(
            integration="Google Ads to GoHighLevel",
            verdict="yes",
            reason="Native lead form integration.",
        ),
        FeasibilityVerdict(
            integration="Jobber to GoHighLevel",
            verdict="partial",
            reason="Needs Zapier; no native connector.",
        ),
        FeasibilityVerdict(
            integration="Forwarding the personal cell",
            verdict="no",
            reason="Use a tracking number instead.",
        ),
    ],
)

FAKE_USAGE = AgentUsage(
    model_used=FAKE_MODEL,
    fallback_used=False,
    tokens_in=1200,
    tokens_out=400,
    duration_ms=5,
    cost_usd=0.0,
    est_cost_usd=0.0005,
)


class FakeAgent:
    """Returns a fixed valid Intake Output, or raises a configured error.

    Args:
        result: What ``run`` returns. Defaults to Mike's Roofing-shaped output.
        error: If set, ``run`` raises it instead (e.g. to test ``failed``).
    """

    def __init__(
        self,
        result: AgentResult | None = None,
        error: IntakeAgentError | None = None,
    ) -> None:
        self.result = result or AgentResult(
            output=MIKES_ROOFING_OUTPUT, usage=FAKE_USAGE
        )
        self.error = error
        self.calls: list[str] = []

    async def run(self, transcript_redacted: str) -> AgentResult:
        """Record the call and return the fixed result (or raise)."""
        self.calls.append(transcript_redacted)
        if self.error is not None:
            raise self.error
        return self.result
