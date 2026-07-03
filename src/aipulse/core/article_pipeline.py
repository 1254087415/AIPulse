"""Concrete article processing pipeline (Template Method pattern)."""

import logging
from dataclasses import dataclass
from typing import Any

from aipulse.archive.base import ArchivePaths
from aipulse.archive.obsidian import ObsidianArchiver
from aipulse.article.base import ExtractedArticle
from aipulse.article.registry import get_article_registry
from aipulse.core.config import AppSettings
from aipulse.core.content_router import classify_url
from aipulse.core.pipeline import BasePipeline, PipelineContext
from aipulse.pushers.base import PushMessage
from aipulse.pushers.registry import get_push_registry
from aipulse.summarizers.factory import SummarizerFactory

logger = logging.getLogger(__name__)


@dataclass
class ArticlePipelineDeps:
    """Injectable dependencies for article pipeline tests."""

    archiver: ObsidianArchiver | None = None


class ArticlePipeline(BasePipeline):
    """End-to-end pipeline for article URLs."""

    def __init__(
        self,
        settings: AppSettings,
        deps: ArticlePipelineDeps | None = None,
    ) -> None:
        super().__init__()
        self.settings = settings
        self.deps = deps or ArticlePipelineDeps()
        self._archiver = deps.archiver if deps else None

    async def _classify(self, ctx: PipelineContext) -> PipelineContext:
        content_type = await classify_url(ctx.url)
        ctx.content_type = content_type.value
        return ctx

    async def _fetch(self, ctx: PipelineContext) -> PipelineContext:
        registry = get_article_registry()
        extractor = registry.resolve(ctx.url)
        if extractor is None:
            raise ValueError(f"no article extractor available for {ctx.url}")

        article = await extractor.extract(ctx.url)
        self._article = article
        ctx.metadata.update(self._article_metadata(article))
        return ctx

    async def _extract_text(self, ctx: PipelineContext) -> PipelineContext:
        article = getattr(self, "_article", None)
        if not isinstance(article, ExtractedArticle):
            raise RuntimeError("fetch stage did not produce an article")

        ctx.transcript = article.content
        return ctx

    async def _summarize(self, ctx: PipelineContext) -> PipelineContext:
        if not ctx.transcript:
            raise RuntimeError("no article text available to summarize")

        summarizer = SummarizerFactory.get_summarizer(
            self.settings,
            content_type=ctx.content_type,
        )
        title = ctx.metadata.get("title")
        ctx.summary = await summarizer.summarize(
            ctx.transcript,
            title=title,
            content_type=ctx.content_type,
        )
        return ctx

    async def _archive(self, ctx: PipelineContext) -> PipelineContext:
        if ctx.summary is None:
            raise RuntimeError("no summary available to archive")

        article = getattr(self, "_article", None)
        archiver = self._archiver or ObsidianArchiver(self.settings)
        paths = await archiver.archive(
            content=article,
            summary=ctx.summary,
            transcript=ctx.transcript,
            settings=self.settings,
        )
        ctx.archive_paths = paths
        ctx.metadata.update(self._archive_metadata(paths))
        return ctx

    async def _notify(self, ctx: PipelineContext) -> PipelineContext:
        summary = ctx.summary
        if summary is None:
            raise RuntimeError("no summary available to notify")

        registry = get_push_registry(self.settings)
        message = PushMessage(
            title=summary.title,
            summary=summary.summary,
            url=ctx.url,
            platform=ctx.content_type,
        )
        for strategy in registry.list_configured():
            try:
                await strategy.send(message)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Push strategy failed: %s", exc)
        return ctx

    def _article_metadata(self, article: ExtractedArticle) -> dict[str, Any]:
        return {
            "title": article.title,
            "author": article.author,
            "platform": "article",
        }

    def _archive_metadata(self, paths: ArchivePaths) -> dict[str, Any]:
        return {
            "source_note_path": str(paths.source_note_path),
            "summary_note_path": str(paths.summary_note_path),
        }
