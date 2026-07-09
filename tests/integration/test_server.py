import pytest
from httpx import ASGITransport, AsyncClient

from aipulse.server import app


@pytest.mark.integration
async def test_health_check():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["success"] is True
