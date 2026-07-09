"""Tests for subtitle strategies.

Exercises SubtitleStrategyRegistry.resolve/fetch, SubtitleStrategy.is_available,
and SubtitleResult return values for Bilibili CC, embedded yt-dlp, and Whisper fallback.
"""

from pathlib import Path
from unittest.mock import patch

from aipulse.video.parsers.base import ParsedContent
from aipulse.video.subtitle.embedded import EmbeddedSubtitleStrategy
from aipulse.video.subtitle.platform_api import BilibiliSubtitleStrategy
from aipulse.video.subtitle.registry import (
    SubtitleStrategyRegistry,
    get_subtitle_registry,
)
from aipulse.video.subtitle.whisper import WhisperSubtitleStrategy


async def test_bilibili_strategy_available_for_bilibili():
    strategy = BilibiliSubtitleStrategy()
    content = ParsedContent(platform="bilibili", url="https://bilibili.com/video", title=None)
    assert await strategy.is_available(content)


async def test_bilibili_strategy_not_available_for_youtube():
    strategy = BilibiliSubtitleStrategy()
    content = ParsedContent(platform="youtube", url="https://youtube.com/watch", title=None)
    assert not await strategy.is_available(content)


async def test_bilibili_strategy_extracts_subtitle(tmp_path):
    strategy = BilibiliSubtitleStrategy()
    content = ParsedContent(platform="bilibili", url="https://bilibili.com/video/1", title=None)
    sub_info = {
        "subtitles": {
            "ai-zh": [
                {
                    "ext": "srt",
                    "data": "1\n00:00:00,000 --> 00:00:01,000\nHello\n\n2\n00:00:01,000 --> 00:00:02,000\nWorld\n",
                }
            ]
        }
    }

    with patch("aipulse.video.subtitle.platform_api.yt_dlp.YoutubeDL") as mock_ydl:
        instance = mock_ydl.return_value.__enter__.return_value
        instance.extract_info.return_value = sub_info
        result = await strategy.fetch(content, tmp_path)

    assert result.source == "bilibili_cc"
    assert result.text == "Hello\nWorld"


async def test_bilibili_strategy_returns_none_when_no_subtitles(tmp_path):
    strategy = BilibiliSubtitleStrategy()
    content = ParsedContent(platform="bilibili", url="https://bilibili.com/video/1", title=None)

    with patch("aipulse.video.subtitle.platform_api.yt_dlp.YoutubeDL") as mock_ydl:
        instance = mock_ydl.return_value.__enter__.return_value
        instance.extract_info.return_value = {"subtitles": {}}
        result = await strategy.fetch(content, tmp_path)

    assert result.text is None
    assert result.source == "bilibili"


async def test_embedded_strategy_available_for_youtube():
    strategy = EmbeddedSubtitleStrategy()
    content = ParsedContent(platform="youtube", url="https://youtube.com/watch", title=None)
    assert await strategy.is_available(content)


async def test_embedded_strategy_fetches_subtitle(tmp_path):
    strategy = EmbeddedSubtitleStrategy()
    content = ParsedContent(platform="youtube", url="https://youtube.com/watch", title=None)
    subtitle_file = tmp_path / "subtitle.srt"
    subtitle_file.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n", encoding="utf-8")

    with patch("aipulse.video.subtitle.embedded.yt_dlp.YoutubeDL") as mock_ydl:
        instance = mock_ydl.return_value.__enter__.return_value
        instance.download.side_effect = lambda _: subtitle_file.write_text(
            "1\n00:00:00,000 --> 00:00:01,000\nHello\n", encoding="utf-8"
        )
        result = await strategy.fetch(content, tmp_path)

    assert result.source == "embedded"
    assert "Hello" in (result.text or "")


async def test_whisper_strategy_available_when_audio_path_present():
    strategy = WhisperSubtitleStrategy()
    content = ParsedContent(
        platform="youtube",
        url="https://youtube.com/watch",
        title=None,
        audio_path=Path("/tmp/audio.mp3"),
    )
    assert await strategy.is_available(content)


async def test_whisper_strategy_transcribes(tmp_path):
    strategy = WhisperSubtitleStrategy()
    audio_path = tmp_path / "audio.mp3"
    audio_path.write_text("dummy")
    content = ParsedContent(
        platform="youtube",
        url="https://youtube.com/watch",
        title=None,
        audio_path=audio_path,
    )

    with patch.object(strategy._transcriber, "transcribe", return_value="transcribed text"):
        result = await strategy.fetch(content, tmp_path)

    assert result.source == "whisper"
    assert result.text == "transcribed text"


async def test_subtitle_registry_resolve():
    registry = SubtitleStrategyRegistry()
    registry.register(BilibiliSubtitleStrategy())
    registry.register(WhisperSubtitleStrategy())

    bilibili = ParsedContent(platform="bilibili", url="https://bilibili.com/video", title=None)
    youtube = ParsedContent(
        platform="youtube",
        url="https://youtube.com/watch",
        title=None,
        audio_path=Path("/tmp/audio.mp3"),
    )

    assert isinstance(await registry.resolve(bilibili), BilibiliSubtitleStrategy)
    assert isinstance(await registry.resolve(youtube), WhisperSubtitleStrategy)


async def test_subtitle_registry_fetch_none():
    registry = SubtitleStrategyRegistry()
    content = ParsedContent(platform="unknown", url="https://example.com", title=None)
    result = await registry.fetch(content, Path("/tmp"))
    assert result.source == "none"


def test_get_subtitle_registry_singleton():
    reg1 = get_subtitle_registry()
    reg2 = get_subtitle_registry()
    assert reg1 is reg2
