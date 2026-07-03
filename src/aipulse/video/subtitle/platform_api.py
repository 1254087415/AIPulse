"""Bilibili CC subtitle strategy."""

import logging
from pathlib import Path

import yt_dlp

from aipulse.core.config import get_settings
from aipulse.video.parsers.base import ParsedContent
from aipulse.video.subtitle.base import SubtitleResult, SubtitleStrategy

logger = logging.getLogger(__name__)


class BilibiliSubtitleStrategy(SubtitleStrategy):
    """Fetch Bilibili CC subtitles using yt-dlp (requires browser cookies)."""

    async def is_available(self, content: ParsedContent) -> bool:
        return content.platform == "bilibili"

    async def fetch(self, content: ParsedContent, work_dir: Path) -> SubtitleResult:
        if not content.url:
            return SubtitleResult(text=None, source="bilibili")

        settings = get_settings()
        ydl_opts: dict[str, object] = {
            "quiet": True,
            "skip_download": True,
            "noplaylist": True,
            "writesubtitles": True,
            "subtitleslangs": ["ai-zh"],
        }
        if settings.ytdlp_user_agent:
            ydl_opts["user_agent"] = settings.ytdlp_user_agent
        if settings.ytdlp_browser_cookies:
            ydl_opts["cookiesfrombrowser"] = (
                settings.ytdlp_browser_cookies,
                None,
                None,
                None,
            )

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(content.url, download=False)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to extract Bilibili subtitle info: %s", exc)
            return SubtitleResult(text=None, source="bilibili")

        if not isinstance(info, dict):
            return SubtitleResult(text=None, source="bilibili")

        subtitles = info.get("subtitles") or {}
        for lang in ("ai-zh", "danmaku"):
            entries = subtitles.get(lang, [])
            if entries:
                text = entries[0].get("data")
                if text:
                    return SubtitleResult(text=self._clean_srt(text), source="bilibili_cc")

        return SubtitleResult(text=None, source="bilibili")

    @staticmethod
    def _clean_srt(text: str) -> str:
        """Strip SRT timing markers and return plain subtitle text."""
        lines: list[str] = []
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.isdigit():
                continue
            if " --> " in stripped:
                continue
            lines.append(stripped)
        return "\n".join(lines)
