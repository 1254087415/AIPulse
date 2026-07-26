"""B 站字幕拉取 helpers（抄 obsidian-clip-summary skill 设计 · 2026-07-26）。

提供：
- 浏览器伪装 header（避免 412 风控）
- macOS Obsidian Media Extended cookie 自动读取
- 多字幕轨道排序（中文 → 英文 → 其它）+ duration 校验

skill 实现：``~/.claude/skills/obsidian-clip-summary/scripts/bilibili_extract.py``
"""

from __future__ import annotations

import json
import logging
import platform
import sqlite3
import time
import urllib.request
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


BILIBILI_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)


def browser_headers(referer_bvid: str) -> dict[str, str]:
    """构造浏览器伪装的 request headers（skill 同款）。"""
    return {
        "User-Agent": BILIBILI_UA,
        "Referer": f"https://www.bilibili.com/video/{referer_bvid}",
    }


def normalize_subtitle_url(url: str) -> str:
    """//host/path → https://host/path（skill 同款）。"""
    if not url:
        return ""
    if url.startswith("//"):
        return f"https:{url}"
    if url.startswith("http://") or url.startswith("https://"):
        return url
    return f"https://{url.lstrip('/')}"


def read_obsidian_media_extended_cookies() -> dict[str, str] | None:
    """macOS Obsidian Media Extended 登录态自动读取。

    路径：``~/Library/Application Support/obsidian/Partitions/mx-player-<vault-id>/Cookies``
    glob 任意 vault id（不硬编码）。

    前提：
    - macOS
    - Obsidian 已登录 B 站
    - 装了 Media Extended 插件（它把 player cookie 落到独立 partition）

    返回 ``{SESSDATA: ..., ...}`` 或 None（非 darwin / 没装 / 没登录）。
    """
    if platform.system() != "Darwin":
        return None

    partitions_dir = (
        Path.home() / "Library/Application Support/obsidian/Partitions"
    )
    if not partitions_dir.exists():
        return None

    candidates = sorted(partitions_dir.glob("mx-player-*/Cookies"))
    if not candidates:
        return None

    cookies: dict[str, str] = {}
    for cookies_db in candidates:
        try:
            conn = sqlite3.connect(str(cookies_db))
            cur = conn.cursor()
            cur.execute(
                "SELECT name, value FROM cookies WHERE host_key LIKE '%bilibili%'"
            )
            rows = cur.fetchall()
            conn.close()
            for name, value in rows:
                # bilibili.com 比 bilibili.cn 更优先（先到先得）
                if name not in cookies:
                    cookies[name] = value
            if cookies.get("SESSDATA"):
                return cookies
        except Exception as exc:  # noqa: BLE001
            logger.debug(
                "obsidian Media Extended Cookies 读取失败 %s: %s",
                cookies_db,
                exc,
            )
            continue
    return cookies if cookies else None


def build_cookie_header(cookies: dict[str, str] | None) -> str:
    """``{k=v; k2=v2}`` 形式（skill 同款）。"""
    if not cookies:
        return ""
    return "; ".join(f"{k}={v}" for k, v in cookies.items())


def validate_subtitle_by_duration(
    body: list[dict[str, Any]],
    video_duration_sec: float | int | None,
) -> bool:
    """B 站 AI 字幕偶尔贴错视频 → 比对 last_timestamp（skill 同款）。

    上限：duration + max(12s, 15%)；下限：长视频 ≥ 18% / 中视频 ≥ 22% /
    短视频 ≥ 25%。duration 缺失时 lenient（True）。
    """
    if not body:
        return False
    try:
        duration = float(video_duration_sec or 0)
    except (TypeError, ValueError):
        duration = 0.0

    max_to = 0.0
    for item in body:
        try:
            to = float(item.get("to") or 0)
            frm = float(item.get("from") or 0)
        except (TypeError, ValueError):
            continue
        if to > max_to:
            max_to = to
        if frm > max_to:
            max_to = frm

    if duration <= 0:
        return True  # 没 duration 时 lenient

    upper_tolerance = max(12.0, duration * 0.15)
    if max_to > duration + upper_tolerance:
        return False

    min_coverage = 0.0
    if duration >= 600:
        min_coverage = 0.18
    elif duration >= 300:
        min_coverage = 0.22
    elif duration >= 180:
        min_coverage = 0.25

    if min_coverage > 0 and max_to < duration * min_coverage:
        return False
    return True


def order_and_verify_subtitles(
    subtitles: list[dict[str, Any]],
    headers: dict[str, str],
    info: dict[str, Any],
) -> list[dict[str, Any]] | None:
    """按 skill 设计排序多字幕轨道 + duration 校验，返回第一个通过 body。

    排序：中文（ai-zh / zh-CN / zh-Hans / zh / zh-Hant / zh-TW / zh-HK）
    → 英文（ai-en）→ 其它。失败轨道自动跳过。
    """
    chinese_lans = {"ai-zh", "zh-CN", "zh-Hans", "zh", "zh-Hant", "zh-TW", "zh-HK"}
    ordered: list[dict[str, Any]] = []
    ordered.extend(s for s in subtitles if s.get("lan") in chinese_lans)
    ordered.extend(s for s in subtitles if s.get("lan") == "ai-en")
    ordered.extend(
        s
        for s in subtitles
        if s.get("lan") not in chinese_lans and s.get("lan") != "ai-en"
    )

    duration_sec = info.get("duration") or 0

    for candidate in ordered:
        sub_url = normalize_subtitle_url(candidate.get("subtitle_url") or "")
        if not sub_url:
            continue
        try:
            req = urllib.request.Request(sub_url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read().decode("utf-8")
            subtitle_data = json.loads(raw)
            body = subtitle_data.get("body") or []
            if not body or len(body) <= 5:
                continue
            if not validate_subtitle_by_duration(body, duration_sec):
                logger.debug(
                    "字幕轨道 %s 时长校验失败（duration=%ss）",
                    candidate.get("lan_doc") or candidate.get("lan"),
                    duration_sec,
                )
                continue
            return body
        except Exception as exc:  # noqa: BLE001
            logger.debug(
                "字幕轨道 %s 拉取失败：%s",
                candidate.get("lan"),
                exc,
            )
            time.sleep(0.1)
            continue
    return None