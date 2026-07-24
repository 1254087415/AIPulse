"""Unit tests for BilibiliUpUapiCollector.

Mock httpx to simulate UAPI responses.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
import respx

from aipulse.collectors.bilibili_up.uapi import BilibiliUpUapiCollector


UAPI_BASE = "https://uapis.cn/api/v1"


@pytest.fixture
def collector():
    c = BilibiliUpUapiCollector()
    yield c
    import asyncio

    asyncio.run(c.close())


class TestFetchVideos:

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_fetch_videos_returns_parsed_videos(self, collector: BilibiliUpUapiCollector):
        with respx.mock(base_url=UAPI_BASE) as mock:
            mock.get("/space/arc/search").mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "code": 0,
                        "data": {
                            "list": [
                                {
                                    "bvid": "BV1abc",
                                    "title": "视频1",
                                    "pubdate": 1721000000,
                                    "duration": 600,
                                    "play": 1234,
                                },
                                {
                                    "bvid": "BV2def",
                                    "title": "视频2",
                                    "pubdate": 1720900000,
                                    "duration": 300,
                                },
                            ],
                            "has_more": False,
                        },
                    },
                )
            )

            videos = await collector.fetch_videos("1567748478", count=10)

        assert len(videos) == 2
        assert videos[0].bvid == "BV1abc"
        assert videos[0].title == "视频1"
        assert videos[0].duration_sec == 600
        assert videos[0].play_count == 1234
        assert videos[1].bvid == "BV2def"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_fetch_videos_returns_empty_on_rate_limit(
        self, collector: BilibiliUpUapiCollector
    ):
        """UAPI 遇到 code != 0 → 返回空 list，不抛异常。"""
        with respx.mock(base_url=UAPI_BASE) as mock:
            mock.get("/space/arc/search").mock(
                return_value=httpx.Response(
                    200,
                    json={"code": 429, "message": "rate limited"},
                )
            )

            videos = await collector.fetch_videos("mid", count=10)

        assert videos == []

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_fetch_videos_returns_empty_on_network_error(
        self, collector: BilibiliUpUapiCollector
    ):
        """UAPI 网络异常 → 返回空 list。"""
        with respx.mock(base_url=UAPI_BASE) as mock:
            mock.get("/space/arc/search").mock(
                side_effect=httpx.ConnectError("boom")
            )

            videos = await collector.fetch_videos("mid", count=10)

        assert videos == []

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_fetch_videos_incremental_cursor_stops(self, collector: BilibiliUpUapiCollector):
        """命中 last_cursor_id 后停止翻页。"""
        with respx.mock(base_url=UAPI_BASE) as mock:
            mock.get("/space/arc/search").mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "code": 0,
                        "data": {
                            "list": [
                                {"bvid": "BV3new", "title": "new", "pubdate": 1721100000},
                                {"bvid": "BV1old", "title": "old", "pubdate": 1721000000},
                            ],
                            "has_more": False,
                        },
                    },
                )
            )

            videos = await collector.fetch_videos("mid", count=10, last_cursor_id="BV1old")

        # BV1old 是 cursor，应跳过；BV3new 在前 → 已加入
        # 实际上顺序：先遍历 BV3new（不等），加入；再遍历 BV1old（==cursor），停止
        assert all(v.bvid != "BV1old" for v in videos)
        assert any(v.bvid == "BV3new" for v in videos)


class TestValidate:

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_validate_existing_up(self, collector: BilibiliUpUapiCollector):
        with respx.mock(base_url=UAPI_BASE) as mock:
            mock.get("/space/card").mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "code": 0,
                        "data": {"user": {"name": "跟李沐学AI", "mid": "1567748478"}},
                    },
                )
            )

            exists, name = await collector.validate_up_exists("1567748478")

        assert exists is True
        assert name == "跟李沐学AI"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_validate_nonexistent_up_returns_false(self, collector: BilibiliUpUapiCollector):
        with respx.mock(base_url=UAPI_BASE) as mock:
            mock.get("/space/card").mock(
                return_value=httpx.Response(
                    200,
                    json={"code": -404, "message": "用户不存在"},
                )
            )

            exists, name = await collector.validate_up_exists("99999")

        assert exists is False
        assert "用户不存在" in name or "不存在" in name

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_validate_disabled_account_returns_false(
        self, collector: BilibiliUpUapiCollector
    ):
        with respx.mock(base_url=UAPI_BASE) as mock:
            mock.get("/space/card").mock(
                return_value=httpx.Response(
                    200,
                    json={"code": 0, "data": {"user": {"name": ""}}},
                )
            )

            exists, name = await collector.validate_up_exists("mid")

        assert exists is False
        assert "注销" in name


class TestParseVideo:

    @pytest.mark.unit
    def test_parse_video_handles_missing_fields(self):
        # 缺 pubdate → 降级到 datetime.now()
        v = BilibiliUpUapiCollector._parse_video({"bvid": "BVx", "title": "t"})
        assert v is not None
        assert v.bvid == "BVx"

    @pytest.mark.unit
    def test_parse_video_returns_none_on_garbage(self):
        v = BilibiliUpUapiCollector._parse_video({})
        assert v is None