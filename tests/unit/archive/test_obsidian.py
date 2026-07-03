"""Tests for Obsidian archiver."""

import pytest

from aipulse.archive.base import ArchivePaths
from aipulse.archive.obsidian import SOURCE_SUBDIR, SUMMARY_SUBDIR, ObsidianArchiver, _build_slug
from aipulse.core.config import AppSettings
from aipulse.summarizers.base import SummaryResult


class FakeContent:
    """Minimal content object for archiver tests."""

    def __init__(self, platform: str, url: str, title: str | None = None, author: str | None = None):
        self.platform = platform
        self.url = url
        self.title = title
        self.author = author


@pytest.fixture
def settings(tmp_path) -> AppSettings:
    return AppSettings(
        data_dir=tmp_path / "data",
        download_dir=tmp_path / "data" / "downloads",
        obsidian_vault_path=tmp_path / "vault",
    )


@pytest.fixture
def summary() -> SummaryResult:
    return SummaryResult(
        title="Test Title",
        summary="A short summary.",
        key_points=["Point one"],
        tags=["tag1"],
        raw_markdown="raw",
    )


@pytest.mark.unit
async def test_obsidian_archiver_writes_notes(settings: AppSettings, summary: SummaryResult) -> None:
    settings.obsidian_vault_path.mkdir(parents=True, exist_ok=True)
    archiver = ObsidianArchiver(settings)
    content = FakeContent(platform="youtube", url="https://example.com", author="Author")

    paths = await archiver.archive(content, summary, "transcript text", settings)

    assert isinstance(paths, ArchivePaths)
    assert paths.source_note_path.exists()
    assert paths.summary_note_path.exists()
    assert str(paths.source_note_path).endswith(f"{SOURCE_SUBDIR}/youtube/test-title.md")
    assert str(paths.summary_note_path).endswith(f"{SUMMARY_SUBDIR}/test-title.md")
    source_text = paths.source_note_path.read_text(encoding="utf-8")
    summary_text = paths.summary_note_path.read_text(encoding="utf-8")
    assert "Test Title" in source_text
    assert "transcript text" in source_text
    assert "Test Title 总结" in summary_text
    assert "Point one" in summary_text


@pytest.mark.unit
async def test_obsidian_archiver_is_configured(settings: AppSettings) -> None:
    archiver = ObsidianArchiver(settings)
    assert not archiver.is_configured()
    settings.obsidian_vault_path.mkdir(parents=True, exist_ok=True)
    assert archiver.is_configured()


@pytest.mark.unit
async def test_obsidian_archiver_raises_when_vault_missing(settings: AppSettings, summary: SummaryResult) -> None:
    archiver = ObsidianArchiver(settings)
    content = FakeContent(platform="youtube", url="https://example.com")

    with pytest.raises(FileNotFoundError, match="Obsidian vault path does not exist"):
        await archiver.archive(content, summary, None, settings)


@pytest.mark.unit
async def test_obsidian_archiver_handles_empty_summary(settings: AppSettings) -> None:
    settings.obsidian_vault_path.mkdir(parents=True, exist_ok=True)
    archiver = ObsidianArchiver(settings)
    content = FakeContent(platform="youtube", url="https://example.com")
    empty_summary = SummaryResult(
        title="Empty",
        summary="",
        key_points=[],
        tags=[],
        raw_markdown="",
    )

    paths = await archiver.archive(content, empty_summary, None, settings)

    summary_text = paths.summary_note_path.read_text(encoding="utf-8")
    assert "## 摘要" in summary_text
    assert "## 要点" not in summary_text
    assert "## 标签" not in summary_text


@pytest.mark.unit
async def test_obsidian_archiver_uses_content_title_when_summary_title_empty(
    settings: AppSettings,
) -> None:
    settings.obsidian_vault_path.mkdir(parents=True, exist_ok=True)
    archiver = ObsidianArchiver(settings)
    content = FakeContent(platform="youtube", url="https://example.com", title="Content Title")
    empty_title_summary = SummaryResult(
        title="",
        summary="Summary text.",
        key_points=[],
        tags=[],
        raw_markdown="",
    )

    paths = await archiver.archive(content, empty_title_summary, None, settings)

    source_text = paths.source_note_path.read_text(encoding="utf-8")
    assert "Content Title" in source_text


@pytest.mark.unit
def test_build_slug_from_title() -> None:
    assert _build_slug("Hello World", "") == "hello-world"


@pytest.mark.unit
def test_build_slug_from_url() -> None:
    assert _build_slug("", "https://example.com/path/to/page") == "page"


@pytest.mark.unit
def test_build_slug_sanitizes_special_characters() -> None:
    assert _build_slug("Title / With \\ Slashes", "") == "title-with-slashes"


@pytest.mark.unit
def test_build_slug_falls_back_to_untitled() -> None:
    assert _build_slug("", "") == "untitled"
    assert _build_slug("!!!", "") == "untitled"
