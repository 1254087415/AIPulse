"""Unit tests for bilibili_up collector base / factory."""

from __future__ import annotations

from datetime import datetime

import pytest

from aipulse.collectors.bilibili_up import (
    BaseBilibiliUpCollector,
    BilibiliUpCollectorFactory,
    BilibiliUpHtmlCollector,
    BilibiliUpUapiCollector,
)
from aipulse.collectors.bilibili_up.base import UpCollection, UpVideo


class TestFactory:

    @pytest.mark.unit
    def test_create_uapi_returns_uapi_collector(self):
        collector = BilibiliUpCollectorFactory.create("uapi")
        assert isinstance(collector, BilibiliUpUapiCollector)
        assert collector.strategy == "uapi"
        assert isinstance(collector, BaseBilibiliUpCollector)

    @pytest.mark.unit
    def test_create_html_returns_html_collector(self):
        collector = BilibiliUpCollectorFactory.create("html")
        assert isinstance(collector, BilibiliUpHtmlCollector)
        assert collector.strategy == "html"

    @pytest.mark.unit
    def test_create_default_is_uapi(self):
        collector = BilibiliUpCollectorFactory.create()
        assert isinstance(collector, BilibiliUpUapiCollector)

    @pytest.mark.unit
    def test_create_unknown_strategy_raises_value_error(self):
        with pytest.raises(ValueError, match="Unknown bilibili_up strategy"):
            BilibiliUpCollectorFactory.create("nonexistent")

    @pytest.mark.unit
    def test_available_strategies_returns_sorted(self):
        strategies = BilibiliUpCollectorFactory.available_strategies()
        assert strategies == ["html", "uapi"]


class TestUpVideo:

    @pytest.mark.unit
    def test_up_video_required_fields(self):
        v = UpVideo(
            bvid="BV1xx411c7mD",
            title="hello",
            pubdate=datetime(2026, 7, 1),
        )
        assert v.bvid == "BV1xx411c7mD"
        assert v.title == "hello"
        assert v.duration_sec == 0
        assert v.is_backfill is False
        assert v.collection_id is None

    @pytest.mark.unit
    def test_up_video_is_frozen(self):
        v = UpVideo(bvid="BV1", title="t", pubdate=datetime.now())
        with pytest.raises(Exception):  # FrozenInstanceError
            v.title = "changed"  # type: ignore[misc]


class TestUpCollection:

    @pytest.mark.unit
    def test_up_collection_defaults(self):
        c = UpCollection(platform_collection_id="sid-1", title="系列")
        assert c.video_count == 0
        assert c.description == ""


class TestBaseCollector:

    @pytest.mark.unit
    def test_base_collector_is_abstract(self):
        # 不能直接实例化抽象基类
        with pytest.raises(TypeError):
            BaseBilibiliUpCollector(strategy="uapi")  # type: ignore[abstract]

    @pytest.mark.unit
    def test_concrete_collectors_close_idempotent(self):
        c = BilibiliUpCollectorFactory.create("uapi")
        # close 不抛异常
        import asyncio

        asyncio.run(c.close())