"""Unit tests for BilibiliUpUapiCollector.

Mock httpx to simulate UAPI responses.

注意（2026-07 换端点）：
- ``/api/v1/space/arc/search`` → 404 NOT_FOUND
- ``/api/v1/space/card`` → 404 NOT_FOUND
- 新端点 ``/api/v1/social/bilibili/archives`` 单接口承担"拉视频"+"校验存在"
- 响应无外层 code 包裹：``{total, page, size, videos[{bvid, title,
  cover, duration, play_count, publish_time, ...}]}``
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
import respx

from aipulse.collectors.bilibili_up.uapi import (
    ARCHIVES_PATH,
    UAPI_BASE,
    BilibiliUpUapiCollector,
)


@pytest.fixture
def collector():
    c = BilibiliUpUapiCollector()
    yield c
    import asyncio

    asyncio.run(c.close())


def _sample_videos() -> list[dict[str, Any]]:
    return [
        {
            "bvid": "BV1abc",
            "title": "视频1",
            "publish_time": 1721000000,
            "duration": 600,
            "play_count": 1234,
            "cover": "http://example.com/1.jpg",
        },
        {
            "bvid": "BV2def",
            "title": "视频2",
            "publish_time": 1720900000,
            "duration": 300,
            "play_count": 100,
        },
    ]


class TestFetchVideos:

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_fetch_videos_returns_parsed_videos(self, collector: BilibiliUpUapiCollector):
        with respx.mock(base_url=UAPI_BASE) as mock:
            mock.get(ARCHIVES_PATH).mock(
                return_value=httpx.Response(
                    200,
                    json={"total": 2, "page": 1, "size": 50, "videos": _sample_videos()},
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
    async def test_fetch_videos_returns_empty_on_http_error(
        self, collector: BilibiliUpUapiCollector
    ):
        """archives 端点 HTTP 4xx/5xx → 返回空 list，不抛异常。"""
        with respx.mock(base_url=UAPI_BASE) as mock:
            mock.get(ARCHIVES_PATH).mock(
                return_value=httpx.Response(
                    500,
                    json={"code": "INTERNAL_ERROR", "message": "upstream down"},
                )
            )

            videos = await collector.fetch_videos("mid", count=10)

        assert videos == []

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_fetch_videos_returns_empty_on_network_error(
        self, collector: BilibiliUpUapiCollector
    ):
        """archives 端点网络异常 → 返回空 list。"""
        with respx.mock(base_url=UAPI_BASE) as mock:
            mock.get(ARCHIVES_PATH).mock(side_effect=httpx.ConnectError("boom"))

            videos = await collector.fetch_videos("mid", count=10)

        assert videos == []

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_fetch_videos_incremental_cursor_stops(self, collector: BilibiliUpUapiCollector):
        """命中 last_cursor_id 后停止翻页。"""
        with respx.mock(base_url=UAPI_BASE) as mock:
            mock.get(ARCHIVES_PATH).mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "total": 2,
                        "page": 1,
                        "size": 50,
                        "videos": [
                            {"bvid": "BV3new", "title": "new", "publish_time": 1721100000},
                            {"bvid": "BV1old", "title": "old", "publish_time": 1721000000},
                        ],
                    },
                )
            )

            videos = await collector.fetch_videos("mid", count=10, last_cursor_id="BV1old")

        assert all(v.bvid != "BV1old" for v in videos)
        assert any(v.bvid == "BV3new" for v in videos)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_fetch_videos_pagination_stops_at_total(self, collector: BilibiliUpUapiCollector):
        """total=2 + size=50 → 单页拿完不再翻 page=2。"""
        with respx.mock(base_url=UAPI_BASE) as mock:
            route = mock.get(ARCHIVES_PATH).mock(
                return_value=httpx.Response(
                    200,
                    json={"total": 2, "page": 1, "size": 50, "videos": _sample_videos()},
                )
            )

            videos = await collector.fetch_videos("1567748478", count=10)

        assert len(videos) == 2
        # 只请求了一次
        assert route.call_count == 1


class TestValidate:

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_validate_existing_up(self, collector: BilibiliUpUapiCollector):
        """UP主 存在（total>0）→ exists=True。"""
        with respx.mock(base_url=UAPI_BASE) as mock:
            mock.get(ARCHIVES_PATH).mock(
                return_value=httpx.Response(
                    200,
                    json={"total": 188, "page": 1, "size": 1, "videos": [
                        {"bvid": "BV1", "title": "第一条视频", "publish_time": 1721000000},
                    ]},
                )
            )

            exists, name = await collector.validate_up_exists("1567748478")

        assert exists is True
        assert name == "第一条视频"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_validate_nonexistent_up_returns_false(self, collector: BilibiliUpUapiCollector):
        """total=0 + videos=[] → exists=False (UP主 不存在或无投稿)。"""
        with respx.mock(base_url=UAPI_BASE) as mock:
            mock.get(ARCHIVES_PATH).mock(
                return_value=httpx.Response(
                    200,
                    json={"total": 0, "page": 1, "size": 1, "videos": []},
                )
            )

            exists, name = await collector.validate_up_exists("99999")

        assert exists is False
        assert "不存在" in name or "暂无" in name

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_validate_returns_false_on_network_error(
        self, collector: BilibiliUpUapiCollector
    ):
        with respx.mock(base_url=UAPI_BASE) as mock:
            mock.get(ARCHIVES_PATH).mock(side_effect=httpx.ConnectError("boom"))

            exists, name = await collector.validate_up_exists("mid")

        assert exists is False
        assert "校验失败" in name


class TestParseVideo:

    @pytest.mark.unit
    def test_parse_video_handles_missing_fields(self):
        # 缺 publish_time → 降级到 datetime.now()
        v = BilibiliUpUapiCollector._parse_video({"bvid": "BVx", "title": "t"})
        assert v is not None
        assert v.bvid == "BVx"

    @pytest.mark.unit
    def test_parse_video_returns_none_on_garbage(self):
        v = BilibiliUpUapiCollector._parse_video({})
        assert v is None

    @pytest.mark.unit
    def test_parse_video_uses_publish_time_field(self):
        """新端点字段是 publish_time（不是 pubdate）。"""
        v = BilibiliUpUapiCollector._parse_video({
            "bvid": "BVx", "title": "t", "publish_time": 1721000000,
        })
        assert v is not None
        assert v.pubdate.timestamp() == 1721000000