"""Article summarizer implementation."""

import logging

from aipulse.summarizers.base import Summarizer, SummaryResult, extract_json_from_llm_response
from aipulse.summarizers.llm import OpenAICompatibleAdapter

logger = logging.getLogger(__name__)

DEFAULT_MAX_ARTICLE_TOKENS = 16000


class ArticleSummarizer(Summarizer):
    """Summarize article text using an LLM."""

    def __init__(self, adapter: OpenAICompatibleAdapter) -> None:
        self.adapter = adapter

    async def summarize(
        self,
        text: str,
        title: str | None = None,
        content_type: str = "",
    ) -> SummaryResult:
        """Summarize an article into a structured result."""
        safe_title = title or "未命名文章"
        system_prompt = (
            "你是一个中文文章总结助手。请用 JSON 格式输出，不要加 markdown 代码块，直接输出 JSON：\n"
            '{"title": "...", "summary": "...", "key_points": ["..."], "tags": ["..."]}\n'
            "要求：\n"
            "- title 用一句话概括文章主题\n"
            "- summary 用 2-4 段中文总结核心论点\n"
            "- key_points 列出 3-7 个关键要点\n"
            "- tags 给出 3-5 个分类标签"
        )
        user_prompt = self._build_prompt(safe_title, text)

        response = await self.adapter.complete(
            prompt=user_prompt,
            system=system_prompt,
        )

        return self._parse_response(response, safe_title)

    def _build_prompt(self, title: str, article_text: str) -> str:
        trimmed = article_text[:DEFAULT_MAX_ARTICLE_TOKENS]
        return f"标题：{title}\n\n正文：\n{trimmed}"

    def _parse_response(self, response: str, fallback_title: str) -> SummaryResult:
        data = extract_json_from_llm_response(response)
        if data is None:
            logger.warning("Failed to parse LLM response as JSON; using raw response")
            return SummaryResult(
                title=fallback_title,
                summary=response,
                key_points=[],
                tags=[],
                raw_markdown=response,
            )

        title = data.get("title") or fallback_title
        summary = data.get("summary", "")
        key_points = data.get("key_points", []) or data.get("key_moments", [])
        tags = data.get("tags", [])
        return SummaryResult(
            title=title,
            summary=summary,
            key_points=[str(point) for point in key_points],
            tags=[str(tag) for tag in tags],
            raw_markdown=response,
        )
