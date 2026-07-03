"""Tests for summarizer base types."""

import pytest

from aipulse.summarizers.base import SummaryResult


@pytest.mark.unit
def test_summary_result_creation() -> None:
    result = SummaryResult(
        title="Test Title",
        summary="A short summary.",
        key_points=["Point one", "Point two"],
        tags=["tag1", "tag2"],
        raw_markdown="# Markdown",
    )
    assert result.title == "Test Title"
    assert result.summary == "A short summary."
    assert result.key_points == ["Point one", "Point two"]
    assert result.tags == ["tag1", "tag2"]
    assert result.raw_markdown == "# Markdown"
