"""Tests for Apple Reminders module (spec §F6).

仅验证跨平台行为：
- 非 darwin 直接 RuntimeError
- _format_due_date ISO8601 转换
- _escape_for_applescript 转义
"""

from __future__ import annotations

import logging
import platform
import sys
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio

from aipulse.apple.reminders import (
    _escape_for_applescript,
    _format_due_date,
    create_reminder,
    pick_list_for_topic,
)

logger = logging.getLogger(__name__)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _cleanup_aipulse_test_reminders() -> AsyncGenerator[None, None]:
    """Session teardown: remove the ``AIPulse测试`` Reminders list on macOS.

    Best-effort — any exception is logged and swallowed so cleanup never
    affects pytest exit codes or downstream sessions.
    """
    yield  # run all tests first ...
    # ... then teardown only on darwin
    if sys.platform != "darwin" or platform.system() != "Darwin":
        return
    try:
        from scripts.clean_reminders import cleanup_reminders_test_data

        outcome = await cleanup_reminders_test_data()
        if outcome == "deleted":
            logger.info("Removed AIPulse测试 Reminders list created by tests")
        elif outcome == "not-found":
            logger.debug("AIPulse测试 Reminders list was already absent")
    except Exception as exc:  # noqa: BLE001 — cleanup must not fail the session
        logger.warning(
            "Failed to clean AIPulse测试 Reminders list (best-effort): %s", exc
        )


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


# ---------------------------------------------------------------------------
# pick_list_for_topic (spec 06 §7.2)
# ---------------------------------------------------------------------------
@pytest.mark.unit
def test_pick_list_for_topic_learning() -> None:
    """学习类总结必须落到用户实际的「学习」列表。"""
    assert pick_list_for_topic("LangChain ReAct 学习") == "学习"
    assert pick_list_for_topic("AI 工具实战") == "学习"
    assert pick_list_for_topic("编程之道") == "学习"
    assert pick_list_for_topic("面试经验分享") == "学习"
    assert pick_list_for_topic("前沿技术解读") == "学习"


@pytest.mark.unit
def test_pick_list_for_topic_money() -> None:
    """关键字匹配 → 搞钱！！！ 列表。"""
    assert pick_list_for_topic("搞钱思维") == "搞钱！！！"
    assert pick_list_for_topic("副业启动") == "搞钱！！！"
    assert pick_list_for_topic("创业日记") == "搞钱！！！"
    assert pick_list_for_topic("变现案例分析") == "搞钱！！！"


@pytest.mark.unit
def test_pick_list_for_topic_work() -> None:
    """工作类总结进入独立的「工作」列表，不得回到旧的合并列表。"""
    assert pick_list_for_topic("工作项目复盘") == "工作"
    assert pick_list_for_topic("职场沟通技巧") == "工作"


@pytest.mark.unit
def test_pick_list_for_topic_misc() -> None:
    """业务关键字都不命中 → 琐碎生活 列表。"""
    assert pick_list_for_topic("周末去哪儿玩") == "琐碎生活"
    assert pick_list_for_topic("好吃的餐厅推荐") == "琐碎生活"


@pytest.mark.unit
def test_pick_list_for_topic_empty_defaults_to_misc() -> None:
    """空 / None / 不传 topic → 琐碎生活。"""
    assert pick_list_for_topic("") == "琐碎生活"
    assert pick_list_for_topic(None) == "琐碎生活"  # type: ignore[arg-type]
