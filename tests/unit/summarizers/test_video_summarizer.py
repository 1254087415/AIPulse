"""Tests for video summarizer prompt building and parsing."""

from unittest.mock import AsyncMock

import pytest

from aipulse.summarizers.base import SummaryResult
from aipulse.summarizers.llm import OpenAICompatibleAdapter
from aipulse.summarizers.video_summarizer import VideoSummarizer


@pytest.fixture
def adapter() -> OpenAICompatibleAdapter:
    mock_adapter = OpenAICompatibleAdapter.__new__(OpenAICompatibleAdapter)
    mock_adapter.complete = AsyncMock()
    return mock_adapter


@pytest.mark.unit
async def test_video_summarizer_builds_prompt(adapter: OpenAICompatibleAdapter) -> None:
    summarizer = VideoSummarizer(adapter)
    adapter.complete.return_value = (
        '{"title": "T", "summary": "S", "key_points": ["P"], "tags": ["tag"]}'
    )

    result = await summarizer.summarize("transcript text", title="My Video")

    assert isinstance(result, SummaryResult)
    assert result.title == "T"
    assert result.summary == "S"
    assert result.key_points == ["P"]
    assert result.tags == ["tag"]
    call_args = adapter.complete.await_args
    assert "My Video" in call_args.kwargs["prompt"]
    assert "transcript text" in call_args.kwargs["prompt"]


@pytest.mark.unit
async def test_video_summarizer_falls_back_to_raw_response(
    adapter: OpenAICompatibleAdapter,
) -> None:
    summarizer = VideoSummarizer(adapter)
    adapter.complete.return_value = "raw summary"

    result = await summarizer.summarize("transcript text")

    assert result.title == "未知视频"
    assert result.summary == "raw summary"
    assert result.key_points == []
    assert result.tags == []
    assert result.raw_markdown == "raw summary"


@pytest.mark.unit
async def test_video_summarizer_parses_fenced_json(adapter: OpenAICompatibleAdapter) -> None:
    summarizer = VideoSummarizer(adapter)
    adapter.complete.return_value = (
        '```json\n{"title": "Fenced", "summary": "S", "key_points": ["P"], "tags": ["tag"]}\n```'
    )

    result = await summarizer.summarize("transcript text")

    assert result.title == "Fenced"
    assert result.summary == "S"
    assert result.key_points == ["P"]
    assert result.tags == ["tag"]


@pytest.mark.unit
def test_video_prompt_trims_long_transcript(adapter: OpenAICompatibleAdapter) -> None:
    summarizer = VideoSummarizer(adapter)
    long_text = "x" * 20000
    prompt = summarizer._build_prompt("Title", long_text)
    assert len(prompt) < 17000
