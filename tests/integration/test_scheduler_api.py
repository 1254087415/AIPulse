import pytest


@pytest.mark.integration
async def test_list_scheduler_jobs_returns_success_envelope(client):
    response = await client.get("/api/scheduler/jobs")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert isinstance(body["data"], list)
