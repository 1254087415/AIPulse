"""Tool implementations for the v0.3 ReAct Agent (spec §5.6).

6 个 @tool 装饰器：
  1. fetch_transcript — 拉 B 站字幕
  2. summarize — 调 Kimi 生成结构化总结
  3. judge_tech_relevance — 判定是否值得归档
  4. create_obsidian_note — 写 Obsidian vault
  5. create_learning_event — 写 DB
  6. send_notification — Obsidian Tasks + Apple Reminders

异步实现。失败一律返回 dict with ok=False（不抛异常），便于 Agent 自行处理。
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from langchain_core.tools import tool

from aipulse.core.config import get_settings


logger = logging.getLogger(__name__)


# =====================================================================
# Tool 1 — fetch_transcript
# =====================================================================
@tool
async def fetch_transcript(video_id: str) -> str:
    """拉取 B 站视频 AI 字幕文本。

    Args:
        video_id: B 站 BV 号 (e.g. BV1xx411c7mD)。
    Returns:
        字幕文本；失败时返回 [ERROR] 前缀字符串（Agent 看到后终止 pipeline）。

    实现：调 api.bilibili.com/x/player/v2 — 无 Cookie 也能拿到部分公共视频的官方字幕。
    """
    import httpx

    try:
        # Step 1：拿 cid
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://api.bilibili.com/x/web-interface/view",
                params={"bvid": video_id},
            )
            resp.raise_for_status()
            view = resp.json()
        if view.get("code") != 0:
            return f"[ERROR] 解析 video_id 失败：{video_id}"

        cid = (view.get("data") or {}).get("cid")
        if not cid:
            return f"[ERROR] 拿不到 cid：{video_id}"

        # Step 2：拿字幕列表
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                "https://api.bilibili.com/x/player/v2",
                params={"bvid": video_id, "cid": str(cid)},
            )
            resp.raise_for_status()
            payload = resp.json()
        if payload.get("code") != 0:
            return f"[ERROR] 字幕接口返回错误：{payload.get('message')}"

        subtitles = (payload.get("data") or {}).get("subtitle") or {}
        sub_list = subtitles.get("subtitles") or []
        if not sub_list:
            return f"[ERROR] 该视频无字幕：{video_id}"

        # 选中文轨；否则第一条
        chosen = next(
            (s for s in sub_list if "zh" in (s.get("lan") or "").lower()),
            sub_list[0],
        )
        sub_url = chosen.get("sub_url")
        if not sub_url:
            return f"[ERROR] 字幕 URL 缺失：{video_id}"
        if sub_url.startswith("//"):
            sub_url = "https:" + sub_url

        # Step 3：下载字幕 JSON
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(sub_url)
            resp.raise_for_status()
            body = resp.json()
        lines = []
        for item in body:
            content = (item.get("content") or "").strip()
            if content:
                lines.append(content)
        if not lines:
            return f"[ERROR] 字幕解析为空：{video_id}"
        return "\n".join(lines)
    except asyncio.TimeoutError:
        return f"[ERROR] 字幕拉取超时（30s）：{video_id}"
    except Exception as exc:  # noqa: BLE001
        logger.warning("fetch_transcript failed for %s: %s", video_id, exc)
        return f"[ERROR] 字幕不可用：{exc!s}"


# =====================================================================
# Tool 2 — summarize (调 Kimi)
# =====================================================================
@tool
async def summarize(video_id: str, transcript: str, extra_context: str = "") -> dict[str, Any]:
    """调用 Kimi 生成结构化 Markdown 总结。

    Args:
        video_id: B 站 BV 号（用于日志关联）。
        transcript: 字幕文本。
        extra_context: 视频标题 / UP主 / tags 等上下文。
    Returns:
        {ok, markdown, model, usage, error?}
    """
    if not transcript or transcript.startswith("[ERROR]"):
        return {"ok": False, "error": "字幕不可用，无法生成总结"}

    from aipulse.summarizers.agent.prompts import build_summary_prompt
    from aipulse.summarizers.llm import OpenAICompatibleAdapter

    settings = get_settings()
    try:
        adapter = OpenAICompatibleAdapter(
            settings=settings,
            base_url=settings.kimi_base_url,
            model=settings.kimi_model,
        )
        prompt = build_summary_prompt(transcript=transcript, extra_context=extra_context)
        markdown = await asyncio.wait_for(
            adapter.complete(prompt=prompt),
            timeout=180.0,
        )
        return {
            "ok": True,
            "markdown": markdown,
            "model": settings.kimi_model,
            "usage": {},
        }
    except asyncio.TimeoutError:
        return {"ok": False, "error": "Kimi 调用超时（180s）"}
    except Exception as exc:  # noqa: BLE001
        logger.exception("summarize failed for %s", video_id)
        return {"ok": False, "error": f"Kimi 调用失败：{exc!s}"}


# =====================================================================
# Tool 3 — judge_tech_relevance
# =====================================================================
@tool
async def judge_tech_relevance(markdown: str) -> dict[str, Any]:
    """判定总结是否值得归档。返回 {ok, score, reason, should_archive}。

    失败保守策略：score=0.7 + should_archive=True，让用户决定。
    """
    from aipulse.summarizers.agent.prompts import build_judge_prompt
    from aipulse.summarizers.llm import OpenAICompatibleAdapter

    settings = get_settings()
    try:
        adapter = OpenAICompatibleAdapter(
            settings=settings,
            base_url=settings.kimi_base_url,
            model=settings.kimi_model,
        )
        prompt = build_judge_prompt(markdown=markdown)
        raw = await asyncio.wait_for(adapter.complete(prompt=prompt), timeout=60.0)
        parsed = json.loads(raw.strip())
        score = float(parsed.get("score", 0.0))
        return {
            "ok": True,
            "score": score,
            "reason": parsed.get("reason", ""),
            "should_archive": score >= 0.6,
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("judge_tech_relevance failed, defaulting to archive: %s", exc)
        return {"ok": False, "score": 0.7, "reason": "判定失败", "should_archive": True}


# =====================================================================
# Tool 4 — create_obsidian_note
# =====================================================================
@tool
async def create_obsidian_note(
    video_id: str,
    markdown: str,
    title: str,
    up_name: str,
) -> dict[str, Any]:
    """写 Obsidian vault 归档笔记。

    写入位置：{vault}/{archive_folder}/{video_id}-{title}.md
    """
    settings = get_settings()
    vault: Path = settings.obsidian_vault_path
    if not vault:
        return {"ok": False, "error": "未配置 obsidian_vault_path"}

    try:
        archive_dir = vault / settings.obsidian_archive_folder
        archive_dir.mkdir(parents=True, exist_ok=True)

        # 安全标题（去 Windows 非法字符 + 截断到 80 字）
        safe_title = re.sub(r'[\\/*?:"<>|]', "", title)[:80] or "untitled"
        note_path = archive_dir / f"{video_id}-{safe_title}.md"

        # 简单 frontmatter 注入
        frontmatter = (
            f"---\n"
            f"video_id: {video_id}\n"
            f"title: {title}\n"
            f"up_name: {up_name}\n"
            f"summarized_at: {datetime.now(UTC).isoformat()}\n"
            f"model: {settings.kimi_model}\n"
            f"---\n\n"
        )
        # 若 markdown 已有 frontmatter，跳过注入
        if not markdown.lstrip().startswith("---"):
            markdown = frontmatter + markdown

        await asyncio.to_thread(note_path.write_text, markdown, encoding="utf-8")
        return {"ok": True, "note_path": str(note_path)}
    except Exception as exc:  # noqa: BLE001
        logger.exception("create_obsidian_note failed")
        return {"ok": False, "error": f"写入 Obsidian 失败：{exc!s}"}


# =====================================================================
# Tool 5 — create_learning_event
# =====================================================================
@tool
async def create_learning_event(
    video_id: str,
    note_path: str,
    scheduled_at: str,
    topic: str,
) -> dict[str, Any]:
    """在 learning_events 表插入一条"即将学习"记录。

    Args:
        video_id: B 站 BV 号。
        note_path: Obsidian 笔记绝对路径。
        scheduled_at: ISO8601 时间字符串。
        topic: 简短主题。
    """
    try:
        from sqlalchemy import select

        from aipulse.hotspot.models import Hotspot
        from aipulse.models.learning_events import LearningEvent
        from aipulse.store.database import get_session_maker

        # 从 video_id 找 hotspot / followed_up
        async with get_session_maker()() as s:
            hotspot = (
                await s.execute(select(Hotspot).where(Hotspot.content_id == video_id))
            ).scalar_one_or_none()
            if hotspot is None:
                return {"ok": False, "error": f"未找到 video_id={video_id} 对应的 hotspot"}
            followed_up_id = hotspot.followed_up_id
            if followed_up_id is None:
                return {"ok": False, "error": "hotspot 没有关联 followed_up，无法创建 learning_event"}

            scheduled = datetime.fromisoformat(scheduled_at)
            event = LearningEvent(
                hotspot_id=hotspot.id,
                followed_up_id=followed_up_id,
                platform="bilibili",
                title=topic[:256],
                summary_note_path=note_path[:512] if note_path else None,
                scheduled_at=scheduled,
                estimated_minutes=15,
                learning_status="unread",
            )
            s.add(event)
            await s.commit()
            return {"ok": True, "event_id": event.id}
    except Exception as exc:  # noqa: BLE001
        logger.exception("create_learning_event failed")
        return {"ok": False, "error": f"DB 写入失败：{exc!s}"}


# =====================================================================
# Tool 6 — send_notification
# =====================================================================
@tool
async def send_notification(
    note_path: str,
    scheduled_at: str,
    topic: str,
) -> dict[str, Any]:
    """追加 Obsidian Task checkbox + Apple Reminders。

    Obsidian Task 必须成功；Apple Reminders 失败不影响整体。
    """
    results: dict[str, Any] = {"ok": True, "obsidian_task": False}

    # Obsidian Task
    try:
        p = Path(note_path)
        if not p.exists():
            return {"ok": False, "error": f"笔记不存在：{note_path}"}
        scheduled = datetime.fromisoformat(scheduled_at)
        task_line = f"\n- [ ] ⏰ {scheduled.strftime('%Y-%m-%d %H:%M')} {topic}\n"

        def _append() -> None:
            with p.open("a", encoding="utf-8") as f:
                f.write(task_line)

        await asyncio.to_thread(_append)
        results["obsidian_task"] = True
    except Exception as exc:  # noqa: BLE001
        results["ok"] = False
        results["error"] = f"Obsidian Task 写入失败：{exc!s}"
        return results

    # Apple Reminders — failure tolerated
    try:
        from aipulse.apple.reminders import create_reminder  # type: ignore[import-not-found]

        reminder_id: Optional[str] = await create_reminder(
            title=topic,
            due_date=scheduled_at,
            notes=f"AIPulse 学习提醒\n笔记：{note_path}",
        )
        results["reminder_id"] = reminder_id
    except ImportError:
        logger.debug("Apple Reminders module not available; skipping")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Apple Reminders 创建失败（不影响整体）: %s", exc)
        results["reminder_error"] = str(exc)

    return results


# =====================================================================
# Tool 列表
# =====================================================================
ALL_TOOLS = [
    fetch_transcript,
    summarize,
    judge_tech_relevance,
    create_obsidian_note,
    create_learning_event,
    send_notification,
]


def default_scheduled_at() -> str:
    """默认学习时间 = 现在 + 24 小时（ISO8601）。"""
    return (datetime.now(UTC) + timedelta(hours=24)).isoformat()