"""Obsidian note builder (Builder pattern)."""

from datetime import datetime
from typing import Any, Self

from aipulse.summarizers.base import SummaryResult


class ObsidianNoteBuilder:
    """Build an Obsidian markdown note step by step."""

    def __init__(self) -> None:
        self._frontmatter: dict[str, Any] = {}
        self._title: str = ""
        self._url: str = ""
        self._author: str | None = None
        self._platform: str = ""
        self._archived_at: str = ""
        self._transcript: str = ""
        self._summary: SummaryResult | None = None

    def with_frontmatter(self, data: dict[str, Any]) -> Self:
        self._frontmatter = dict(data)
        return self

    def with_title(self, title: str) -> Self:
        self._title = title
        return self

    def with_url(self, url: str) -> Self:
        self._url = url
        return self

    def with_author(self, author: str | None) -> Self:
        self._author = author
        return self

    def with_platform(self, platform: str) -> Self:
        self._platform = platform
        return self

    def with_archived_at(self, archived_at: str) -> Self:
        self._archived_at = archived_at
        return self

    def with_transcript(self, transcript: str) -> Self:
        self._transcript = transcript
        return self

    def with_summary(self, summary: SummaryResult) -> Self:
        self._summary = summary
        return self

    def build_source_note(self) -> str:
        """Build the source note markdown with YAML frontmatter."""
        frontmatter = dict(self._frontmatter)
        frontmatter.setdefault("title", self._title)
        frontmatter.setdefault("url", self._url)
        if self._author:
            frontmatter.setdefault("author", self._author)
        frontmatter.setdefault("platform", self._platform)
        frontmatter.setdefault("archived_at", self._archived_at)

        lines = [self._render_frontmatter(frontmatter), f"# {self._title}"]
        if self._url:
            lines.append(f"- 来源：{self._url}")
        if self._platform:
            lines.append(f"- 平台：{self._platform}")
        if self._author:
            lines.append(f"- 作者：{self._author}")
        if self._transcript:
            lines.extend(["", "## 转写", self._transcript])
        return "\n".join(lines)

    def build_summary_note(self) -> str:
        """Build the summary note markdown with YAML frontmatter."""
        frontmatter = dict(self._frontmatter)
        frontmatter.setdefault("title", f"{self._title} 总结")
        frontmatter.setdefault("url", self._url)
        frontmatter.setdefault("platform", self._platform)
        frontmatter.setdefault("archived_at", self._archived_at)

        lines = [self._render_frontmatter(frontmatter), f"# {self._title} 总结"]
        if self._summary is None:
            return "\n".join(lines)

        lines.extend(["", "## 摘要", self._summary.summary])
        if self._summary.key_points:
            lines.extend(["", "## 要点"])
            for point in self._summary.key_points:
                lines.append(f"- {point}")
        if self._summary.tags:
            lines.extend(["", "## 标签"])
            lines.append(", ".join(f"#{tag}" for tag in self._summary.tags))
        return "\n".join(lines)

    def _render_frontmatter(self, data: dict[str, Any]) -> str:
        lines = ["---"]
        for key, value in data.items():
            lines.append(f"{key}: {value}")
        lines.append("---")
        return "\n".join(lines)


def format_archived_at(dt: datetime) -> str:
    """Return an ISO-formatted archived timestamp."""
    return dt.isoformat()
