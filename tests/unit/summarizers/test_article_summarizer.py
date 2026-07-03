"""Tests for article summarizer prompt building and parsing."""

from unittest.mock import AsyncMock

import pytest

from aipulse.summarizers.article_summarizer import ArticleSummarizer
from aipulse.summarizers.base import SummaryResult
from aipulse.summarizers.llm import OpenAICompatibleAdapter


@pytest.fixture
def adapter() -> OpenAICompatibleAdapter:
    mock_adapter = OpenAICompatibleAdapter.__new__(OpenAICompatibleAdapter)
    mock_adapter.complete = AsyncMock()
    return mock_adapter


@pytest.mark.unit
async def test_article_summarizer_builds_prompt(adapter: OpenAICompatibleAdapter) -> None:
    summarizer = ArticleSummarizer(adapter)
    adapter.complete.return_value = (
        '{"title": "T", "summary": "S", "key_points": ["P"], "tags": ["tag"]}'
    )

    result = await summarizer.summarize("article body", title="My Article")

    assert isinstance(result, SummaryResult)
    assert result.title == "T"
    assert result.summary == "S"
    assert result.key_points == ["P"]
    assert result.tags == ["tag"]
    call_args = adapter.complete.await_args
    assert "My Article" in call_args.kwargs["prompt"]
    assert "article body" in call_args.kwargs["prompt"]


@pytest.mark.unit
async def test_article_summarizer_falls_back_to_raw_response(adapter: OpenAICompatibleAdapter) -> None:
    summarizer = ArticleSummarizer(adapter)
    adapter.complete.return_value = "raw summary"

    result = await summarizer.summarize("article body")

    assert result.title == "未命名文章"
    assert result.summary == "raw summary"
    assert result.key_points == []
    assert result.tags == []
    assert result.raw_markdown == "raw summary"


@pytest.mark.unit
async def test_article_summarizer_parses_fenced_json(adapter: OpenAICompatibleAdapter) -> None:
    summarizer = ArticleSummarizer(adapter)
    adapter.complete.return_value = (
        '```json\n{"title": "Fenced", "summary": "S", "key_points": ["P"], "tags": ["tag"]}\n```'
    )

    result = await summarizer.summarize("article body")

    assert result.title == "Fenced"
    assert result.summary == "S"
    assert result.key_points == ["P"]
    assert result.tags == ["tag"]
