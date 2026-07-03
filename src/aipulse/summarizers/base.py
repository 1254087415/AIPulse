"""Summarizer base classes and result types."""

import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class SummaryResult:
    """Result of summarizing content."""

    title: str
    summary: str
    key_points: list[str]
    tags: list[str]
    raw_markdown: str


class Summarizer(ABC):
    """Strategy for generating a summary from text."""

    @abstractmethod
    async def summarize(
        self,
        text: str,
        title: str | None = None,
        content_type: str = "",
    ) -> SummaryResult:
        """Summarize the provided text and return a structured result."""


def extract_json_from_llm_response(response: str) -> dict | None:
    """Strip markdown fences and parse the JSON object in an LLM response."""
    text = response.strip()
    if text.startswith("```"):
        # Drop the opening fence line and any language label.
        text = text.split("\n", 1)[1] if "\n" in text else ""
    if text.endswith("```"):
        text = text.rsplit("\n", 1)[0]
    text = text.strip()

    # If the response still contains a fenced block somewhere, extract it.
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None
