import pytest

from aipulse.hotspot.summarizer import HotspotAnalysis, analyze_hotspot


class FakeAdapter:
    def __init__(self, response: str):
        self._response = response

    async def complete(self, prompt: str, system: str | None = None) -> str:
        return self._response


@pytest.mark.unit
async def test_analyze_hotspot_returns_summary():
    fake = FakeAdapter(
        '{"is_real": true, "relevance": 80, "importance": "high", "summary": "测试摘要", "category": "ai-models"}'
    )
    result = await analyze_hotspot("OpenAI", "OpenAI releases GPT-5", adapter=fake)
    assert result.is_real is True
    assert result.importance == "high"
    assert result.summary == "测试摘要"
    assert result.category == "ai-models"
    assert result.relevance == 80
    assert isinstance(result, HotspotAnalysis)


@pytest.mark.unit
async def test_analyze_hotspot_uses_defaults_for_invalid_json():
    fake = FakeAdapter("not valid json")
    result = await analyze_hotspot("OpenAI", "OpenAI releases GPT-5", adapter=fake)
    assert result.is_real is False
    assert result.relevance == 0
    assert result.importance == "low"
    assert result.summary == ""
    assert result.category == "industry"
