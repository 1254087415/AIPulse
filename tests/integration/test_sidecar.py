"""Integration tests for the JSON-RPC sidecar."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aipulse.core.config import AppSettings, reset_settings
from aipulse.core.rpc import JsonRpcRequest, JsonRpcResponse
from aipulse.desktop.sidecar import Sidecar, main


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


@pytest.mark.integration
async def test_sidecar_submit_url_returns_task_id(sidecar: Sidecar) -> None:
    result = await sidecar.handle_request(
        JsonRpcRequest(method="submit_url", params={"url": "https://example.com"})
    )
    assert isinstance(result, JsonRpcResponse)
    assert result.error is None
    assert result.result is not None
    assert "task_id" in result.result
    await sidecar.shutdown()


@pytest.mark.integration
async def test_sidecar_get_task_status_round_trip(sidecar: Sidecar) -> None:
    submit = await sidecar.handle_request(
        JsonRpcRequest(method="submit_url", params={"url": "https://example.com"})
    )
    task_id = submit.result["task_id"]
    status = await sidecar.handle_request(
        JsonRpcRequest(method="get_task_status", params={"task_id": task_id})
    )
    assert status.error is None
    assert status.result["task_id"] == task_id
    await sidecar.shutdown()


@pytest.mark.integration
async def test_sidecar_retry_task_runs_pipeline(sidecar: Sidecar) -> None:
    submit = await sidecar.handle_request(
        JsonRpcRequest(method="submit_url", params={"url": "https://example.com"})
    )
    task_id = submit.result["task_id"]
    await sidecar.shutdown()

    retry = await sidecar.handle_request(
        JsonRpcRequest(method="retry_task", params={"task_id": task_id})
    )
    assert retry.error is None
    assert retry.result["status"] == "pending"
    await sidecar.shutdown()


@pytest.mark.integration
async def test_sidecar_update_settings_persists(sidecar: Sidecar, tmp_path: Path) -> None:
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


@pytest.mark.integration
async def test_sidecar_main_loop_with_mocked_stdio(
    monkeypatch,
    tmp_path: Path,
) -> None:
    reset_settings()
    settings = AppSettings(
        data_dir=tmp_path / "data",
        download_dir=tmp_path / "data" / "downloads",
        database_url=f"sqlite+aiosqlite:///{tmp_path}/aipulse.db",
    )
    input_lines = [
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "get_settings"}),
        json.dumps({"jsonrpc": "2.0", "id": 2, "method": "submit_url", "params": {"url": "https://example.com"}}),
    ]
    stdin = MagicMock()
    stdin.readline = AsyncMock(
        side_effect=[line.encode("utf-8") for line in input_lines] + [b""]
    )
    stdout_lines: list[str] = []
    stdout = MagicMock()
    stdout.write = stdout_lines.append
    stdout.flush = MagicMock()

    monkeypatch.setattr("aipulse.desktop.sidecar.sys.stdin", stdin)
    monkeypatch.setattr("aipulse.desktop.sidecar.sys.stdout", stdout)

    async def _lines():
        for line in input_lines:
            yield line.encode("utf-8")

    with (
        patch("aipulse.desktop.sidecar.init_db", new_callable=AsyncMock),
        patch("aipulse.desktop.sidecar.close_db", new_callable=AsyncMock),
        patch("aipulse.desktop.sidecar.get_settings", return_value=settings),
        patch("aipulse.desktop.sidecar._read_stdin_lines", return_value=_lines()),
        patch.dict("os.environ", {"all_proxy": "", "http_proxy": "", "https_proxy": ""}),
    ):
        await main()

    responses = [json.loads(line) for line in stdout_lines if '"id":' in line]
    assert len(responses) == 2
    assert responses[0]["id"] == 1
    assert responses[0]["result"]["llm_model"] == "kimi-for-coding"
    assert responses[1]["id"] == 2
    assert "task_id" in responses[1]["result"]


@pytest.mark.integration
async def test_sidecar_main_loop_handles_parse_error(
    monkeypatch,
    tmp_path: Path,
) -> None:
    reset_settings()
    settings = AppSettings(
        data_dir=tmp_path / "data",
        download_dir=tmp_path / "data" / "downloads",
        database_url=f"sqlite+aiosqlite:///{tmp_path}/aipulse.db",
    )
    input_lines = ["not valid json"]
    stdout_lines: list[str] = []
    stdout = MagicMock()
    stdout.write = stdout_lines.append
    stdout.flush = MagicMock()

    monkeypatch.setattr("aipulse.desktop.sidecar.sys.stdout", stdout)

    async def _lines():
        for line in input_lines:
            yield line.encode("utf-8")

    with (
        patch("aipulse.desktop.sidecar.init_db", new_callable=AsyncMock),
        patch("aipulse.desktop.sidecar.close_db", new_callable=AsyncMock),
        patch("aipulse.desktop.sidecar.get_settings", return_value=settings),
        patch("aipulse.desktop.sidecar._read_stdin_lines", return_value=_lines()),
    ):
        await main()

    assert len(stdout_lines) == 1
    response = json.loads(stdout_lines[0])
    assert response["error"]["code"] == -32700
