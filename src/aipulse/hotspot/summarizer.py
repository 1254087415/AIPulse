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
    """Analyze hotspot content using an LLM adapter.

    Falls back to a simple heuristic when no LLM API key is configured so that
    the hotspot stream still works in development or offline setups.
    """
    if adapter is None:
        settings = get_settings()
        api_key = settings.llm_api_key.get_secret_value() if settings.llm_api_key else ""
        if not api_key:
            logger.warning("No LLM API key configured; using heuristic analysis")
            return _heuristic_analysis(keyword, content)
        adapter = OpenAICompatibleAdapter(settings)

    prompt = _build_prompt(keyword, content)
    response = await adapter.complete(prompt)
    data = _parse_analysis(response)
    return HotspotAnalysis(**data)


def _heuristic_analysis(keyword: str, content: str) -> HotspotAnalysis:
    """Rule-based analysis used when no LLM is available.

    Treats all non-empty items as real with medium importance so the stream
    remains populated. Keyword matches increase relevance.
    """
    text = (content or "").lower()
    keyword_lower = (keyword or "").lower()
    relevance = 70
    if keyword_lower and keyword_lower in text:
        relevance = 85
    return HotspotAnalysis(
        is_real=True,
        relevance=relevance,
        importance="medium",
        summary=(content or "")[:120],
        category="industry",
    )


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
