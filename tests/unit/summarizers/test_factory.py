"""Tests for summarizer factory."""

from unittest.mock import MagicMock, patch

import pytest
from openai import AsyncOpenAI

from aipulse.core.config import AppSettings
from aipulse.summarizers.article_summarizer import ArticleSummarizer
from aipulse.summarizers.factory import SummarizerFactory
from aipulse.summarizers.llm import OpenAICompatibleAdapter
from aipulse.summarizers.video_summarizer import VideoSummarizer


@pytest.fixture
def settings(tmp_path) -> AppSettings:
    return AppSettings(
        data_dir=tmp_path / "data",
        download_dir=tmp_path / "data" / "downloads",
    )


@pytest.fixture
def adapter(settings: AppSettings) -> OpenAICompatibleAdapter:
    mock_client = MagicMock(spec=AsyncOpenAI)
    return OpenAICompatibleAdapter(settings, client=mock_client)


@pytest.mark.unit
def test_factory_returns_video_summarizer_for_video_types(
    settings: AppSettings, adapter: OpenAICompatibleAdapter
) -> None:
    for content_type in ("youtube", "bilibili", "douyin", "xiaohongshu", "generic_video", "video"):
        summarizer = SummarizerFactory.get_summarizer(settings, content_type, adapter=adapter)
        assert isinstance(summarizer, VideoSummarizer)


@pytest.mark.unit
def test_factory_returns_article_summarizer_for_unknown_types(
    settings: AppSettings, adapter: OpenAICompatibleAdapter
) -> None:
    for content_type in ("wechat_article", "rss_feed", "generic_article", "", "unknown"):
        summarizer = SummarizerFactory.get_summarizer(settings, content_type, adapter=adapter)
        assert isinstance(summarizer, ArticleSummarizer)


@pytest.mark.unit
def test_factory_is_case_insensitive(
    settings: AppSettings, adapter: OpenAICompatibleAdapter
) -> None:
    summarizer = SummarizerFactory.get_summarizer(settings, "YouTube", adapter=adapter)
    assert isinstance(summarizer, VideoSummarizer)
    summarizer = SummarizerFactory.get_summarizer(settings, "RSS", adapter=adapter)
    assert isinstance(summarizer, ArticleSummarizer)


@pytest.mark.unit
def test_factory_creates_adapter_when_none_provided(settings: AppSettings) -> None:
    with patch("aipulse.summarizers.factory.OpenAICompatibleAdapter") as mock_adapter_cls:
        mock_adapter = MagicMock(spec=OpenAICompatibleAdapter)
        mock_adapter_cls.return_value = mock_adapter
        summarizer = SummarizerFactory.get_summarizer(settings, "youtube")
        assert isinstance(summarizer, VideoSummarizer)
        mock_adapter_cls.assert_called_once_with(settings)
        assert summarizer.adapter is mock_adapter
