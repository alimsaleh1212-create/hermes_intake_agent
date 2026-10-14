"""Guardrail contracts: PII redaction and the Injection Flag."""

from typing import Protocol


class Redactor(Protocol):
    """Replaces PII with numbered placeholders.

    Emails, phone numbers and street addresses become ``[EMAIL_1]``,
    ``[PHONE_1]``, ``[ADDRESS_1]``; repeats of the same value in one Transcript
    map to the same placeholder.
    """

    def redact(self, text: str) -> str:
        """Return the Redacted Transcript for ``text``."""
        ...


class InjectionDetector(Protocol):
    """Decides whether a Transcript gets the Injection Flag."""

    def is_flagged(self, text: str) -> bool:
        """Return True if ``text`` contains phrases that try to instruct the agent."""
        ...
