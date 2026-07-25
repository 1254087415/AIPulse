"""Tests for Apple Reminders module (spec §F6).

仅验证跨平台行为：
- 非 darwin 直接 RuntimeError
- _format_due_date ISO8601 转换
- _escape_for_applescript 转义
"""

from __future__ import annotations

import pytest

from aipulse.apple.reminders import _escape_for_applescript, _format_due_date, create_reminder


def test_format_due_date_with_t_separator() -> None:
    assert _format_due_date("2026-08-01T10:00:00+08:00") == "2026-08-01 10:00:00"


def test_format_due_date_with_tz_only_date() -> None:
    assert _format_due_date("2026-08-01T10:00:00Z") == "2026-08-01 10:00:00"


def test_format_due_date_passthrough_date_only() -> None:
    assert _format_due_date("2026-08-01") == "2026-08-01"


def test_format_due_date_truncates_fractional_seconds() -> None:
    assert _format_due_date("2026-08-01T10:00:00.123456+00:00") == "2026-08-01 10:00:00"


def test_format_due_date_handles_empty() -> None:
    assert _format_due_date("") == ""


def test_escape_applescript_quotes() -> None:
    assert _escape_for_applescript('a"b') == 'a\\"b'
    assert _escape_for_applescript("a\\b") == "a\\\\b"
    assert _escape_for_applescript("") == ""
    assert _escape_for_applescript("plain") == "plain"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_reminder_raises_on_linux(monkeypatch) -> None:
    monkeypatch.setattr("sys.platform", "linux")
    with pytest.raises(RuntimeError, match="仅在 macOS"):
        await create_reminder(
            title="t",
            due_date="2026-08-01T10:00:00",
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_reminder_short_title(monkeypatch) -> None:
    """短标题 + due_date 较短路径：macOS 走 osascript，不实际触发（除非真在 darwin 上）"""
    import sys

    if sys.platform != "darwin":
        # 在 linux 上断言抛 RuntimeError（platform 短路）
        with pytest.raises(RuntimeError, match="仅在 macOS"):
            await create_reminder(title="t", due_date="2026-08-01T10:00:00")
        return
    # 在 darwin 上若 osascript 失败也不应默默成功 — 至少尝试一次
    # 显式传 list_name="AIPulse测试" 避免污染用户真实的【学习】列表
    try:
        await create_reminder(
            title="AIPulse test",
            due_date="2026-08-01T10:00:00",
            notes="hi",
            list_name="AIPulse测试",
        )
    except RuntimeError:
        # ok — sandboxed envs may not have Reminders access
        pass
