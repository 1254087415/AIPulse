"""Tests for Obsidian note builder."""

from datetime import UTC, datetime

import pytest

from aipulse.archive.builder import ObsidianNoteBuilder, format_archived_at
from aipulse.summarizers.base import SummaryResult


@pytest.fixture
def summary() -> SummaryResult:
    return SummaryResult(
        title="Test Title",
        summary="A short summary.",
        key_points=["Point one", "Point two"],
        tags=["tag1", "tag2"],
        raw_markdown="raw",
    )


@pytest.mark.unit
def test_source_note_markdown(summary: SummaryResult) -> None:
    archived_at = format_archived_at(datetime(2026, 6, 30, 12, 0, 0, tzinfo=UTC))
    note = (
        ObsidianNoteBuilder()
        .with_title("Test Title")
        .with_url("https://example.com")
        .with_platform("youtube")
        .with_author("Author")
        .with_archived_at(archived_at)
        .with_transcript("transcript text")
        .with_summary(summary)
        .build_source_note()
    )
    assert note.startswith("---")
    assert "title: Test Title" in note
    assert "url: https://example.com" in note
    assert "platform: youtube" in note
    assert "author: Author" in note
    assert "archived_at: 2026-06-30T12:00:00+00:00" in note
    assert "# Test Title" in note
    assert "transcript text" in note


@pytest.mark.unit
def test_summary_note_markdown(summary: SummaryResult) -> None:
    archived_at = format_archived_at(datetime(2026, 6, 30, 12, 0, 0, tzinfo=UTC))
    note = (
        ObsidianNoteBuilder()
        .with_title("Test Title")
        .with_url("https://example.com")
        .with_platform("youtube")
        .with_archived_at(archived_at)
        .with_summary(summary)
        .build_summary_note()
    )
    assert note.startswith("---")
    assert "title: Test Title 总结" in note
    assert "## 摘要" in note
    assert "## 要点" in note
    assert "- Point one" in note
    assert "## 标签" in note
    assert "#tag1" in note


@pytest.mark.unit
def test_summary_note_without_summary() -> None:
    archived_at = format_archived_at(datetime(2026, 6, 30, 12, 0, 0, tzinfo=UTC))
    note = (
        ObsidianNoteBuilder()
        .with_title("Test Title")
        .with_url("https://example.com")
        .with_platform("youtube")
        .with_archived_at(archived_at)
        .build_summary_note()
    )
    assert note.startswith("---")
    assert "# Test Title 总结" in note
    assert "## 摘要" not in note


@pytest.mark.unit
def test_summary_note_with_empty_summary() -> None:
    archived_at = format_archived_at(datetime(2026, 6, 30, 12, 0, 0, tzinfo=UTC))
    empty_summary = SummaryResult(
        title="",
        summary="",
        key_points=[],
        tags=[],
        raw_markdown="",
    )
    note = (
        ObsidianNoteBuilder()
        .with_title("Test Title")
        .with_url("https://example.com")
        .with_platform("youtube")
        .with_archived_at(archived_at)
        .with_summary(empty_summary)
        .build_summary_note()
    )
    assert "## 摘要" in note
    assert "## 要点" not in note
    assert "## 标签" not in note


@pytest.mark.unit
def test_format_archived_at() -> None:
    dt = datetime(2026, 6, 30, 12, 0, 0, tzinfo=UTC)
    assert format_archived_at(dt) == "2026-06-30T12:00:00+00:00"
