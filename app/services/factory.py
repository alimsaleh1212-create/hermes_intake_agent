"""Builds the ``IntakeService`` from its collaborators."""

from app.agents.base import IntakeAgent
from app.db.repository import IntakeRepository
from app.guardrails.base import InjectionDetector, Redactor
from app.services.intake_service import IntakeService
from app.slack.base import SlackNotifier


def build_intake_service(
    repository: IntakeRepository,
    agent: IntakeAgent,
    redactor: Redactor,
    detector: InjectionDetector,
    notifier: SlackNotifier,
) -> IntakeService:
    """Return an ``IntakeService`` wired with these collaborators."""
    return IntakeService(repository, agent, redactor, detector, notifier)
