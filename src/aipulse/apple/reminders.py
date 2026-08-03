"""Apple Reminders 集成（macOS only）.

Strategy：调 AppleScript / ``osascript`` 创建 Reminder，支持 due date / notes。
失败一律 raise RuntimeError，让上层容错（spec F6：失败不影响 Obsidian Task）。
"""

from __future__ import annotations

import asyncio
import logging
import re
import uuid
from typing import Optional

logger = logging.getLogger(__name__)


# 业务列表按总结主题关键字分类选单。
_TOPIC_TO_LIST: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "工作",
        (
            "工作",
            "职场",
            "办公",
            "职业",
            "团队管理",
        ),
    ),
    (
        "学习",
        (
            "学习",
            "AI",
            "技术",
            "编程",
            "面试",
        ),
    ),
    (
        "搞钱！！！",
        (
            "搞钱",
            "副业",
            "创业",
            "变现",
        ),
    ),
)
_DEFAULT_LIST = "琐碎生活"


def pick_list_for_topic(topic: str) -> str:
    """按 topic 关键字匹配 spec 06 §7.2 的 3 业务列表。

    匹配优先级：``工作`` > ``学习`` > ``搞钱！！！`` > 默认 ``琐碎生活``。
    ``topic`` 是 None / 空 → 返回默认 ``琐碎生活``。
    """
    if not topic:
        return _DEFAULT_LIST
    haystack = topic.lower()
    for list_name, keywords in _TOPIC_TO_LIST:
        for kw in keywords:
            if kw.lower() in haystack:
                return list_name
    return _DEFAULT_LIST


async def create_reminder(
    title: str,
    due_date: str,
    notes: str = "",
    *,
    list_name: Optional[str] = None,
    executor_timeout_s: float = 5.0,
) -> str:
    """Create an Apple Reminders entry; return the Reminder's ID.

    Args:
        title: Reminder 标题（≤ 200 字符；过长截断）。
        due_date: ISO8601 时间字符串（Apple Reminders 期望 YYYY-MM-DD HH:MM:SS 或
            YYYY-MM-DD 形式）。
        notes: Reminder 备注（≤ 5000 字符）。
        list_name: 目标 Reminders 列表名（None → 按 topic 走 ``pick_list_for_topic``
            默认 3 业务列表；显式传入时覆盖）。
        executor_timeout_s: 调 osascript 的超时。

    Returns:
        Reminder ID（随机 UUID 形式；macOS AppleScript 无法可靠返回 reminder id）。

    Raises:
        RuntimeError: 非 macOS / AppleScript 失败。
    """
    import platform
    import sys

    if sys.platform != "darwin" or platform.system() != "Darwin":
        raise RuntimeError("Apple Reminders 仅在 macOS 上可用")

    safe_title = title.strip()[:200] or "AIPulse Reminder"
    safe_notes = notes.strip()[:5000]
    # 把 ISO8601 拆成 macOS 友好的 YYYY-MM-DD HH:MM:SS；若无时间则纯日期
    pretty_due = _format_due_date(due_date)
    # spec 06 §7.2：list_name 未显式传入 → 按 topic 走 pick_list_for_topic 默认映射。
    effective_list = list_name if list_name else pick_list_for_topic(safe_title)
    list_esc = _escape_for_applescript(effective_list)
    title_esc = _escape_for_applescript(safe_title)
    notes_esc = _escape_for_applescript(safe_notes)
    due_esc = _escape_for_applescript(pretty_due)

    # 三步走：1）确保列表存在；2）创建 reminder；3）设 dueDate + notes
    script = f"""
    tell application "Reminders"
        if not (exists list "{list_esc}") then
            make new list with properties {{name:"{list_esc}"}}
        end if
        set targetList to list "{list_esc}"
        tell targetList
            set newReminder to make new reminder with properties {{name:"{title_esc}", body:"{notes_esc}"}}
            set remindMeDate to date "{due_esc}"
            set due date of newReminder to remindMeDate
        end tell
        return id of newReminder
    end tell
    """

    proc = await asyncio.create_subprocess_exec(
        "osascript",
        "-e",
        script,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=executor_timeout_s
        )
    except asyncio.TimeoutError as exc:
        proc.kill()
        raise RuntimeError(
            f"osascript 超时 ({executor_timeout_s}s)"
        ) from exc

    if proc.returncode != 0:
        err = stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(
            f"AppleScript 创建 Reminder 失败 ({proc.returncode}): {err}"
        )
    raw_id = stdout.decode("utf-8", errors="replace").strip()
    # 当 apple 拒绝返回 ID 时，用本地 UUID 兜底
    if not raw_id or not re.match(r"^x-coredata://", raw_id):
        return "rem-" + uuid.uuid4().hex[:12]
    return raw_id


def _format_due_date(iso8601: str) -> str:
    """Normalize ISO8601 → 'YYYY-MM-DD HH:MM:SS' (AppleScript date 期望)."""
    iso8601 = iso8601.strip()
    if not iso8601:
        return ""
    # 处理 'YYYY-MM-DDTHH:MM:SS[+HH:MM|Z]' 形式
    if "T" in iso8601:
        date_part, time_part = iso8601.split("T", 1)
        # 截掉小数秒、tz 后缀（包含 'Z'）
        for sep in (".", "+", "-", "Z"):
            if sep in time_part:
                time_part = time_part.split(sep, 1)[0]
                # 用 Z 截一次后保持；其它截完跳出
                if sep == "Z":
                    break
        return f"{date_part} {time_part}"
    return iso8601  # already 'YYYY-MM-DD'


def _escape_for_applescript(s: str) -> str:
    """AppleScript string literal 中需要转义 \\ 和 "."""
    if not s:
        return ""
    return s.replace("\\", "\\\\").replace('"', '\\"')
