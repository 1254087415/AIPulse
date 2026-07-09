import pytest
from httpx import AsyncClient


@pytest.mark.e2e
async def test_keyword_create_then_list(client: AsyncClient) -> None:
    created = await client.post("/api/keywords", json={"value": "OpenAI"})
    assert created.status_code == 200
    response = await client.get("/api/hotspots")
    assert response.status_code == 200
    assert response.json()["success"] is True
