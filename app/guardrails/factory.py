"""Builds the guardrails used on submission. Owned by #3."""

from app.guardrails.base import InjectionDetector, Redactor
from app.guardrails.injection import KeywordInjectionDetector
from app.guardrails.redaction import RegexRedactor

__all__ = [
    "InjectionDetector",
    "Redactor",
    "build_injection_detector",
    "build_redactor",
]


def build_redactor() -> Redactor:
    """Return the ``Redactor`` used on every submission."""
    return RegexRedactor()


def build_injection_detector() -> InjectionDetector:
    """Return the ``InjectionDetector`` used on every submission."""
    return KeywordInjectionDetector()
