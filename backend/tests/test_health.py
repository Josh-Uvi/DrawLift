"""Tests for the health check endpoint."""

import pytest


@pytest.mark.asyncio
async def test_health_check(client):
    """Test that GET /api/v1/health returns 200 with {"status": "ok"}."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
