"""Prompt pieces shared by every ``IntakeAgent`` implementation."""


def build_user_prompt(transcript_redacted: str) -> str:
    """Wrap the Redacted Transcript in ``<transcript>`` tags."""
    return f"<transcript>\n{transcript_redacted}\n</transcript>"
