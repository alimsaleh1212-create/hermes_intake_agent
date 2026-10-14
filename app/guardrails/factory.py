"""Builds the guardrails used on submission. Owned by #3.

Until #3 lands these are pass-through stubs: nothing is redacted and nothing is
flagged.
"""

from app.core.config import Settings
from app.guardrails.base import InjectionDetector, Redactor


class PassThroughRedactor:
    """Stub ``Redactor`` that returns the text unchanged."""

    def redact(self, text: str) -> str:
        return text


class NeverFlagDetector:
    """Stub ``InjectionDetector`` that never flags."""

    def is_flagged(self, text: str) -> bool:
        return False


def build_redactor(settings: Settings) -> Redactor:
    """Return the ``Redactor`` used on every submission."""
    return PassThroughRedactor()


def build_injection_detector(settings: Settings) -> InjectionDetector:
    """Return the ``InjectionDetector`` used on every submission."""
    return NeverFlagDetector()
