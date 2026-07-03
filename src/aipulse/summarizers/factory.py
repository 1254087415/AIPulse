"""Summarizer factory."""

from aipulse.core.config import AppSettings
from aipulse.summarizers.article_summarizer import ArticleSummarizer
from aipulse.summarizers.base import Summarizer
from aipulse.summarizers.llm import OpenAICompatibleAdapter
from aipulse.summarizers.video_summarizer import VideoSummarizer


class SummarizerFactory:
    """Factory for creating summarizer strategies."""

    @staticmethod
    def get_summarizer(
        settings: AppSettings,
        content_type: str = "",
        adapter: OpenAICompatibleAdapter | None = None,
    ) -> Summarizer:
        """Return a summarizer suitable for the given content type."""
        resolved_adapter = adapter or OpenAICompatibleAdapter(settings)
        normalized = content_type.lower()
        if normalized in {"youtube", "bilibili", "douyin", "xiaohongshu", "generic_video", "video"}:
            return VideoSummarizer(resolved_adapter)
        return ArticleSummarizer(resolved_adapter)
