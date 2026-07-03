"""Shared yt-dlp extraction helper for video parsers.

Internal helper used by all platform parsers to extract metadata via yt-dlp
without downloading. Returns a ParsedContent dataclass.
"""

from pathlib import Path
from typing import Any

import yt_dlp

from aipulse.core.config import get_settings
from aipulse.video.parsers.base import ParsedContent


def _yt_dlp_options() -> dict[str, Any]:
    """Build yt-dlp options with browser cookies and a realistic user agent."""
    settings = get_settings()
    opts: dict[str, Any] = {
        "quiet": True,
        "noplaylist": True,
        "skip_download": True,
    }
    if settings.ytdlp_user_agent:
        opts["user_agent"] = settings.ytdlp_user_agent
    if settings.ytdlp_browser_cookies:
        opts["cookiesfrombrowser"] = (settings.ytdlp_browser_cookies, None, None, None)
    return opts


async def extract_with_yt_dlp(url: str, work_dir: Path, platform: str) -> ParsedContent:
    """Extract metadata from a URL using yt-dlp without downloading."""
    ydl_opts = _yt_dlp_options()
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    if not isinstance(info, dict):
        return ParsedContent(platform=platform, url=url, title=None)

    return ParsedContent(
        platform=platform,
        url=url,
        title=info.get("title"),
        metadata={
            "description": info.get("description"),
            "author": info.get("uploader") or info.get("channel"),
            "duration": info.get("duration"),
            "thumbnail": info.get("thumbnail"),
            "original_url": info.get("original_url") or info.get("webpage_url") or url,
        },
    )
