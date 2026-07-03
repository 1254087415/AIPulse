"""Tests for video parsers.

Exercises ParserRegistry.resolve, ContentParser.can_parse, and ContentParser.parse for all platforms.
"""

from unittest.mock import patch

import pytest

from aipulse.video.parsers.bilibili import BilibiliParser
from aipulse.video.parsers.douyin import DouyinParser
from aipulse.video.parsers.generic import GenericParser
from aipulse.video.parsers.registry import ParserRegistry, get_parser_registry
from aipulse.video.parsers.xiaohongshu import XiaohongshuParser
from aipulse.video.parsers.youtube import YoutubeParser


@pytest.fixture
def sample_info():
    return {
        "title": "Sample Title",
        "description": "Sample description",
        "uploader": "Uploader Name",
        "duration": 120,
        "thumbnail": "https://example.com/thumb.jpg",
        "original_url": "https://example.com/video",
    }


async def test_bilibili_parser_can_parse():
    parser = BilibiliParser()
    assert await parser.can_parse("https://www.bilibili.com/video/BV1xx411c7mD")
    assert not await parser.can_parse("https://youtube.com/watch")


async def test_bilibili_parser_parse(sample_info, tmp_path):
    parser = BilibiliParser()
    with patch("aipulse.video.parsers._yt_dlp.yt_dlp.YoutubeDL") as mock_ydl:
        instance = mock_ydl.return_value.__enter__.return_value
        instance.extract_info.return_value = sample_info
        result = await parser.parse("https://bilibili.com/video", tmp_path)

    assert result.platform == "bilibili"
    assert result.title == "Sample Title"
    assert result.metadata["author"] == "Uploader Name"


async def test_youtube_parser_can_parse():
    parser = YoutubeParser()
    assert await parser.can_parse("https://www.youtube.com/watch?v=123")
    assert await parser.can_parse("https://youtu.be/123")
    assert not await parser.can_parse("https://bilibili.com/video")


async def test_douyin_parser_can_parse():
    parser = DouyinParser()
    assert await parser.can_parse("https://www.douyin.com/video/123")
    assert not await parser.can_parse("https://youtube.com/watch")


async def test_xiaohongshu_parser_can_parse():
    parser = XiaohongshuParser()
    assert await parser.can_parse("https://www.xiaohongshu.com/explore/123")
    assert await parser.can_parse("https://xhslink.com/abc")
    assert not await parser.can_parse("https://youtube.com/watch")


async def test_generic_parser_can_parse():
    parser = GenericParser()
    assert await parser.can_parse("https://any-site.com/video")


async def test_parser_registry_resolve():
    registry = ParserRegistry()
    registry.register(BilibiliParser())
    registry.register(YoutubeParser())
    registry.register(GenericParser())

    assert isinstance(registry.resolve("https://bilibili.com/video"), BilibiliParser)
    assert isinstance(registry.resolve("https://youtube.com/watch"), YoutubeParser)
    assert isinstance(registry.resolve("https://unknown.com"), GenericParser)


def test_get_parser_registry_singleton():
    reg1 = get_parser_registry()
    reg2 = get_parser_registry()
    assert reg1 is reg2


def test_default_parsers_registered():
    registry = get_parser_registry()
    parser = registry.resolve("https://www.bilibili.com/video/BV1xx411c7mD")
    assert isinstance(parser, BilibiliParser)


async def test_extract_info_not_dict(tmp_path):
    parser = BilibiliParser()
    with patch("aipulse.video.parsers._yt_dlp.yt_dlp.YoutubeDL") as mock_ydl:
        instance = mock_ydl.return_value.__enter__.return_value
        instance.extract_info.return_value = None
        result = await parser.parse("https://bilibili.com/video", tmp_path)
        assert result.title is None


async def test_parser_parse_returns_metadata(sample_info, tmp_path):
    parser = YoutubeParser()
    with patch("aipulse.video.parsers._yt_dlp.yt_dlp.YoutubeDL") as mock_ydl:
        instance = mock_ydl.return_value.__enter__.return_value
        instance.extract_info.return_value = sample_info
        result = await parser.parse("https://youtube.com/watch", tmp_path)

    assert result.metadata["duration"] == 120
    assert result.metadata["thumbnail"] == "https://example.com/thumb.jpg"
