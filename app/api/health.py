"""``GET /health``, used by the container healthcheck."""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Report that the API process is up."""
    return {"status": "ok"}
