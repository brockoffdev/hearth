"""Health check endpoint."""

from fastapi import APIRouter
from pydantic import BaseModel

from backend.app.config import get_settings

router = APIRouter()


class HealthResponse(BaseModel):
    ok: bool
    version: str
    name: str


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(ok=True, version=settings.version, name=settings.app_name)
