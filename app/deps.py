"""FastAPI ``Depends`` providers.

Each collaborator comes from its own factory (``app/<concern>/factory.py``), so a
ticket changes its factory, not this file. Tests swap any provider through
``app.dependency_overrides``.
"""

from typing import Annotated

import httpx
from fastapi import Depends, Request
from slack_sdk.web.async_client import AsyncWebClient

from app.agents.factory import IntakeAgent, build_agent
from app.core.config import Settings
from app.db.factory import IntakeRepository, build_repository
from app.guardrails.factory import (
    InjectionDetector,
    Redactor,
    build_injection_detector,
    build_redactor,
)
from app.services.factory import IntakeService, build_intake_service
from app.slack.factory import SlackNotifier, build_notifier


def get_settings(request: Request) -> Settings:
    """The settings the app was created with."""
    return request.app.state.settings


def get_http_client(request: Request) -> httpx.AsyncClient:
    """The shared httpx client created in lifespan."""
    return request.app.state.http_client


def get_slack_client(request: Request) -> AsyncWebClient | None:
    """The Slack client created in lifespan, or ``None`` without a bot token."""
    return request.app.state.slack_client


def get_repository(request: Request) -> IntakeRepository:
    """The Intake repository over the lifespan's session factory."""
    return build_repository(request.app.state.session_factory)


SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_agent(
    settings: SettingsDep,
    http_client: Annotated[httpx.AsyncClient, Depends(get_http_client)],
) -> IntakeAgent:
    """The configured ``IntakeAgent``."""
    return build_agent(settings, http_client)


def get_redactor() -> Redactor:
    """The configured ``Redactor``."""
    return build_redactor()


def get_injection_detector() -> InjectionDetector:
    """The configured ``InjectionDetector``."""
    return build_injection_detector()


def get_notifier(
    settings: SettingsDep,
    slack_client: Annotated[AsyncWebClient | None, Depends(get_slack_client)],
) -> SlackNotifier:
    """The configured ``SlackNotifier``."""
    return build_notifier(settings, slack_client)


def get_intake_service(
    repository: Annotated[IntakeRepository, Depends(get_repository)],
    agent: Annotated[IntakeAgent, Depends(get_agent)],
    redactor: Annotated[Redactor, Depends(get_redactor)],
    detector: Annotated[InjectionDetector, Depends(get_injection_detector)],
    notifier: Annotated[SlackNotifier, Depends(get_notifier)],
) -> IntakeService:
    """An ``IntakeService`` wired with the configured collaborators."""
    return build_intake_service(repository, agent, redactor, detector, notifier)


IntakeServiceDep = Annotated[IntakeService, Depends(get_intake_service)]
