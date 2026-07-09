"""Douyin video parser using share-link public API.

Supports v.douyin.com share links. Direct www.douyin.com/video/ links are
resolved from share redirects when possible.
"""

import json
import logging
import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx

from aipulse.video.parsers.base import ContentParser, ParsedContent

logger = logging.getLogger(__name__)

_MOBILE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 "
        "Mobile/15E148 Safari/604.1"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": "https://www.douyin.com/",
}

_URL_PATTERN = re.compile(r"https?://[^\s]+", re.IGNORECASE)
_DOUYIN_DOMAINS = ["douyin.com", "iesdouyin.com", "v.douyin.com"]


class DouyinApiClient:
    """Low-level client for Douyin share-link metadata and download."""

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is not None:
            return self._client
        # Disable environment proxy for Douyin to avoid SOCKS/HTTP proxy issues.
        return httpx.AsyncClient(
            headers=_MOBILE_HEADERS,
            follow_redirects=True,
            trust_env=False,
        )

    async def parse_share_link(self, url: str) -> dict:
        """Resolve a Douyin share link and return video item info."""
        share_url = self._extract_url(url)
        async with await self._get_client() as client:
            resolved = await self._resolve_redirect(client, share_url)
            video_id = self._extract_video_id(resolved)
            item_info = await self._fetch_item_info(client, video_id, resolved)
        return item_info

    async def download(self, media_url: str, filepath: Path) -> None:
        """Download a Douyin video to filepath, creating parent directories."""
        filepath.parent.mkdir(parents=True, exist_ok=True)
        temp_path = filepath.with_suffix(filepath.suffix + ".part")
        async with (
            await self._get_client() as client,
            client.stream("GET", media_url, follow_redirects=True) as resp,
        ):
            resp.raise_for_status()
            with temp_path.open("wb") as fh:
                async for chunk in resp.aiter_bytes():
                    if chunk:
                        fh.write(chunk)
        temp_path.rename(filepath)

    @staticmethod
    def _extract_url(text: str) -> str:
        match = _URL_PATTERN.search(text)
        if not match:
            raise ValueError("未找到有效的抖音链接")
        return match.group(0).strip().strip("\"'").rstrip(").,;!?'")

    async def _resolve_redirect(self, client: httpx.AsyncClient, share_url: str) -> str:
        resp = await client.get(share_url, follow_redirects=True)
        resp.raise_for_status()
        return str(resp.url)

    @staticmethod
    def _extract_video_id(url: str) -> str:
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        for key in ("modal_id", "item_ids", "group_id", "aweme_id"):
            values = query.get(key)
            if values:
                match = re.search(r"(\d{8,24})", values[0])
                if match:
                    return match.group(1)
        for pattern in (r"/video/(\d{8,24})", r"/note/(\d{8,24})", r"/(\d{8,24})(?:/|$)"):
            match = re.search(pattern, parsed.path)
            if match:
                return match.group(1)
        fallback = re.search(r"(\d{15,24})", url)
        if fallback:
            return fallback.group(1)
        raise ValueError("无法从链接中提取视频ID")

    async def _fetch_item_info(
        self, client: httpx.AsyncClient, video_id: str, resolved_url: str
    ) -> dict:
        api_url = "https://www.iesdouyin.com/web/api/v2/aweme/iteminfo/"
        for attempt in range(3):
            try:
                resp = await client.get(api_url, params={"item_ids": video_id})
                resp.raise_for_status()
                data = resp.json()
                items = data.get("item_list") or []
                if items:
                    return items[0]
            except Exception:
                if attempt == 2:
                    logger.warning("Douyin API failed for %s, trying share page", video_id)
                else:
                    await __import__("asyncio").sleep(1 * (2**attempt))

        resp = await client.get(resolved_url)
        resp.raise_for_status()
        html = resp.text or ""
        return self._parse_share_page(html)

    @staticmethod
    def _parse_share_page(html: str) -> dict:
        marker = "window._ROUTER_DATA = "
        start = html.find(marker)
        if start < 0:
            raise ValueError("无法从分享页提取数据")
        idx = start + len(marker)
        while idx < len(html) and html[idx].isspace():
            idx += 1
        depth = 0
        in_str = False
        escaped = False
        for cursor in range(idx, len(html)):
            ch = html[cursor]
            if in_str:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    router_data = json.loads(html[idx : cursor + 1])
                    loader_data = router_data.get("loaderData", {})
                    for node in loader_data.values():
                        if not isinstance(node, dict):
                            continue
                        video_info_res = node.get("videoInfoRes", {})
                        item_list = video_info_res.get("item_list", [])
                        if item_list and isinstance(item_list[0], dict):
                            return item_list[0]
                    raise ValueError("分享页中未找到视频信息")
        raise ValueError("无法解析分享页数据")


class DouyinParser(ContentParser):
    """Parse Douyin video URLs using the share-link public API."""

    @property
    def supported_domains(self) -> list[str]:
        return _DOUYIN_DOMAINS

    async def can_parse(self, url: str) -> bool:
        return any(domain in url for domain in self.supported_domains)

    async def parse(self, url: str, work_dir: Path) -> ParsedContent:
        """Extract metadata from a Douyin share link."""
        client = DouyinApiClient()
        item_info = await client.parse_share_link(url)
        return self._build_parsed_content(item_info, url)

    async def download(self, url: str, download_dir: Path, task_id: str) -> dict[str, Path]:
        """Download a Douyin video to the task work directory.

        Returns a dict compatible with VideoDownloader.download().
        """
        client = DouyinApiClient()
        item_info = await client.parse_share_link(url)
        work_dir = download_dir / task_id
        work_dir.mkdir(parents=True, exist_ok=True)

        video = item_info.get("video", {})
        play_urls = video.get("play_addr", {}).get("url_list", [])
        if not play_urls:
            raise ValueError("未找到视频播放地址")
        media_url = play_urls[0].replace("playwm", "play")

        title = item_info.get("desc") or f"douyin_{item_info.get('aweme_id', 'video')}"
        safe_title = re.sub(r'[\\/*?:"<>|\n\r\t#@]', "_", title).strip("_. ")[:60]
        safe_title = re.sub(r"_+", "_", safe_title)
        if not safe_title:
            safe_title = f"douyin_{item_info.get('aweme_id', 'video')}"
        filepath = work_dir / f"{safe_title}.mp4"

        await client.download(media_url, filepath)
        return {
            "video_path": filepath,
            "audio_path": filepath,
            "work_dir": work_dir,
        }

    @staticmethod
    def _build_parsed_content(item_info: dict, url: str) -> ParsedContent:
        author = item_info.get("author", {})
        video = item_info.get("video", {})
        duration_ms = video.get("duration", 0)
        duration_sec = duration_ms // 1000 if duration_ms > 1000 else duration_ms
        cover_urls = video.get("cover", {}).get("url_list", [])
        return ParsedContent(
            platform="douyin",
            url=url,
            title=item_info.get("desc"),
            metadata={
                "author": author.get("nickname"),
                "duration": duration_sec,
                "thumbnail": cover_urls[0] if cover_urls else None,
                "original_url": item_info.get("share_url") or url,
            },
        )
