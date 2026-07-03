"""Bilibili video parser."""

from pathlib import Path

from aipulse.video.parsers._yt_dlp import extract_with_yt_dlp
from aipulse.video.parsers.base import ContentParser, ParsedContent


class BilibiliParser(ContentParser):
    """Parse Bilibili video URLs."""

    @property
    def supported_domains(self) -> list[str]:
        return ["bilibili.com", "b23.tv"]

    async def can_parse(self, url: str) -> bool:
        return any(domain in url for domain in self.supported_domains)

    async def parse(self, url: str, work_dir: Path) -> ParsedContent:
        return await extract_with_yt_dlp(url, work_dir, "bilibili")
