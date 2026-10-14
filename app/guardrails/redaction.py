"""Regex PII redaction into numbered placeholders.

Regex misses names; Presidio is the named next step.
"""

import re
from collections.abc import Callable

_EMAIL = re.compile(
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}"
)

_STREET_SUFFIX = (
    r"(?i:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln|Court|Ct"
    r"|Way|Place|Pl|Parkway|Pkwy|Circle|Cir|Highway|Hwy|Terrace|Trail)"
)
_ADDRESS = re.compile(
    r"\b\d{1,6}\s+"
    r"(?:(?:[A-Z][\w'.-]*|\d+(?:st|nd|rd|th))\s+){1,4}"
    rf"{_STREET_SUFFIX}\b\.?"
    r"(?:,?\s+(?:[A-Z][a-zA-Z.'-]*\s+){0,2}[A-Z][a-zA-Z.'-]*,?\s+[A-Z]{2}"
    r"(?:\s+\d{5}(?:-\d{4})?)?)?"
)

_PHONE = re.compile(
    r"(?<![\w$.,+-])"
    r"(?:"
    r"(?:\+\d{1,3}[\s.-]?)?(?:\(\d{3}\)\s?|\d{3}[\s.-]?)\d{3}[\s.-]?\d{4}"
    r"|\+\d{1,3}(?:[\s.-]?\d{2,4}){2,5}"
    r")(?![\w-])"
)


class RegexRedactor:
    """``Redactor`` replacing emails, phones and street addresses.

    Repeats of the same value in one text share a placeholder; distinct values
    get the next number. State is per ``redact`` call.
    """

    def redact(self, text: str) -> str:
        """Return ``text`` with PII replaced by ``[KIND_n]`` placeholders."""
        text = self._replace(text, _EMAIL, "EMAIL", str.lower)
        text = self._replace(text, _ADDRESS, "ADDRESS", _squash)
        return self._replace(text, _PHONE, "PHONE", _phone_key)

    @staticmethod
    def _replace(
        text: str, pattern: re.Pattern[str], kind: str, key: Callable[[str], str]
    ) -> str:
        seen: dict[str, int] = {}

        def sub(match: re.Match[str]) -> str:
            number = seen.setdefault(key(match.group()), len(seen) + 1)
            return f"[{kind}_{number}]"

        return pattern.sub(sub, text)


def _squash(value: str) -> str:
    return " ".join(value.lower().split())


def _phone_key(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    return digits[-10:] if len(digits) == 11 and value.startswith("+1") else digits
