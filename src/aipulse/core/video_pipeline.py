"""Concrete video processing pipeline (Template Method pattern)."""

import logging
from dataclasses import dataclass
from typing import Any

from aipulse.archive.base import ArchivePaths
from aipulse.archive.obsidian import ObsidianArchiver
from aipulse.core.config import AppSettings
from aipulse.core.content_router import classify_url
from aipulse.core.pipeline import BasePipeline, PipelineContext
from aipulse.pushers.base import PushMessage
from aipulse.pushers.registry import get_push_registry
from aipulse.summarizers.factory import SummarizerFactory
from aipulse.video.downloader import VideoDownloader
from aipulse.video.parsers.base import ParsedContent
from aipulse.video.parsers.registry import get_parser_registry
from aipulse.video.subtitle.registry import get_subtitle_registry
from aipulse.video.transcriber import AudioTranscriber

logger = logging.getLogger(__name__)


@dataclass
class VideoPipelineDeps:
    """Injectable dependencies for video pipeline tests."""

    downloader: VideoDownloader | None = None
    transcriber: AudioTranscriber | None = None
    archiver: ObsidianArchiver | None = None


class VideoPipeline(BasePipeline):
    """End-to-end pipeline for video URLs."""

    def __init__(
        self,
        settings: AppSettings,
        deps: VideoPipelineDeps | None = None,
    ) -> None:
        super().__init__()
        self.settings = settings
        self.deps = deps or VideoPipelineDeps()
        self._downloader = deps.downloader if deps else None
        self._transcriber = deps.transcriber if deps else None
        self._archiver = deps.archiver if deps else None

    async def _classify(self, ctx: PipelineContext) -> PipelineContext:
        content_type = await classify_url(ctx.url)
        ctx.content_type = content_type.value
        return ctx

    async def _fetch(self, ctx: PipelineContext) -> PipelineContext:
        registry = get_parser_registry()
        parser = registry.resolve(ctx.url)
        if parser is None:
            raise ValueError(f"no parser available for {ctx.url}")

        parser_download = getattr(parser, "download", None)
        if callable(parser_download):
            downloaded = await parser_download(ctx.url, self.settings.download_dir, ctx.task_id)
        else:
            downloader = self._downloader or VideoDownloader(self.settings.download_dir)
            downloaded = await downloader.download(ctx.url, ctx.task_id)
        work_dir = downloaded["work_dir"]

        parsed = await parser.parse(ctx.url, work_dir)
        parsed.video_path = downloaded.get("video_path")
        parsed.audio_path = downloaded.get("audio_path")

        ctx.downloaded_path = work_dir
        ctx.metadata.update(self._parsed_metadata(parsed))
        self._parsed_content = parsed
        return ctx

    async def _extract_text(self, ctx: PipelineContext) -> PipelineContext:
        parsed = getattr(self, "_parsed_content", None)
        if not isinstance(parsed, ParsedContent):
            raise RuntimeError("fetch stage did not produce parsed content")

        subtitle_registry = get_subtitle_registry()
        if ctx.downloaded_path is None:
            raise RuntimeError("download path not set")
        result = await subtitle_registry.fetch(parsed, ctx.downloaded_path)

        if result.text:
            ctx.transcript = result.text
            return ctx

        audio_path = parsed.audio_path or parsed.video_path
        if audio_path is None:
            raise RuntimeError("no subtitle or audio available for transcription")

        transcriber = self._transcriber or AudioTranscriber(model_size=self.settings.whisper_model)
        ctx.transcript = await transcriber.transcribe(audio_path)
        return ctx

    async def _summarize(self, ctx: PipelineContext) -> PipelineContext:
        if not ctx.transcript:
            raise RuntimeError("no transcript available to summarize")

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

        parsed = getattr(self, "_parsed_content", None)
        archiver = self._archiver or ObsidianArchiver(self.settings)
        paths = await archiver.archive(
            content=parsed,
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

    def _parsed_metadata(self, parsed: ParsedContent) -> dict[str, Any]:
        return {
            "title": parsed.title,
            "platform": parsed.platform,
            **parsed.metadata,
        }

    def _archive_metadata(self, paths: ArchivePaths) -> dict[str, Any]:
        return {
            "source_note_path": str(paths.source_note_path),
            "summary_note_path": str(paths.summary_note_path),
        }
