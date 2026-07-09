"""Tests for WeChat bot push strategy."""

from pathlib import Path

import pytest

from aipulse.core.config import AppSettings
from aipulse.pushers.base import PushMessage
from aipulse.pushers.wechat_bot import WechatBotPushStrategy


class FakeProcess:
    def __init__(self, returncode: int = 0):
        self.returncode = returncode

    async def communicate(self, input: bytes | None = None) -> tuple[bytes, bytes]:  # noqa: A002
        return (b"", b"")


@pytest.mark.unit
async def test_send_skips_when_unconfigured() -> None:
    strategy = WechatBotPushStrategy(AppSettings(wechat_send_script=""))
    result = await strategy.send(PushMessage(title="t", summary="s"))
    assert result is False


@pytest.mark.unit
async def test_send_uses_configured_script_and_stdin(monkeypatch, tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    script = data_dir / "scripts" / "send.sh"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text("#!/usr/bin/env bash\ncat > /dev/null\n")
    script.chmod(0o755)
    calls: list[tuple] = []

    async def fake_exec(*cmd: str, **kwargs):
        calls.append(cmd)
        return FakeProcess(returncode=0)

    monkeypatch.setattr("aipulse.pushers.wechat_bot.asyncio.create_subprocess_exec", fake_exec)
    strategy = WechatBotPushStrategy(
        AppSettings(data_dir=data_dir, wechat_send_script=str(script))
    )
    result = await strategy.send(PushMessage(title="Title", summary="Summary"))
    assert result is True
    assert calls[0] == (str(script),)


@pytest.mark.unit
async def test_send_returns_false_on_subprocess_error(monkeypatch, tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    script = data_dir / "scripts" / "send.sh"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text("#!/usr/bin/env bash\necho ok\n")
    script.chmod(0o755)

    async def fake_exec(*cmd: str, **kwargs):  # noqa: ARG001
        raise OSError("boom")

    monkeypatch.setattr("aipulse.pushers.wechat_bot.asyncio.create_subprocess_exec", fake_exec)
    strategy = WechatBotPushStrategy(
        AppSettings(data_dir=data_dir, wechat_send_script=str(script))
    )
    result = await strategy.send(PushMessage(title="T", summary="S"))
    assert result is False


@pytest.mark.unit
async def test_send_returns_false_on_non_zero_exit(monkeypatch, tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    script = data_dir / "scripts" / "send.sh"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text("#!/usr/bin/env bash\nexit 1\n")
    script.chmod(0o755)

    async def fake_exec(*cmd: str, **kwargs):  # noqa: ARG001
        return FakeProcess(returncode=1)

    monkeypatch.setattr("aipulse.pushers.wechat_bot.asyncio.create_subprocess_exec", fake_exec)
    strategy = WechatBotPushStrategy(
        AppSettings(data_dir=data_dir, wechat_send_script=str(script))
    )
    result = await strategy.send(PushMessage(title="T", summary="S"))
    assert result is False


@pytest.mark.unit
async def test_send_rejects_script_outside_scripts_dir(tmp_path: Path) -> None:
    script = tmp_path / "send.sh"
    script.write_text("#!/usr/bin/env bash\necho ok\n")
    script.chmod(0o755)

    strategy = WechatBotPushStrategy(
        AppSettings(data_dir=tmp_path, wechat_send_script=str(script))
    )
    result = await strategy.send(PushMessage(title="T", summary="S"))
    assert result is False
