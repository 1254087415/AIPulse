"""Embedded subtitle strategy via yt-dlp."""

import logging
from pathlib import Path
from typing import Any

import yt_dlp

from aipulse.video.parsers.base import ParsedContent
from aipulse.video.subtitle.base import SubtitleResult, SubtitleStrategy

logger = logging.getLogger(__name__)


class EmbeddedSubtitleStrategy(SubtitleStrategy):
    """Download embedded subtitles using yt-dlp."""

    async def is_available(self, content: ParsedContent) -> bool:
        return content.platform in {"youtube", "generic_video"}

    async def fetch(self, content: ParsedContent, work_dir: Path) -> SubtitleResult:
        if not content.url:
            return SubtitleResult(text=None, source="embedded")

        subtitle_path = work_dir / "subtitle.srt"
        ydl_opts: dict[str, Any] = {
            "quiet": True,
            "skip_download": True,
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": ["zh-CN", "zh-Hans", "zh", "en"],
            "subtitlesformat": "srt",
            "outtmpl": str(work_dir / "subtitle"),
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([content.url])
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to download embedded subtitles: %s", exc)
            return SubtitleResult(text=None, source="embedded")

        if subtitle_path.exists():
            return SubtitleResult(
                text=subtitle_path.read_text(encoding="utf-8"),
                source="embedded",
                path=subtitle_path,
            )
        return SubtitleResult(text=None, source="embedded")
