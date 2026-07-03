from pathlib import Path
from unittest.mock import MagicMock

import pytest

from aipulse.core.config import AppSettings
from aipulse.desktop.sidecar import Sidecar


@pytest.mark.unit
async def test_submit_url_accepts_browser_extension_source_and_mode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = AppSettings(
        data_dir=tmp_path,
        database_url=f"sqlite+aiosqlite:///{tmp_path}/aipulse.db",
    )
    sidecar = Sidecar(settings=settings)
    monkeypatch.setattr(sidecar, "_spawn_pipeline", MagicMock())

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
    assert result.result is not None
    assert result.result["url"] == "https://www.bilibili.com/video/BV1xx411c7mD"
    assert "task_id" in result.result
    cached = sidecar._tasks[result.result["task_id"]]
    assert cached["source"] == "browser_extension"
    assert cached["mode"] == "knowledge_check"
