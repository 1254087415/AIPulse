"""Unit tests for aipulse.core.datetime_utils.

覆盖 v0.3 时区缺陷修复（spec §9.1）：

- now_utc 返回 aware UTC
- to_utc 对 naive 视为 UTC，对 aware 转 UTC
- format_iso_utc 永远带 ``+00:00`` 偏移
- format_iso_utc 对 None 返回 None
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest

from aipulse.core.datetime_utils import format_iso_utc, now_utc, to_utc


class TestNowUtc:
    @pytest.mark.unit
    def test_returns_aware_utc(self):
        """now_utc 必须返回 tz-aware UTC datetime（替代 deprecated utcnow）。"""
        dt = now_utc()
        assert dt.tzinfo is not None
        assert dt.utcoffset() == timedelta(0)

    @pytest.mark.unit
    def test_close_to_wall_clock(self):
        """now_utc 应接近 wall-clock UTC（容忍 5s 漂移）。"""
        before = datetime.now(UTC)
        actual = now_utc()
        after = datetime.now(UTC)
        assert before <= actual <= after


class TestToUtc:
    @pytest.mark.unit
    def test_none_returns_none(self):
        """to_utc(None) 应透传 None。"""
        assert to_utc(None) is None

    @pytest.mark.unit
    def test_naive_treated_as_utc(self):
        """存量 naive UTC 数据必须归一为 aware UTC。"""
        naive = datetime(2026, 7, 29, 16, 55, 1)
        result = to_utc(naive)
        assert result is not None
        assert result.tzinfo is UTC
        assert result == datetime(2026, 7, 29, 16, 55, 1, tzinfo=UTC)

    @pytest.mark.unit
    def test_aware_converted_to_utc(self):
        """非 UTC aware（如 +08:00）必须转 UTC。"""
        cn = timezone(timedelta(hours=8))
        aware = datetime(2026, 7, 30, 0, 55, 1, tzinfo=cn)
        result = to_utc(aware)
        assert result is not None
        assert result.tzinfo is UTC
        assert result == datetime(2026, 7, 29, 16, 55, 1, tzinfo=UTC)

    @pytest.mark.unit
    def test_naive_then_compare_works(self):
        """归一后让 naive 与 aware 比较不再抛 TypeError。

        这是修复 _is_due 崩溃的核心场景：now 是 aware，DB 读出的
        last_checked_at 是 naive（SQLite 丢 tz），二者直接比较就会
        抛 TypeError。to_utc 在比较前归一。
        """
        naive = datetime(2026, 7, 29, 16, 55, 1)
        aware = datetime(2026, 7, 29, 17, 55, 1, tzinfo=UTC)
        # 不归一会抛 TypeError
        with pytest.raises(TypeError):
            naive + timedelta(minutes=30) >= aware  # type: ignore[operator]
        # 归一后 OK
        assert to_utc(naive) <= aware


class TestFormatIsoUtc:
    @pytest.mark.unit
    def test_none_returns_none(self):
        """format_iso_utc(None) 透传 None。"""
        assert format_iso_utc(None) is None

    @pytest.mark.unit
    def test_naive_gets_offset(self):
        """naive 输入（存量数据）输出必须带 +00:00。"""
        naive = datetime(2026, 7, 29, 16, 55, 1)
        result = format_iso_utc(naive)
        assert result == "2026-07-29T16:55:01+00:00"

    @pytest.mark.unit
    def test_aware_utc_keeps_offset(self):
        """aware UTC 输入输出 +00:00。"""
        aware = datetime(2026, 7, 29, 16, 55, 1, tzinfo=UTC)
        assert format_iso_utc(aware) == "2026-07-29T16:55:01+00:00"

    @pytest.mark.unit
    def test_aware_non_utc_converted_to_utc(self):
        """aware 非 UTC（如 +08:00）必须转 UTC 后输出。"""
        cn = timezone(timedelta(hours=8))
        aware = datetime(2026, 7, 30, 0, 55, 1, tzinfo=cn)
        result = format_iso_utc(aware)
        assert result == "2026-07-29T16:55:01+00:00"

    @pytest.mark.unit
    def test_output_never_has_no_offset(self):
        """Output 必带 ``+00:00`` 或 ``Z``；naive 字符串（无偏移）= 缺陷。"""
        naive = datetime(2026, 7, 29, 16, 55, 1)
        result = format_iso_utc(naive)
        assert result is not None
        assert result.endswith("+00:00") or result.endswith("Z")
        # 反例：未修复的会输出 "2026-07-29T16:55:01" 无偏移
        assert "+" in result or result.endswith("Z")
