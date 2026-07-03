"""Subtitle strategy registry (factory)."""

from pathlib import Path

from aipulse.video.parsers.base import ParsedContent
from aipulse.video.subtitle.base import SubtitleResult, SubtitleStrategy


class SubtitleStrategyRegistry:
    """Factory that picks the best subtitle strategy for a platform."""

    def __init__(self) -> None:
        self._strategies: list[SubtitleStrategy] = []

    def register(self, strategy: SubtitleStrategy) -> None:
        """Register a subtitle strategy."""
        self._strategies.append(strategy)

    async def resolve(self, content: ParsedContent) -> SubtitleStrategy | None:
        """Return the first strategy that can provide subtitles."""
        for strategy in self._strategies:
            if await strategy.is_available(content):
                return strategy
        return None

    async def fetch(self, content: ParsedContent, work_dir: Path) -> SubtitleResult:
        """Fetch subtitles using the best available strategy."""
        strategy = await self.resolve(content)
        if strategy is None:
            return SubtitleResult(text=None, source="none")
        return await strategy.fetch(content, work_dir)


# Global registry populated at import time.
_registry: SubtitleStrategyRegistry | None = None


def get_subtitle_registry() -> SubtitleStrategyRegistry:
    """Return the singleton subtitle registry."""
    global _registry
    if _registry is None:
        _registry = SubtitleStrategyRegistry()
        _register_default_strategies(_registry)
    return _registry


def _register_default_strategies(registry: SubtitleStrategyRegistry) -> None:
    """Register built-in subtitle strategies."""
    from aipulse.video.subtitle.embedded import EmbeddedSubtitleStrategy
    from aipulse.video.subtitle.platform_api import BilibiliSubtitleStrategy
    from aipulse.video.subtitle.whisper import WhisperSubtitleStrategy

    registry.register(BilibiliSubtitleStrategy())
    registry.register(EmbeddedSubtitleStrategy())
    registry.register(WhisperSubtitleStrategy())
