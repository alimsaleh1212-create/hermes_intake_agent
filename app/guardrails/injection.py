"""Keyword Injection Flag."""

import re

_PATTERNS = [
    r"\b(?:ignore|disregard|forget|override)\s+(?:(?:all|any|the|your|my)\s+)*"
    r"(?:(?:previous|prior|above|earlier|preceding|system)\s+)?"
    r"(?:instructions?|prompts?|rules|directions)\b",
    r"\bsystem\s+prompt\b",
    r"\byou\s+are\s+now\b",
    r"\b(?:reveal|print|show|send|leak)\s+(?:me\s+)?(?:your\s+)?"
    r"(?:api\s+keys?|secrets?|credentials|passwords?)\b",
    r"\bdeveloper\s+mode\b",
    r"\bjailbreak\b",
]
_INJECTION = re.compile("|".join(_PATTERNS), re.IGNORECASE)


class KeywordInjectionDetector:
    """``InjectionDetector`` matching known instruction-override phrases."""

    def is_flagged(self, text: str) -> bool:
        """Return True if ``text`` contains an injection phrase (any case)."""
        return _INJECTION.search(text) is not None
