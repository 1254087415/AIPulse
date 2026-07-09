"""AI-powered hotspot analysis and summarization."""

import json
import logging
from dataclasses import dataclass
from typing import Any, cast

from aipulse.core.config import get_settings
from aipulse.summarizers.llm import OpenAICompatibleAdapter

VALID_IMPORTANCE = {"low", "medium", "high", "critical"}
VALID_CATEGORY = {"ai-models", "ai-products", "industry", "paper", "tip"}

logger = logging.getLogger(__name__)


@dataclass
class HotspotAnalysis:
    is_real: bool
    relevance: int
    importance: str
    summary: str
    category: str


async def analyze_hotspot(
    keyword: str,
    content: str,
    adapter: Any | None = None,
) -> HotspotAnalysis:
    """Analyze hotspot content using an LLM adapter."""
    adapter = adapter or OpenAICompatibleAdapter(get_settings())
    prompt = _build_prompt(keyword, content)
    response = await adapter.complete(prompt)
    data = _parse_analysis(response)
    return HotspotAnalysis(**data)


def _build_prompt(keyword: str, content: str) -> str:
    return f"""Analyze the following content about '{keyword}'. Return JSON only:
{{"is_real": bool, "relevance": 0-100, "importance": "low|medium|high|critical", "summary": "one sentence in Chinese", "category": "ai-models|ai-products|industry|paper|tip"}}

Content: {content[:2000]}
"""


def _parse_analysis(response: str) -> dict[str, Any]:
    try:
        data = cast(dict[str, Any], json.loads(response))
    except json.JSONDecodeError:
        logger.warning("LLM response is not valid JSON, using conservative defaults")
        return {
            "is_real": False,
            "relevance": 0,
            "importance": "low",
            "summary": "",
            "category": "industry",
        }
    if data.get("importance") not in VALID_IMPORTANCE:
        data["importance"] = "medium"
    if data.get("category") not in VALID_CATEGORY:
        data["category"] = "industry"
    data["relevance"] = max(0, min(100, int(data.get("relevance", 0))))
    return data
