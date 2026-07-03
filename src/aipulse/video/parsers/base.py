"""Video parser strategy base classes."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ParsedContent:
    """Result of parsing a URL."""

    platform: str
    url: str
    title: str | None
    video_path: Path | None = None
    audio_path: Path | None = None
    subtitle_path: Path | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class ContentParser(ABC):
    """Strategy for parsing a content URL."""

    @property
    @abstractmethod
    def supported_domains(self) -> list[str]:
        """Return the list of supported domains."""

    @abstractmethod
    async def can_parse(self, url: str) -> bool:
        """Return True if this parser can handle the URL."""

    @abstractmethod
    async def parse(self, url: str, work_dir: Path) -> ParsedContent:
        """Parse the URL and return metadata plus downloaded media paths."""
