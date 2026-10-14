"""Builds the guardrails used on submission. Owned by #3."""

from app.core.config import Settings
from app.guardrails.base import InjectionDetector, Redactor
from app.guardrails.injection import KeywordInjectionDetector
from app.guardrails.redaction import RegexRedactor


def build_redactor(settings: Settings) -> Redactor:
    """Return the ``Redactor`` used on every submission."""
    return RegexRedactor()


def build_injection_detector(settings: Settings) -> InjectionDetector:
    """Return the ``InjectionDetector`` used on every submission."""
    return KeywordInjectionDetector()
