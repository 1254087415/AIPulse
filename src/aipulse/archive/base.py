"""Archive target base classes."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from aipulse.core.config import AppSettings
from aipulse.summarizers.base import SummaryResult


@dataclass
class ArchivePaths:
    """Paths to generated notes."""

    source_note_path: Path
    summary_note_path: Path


class Archiver(ABC):
    """Strategy for archiving content summaries."""

    @abstractmethod
    async def archive(
        self,
        content: object,
        summary: SummaryResult,
        transcript: str | None,
        settings: AppSettings,
    ) -> ArchivePaths:
        """Archive source and summary notes, returning their paths."""

    @abstractmethod
    def is_configured(self) -> bool:
        """Return True if the archiver is ready to write."""
