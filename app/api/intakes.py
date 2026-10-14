"""``/intakes`` routes. Routes call the service only; they never touch the DB."""

import secrets
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Response,
    Security,
    status,
)
from fastapi.security import APIKeyHeader

from app.deps import IntakeServiceDep, SettingsDep
from app.schemas.intake import IntakeCreate, IntakeDetail, IntakeSummary

router = APIRouter(prefix="/intakes", tags=["intakes"])

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key(
    settings: SettingsDep,
    api_key: Annotated[str | None, Security(_api_key_header)] = None,
) -> None:
    """Reject the request unless ``X-API-Key`` matches the configured key.

    An unset server key rejects everything, so a missing config never opens
    submission to the public.
    """
    expected = settings.intake_api_key.get_secret_value()
    if not expected or api_key is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or missing API key")
    if not secrets.compare_digest(api_key.encode(), expected.encode()):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or missing API key")


@router.post(
    "",
    response_model=IntakeDetail,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_api_key)],
    responses={200: {"model": IntakeDetail, "description": "Existing duplicate"}},
)
async def submit_intake(
    body: IntakeCreate,
    service: IntakeServiceDep,
    background_tasks: BackgroundTasks,
    response: Response,
) -> IntakeDetail:
    """Submit a Client's Transcript; the agent runs in the background."""
    submission = await service.submit(body)
    if submission.created:
        background_tasks.add_task(service.process, submission.intake.id)
    else:
        response.status_code = status.HTTP_200_OK
    return submission.intake


@router.get("", response_model=list[IntakeSummary])
async def list_intakes(service: IntakeServiceDep) -> list[IntakeDetail]:
    """List Intakes, newest first, as summaries."""
    return await service.list_intakes()


@router.get("/{intake_id}", response_model=IntakeDetail)
async def get_intake(intake_id: UUID, service: IntakeServiceDep) -> IntakeDetail:
    """Return one Intake with its Intake Output and Redacted Transcript."""
    intake = await service.get_intake(intake_id)
    if intake is None:
        raise HTTPException(status_code=404, detail="Intake not found")
    return intake
