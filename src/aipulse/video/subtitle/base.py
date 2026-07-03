"""Subtitle strategy base classes."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from aipulse.video.parsers.base import ParsedContent


@dataclass
class SubtitleResult:
    """Result of fetching subtitles."""

    text: str | None
    source: str
    path: Path | None = None


class SubtitleStrategy(ABC):
    """Strategy for obtaining video subtitles."""

    @abstractmethod
    async def fetch(self, content: ParsedContent, work_dir: Path) -> SubtitleResult:
        """Return subtitles for the parsed content if available."""

    @abstractmethod
    async def is_available(self, content: ParsedContent) -> bool:
        """Return True if this strategy can provide subtitles."""
