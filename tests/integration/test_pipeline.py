"""Integration tests for concrete pipelines."""

from dataclasses import dataclass
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aipulse.archive.obsidian import ObsidianArchiver
from aipulse.article.base import ExtractedArticle
from aipulse.core.article_pipeline import ArticlePipeline, ArticlePipelineDeps
from aipulse.core.config import AppSettings
from aipulse.core.content_router import ContentType
from aipulse.core.pipeline import PipelineContext
from aipulse.core.video_pipeline import VideoPipeline, VideoPipelineDeps
from aipulse.pushers.base import PushStrategy
from aipulse.summarizers.base import SummaryResult
from aipulse.video.parsers.base import ContentParser, ParsedContent
from aipulse.video.subtitle.base import SubtitleResult, SubtitleStrategy
from aipulse.video.transcriber import AudioTranscriber


@pytest.fixture
def settings(tmp_path: Path) -> AppSettings:
    return AppSettings(
        data_dir=tmp_path / "data",
        download_dir=tmp_path / "data" / "downloads",
        obsidian_vault_path=tmp_path / "vault",
    )


@pytest.fixture
def vault_path(settings: AppSettings) -> Path:
    settings.obsidian_vault_path.mkdir(parents=True, exist_ok=True)
    return settings.obsidian_vault_path


@dataclass
class FakeParsedContent:
    """Minimal parsed content stand-in for archiver tests."""

    platform: str
    url: str
    title: str | None
    author: str | None = None


class FakeParser(ContentParser):
    """Parser that returns canned metadata without network calls."""

    @property
    def supported_domains(self) -> list[str]:
        return ["example.com"]

    async def can_parse(self, url: str) -> bool:
        return True

    async def parse(self, url: str, work_dir: Path) -> ParsedContent:
        return ParsedContent(
            platform="generic_video",
            url=url,
            title="Fake Video",
            metadata={"author": "Tester"},
        )


class FakeVideoHandler:
    """Force video classification for test URLs."""

    async def handle(self, url: str) -> str:
        return "generic_video"


class FakeSubtitleStrategy(SubtitleStrategy):
    """Subtitle strategy that returns canned text."""

    def __init__(self, text: str | None = "fake subtitle"):
        self.text = text

    async def is_available(self, content: ParsedContent) -> bool:
        return True

    async def fetch(self, content: ParsedContent, work_dir: Path) -> SubtitleResult:
        return SubtitleResult(text=self.text, source="fake")


class FakeDownloader:
    """Downloader that creates a fake work directory."""

    def __init__(self, download_dir: Path):
        self.download_dir = download_dir

    async def download(self, url: str, task_id: str) -> dict:
        work_dir = self.download_dir / task_id
        work_dir.mkdir(parents=True, exist_ok=True)
        audio_path = work_dir / "audio.mp3"
        audio_path.write_text("dummy audio")
        return {
            "video_path": audio_path,
            "audio_path": audio_path,
            "work_dir": work_dir,
        }


@pytest.fixture
def summary_result() -> SummaryResult:
    return SummaryResult(
        title="Test Summary",
        summary="A short summary.",
        key_points=["Point one"],
        tags=["tag1"],
        raw_markdown="raw",
    )


class FakeParserWithDownload(FakeParser):
    """Parser that also provides its own download method."""

    async def download(self, url: str, download_dir: Path, task_id: str) -> dict:
        work_dir = download_dir / task_id
        work_dir.mkdir(parents=True, exist_ok=True)
        audio_path = work_dir / "downloaded.mp3"
        audio_path.write_text("parser-downloaded audio")
        return {
            "video_path": audio_path,
            "audio_path": audio_path,
            "work_dir": work_dir,
        }


@pytest.mark.integration
async def test_video_pipeline_uses_parser_download_when_available(
    settings: AppSettings,
    vault_path: Path,
    summary_result: SummaryResult,
) -> None:
    archiver = ObsidianArchiver(settings)
    pipeline = VideoPipeline(settings, deps=VideoPipelineDeps(archiver=archiver))

    async def fake_fetch(parsed: ParsedContent, work_dir: Path) -> SubtitleResult:
        return SubtitleResult(text="subtitle text", source="fake")

    with (
        patch("aipulse.core.video_pipeline.classify_url") as mock_classify,
        patch("aipulse.core.video_pipeline.get_parser_registry") as mock_parser_reg,
        patch("aipulse.core.video_pipeline.get_subtitle_registry") as mock_sub_reg,
        patch.object(
            VideoPipeline,
            "_summarize",
            side_effect=lambda ctx: setattr(ctx, "summary", summary_result) or ctx,
        ),
        patch("aipulse.core.video_pipeline.get_push_registry") as mock_push_reg,
    ):
        mock_classify.return_value = ContentType.DOUYIN
        parser = FakeParserWithDownload()
        mock_parser_reg.return_value.resolve.return_value = parser
        mock_sub_reg.return_value.fetch = fake_fetch
        mock_push_reg.return_value.list_configured.return_value = []

        ctx = PipelineContext(task_id="task-douyin", url="https://v.douyin.com/xxxxx/")
        result = await pipeline.run(ctx)

    assert result.content_type == "douyin"
    assert result.transcript == "subtitle text"
    assert result.summary == summary_result
    assert result.archive_paths is not None
    assert result.archive_paths.source_note_path.exists()


@pytest.mark.integration
async def test_video_pipeline_runs_end_to_end(
    settings: AppSettings,
    vault_path: Path,
    summary_result: SummaryResult,
) -> None:
    downloader = FakeDownloader(settings.download_dir)
    archiver = ObsidianArchiver(settings)

    deps = VideoPipelineDeps(
        downloader=downloader,  # type: ignore[arg-type]
        archiver=archiver,
    )
    pipeline = VideoPipeline(settings, deps=deps)

    fake_summarizer = AsyncMock()
    fake_summarizer.summarize.return_value = summary_result

    fake_pusher = MagicMock(spec=PushStrategy)
    fake_pusher.is_configured.return_value = True
    fake_pusher.send = AsyncMock(return_value=True)

    async def fake_fetch(parsed: ParsedContent, work_dir: Path) -> SubtitleResult:
        return SubtitleResult(text="subtitle text", source="fake")

    with (
        patch("aipulse.core.video_pipeline.classify_url") as mock_classify,
        patch("aipulse.core.video_pipeline.get_parser_registry") as mock_parser_reg,
        patch("aipulse.core.video_pipeline.get_subtitle_registry") as mock_sub_reg,
        patch.object(
            VideoPipeline,
            "_summarize",
            side_effect=lambda ctx: setattr(ctx, "summary", summary_result) or ctx,
        ),
        patch("aipulse.core.video_pipeline.get_push_registry") as mock_push_reg,
    ):
        mock_classify.return_value = ContentType.GENERIC_VIDEO
        mock_parser_reg.return_value.resolve.return_value = FakeParser()
        mock_sub_reg.return_value.fetch = fake_fetch
        mock_push_reg.return_value.list_configured.return_value = [fake_pusher]

        ctx = PipelineContext(task_id="task-1", url="https://example.com/video.mp4")
        result = await pipeline.run(ctx)

    assert result.content_type == "generic_video"
    assert result.transcript == "subtitle text"
    assert result.summary == summary_result
    assert result.archive_paths is not None
    assert result.archive_paths.source_note_path.exists()
    assert result.archive_paths.summary_note_path.exists()


@pytest.mark.integration
async def test_video_pipeline_falls_back_to_transcription(
    settings: AppSettings,
    vault_path: Path,
    summary_result: SummaryResult,
) -> None:
    downloader = FakeDownloader(settings.download_dir)
    archiver = ObsidianArchiver(settings)
    transcriber = AudioTranscriber(model_size="tiny")

    deps = VideoPipelineDeps(
        downloader=downloader,  # type: ignore[arg-type]
        transcriber=transcriber,
        archiver=archiver,
    )
    pipeline = VideoPipeline(settings, deps=deps)

    async def fake_fetch_none(parsed: ParsedContent, work_dir: Path) -> SubtitleResult:
        return SubtitleResult(text=None, source="none")

    with (
        patch("aipulse.core.video_pipeline.get_parser_registry") as mock_parser_reg,
        patch("aipulse.core.video_pipeline.get_subtitle_registry") as mock_sub_reg,
        patch.object(
            AudioTranscriber,
            "transcribe",
            return_value="transcribed text",
        ),
        patch.object(
            VideoPipeline,
            "_summarize",
            side_effect=lambda ctx: setattr(ctx, "summary", summary_result) or ctx,
        ),
        patch("aipulse.core.video_pipeline.get_push_registry") as mock_push_reg,
    ):
        mock_parser_reg.return_value.resolve.return_value = FakeParser()
        mock_sub_reg.return_value.fetch = fake_fetch_none
        mock_push_reg.return_value.list_configured.return_value = []

        ctx = PipelineContext(task_id="task-2", url="https://example.com/video.mp4")
        result = await pipeline.run(ctx)

    assert result.transcript == "transcribed text"
    assert result.summary == summary_result


@pytest.mark.integration
async def test_article_pipeline_runs_end_to_end(
    settings: AppSettings,
    vault_path: Path,
    summary_result: SummaryResult,
) -> None:

    archiver = ObsidianArchiver(settings)
    pipeline = ArticlePipeline(settings, deps=ArticlePipelineDeps(archiver=archiver))

    article = ExtractedArticle(
        url="https://example.com/article",
        title="Article Title",
        author="Author",
        content="Article body text.",
    )

    fake_extractor = AsyncMock()
    fake_extractor.extract.return_value = article

    fake_pusher = MagicMock(spec=PushStrategy)
    fake_pusher.is_configured.return_value = True
    fake_pusher.send = AsyncMock(return_value=True)

    with (
        patch("aipulse.core.article_pipeline.get_article_registry") as mock_reg,
        patch.object(
            ArticlePipeline,
            "_summarize",
            side_effect=lambda ctx: setattr(ctx, "summary", summary_result) or ctx,
        ),
        patch("aipulse.core.article_pipeline.get_push_registry") as mock_push_reg,
    ):
        mock_reg.return_value.resolve.return_value = fake_extractor
        mock_push_reg.return_value.list_configured.return_value = [fake_pusher]

        ctx = PipelineContext(task_id="task-3", url="https://example.com/article")
        result = await pipeline.run(ctx)

    assert result.content_type == "generic_article"
    assert result.transcript == "Article body text."
    assert result.summary == summary_result
    assert result.archive_paths is not None
    fake_extractor.extract.assert_awaited_once_with("https://example.com/article")


@pytest.mark.integration
async def test_article_pipeline_raises_when_no_extractor(
    settings: AppSettings,
) -> None:
    pipeline = ArticlePipeline(settings)
    with patch("aipulse.core.article_pipeline.get_article_registry") as mock_reg:
        mock_reg.return_value.resolve.return_value = None
        ctx = PipelineContext(task_id="task-4", url="https://unknown.com/article")
        with pytest.raises(ValueError, match="no article extractor available"):
            await pipeline.run(ctx)


@pytest.mark.integration
async def test_video_pipeline_raises_when_no_parser(
    settings: AppSettings,
) -> None:
    pipeline = VideoPipeline(settings)
    with patch("aipulse.core.video_pipeline.get_parser_registry") as mock_reg:
        mock_reg.return_value.resolve.return_value = None
        ctx = PipelineContext(task_id="task-5", url="https://unknown.com/video")
        with pytest.raises(ValueError, match="no parser available"):
            await pipeline.run(ctx)
