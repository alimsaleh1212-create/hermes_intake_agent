"""Pydantic schemas: the Intake Output and the ``/intakes`` request and responses.

These are shared contracts. The Intake Output schema is what the agent must
return (and what strict ``json_schema`` structured output is built from); the
response schemas are mirrored by the dashboard's API types.
"""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

Verdict = Literal["yes", "partial", "no"]


class _StrictModel(BaseModel):
    """Base for Intake Output parts: unknown keys are rejected.

    ``extra="forbid"`` makes the generated JSON schema carry
    ``additionalProperties: false``, which strict structured output requires.
    """

    model_config = ConfigDict(extra="forbid")


class ArchitectureComponent(_StrictModel):
    """One proposed system in the Architecture Doc."""

    name: str
    purpose: str


class AccessItem(_StrictModel):
    """One entry of the Access Checklist: what access the agency needs, where."""

    system: str
    access: str


class FeasibilityVerdict(_StrictModel):
    """A judgement on one integration. A verdict of "no" is an Issue."""

    integration: str
    verdict: Verdict
    reason: str


class IntakeOutput(_StrictModel):
    """What an Intake produces."""

    current_systems: list[str]
    architecture: list[ArchitectureComponent]
    access_checklist: list[AccessItem]
    feasibility: list[FeasibilityVerdict]


class IntakeStatus(StrEnum):
    """Status lifecycle of an Intake.

    ``processing`` -> ``awaiting_approval`` -> ``approved`` | ``changes_requested``.
    Any agent failure after both models were tried -> ``failed``.
    """

    PROCESSING = "processing"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"
    FAILED = "failed"


class Decision(StrEnum):
    """An Approval decision made in Slack."""

    APPROVE = "approve"
    REQUEST_CHANGES = "request_changes"


DECISION_STATUS = {
    Decision.APPROVE: IntakeStatus.APPROVED,
    Decision.REQUEST_CHANGES: IntakeStatus.CHANGES_REQUESTED,
}
"""The Intake status each Slack ``Decision`` leads to."""

DECISION_LABEL = {
    Decision.APPROVE: "Approved",
    Decision.REQUEST_CHANGES: "Changes requested",
}
"""Human wording of each ``Decision``, used in the Slack message."""

DECISION_BY_STATUS = {status: decision for decision, status in DECISION_STATUS.items()}
"""Inverse of ``DECISION_STATUS`` for decided Intakes."""


class IntakeCreate(BaseModel):
    """Body of ``POST /intakes``."""

    client_name: NonEmptyStr
    transcript: NonEmptyStr


class IntakeSummary(BaseModel):
    """One row of ``GET /intakes``: everything except the documents."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    client_name: str
    status: IntakeStatus
    error: str | None = None
    model_used: str | None = None
    fallback_used: bool = False
    fallback_reason: str | None = None
    injection_flagged: bool = False
    tokens_in: int | None = None
    tokens_out: int | None = None
    cost_usd: float | None = None
    est_cost_usd: float | None = None
    duration_ms: int | None = None
    approved_by: str | None = None
    decided_at: datetime | None = None
    created_at: datetime


class IntakeDetail(IntakeSummary):
    """``GET /intakes/{id}``: the full Intake, including Intake Output and Transcript.

    This is also the read model the repository returns to the service.
    """

    transcript_redacted: str
    transcript_hash: str
    output: IntakeOutput | None = None
    slack_ts: str | None = None
