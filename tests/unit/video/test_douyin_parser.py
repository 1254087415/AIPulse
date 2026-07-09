"""Tests for Douyin share-link parser and downloader.

Exercises DouyinApiClient.parse_share_link and DouyinParser.parse/download
using mocked httpx responses.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aipulse.video.parsers.base import ParsedContent
from aipulse.video.parsers.douyin import DouyinApiClient, DouyinParser

SHARE_HTML = """
<!doctype html>
<html>
<head></head>
<body>
<script>window._ROUTER_DATA = {"loaderData": {"video-page": {"videoInfoRes": {"item_list": [{"aweme_id": "7649722907526521195", "desc": "Test Title", "author": {"nickname": "Test Author"}, "video": {"duration": 60000, "play_addr": {"url_list": ["https://play.com/test.mp4"]}, "cover": {"url_list": ["https://cover.com/test.jpg"]}}}]}}}}</script>
</body>
</html>
"""


def _mock_httpx_client(
    response_text: str, resolved_url: str = "https://www.douyin.com/video/7649722907526521195/"
) -> MagicMock:
    """Return a mock httpx.AsyncClient that yields the given response text."""
    response = MagicMock()
    response.text = response_text
    response.url = resolved_url
    response.raise_for_status = MagicMock()
    response.json = MagicMock(return_value={"item_list": []})

    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    client.get = AsyncMock(return_value=response)
    return client


@pytest.mark.unit
async def test_douyin_api_client_parses_share_link():
    client = DouyinApiClient(client=_mock_httpx_client(SHARE_HTML))
    info = await client.parse_share_link("https://v.douyin.com/xB-D6KXF8Ps/")

    assert info["aweme_id"] == "7649722907526521195"
    assert info["desc"] == "Test Title"
    assert info["author"]["nickname"] == "Test Author"


@pytest.mark.unit
async def test_douyin_parser_parses_share_link(tmp_path):
    parser = DouyinParser()
    with patch("aipulse.video.parsers.douyin.DouyinApiClient") as mock_client_cls:
        mock_client_cls.return_value = DouyinApiClient(client=_mock_httpx_client(SHARE_HTML))
        result = await parser.parse("https://v.douyin.com/xB-D6KXF8Ps/", tmp_path)

    assert isinstance(result, ParsedContent)
    assert result.platform == "douyin"
    assert result.title == "Test Title"
    assert result.metadata["author"] == "Test Author"
    assert result.metadata["duration"] == 60


@pytest.mark.unit
async def test_douyin_api_client_download_creates_directory(tmp_path):
    async def _aiter_bytes():
        for chunk in [b"video", b"data"]:
            yield chunk

    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.aiter_bytes = _aiter_bytes

    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    client.stream = MagicMock()
    client.stream.return_value.__aenter__ = AsyncMock(return_value=response)
    client.stream.return_value.__aexit__ = AsyncMock(return_value=None)

    api_client = DouyinApiClient(client=client)
    work_dir = tmp_path / "task_1"
    filepath = work_dir / "test.mp4"
    await api_client.download("https://play.com/test.mp4", filepath)

    assert filepath.exists()
    assert filepath.read_bytes() == b"videodata"


async def async_iter(chunks):
    for chunk in chunks:
        yield chunk
