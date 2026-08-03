"""Tool implementations for the v0.3 ReAct Agent (spec §5.6).

6 个 @tool 装饰器：
  1. fetch_transcript — 拉 B 站字幕
  2. summarize — 调 LLM 生成结构化总结
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
import tempfile
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional, Union

import httpx
from langchain_core.tools import tool
from pydantic import BaseModel, Field, field_validator

from aipulse.core.config import get_settings
from aipulse.summarizers.agent.bilibili_subtitle import (
    browser_headers as _bilibili_browser_headers,
    build_cookie_header as _bilibili_cookie_header,
    order_and_verify_subtitles as _bilibili_order_and_verify,
    read_obsidian_media_extended_cookies as _bilibili_read_cookies,
)


logger = logging.getLogger(__name__)


# =====================================================================
# Tool 1 — fetch_transcript
# =====================================================================
class FetchTranscriptInput(BaseModel):
    """Arg schema for fetch_transcript.

    L2#2 (2026-07-26) 签约修复：LLM ReAct 偶尔会把整段
    ``{"video_id": "BV..."}`` dict 序列化成 Action.input 传入。LangChain
    默认 args_schema 是 ``video_id: str``，会在 BaseModel 校验阶段抛
    ``ValidationError`` 然后 ReAct parser 抛
    ``Missing 'Action:' after 'Thought:'``，把整个 pipeline 拖入 status
    错位状态。这里用自定义 Pydantic 模型接受 ``Union[str, dict, list]``，
    校验时把 dict 兜底成 ``.video_id / .bvid`` 字符串，让 LangChain
    的输入校验直接通过、不会再触发 parser 崩栈。
    """

    video_id: Union[str, dict, list, None] = None

    model_config = {"arbitrary_types_allowed": True}

    @field_validator("video_id", mode="before")
    @classmethod
    def _coerce_video_id(cls, value: Any) -> Any:
        # 把 int / float 强制转 str；None / dict / str / list 原样返回让函数体再判。
        if isinstance(value, (int, float)):
            return str(value)
        return value


@tool(args_schema=FetchTranscriptInput)
async def fetch_transcript(video_id: str) -> str:
    """拉取 B 站视频 AI 字幕文本，落盘到 ``data/cache/transcripts/<video_id>.md``。

    R5-C (2026-07-26)：字幕内容写到磁盘文件而不是直接返回文本。
    Agent 通过单参数 ``fetch_transcript(video_id)`` 拿到字幕文件绝对路径，
    再把路径传给 ``summarize(video_id, transcript_path)`` —— 这样 ReAct
    Action Input 里不会出现 61699 字节字幕这种巨型字符串，模型协议负担最小。

    Args:
        video_id: B 站 BV 号 (e.g. BV1xx411c7mD)。
    Returns:
        字幕文件绝对路径字符串；失败时返回 ``[ERROR]`` 前缀字符串（Agent 看到后终止 pipeline）。

    落盘格式：
        ---
        bvid: <video_id>
        fetched_at: <ISO8601>
        source: bilibili
        ---
        <完整字幕文本>

    签约修复（2026-07-26 L2#2）：FetchTranscriptInput 在 Pydantic 层先
    把 dict 兜底成 ``.video_id / .bvid`` 字符串；函数体内再做严格的
    ``startswith("BV")`` 校验，挡掉 URL-encoded / 乱码输入。
    """
    # Pydantic 通过校验后值仍是 Any；函数体再做一次类型兜底。
    if not isinstance(video_id, str):
        if isinstance(video_id, dict):
            candidate = video_id.get("video_id") or video_id.get("bvid")
            if isinstance(candidate, str) and candidate:
                video_id = candidate
            else:
                return (
                    "[ERROR] fetch_transcript 收到 dict 但无 video_id/bvid 字段："
                    f"{video_id!r}"
                )
        else:
            return (
                "[ERROR] fetch_transcript video_id 类型错误："
                f"{type(video_id).__name__}；期望 str / dict"
            )

    video_id = video_id.strip()
    if not video_id or not video_id.startswith("BV"):
        return f"[ERROR] video_id 必须以 'BV' 开头（收到：{video_id!r}）"

    try:
        # 浏览器伪装 + Referer（skill 设计：避免 412 风控）
        headers = _bilibili_browser_headers(video_id)

        # Step 1：拿 cid
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://api.bilibili.com/x/web-interface/view",
                params={"bvid": video_id},
                headers=headers,
            )
            resp.raise_for_status()
            view = resp.json()
        if view.get("code") != 0:
            return f"[ERROR] 解析 video_id 失败：{video_id}"

        info = view.get("data") or {}
        cid = info.get("cid")
        if not cid:
            return f"[ERROR] 拿不到 cid：{video_id}"

        # Step 2a：尝试 macOS Obsidian Media Extended cookie 自动读取
        cookies = _bilibili_read_cookies()
        sub_list: list = []
        if cookies and cookies.get("SESSDATA"):
            cookie_header = _bilibili_cookie_header(cookies)
            cookie_headers = {**headers, "Cookie": cookie_header}
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    "https://api.bilibili.com/x/player/v2",
                    params={"bvid": video_id, "cid": str(cid)},
                    headers=cookie_headers,
                )
                resp.raise_for_status()
                payload = resp.json()
            if payload.get("code") == 0:
                sub_list = (
                    (payload.get("data") or {}).get("subtitle") or {}
                ).get("subtitles") or []

        # Step 2b：无 cookie / 失败 → 落回公开 dm/view 接口
        if not sub_list:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    "https://api.bilibili.com/x/v2/dm/view",
                    params={"oid": str(cid), "type": "1"},
                    headers=headers,
                )
                resp.raise_for_status()
                payload = resp.json()
            if payload.get("code") == 0:
                sub_list = (
                    (payload.get("data") or {}).get("subtitle") or {}
                ).get("subtitles") or []

        if not sub_list:
            # Step 2c：无官方字幕 → 尝试 Whisper ASR fallback
            # B 站音频下载需要登录 cookie + Referer；任何一步失败都返回 [ERROR]
            whisper_text = await _try_whisper_fallback(video_id, info, headers, cookies)
            if whisper_text is not None:
                transcript_text = whisper_text
                # 跳到 Step 4 落盘
                cache_dir = _transcript_cache_dir()
                cache_dir.mkdir(parents=True, exist_ok=True)
                transcript_path = cache_dir / f"{video_id}.md"
                frontmatter = (
                    f"---\n"
                    f"bvid: {video_id}\n"
                    f"fetched_at: {datetime.now(UTC).isoformat()}\n"
                    f"source: whisper\n"
                    f"---\n\n"
                )
                await asyncio.to_thread(
                    transcript_path.write_text,
                    frontmatter + transcript_text,
                    encoding="utf-8",
                )
                return str(transcript_path)
            return f"[ERROR] 该视频无字幕：{video_id}"

        # Step 3：多字幕轨道排序（中文 → 英文 → 其它）+ duration 校验
        chosen_body = _bilibili_order_and_verify(sub_list, headers, info)
        if chosen_body is None:
            return f"[ERROR] 所有字幕轨道验证失败：{video_id}"

        lines: list[str] = []
        for item in chosen_body:
            content = (item.get("content") or "").strip()
            if content:
                lines.append(content)
        if not lines:
            return f"[ERROR] 字幕解析为空：{video_id}"
        transcript_text = "\n".join(lines)

        # Step 4 (R5-C)：落盘到 data/cache/transcripts/<bvid>.md
        cache_dir = _transcript_cache_dir()
        cache_dir.mkdir(parents=True, exist_ok=True)
        transcript_path = cache_dir / f"{video_id}.md"
        # spec 06 §7.2: estimated_minutes = max(15, video_duration × 2)
        # duration 写进 frontmatter 让 create_learning_event 读得到。
        duration_seconds = int(info.get("duration") or 0)
        frontmatter = (
            f"---\n"
            f"bvid: {video_id}\n"
            f"fetched_at: {datetime.now(UTC).isoformat()}\n"
            f"source: bilibili\n"
            f"duration_seconds: {duration_seconds}\n"
            f"---\n\n"
        )
        await asyncio.to_thread(
            transcript_path.write_text,
            frontmatter + transcript_text,
            encoding="utf-8",
        )
        return str(transcript_path)
    except asyncio.TimeoutError:
        return f"[ERROR] 字幕拉取超时（30s）：{video_id}"
    except Exception as exc:  # noqa: BLE001
        logger.warning("fetch_transcript failed for %s: %s", video_id, exc)
        return f"[ERROR] 字幕不可用：{exc!s}"


def _transcript_cache_dir() -> Path:
    """``data/cache/transcripts/`` 绝对路径 —— settings.data_dir 派生。"""
    settings = get_settings()
    return Path(settings.data_dir) / "cache" / "transcripts"


async def _try_whisper_fallback(
    video_id: str,
    info: dict,
    headers: dict,
    cookies: dict | None,
) -> str | None:
    """Whisper ASR fallback —— 拉音频 → faster-whisper 转写。

    返回转写文本；任何失败（无 cookie / 音频 URL 被 B 站风控 / Whisper
    模型未装 / 转写失败）都返回 ``None``，调用方把它映射成现有 ``[ERROR]``
    字符串。

    硬约束：
      - 不硬编码 cookie / secret；只复用 _bilibili_read_cookies() 已读到的 cookie。
      - 不持久化下载的音频（用完即删）。
      - Whisper 模型由 faster-whisper 内部管理；不写本地路径以外的副作用。
    """
    # B 站音频下载接口需要登录；匿名会话不触发 fallback（避免噪音失败）
    if not cookies or not cookies.get("SESSDATA"):
        logger.debug(
            "[whisper-fallback] %s skipped: no SESSDATA cookie",
            video_id,
        )
        return None

    # 从 /web-interface/view 拿到的 data.dash.audio[*].baseUrl / base_url
    dash = info.get("dash") or {}
    audios = dash.get("audio") or []
    audio_url: Optional[str] = None
    for item in audios:
        if not isinstance(item, dict):
            continue
        url = item.get("base_url") or item.get("baseUrl")
        if isinstance(url, str) and url:
            audio_url = url
            break
    if not audio_url:
        logger.debug(
            "[whisper-fallback] %s skipped: no audio url in dash.audio",
            video_id,
        )
        return None

    # 下载音频到临时文件
    cookie_header = _bilibili_cookie_header(cookies)
    download_headers = {
        **headers,
        "Cookie": cookie_header,
        "Referer": f"https://www.bilibili.com/video/{video_id}",
    }
    tmp_audio: Optional[Path] = None
    try:
        async with httpx.AsyncClient(
            timeout=60.0,
            follow_redirects=True,
        ) as client:
            audio_resp = await client.get(audio_url, headers=download_headers)
            audio_resp.raise_for_status()

        tmp_audio = Path(tempfile.gettempdir()) / f"aipulse_{video_id}.m4a"
        await asyncio.to_thread(tmp_audio.write_bytes, audio_resp.content)

        # 构造 ParsedContent 用 WhisperSubtitleStrategy 的真实接口
        from aipulse.video.parsers.base import ParsedContent
        from aipulse.video.subtitle.whisper import WhisperSubtitleStrategy

        content = ParsedContent(
            platform="bilibili",
            url=f"https://www.bilibili.com/video/{video_id}",
            title=info.get("title"),
            audio_path=tmp_audio,
        )
        strategy = WhisperSubtitleStrategy()
        work_dir = Path(tempfile.gettempdir())
        result = await strategy.fetch(content, work_dir)
        if result.text:
            logger.info(
                "[whisper-fallback] %s transcribed via Whisper (source=%s)",
                video_id,
                result.source,
            )
            return result.text
        logger.debug(
            "[whisper-fallback] %s returned no text (source=%s)",
            video_id,
            result.source,
        )
        return None
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "[whisper-fallback] %s failed: %s",
            video_id,
            exc,
        )
        return None
    finally:
        if tmp_audio is not None and tmp_audio.exists():
            try:
                await asyncio.to_thread(tmp_audio.unlink)
            except Exception:  # noqa: BLE001
                pass


def _read_transcript_file(path_str: str) -> str | None:
    """读 frontmatter + 正文，剥 frontmatter 返回纯字幕文本。

    路径不存在 / 解析失败 → 返回 None。
    """
    p = Path(path_str)
    if not p.exists() or not p.is_file():
        return None
    try:
        raw = p.read_text(encoding="utf-8")
    except Exception:
        return None
    # frontmatter 形如 "---\n...\n---\n\n<正文>"
    if not raw.startswith("---\n"):
        return raw
    end = raw.find("\n---\n", 4)
    if end < 0:
        return raw
    return raw[end + len("\n---\n"):]


def _read_transcript_duration_seconds(video_id: str) -> int | None:
    """读 fetch_transcript 落盘的 frontmatter 里的 ``duration_seconds``。

    返回 ``int`` 秒；文件不存在 / 解析失败 / 缺字段 → 返回 ``None``。
    调用方 fallback 到 15（spec 06 §7.2：estimated_minutes = max(15, duration_minutes × 2)）。
    """
    try:
        cache_dir = _transcript_cache_dir()
        transcript_path = cache_dir / f"{video_id}.md"
        if not transcript_path.exists() or not transcript_path.is_file():
            return None
        raw = transcript_path.read_text(encoding="utf-8")
    except Exception:  # noqa: BLE001
        return None
    if not raw.startswith("---\n"):
        return None
    end = raw.find("\n---\n", 4)
    if end < 0:
        return None
    fm = raw[4:end]
    for line in fm.splitlines():
        line = line.strip()
        if line.startswith("duration_seconds:"):
            value = line.split(":", 1)[1].strip()
            try:
                return int(value)
            except ValueError:
                return None
    return None


def _compute_estimated_minutes(video_id: str) -> int:
    """spec 06 §7.2：``estimated_minutes = max(15, video_duration_minutes × 2)``。

    ``video_duration`` 不可得 → fallback 15（保留原硬编码行为）。
    """
    duration_seconds = _read_transcript_duration_seconds(video_id)
    if duration_seconds is None or duration_seconds <= 0:
        return 15
    duration_minutes = duration_seconds // 60
    return max(15, duration_minutes * 2)


# =====================================================================
# Tool 2 — summarize (调 LLM)
# =====================================================================
class SummarizeInput(BaseModel):
    """Arg schema for summarize.

    R5-C 续 (2026-07-26)：summarize 现在接 ``transcript_path`` + ``video_id`` +
    ``extra_context`` 三个字段。LLM ReAct parser 不稳定时会偶发把整个
    ``{"video_id": "...", "transcript_path": "..."}`` dict 序列化成
    Action.input 一个字段（典型：把 fetch_transcript 返回的字幕全文 + 标题 / UP主
    拼成 ``{"video_id": "{...标题：；UP主：}"}`` 塞给 summarize.video_id）。
    LangChain 默认 args_schema 校验阶段会抛 ``ValidationError`` 然后 ReAct
    parser 抛 ``Missing 'Action:' after 'Thought:'``，把整个 pipeline
    拖入 status 错位状态。这里用自定义 Pydantic 模型接受
    ``Union[str, dict, list, None]``，校验时把 dict 兜底成 ``.video_id / .bvid``
    字符串，让 LangChain 输入校验直接通过、不会再触发 parser 崩栈。
    """

    video_id: Union[str, dict, list, None] = None
    transcript_path: Union[str, dict, list, None] = None
    extra_context: Union[str, dict, list, None] = None

    model_config = {"arbitrary_types_allowed": True}

    @field_validator("video_id", "transcript_path", "extra_context", mode="before")
    @classmethod
    def _coerce_str(cls, value: Any) -> Any:
        # 把 int / float 强制转 str；None / dict / str / list 原样返回让函数体再判。
        if isinstance(value, (int, float)):
            return str(value)
        return value


def _extract_str_field(value: Any, *keys: str) -> str | None:
    """从 dict/list 里按 key 顺序取字符串字段；找不到回 None。"""
    if isinstance(value, dict):
        for k in keys:
            v = value.get(k)
            if isinstance(v, str) and v:
                return v
        # dict 的 list-of-pairs 形态
        for k in keys:
            for item in value.get("args", []) if isinstance(value.get("args"), list) else []:
                if isinstance(item, dict) and item.get("key") == k:
                    vv = item.get("value")
                    if isinstance(vv, str) and vv:
                        return vv
    if isinstance(value, list) and value:
        first = value[0]
        if isinstance(first, dict):
            return _extract_str_field(first, *keys)
    if isinstance(value, str):
        return value or None
    return None


@tool(args_schema=SummarizeInput)
async def summarize(
    video_id: str,
    transcript_path: str | None = None,
    extra_context: str = "",
) -> dict[str, Any]:
    """从字幕文件读出文本，调 LLM 生成结构化 Markdown 总结。

    R5-C (2026-07-26)：summarize 不再接 ``transcript`` 字符串，而是接
    ``transcript_path``（来自 fetch_transcript 返回值）。这样 ReAct
    Action Input 只是个路径字符串，模型协议负担最小，字幕大文本
    不会被 Action Input JSON 撑爆 pydantic 长字符串边界。

    R5-C 续：transcript_path 函数签名改为 ``str | None = None`` 而不是
    ``str`` —— LangChain ``StructuredTool._arun`` 直接 ``coroutine(*args, **kwargs)``，
    LLM ReAct parser 漏字段时不会用 None 默认填 → TypeError missing argument。
    函数体继续强校验 transcript_path 非空（``if not transcript_path: return {ok: False}``），
    业务契约保持。

    Args:
        video_id: B 站 BV 号（用于日志关联）。
        transcript_path: 字幕文件绝对路径（fetch_transcript 返回值）。
        extra_context: 视频标题 / UP主 / tags 等上下文。
    Returns:
        {ok, markdown, model, usage, error?, transcript_path}
    """
    # 兜底：LLM ReAct parser 不稳时会把 dict / list 整个塞进来。
    if video_id is None:
        return {"ok": False, "error": "video_id 必传"}
    if not isinstance(video_id, str):
        v = _extract_str_field(video_id, "video_id", "bvid")
        if v is None:
            return {"ok": False, "error": f"video_id 类型错误：{type(video_id).__name__}"}
        video_id = v
    if transcript_path is None:
        # LangChain 把缺字段填 None；函数体强校验 transcript_path 必传。
        return {"ok": False, "error": "transcript_path 必传"}
    if not isinstance(transcript_path, str):
        v = _extract_str_field(transcript_path, "transcript_path")
        if v is None:
            return {"ok": False, "error": f"transcript_path 类型错误：{type(transcript_path).__name__}"}
        transcript_path = v
    if extra_context is None:
        extra_context = ""
    if not isinstance(extra_context, str):
        v = _extract_str_field(extra_context, "extra_context")
        extra_context = v or ""

    video_id = video_id.strip() if isinstance(video_id, str) else ""
    transcript_path = transcript_path.strip() if isinstance(transcript_path, str) else ""
    if not transcript_path:
        return {"ok": False, "error": "transcript_path 必传"}

    transcript_text = _read_transcript_file(transcript_path)
    if transcript_text is None or not transcript_text.strip():
        return {
            "ok": False,
            "transcript_path": transcript_path,
            "error": f"字幕文件不存在或为空：{transcript_path}",
        }
    # 透传存储的错误前缀（例如 [ERROR] ...）
    if transcript_text.startswith("[ERROR]"):
        return {
            "ok": False,
            "transcript_path": transcript_path,
            "error": "字幕拉取失败（fetch_transcript 标记为 [ERROR]）",
        }

    from aipulse.summarizers.agent.prompts import build_summary_prompt
    from aipulse.summarizers.llm import OpenAICompatibleAdapter

    settings = get_settings()
    try:
        adapter = OpenAICompatibleAdapter(
            settings=settings,
            base_url=settings.llm_base_url,
            model=settings.llm_model,
        )
        prompt = build_summary_prompt(
            transcript=transcript_text, extra_context=extra_context
        )
        markdown = await asyncio.wait_for(
            adapter.complete(prompt=prompt),
            timeout=180.0,
        )
        return {
            "ok": True,
            "markdown": markdown,
            "model": settings.llm_model,
            "usage": {},
            "transcript_path": transcript_path,
        }
    except asyncio.TimeoutError:
        return {
            "ok": False,
            "error": "LLM 调用超时（180s）",
            "transcript_path": transcript_path,
        }
    except Exception as exc:  # noqa: BLE001
        logger.exception("summarize failed for %s", video_id)
        return {
            "ok": False,
            "error": f"LLM 调用失败：{exc!s}",
            "transcript_path": transcript_path,
        }


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
            base_url=settings.llm_base_url,
            model=settings.llm_model,
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
            f"model: {settings.llm_model}\n"
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
                estimated_minutes=_compute_estimated_minutes(video_id),
                learning_status="unread",
            )
            s.add(event)
            await s.commit()
            return {
                "ok": True,
                "event_id": event.id,
                "hotspot_id": hotspot.id,
                "followed_up_id": followed_up_id,
            }
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
    reminder_list: str | None = None,
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
        from aipulse.apple.reminders import (
            create_reminder,
            pick_list_for_topic,
        )

        list_name = reminder_list or pick_list_for_topic(topic)
        reminder_id: Optional[str] = await create_reminder(
            title=topic,
            due_date=scheduled_at,
            notes=f"AIPulse 学习提醒\n笔记：{note_path}",
            list_name=list_name,
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
    """默认学习时间 = 今天 20:00 Asia/Shanghai（spec 06 §7.2）。

    已过 20:00 → 推 tomorrow 20:00 Asia/Shanghai。
    返回 ISO8601 带时区偏移 ``+08:00``（Apple Reminders / DB 持久化都接受）。
    """
    cn_tz = timezone(timedelta(hours=8))  # Asia/Shanghai = UTC+8
    now_cn = datetime.now(cn_tz)
    target = now_cn.replace(hour=20, minute=0, second=0, microsecond=0)
    if now_cn >= target:
        target = target + timedelta(days=1)
    return target.isoformat()
