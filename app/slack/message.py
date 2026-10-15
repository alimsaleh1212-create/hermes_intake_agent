"""Builds the Block Kit body of the Slack Approval message.

The message carries what a reviewer needs to Approve or Request changes
without opening the dashboard: Issues and partial verdicts with their reasons
first, then Current Systems, the Architecture Doc and the Access Checklist.
Model text is escaped so it can never mention a channel or hide a link.
"""

from collections.abc import Sequence
from typing import Any

from app.schemas.intake import IntakeDetail, IntakeOutput

SECTION_LIMIT = 3000
"""Slack's maximum length for a section's text."""

HEADER_LIMIT = 150
"""Slack's maximum length for a header's text."""


def headline(intake: IntakeDetail) -> str:
    """The one-line summary used as the notification text.

    Args:
        intake: The Intake being announced.

    Returns:
        For example ``New intake: Mike's Roofing. 3 systems found, 1 issue flagged``.
    """
    return f"New intake: {intake.client_name}. {_counts(intake.output)}"


def intake_blocks(intake: IntakeDetail, dashboard_url: str) -> list[dict[str, Any]]:
    """The blocks describing an Intake, without buttons or decision.

    Args:
        intake: The Intake to describe.
        dashboard_url: The dashboard's base URL, or ``""`` to omit the link.

    Returns:
        Block Kit blocks, each within Slack's length limits.
    """
    output = intake.output
    summary = f"*{_counts(output)}*"
    if intake.injection_flagged:
        summary += "\n:warning: Injection Flag: the Transcript looked suspicious"
    blocks: list[dict[str, Any]] = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": _truncate(f"New intake: {intake.client_name}", HEADER_LIMIT),
            },
        },
        _section(summary),
    ]
    if output is not None:
        blocks += _verdict_blocks(output)
        blocks.append({"type": "divider"})
        blocks += _document_blocks(output)
    blocks.append(
        {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": _run_facts(intake, dashboard_url)}],
        }
    )
    return blocks


def _counts(output: IntakeOutput | None) -> str:
    systems = len(output.current_systems) if output else 0
    issues = sum(v.verdict == "no" for v in output.feasibility) if output else 0
    noun = "issue" if issues == 1 else "issues"
    return f"{systems} systems found, {issues} {noun} flagged"


def _verdict_blocks(output: IntakeOutput) -> list[dict[str, Any]]:
    by_verdict = {
        verdict: [v for v in output.feasibility if v.verdict == verdict]
        for verdict in ("no", "partial", "yes")
    }
    blocks = []
    if by_verdict["no"]:
        blocks.append(
            _list_section(
                ":no_entry: *Issues: can't be done as the Client asked*",
                [
                    f"• *{_esc(v.integration)}*: {_esc(v.reason)}"
                    for v in by_verdict["no"]
                ],
            )
        )
    if by_verdict["partial"]:
        blocks.append(
            _list_section(
                ":warning: *Partial: needs a workaround*",
                [
                    f"• *{_esc(v.integration)}*: {_esc(v.reason)}"
                    for v in by_verdict["partial"]
                ],
            )
        )
    if by_verdict["yes"]:
        blocks.append(
            _list_section(
                ":white_check_mark: *Feasible*",
                [f"• {_esc(v.integration)}" for v in by_verdict["yes"]],
            )
        )
    return blocks


def _document_blocks(output: IntakeOutput) -> list[dict[str, Any]]:
    systems = ", ".join(_esc(s) for s in output.current_systems)
    return [
        _section(_truncate(f"*Current Systems*\n{systems or '_None_'}", SECTION_LIMIT)),
        _list_section(
            "*Proposed setup*",
            [f"• *{_esc(c.name)}*: {_esc(c.purpose)}" for c in output.architecture],
        ),
        _list_section(
            "*Access to request*",
            [
                f"• *{_esc(a.system)}*: {_esc(a.access)}"
                for a in output.access_checklist
            ],
        ),
    ]


def _run_facts(intake: IntakeDetail, dashboard_url: str) -> str:
    facts = [f"Model {_esc(intake.model_used or 'unknown')}"]
    if intake.fallback_used:
        reason = f" ({_esc(intake.fallback_reason)})" if intake.fallback_reason else ""
        facts.append(f":arrows_counterclockwise: Fallback{reason}")
    if intake.duration_ms is not None:
        facts.append(f"{intake.duration_ms / 1000:.1f} s")
    cost = _cost(intake.cost_usd, intake.est_cost_usd)
    if cost:
        facts.append(cost)
    if dashboard_url:
        link = f"{dashboard_url.rstrip('/')}/#/intakes/{intake.id}"
        facts.append(f"<{link}|Open in dashboard>")
    return " · ".join(facts)


def _cost(cost_usd: float | None, est_cost_usd: float | None) -> str:
    """Same wording as the dashboard: ``$0 (≈ $0.0012 at paid rates)``."""
    if cost_usd is None and est_cost_usd is None:
        return ""
    paid = "$0" if not cost_usd else f"${cost_usd:.2f}"
    if est_cost_usd is None:
        return paid
    return f"{paid} (≈ ${est_cost_usd:.4f} at paid rates)"


def _list_section(title: str, lines: Sequence[str]) -> dict[str, Any]:
    """A titled list, cut short with "…and N more" to fit one section."""
    if not lines:
        return _section(f"{title}\n_None_")
    kept: list[str] = []
    length = len(title)
    reserve = len("\n_…and 9999 more in the dashboard_")
    for line in lines:
        line = _truncate(line, SECTION_LIMIT - len(title) - reserve - 1)
        if length + 1 + len(line) > SECTION_LIMIT - reserve:
            break
        kept.append(line)
        length += 1 + len(line)
    text = "\n".join([title, *kept])
    if len(kept) < len(lines):
        text += f"\n_…and {len(lines) - len(kept)} more in the dashboard_"
    return _section(text)


def _section(text: str) -> dict[str, Any]:
    return {"type": "section", "text": {"type": "mrkdwn", "text": text}}


def _truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _esc(text: str) -> str:
    """Escape Slack's control characters so model text renders literally."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
