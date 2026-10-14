"""Errors shared across packages, so no package imports another just for an error."""


class IntakeAgentError(Exception):
    """Raised when no model could produce a valid Intake Output.

    The service turns this into a ``failed`` Intake with ``str(error)`` stored, so
    the message must never contain Transcript text.
    """
