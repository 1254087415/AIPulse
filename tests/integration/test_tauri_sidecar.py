"""Tauri sidecar JSON-RPC integration tests over stdio.

These tests exercise the real Python sidecar as a subprocess, sending
JSON-RPC requests line-by-line over stdin and reading responses from stdout.
"""

import json
import os
import select
import subprocess
import sys
from pathlib import Path

import pytest

JSONRPC_METHOD_NOT_FOUND = -32601
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _read_response(proc: subprocess.Popen[str], timeout: float = 10.0) -> dict[str, object]:
    """Read a single JSON-RPC response line from the sidecar with a timeout."""
    assert proc.stdout is not None
    ready, _, _ = select.select([proc.stdout], [], [], timeout)
    if not ready:
        raise TimeoutError("sidecar did not respond in time")
    line = proc.stdout.readline()
    if not line:
        raise RuntimeError("sidecar stdout closed")
    return json.loads(line)


@pytest.fixture
def sidecar(tmp_path: Path) -> subprocess.Popen[str]:
    """Spawn a fresh sidecar subprocess for each test and clean it up after."""
    data_dir = tmp_path / "sidecar"
    data_dir.mkdir()
    download_dir = data_dir / "downloads"
    db_path = data_dir / "aipulse.db"

    env = {
        **os.environ,
        "DATA_DIR": str(data_dir),
        "DOWNLOAD_DIR": str(download_dir),
        "DATABASE_URL": f"sqlite+aiosqlite:///{db_path}",
        "all_proxy": "",
        "http_proxy": "",
        "https_proxy": "",
    }

    proc = subprocess.Popen(
        [sys.executable, "-m", "aipulse.desktop.sidecar"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        cwd=str(PROJECT_ROOT),
        env=env,
    )

    yield proc

    if proc.stdin is not None:
        proc.stdin.close()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)


def _send_request(
    proc: subprocess.Popen[str],
    method: str,
    params: dict[str, object] | None = None,
    request_id: int | None = None,
) -> dict[str, object]:
    """Send a single JSON-RPC request and return the parsed response line."""
    request = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": method,
        "params": params or {},
    }
    assert proc.stdin is not None
    proc.stdin.write(json.dumps(request) + "\n")
    proc.stdin.flush()
    return _read_response(proc)


@pytest.mark.integration
def test_get_settings_returns_defaults(sidecar: subprocess.Popen[str]) -> None:
    """get_settings returns the default configuration keys."""
    response = _send_request(sidecar, "get_settings", request_id=1)

    assert "result" in response
    result = response["result"]
    assert "llm_base_url" in result
    assert "llm_model" in result
    assert result["llm_base_url"] == "https://api.kimi.com/coding/v1"
    assert result["llm_model"] == "kimi-for-coding"


@pytest.mark.integration
def test_update_settings_persists_values(
    sidecar: subprocess.Popen[str], tmp_path: Path
) -> None:
    """update_settings changes a value and a later get_settings reflects it."""
    new_vault_path = str(tmp_path / "test-vault")
    response = _send_request(
        sidecar,
        "update_settings",
        params={"obsidian_vault_path": new_vault_path},
        request_id=2,
    )

    assert "result" in response
    assert response["result"]["obsidian_vault_path"] == new_vault_path

    second = _send_request(sidecar, "get_settings", request_id=3)
    assert second["result"]["obsidian_vault_path"] == new_vault_path


@pytest.mark.integration
def test_submit_url_returns_task_id(sidecar: subprocess.Popen[str]) -> None:
    """submit_url accepts a URL and returns a non-empty task id quickly."""
    # Use localhost so the background pipeline fails fast without external network.
    response = _send_request(
        sidecar,
        "submit_url",
        params={"url": "http://localhost:1/test"},
        request_id=4,
    )

    assert "result" in response
    assert "task_id" in response["result"]
    task_id = response["result"]["task_id"]
    assert isinstance(task_id, str)
    assert len(task_id) > 0


@pytest.mark.integration
def test_invalid_method_returns_error(sidecar: subprocess.Popen[str]) -> None:
    """An unknown JSON-RPC method returns a method-not-found error."""
    response = _send_request(sidecar, "not_a_real_method", request_id=5)

    assert "error" in response
    error = response["error"]
    assert "code" in error
    assert "message" in error
    assert error["code"] == JSONRPC_METHOD_NOT_FOUND
