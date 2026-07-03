import pytest

from aipulse.desktop.sidecar import Sidecar


@pytest.mark.unit
async def test_submit_url_accepts_browser_extension_source_and_mode():
    sidecar = Sidecar()
    result = await sidecar.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "submit_url",
            "params": {
                "url": "https://www.bilibili.com/video/BV1xx411c7mD",
                "source": "browser_extension",
                "mode": "knowledge_check",
            },
        }
    )
    assert result is not None
    assert result.error is None
    assert result.result["url"] == "https://www.bilibili.com/video/BV1xx411c7mD"
    assert "task_id" in result.result
