"""Generic video parser fallback."""

from pathlib import Path

from aipulse.video.parsers._yt_dlp import extract_with_yt_dlp
from aipulse.video.parsers.base import ContentParser, ParsedContent


class GenericParser(ContentParser):
    """Fallback parser for any URL that yt-dlp can handle."""

    @property
    def supported_domains(self) -> list[str]:
        return []

    async def can_parse(self, url: str) -> bool:
        return True

    async def parse(self, url: str, work_dir: Path) -> ParsedContent:
        return await extract_with_yt_dlp(url, work_dir, "generic_video")
