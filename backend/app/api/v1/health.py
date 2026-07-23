"""Health check endpoint."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Liveness/readiness probe.

    Returns:
        dict with status "ok".
    """
    return {"status": "ok"}
