"""archive_service — v0.3 三方向归档（DB + Obsidian Tasks + Apple Reminders）"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ArchiveOutcome:
    """聚合的三方向归档结果。"""

    note_path: Optional[str]
    learning_event_id: Optional[str]
    reminder_id: Optional[str]
    obsidian_task_written: bool
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return bool(self.note_path and not self.errors)


async def append_obsidian_task(
    note_path: str,
    *,
    scheduled_at: str,
    topic: str,
) -> bool:
    """Append ``- [ ] ⏰ scheduled topic`` to the Obsidian note. Returns success.

    严格来说这是 ``send_notification`` 工具已经做的；这里抽出共享 helper
    让 archive_service 与 tools 行为一致。
    """
    from datetime import datetime

    from aipulse.summarizers.agent.tools import send_notification as _sn

    res = await _sn.coroutine(  # type: ignore[attr-defined]
        note_path=note_path,
        scheduled_at=scheduled_at,
        topic=topic,
    ) if hasattr(_sn, "coroutine") else None
    if res is not None:
        return bool(res.get("obsidian_task"))

    # 退化路径：直接复用工具的内部逻辑
    p = Path(note_path)
    if not p.exists():
        return False
    scheduled = datetime.fromisoformat(scheduled_at)
    task_line = f"\n- [ ] ⏰ {scheduled.strftime('%Y-%m-%d %H:%M')} {topic}\n"
    try:
        with p.open("a", encoding="utf-8") as f:
            f.write(task_line)
        return True
    except OSError as exc:  # noqa: BLE001
        logger.warning("append_obsidian_task failed: %s", exc)
        return False


async def record_learning_event(
    *,
    video_id: str,
    note_path: str,
    scheduled_at: str,
    topic: str,
) -> Optional[str]:
    """Persist a learning_events row via the tool. Returns the new event id."""
    from aipulse.summarizers.agent import tools as agent_tools

    _cle = agent_tools.create_learning_event
    scheduled = scheduled_at
    # 工具期望 ISO8601；如果传过来是 None 给出 ISO
    res = await _cle.ainvoke(  # type: ignore[attr-defined]
        {
            "video_id": video_id,
            "note_path": note_path,
            "scheduled_at": scheduled,
            "topic": topic,
        }
    )
    if res.get("ok"):
        return res.get("event_id")
    logger.warning("record_learning_event failed: %s", res.get("error"))
    return None


async def archive_three_way(
    *,
    video_id: str,
    title: str,
    up_name: str,
    markdown: str,
    scheduled_at: str,
    topic: str,
) -> ArchiveOutcome:
    """Run the v0.3 three-way archive pipeline.

    步骤：
    1. ``create_obsidian_note`` — 写 vault note (失败 → 整体失败)
    2. ``create_learning_event`` — 写 DB (失败容错，记录 error)
    3. ``append_obsidian_task`` + Apple Reminder — 通知
    """
    from aipulse.summarizers.agent import tools as agent_tools

    create_obsidian_note = agent_tools.create_obsidian_note

    errors: list[str] = []
    note: dict[str, Any] = await create_obsidian_note.ainvoke(
        {
            "video_id": video_id,
            "markdown": markdown,
            "title": title,
            "up_name": up_name,
        }
    )
    if not note.get("ok"):
        errors.append(f"obsidian_note: {note.get('error')}")
        return ArchiveOutcome(
            note_path=None,
            learning_event_id=None,
            reminder_id=None,
            obsidian_task_written=False,
            errors=errors,
        )
    note_path = note["note_path"]

    # 第二步：DB
    event_id = await record_learning_event(
        video_id=video_id,
        note_path=note_path,
        scheduled_at=scheduled_at,
        topic=topic,
    )
    if event_id is None:
        errors.append("learning_event")

    # 第三步：通知 (Obsidian Task 必填；Apple Reminders 容错)
    task_ok = await append_obsidian_task(
        note_path, scheduled_at=scheduled_at, topic=topic
    )
    reminder_id: Optional[str] = None
    if not task_ok:
        errors.append("obsidian_task")

    try:
        import platform
        import sys

        if sys.platform == "darwin":
            from aipulse.apple.reminders import create_reminder

            reminder_id = await create_reminder(
                title=topic,
                due_date=scheduled_at,
                notes=f"AIPulse 学习提醒\n笔记：{note_path}",
            )
    except Exception as exc:  # noqa: BLE001
        logger.info("Apple Reminders unavailable: %s", exc)
        # 容错：不写进 errors（spec：Apple Reminders 失败不影响整体）

    return ArchiveOutcome(
        note_path=note_path,
        learning_event_id=event_id,
        reminder_id=reminder_id,
        obsidian_task_written=task_ok,
        errors=errors,
    )
