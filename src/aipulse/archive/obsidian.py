"""Obsidian archiver implementation."""

import logging
import re
from datetime import UTC, datetime
from urllib.parse import urlparse

from aipulse.archive.base import ArchivePaths, Archiver
from aipulse.archive.builder import ObsidianNoteBuilder, format_archived_at
from aipulse.core.config import AppSettings
from aipulse.summarizers.base import SummaryResult

logger = logging.getLogger(__name__)

SOURCE_SUBDIR = "工作学习/已归档"
SUMMARY_SUBDIR = "工作学习/AI/AI总结文档"


class ObsidianArchiver(Archiver):
    """Archive source and summary notes to an Obsidian vault."""

    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings
        self.vault_path = settings.obsidian_vault_path

    def is_configured(self) -> bool:
        return self.vault_path.exists() and self.vault_path.is_dir()

    async def archive(
        self,
        content: object,
        summary: SummaryResult,
        transcript: str | None,
        settings: AppSettings,
    ) -> ArchivePaths:
        """Archive source and summary notes to the configured Obsidian vault."""
        if not self.is_configured():
            raise FileNotFoundError(f"Obsidian vault path does not exist: {self.vault_path}")

        content_type = getattr(content, "platform", "unknown") or "unknown"
        url = getattr(content, "url", "") or ""
        author = getattr(content, "author", None)
        title = summary.title or getattr(content, "title", None) or "untitled"
        archived_at = format_archived_at(datetime.now(UTC))
        slug = _build_slug(title, url)

        source_dir = self.vault_path / SOURCE_SUBDIR / content_type
        summary_dir = self.vault_path / SUMMARY_SUBDIR
        source_dir.mkdir(parents=True, exist_ok=True)
        summary_dir.mkdir(parents=True, exist_ok=True)

        source_path = source_dir / f"{slug}.md"
        summary_path = summary_dir / f"{slug}.md"

        frontmatter = {
            "title": title,
            "url": url,
            "platform": content_type,
            "archived_at": archived_at,
        }

        builder = (
            ObsidianNoteBuilder()
            .with_frontmatter(frontmatter)
            .with_title(title)
            .with_url(url)
            .with_author(author)
            .with_platform(content_type)
            .with_archived_at(archived_at)
            .with_transcript(transcript or "")
            .with_summary(summary)
        )

        source_path.write_text(builder.build_source_note(), encoding="utf-8")
        summary_path.write_text(builder.build_summary_note(), encoding="utf-8")
        logger.info("Archived notes to %s and %s", source_path, summary_path)

        return ArchivePaths(
            source_note_path=source_path,
            summary_note_path=summary_path,
        )


def _build_slug(title: str, url: str) -> str:
    """Build a filesystem-safe slug from the title or URL."""
    base = title.strip() if title.strip() else _slug_from_url(url)
    slug = re.sub(r"[^\w\s-]", "", base).strip().lower()
    slug = re.sub(r"[-\s]+", "-", slug)
    return slug or "untitled"


def _slug_from_url(url: str) -> str:
    """Extract a usable identifier from a URL path."""
    parsed = urlparse(url)
    path = parsed.path.strip("/")
    if not path:
        return parsed.netloc or "untitled"
    last_segment = path.split("/")[-1]
    return re.sub(r"[^\w\s-]", "", last_segment) or "untitled"
