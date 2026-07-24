"""Unit tests for BilibiliUpHtmlCollector.

Mock httpx to simulate HTML responses with bili-video-card DOM.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from aipulse.collectors.bilibili_up.html import BilibiliUpHtmlCollector


SPACE_URL = "https://space.bilibili.com/{mid}".replace("{mid}", "1567748478")


@pytest.fixture
def collector():
    c = BilibiliUpHtmlCollector()
    yield c
    import asyncio

    asyncio.run(c.close())


SAMPLE_HTML = """
<!DOCTYPE html>
<html>
<body>
<bili-video-card data-bvid="BV1xx" pubdate="2026-07-12 10:30">
    <a href="//www.bilibili.com/video/BV1xx"></a>
    <p>描述1</p>
    <h3 title="视频一">视频一</h3>
    <img src="https://i0.hdslb.com/bfs/cover1.jpg" />
</bili-video-card>
<bili-video-card data-bvid="BV2yy" pubdate="2026-07-10 09:00">
    <a href="//www.bilibili.com/video/BV2yy"></a>
    <h3 title="视频二">视频二</h3>
    <img src="https://i0.hdslb.com/bfs/cover2.jpg" />
</bili-video-card>
</body>
</html>
"""


class TestFetchVideos:

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_fetch_videos_parses_bili_video_cards(self, collector: BilibiliUpHtmlCollector):
        with respx.mock() as mock:
            mock.get(SPACE_URL).mock(return_value=httpx.Response(200, text=SAMPLE_HTML))

            videos = await collector.fetch_videos("1567748478", count=10)

        assert len(videos) == 2
        assert videos[0].bvid == "BV1xx"
        assert videos[0].title == "视频一"
        assert videos[0].cover_url == "https://i0.hdslb.com/bfs/cover1.jpg"
        assert videos[0].pubdate.year == 2026
        assert videos[1].bvid == "BV2yy"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_fetch_videos_returns_empty_when_no_cards(
        self, collector: BilibiliUpHtmlCollector
    ):
        empty_html = "<html><body><p>not a space page</p></body></html>"
        with respx.mock() as mock:
            mock.get(SPACE_URL).mock(return_value=httpx.Response(200, text=empty_html))

            videos = await collector.fetch_videos("1567748478", count=10)

        assert videos == []

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_fetch_videos_returns_empty_on_network_error(
        self, collector: BilibiliUpHtmlCollector
    ):
        with respx.mock() as mock:
            mock.get(SPACE_URL).mock(side_effect=httpx.ConnectError("boom"))

            videos = await collector.fetch_videos("1567748478", count=10)

        assert videos == []

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_fetch_videos_respects_count(self, collector: BilibiliUpHtmlCollector):
        with respx.mock() as mock:
            mock.get(SPACE_URL).mock(return_value=httpx.Response(200, text=SAMPLE_HTML))

            videos = await collector.fetch_videos("1567748478", count=1)

        assert len(videos) == 1
        assert videos[0].bvid == "BV1xx"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_fetch_videos_incremental_cursor(self, collector: BilibiliUpHtmlCollector):
        with respx.mock() as mock:
            mock.get(SPACE_URL).mock(return_value=httpx.Response(200, text=SAMPLE_HTML))

            videos = await collector.fetch_videos("1567748478", count=10, last_cursor_id="BV1xx")

        # cursor = BV1xx，遇到就 break，BV2yy 不会进入
        assert videos == []


class TestValidate:

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_validate_existing_up_via_h1(self, collector: BilibiliUpHtmlCollector):
        valid_html = '<html><body><h1 id="h-name">跟李沐学AI</h1></body></html>'
        with respx.mock() as mock:
            mock.get(SPACE_URL).mock(return_value=httpx.Response(200, text=valid_html))

            exists, name = await collector.validate_up_exists("1567748478")

        assert exists is True
        assert name == "跟李沐学AI"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_validate_missing_up_via_404(self, collector: BilibiliUpHtmlCollector):
        with respx.mock() as mock:
            mock.get("https://space.bilibili.com/99999").mock(return_value=httpx.Response(404))

            exists, name = await collector.validate_up_exists("99999")

        assert exists is False
        assert "不存在" in name

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_validate_returns_false_when_no_h1(self, collector: BilibiliUpHtmlCollector):
        empty = "<html><body></body></html>"
        with respx.mock() as mock:
            mock.get(SPACE_URL).mock(return_value=httpx.Response(200, text=empty))

            exists, name = await collector.validate_up_exists("1567748478")

        assert exists is False


class TestParseCard:

    @pytest.mark.unit
    def test_parse_card_fallback_to_href(self):
        # 没有 data-bvid，从 href 提取
        from bs4 import BeautifulSoup

        html = (
            '<bili-video-card>'
            '<a href="//www.bilibili.com/video/BVfallback"></a>'
            '<h3>标题</h3>'
            '</bili-video-card>'
        )
        card = BeautifulSoup(html, "html.parser").find("bili-video-card")
        v = BilibiliUpHtmlCollector._parse_card(card)
        assert v is not None
        assert v.bvid == "BVfallback"

    @pytest.mark.unit
    def test_parse_card_returns_none_if_no_bvid(self):
        from bs4 import BeautifulSoup

        html = "<bili-video-card></bili-video-card>"
        card = BeautifulSoup(html, "html.parser").find("bili-video-card")
        v = BilibiliUpHtmlCollector._parse_card(card)
        assert v is None