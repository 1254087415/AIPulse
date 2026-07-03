"""Video downloader using yt-dlp."""

from pathlib import Path

import yt_dlp

from aipulse.core.config import get_settings


class VideoDownloader:
    """Download video and audio from a URL."""

    def __init__(self, download_dir: Path):
        self.download_dir = download_dir

    async def download(self, url: str, task_id: str) -> dict:
        """Download video/audio and return file paths."""
        work_dir = self.download_dir / task_id
        work_dir.mkdir(parents=True, exist_ok=True)

        settings = get_settings()
        ydl_opts: dict[str, object] = {
            "format": "bestaudio/best",
            "outtmpl": str(work_dir / "%(title)s.%(ext)s"),
            "quiet": True,
            "noplaylist": True,
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

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

        return {
            "video_path": Path(filename),
            "audio_path": Path(filename),
            "work_dir": work_dir,
        }
