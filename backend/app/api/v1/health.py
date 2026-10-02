"""Health check endpoint."""

from fastapi import APIRouter

router = APIRouter()


def _build_health_response() -> dict[str, str]:
    """Helper to build the health response.

    Returns:
        dict with status "ok".
    """
    return {"status": "ok"}


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Liveness/readiness probe.

    Returns:
        dict with status "ok".
    """
    return _build_health_response()
