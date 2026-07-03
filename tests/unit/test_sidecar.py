"""Smoke tests for JSON-RPC sidecar request parsing."""

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aipulse.core.config import AppSettings, reset_settings
from aipulse.core.rpc import JsonRpcRequest, JsonRpcResponse
from aipulse.desktop.sidecar import Sidecar


@pytest.fixture
def settings(tmp_path: Path) -> AppSettings:
    reset_settings()
    return AppSettings(
        data_dir=tmp_path / "data",
        download_dir=tmp_path / "data" / "downloads",
        database_url=f"sqlite+aiosqlite:///{tmp_path}/aipulse.db",
    )


@pytest.fixture
def sidecar(settings: AppSettings) -> Sidecar:
    return Sidecar(settings=settings)


@pytest.mark.unit
async def test_submit_url_creates_task(sidecar: Sidecar) -> None:
    result = await sidecar.handle_request(
        JsonRpcRequest(method="submit_url", params={"url": "https://example.com"})
    )
    assert isinstance(result, JsonRpcResponse)
    assert result.error is None
    assert result.result is not None
    assert "task_id" in result.result
    assert result.result["url"] == "https://example.com"


@pytest.mark.unit
async def test_submit_url_requires_url(sidecar: Sidecar) -> None:
    result = await sidecar.handle_request(
        JsonRpcRequest(method="submit_url", params={})
    )
    assert isinstance(result, JsonRpcResponse)
    assert result.error is not None
    assert result.error.code == -32603


@pytest.mark.unit
async def test_get_task_status_returns_status(sidecar: Sidecar) -> None:
    submit = await sidecar.handle_request(
        JsonRpcRequest(method="submit_url", params={"url": "https://example.com"})
    )
    task_id = submit.result["task_id"]
    status = await sidecar.handle_request(
        JsonRpcRequest(method="get_task_status", params={"task_id": task_id})
    )
    assert status.error is None
    assert status.result["task_id"] == task_id
    assert status.result["status"] == "pending"


@pytest.mark.unit
async def test_retry_task_resets_status(sidecar: Sidecar) -> None:
    submit = await sidecar.handle_request(
        JsonRpcRequest(method="submit_url", params={"url": "https://example.com"})
    )
    task_id = submit.result["task_id"]
    retry = await sidecar.handle_request(
        JsonRpcRequest(method="retry_task", params={"task_id": task_id})
    )
    assert retry.error is None
    assert retry.result["status"] == "pending"


@pytest.mark.unit
async def test_get_settings_masks_secrets(sidecar: Sidecar) -> None:
    result = await sidecar.handle_request(
        JsonRpcRequest(method="get_settings", params={})
    )
    assert result.error is None
    assert result.result["llm_base_url"] == "https://api.kimi.com/coding/v1"
    assert result.result["llm_model"] == "kimi-for-coding"
    assert result.result["llm_api_key"] == ""


@pytest.mark.unit
async def test_update_settings_persists_changes(sidecar: Sidecar, tmp_path: Path) -> None:
    result = await sidecar.handle_request(
        JsonRpcRequest(
            method="update_settings",
            params={"llm_model": "kimi-latest"},
        )
    )
    assert result.error is None
    assert result.result["llm_model"] == "kimi-latest"
    settings_file = tmp_path / "data" / "settings.json"
    assert settings_file.exists()
    persisted = json.loads(settings_file.read_text(encoding="utf-8"))
    assert persisted["llm_model"] == "kimi-latest"


@pytest.mark.unit
async def test_unknown_method_returns_error(sidecar: Sidecar) -> None:
    result = await sidecar.handle_request(
        JsonRpcRequest(method="unknown_method", params={})
    )
    assert result.error is not None
    assert result.error.code == -32601


@pytest.mark.unit
async def test_emit_progress_writes_notification(sidecar: Sidecar) -> None:
    lines: list[str] = []
    sidecar._write_line = lines.append
    await sidecar.emit_progress("task-1", "running", 50, "halfway")
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["method"] == "task_progress"
    assert payload["params"]["task_id"] == "task-1"
    assert payload["params"]["progress_pct"] == 50


@pytest.mark.unit
async def test_emit_complete_writes_notification(sidecar: Sidecar) -> None:
    lines: list[str] = []
    sidecar._write_line = lines.append
    await sidecar.emit_complete("task-1", "success", {"url": "https://example.com"})
    payload = json.loads(lines[0])
    assert payload["method"] == "task_complete"
    assert payload["params"]["status"] == "success"
    assert payload["params"]["result"]["url"] == "https://example.com"


@pytest.mark.unit
async def test_main_parses_line_and_responds(monkeypatch, tmp_path: Path) -> None:
    reset_settings()
    settings = AppSettings(
        data_dir=tmp_path / "data",
        download_dir=tmp_path / "data" / "downloads",
        database_url=f"sqlite+aiosqlite:///{tmp_path}/aipulse.db",
    )
    input_lines = [json.dumps({"jsonrpc": "2.0", "id": 1, "method": "get_settings"})]
    stdin = MagicMock()
    stdin.readline = AsyncMock(side_effect=[line.encode("utf-8") for line in input_lines] + [b""])
    stdout_lines: list[str] = []
    stdout = MagicMock()
    stdout.write = stdout_lines.append
    stdout.flush = MagicMock()

    monkeypatch.setattr(sys, "stdin", stdin)
    monkeypatch.setattr(sys, "stdout", stdout)

    with patch("aipulse.desktop.sidecar.init_db", new_callable=AsyncMock), patch(
        "aipulse.desktop.sidecar.close_db", new_callable=AsyncMock
    ), patch("aipulse.desktop.sidecar.get_settings", return_value=settings), patch(
        "aipulse.desktop.sidecar._read_stdin_lines"
    ) as mock_read_lines:
        async def _lines():
            for line in input_lines:
                yield line.encode("utf-8")

        mock_read_lines.return_value = _lines()

        from aipulse.desktop.sidecar import main

        await main()

    assert len(stdout_lines) == 1
    response = json.loads(stdout_lines[0])
    assert response["id"] == 1
    assert response["result"]["llm_model"] == "kimi-for-coding"
