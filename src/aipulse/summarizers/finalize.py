"""L6 (2026-07-26) 业务侧终态分支契约。

按 :class:`feedback_status-must-not-mask-failure` 硬约束：hotspot_id + note_path + 无 error
三件齐才允许 ``status=completed``；缺一项则降级为 ``failed``（若有 error）或 ``partial``；
pipeline 异常路径必须经过这个 finalizer，**不允许 early return 跳过 finalize**。

调用方：

- ``summarizers/queue.py::_run_submission`` —— 三个终态分支（成功/timeout/exception）
  都必须在 DB 写入前调 :func:`finalize_summary_job`，把返回值（status + error + event 名）
  用于 ``mark_finished`` + SSE 广播。
- ``summarizers/agent/runner.py::run_summary_pipeline`` —— 不直接调 finalize，**永远
  返回 raw result**；finalize 是队列层的事，不污染 agent 输出。

返回字段：
- ``status``: 终态字符串（``completed`` / ``partial`` / ``failed``）
- ``error``: 标准化错误信息（缺字段时自动追加 "业务侧结果字段缺失：..."）
- ``event_name``: SSE 事件名 = ``task.{bvid}.{status}``，供调用方广播用
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from aipulse.models.summary_jobs import (
    JOB_STATUS_COMPLETED,
    JOB_STATUS_FAILED,
    JOB_STATUS_PARTIAL,
)


@dataclass(frozen=True)
class FinalizedJob:
    """Immutable terminal-state decision from :func:`finalize_summary_job`."""

    status: str  # JOB_STATUS_COMPLETED / JOB_STATUS_PARTIAL / JOB_STATUS_FAILED
    error: Optional[str]
    event_name: str  # "task.{video_id}.{status}"

    def sse_payload(self, job_id: str, **extra: Any) -> dict[str, Any]:
        """Build the JSON payload that callers broadcast on ``self.event_name``."""
        payload: dict[str, Any] = {
            "type": self.status,
            "job_id": job_id,
            "status": self.status,
        }
        if self.error:
            payload["error"] = self.error
        payload.update(extra)
        return payload


def finalize_summary_job(
    *,
    video_id: str,
    hotspot_id: Optional[str],
    note_path: Optional[str],
    error: Optional[str],
) -> FinalizedJob:
    """Map business-side result fields to the terminal status / error / event name.

    The hard contract:

    - If ``hotspot_id`` OR ``note_path`` is missing → ``failed`` (when an error is
      already set) or ``partial`` (when no error) — and append a default error
      message so downstream debugging is unambiguous.
    - Else if any error is present → ``partial`` (the work produced *something*,
      just not the full side-effects).
    - Else → ``completed`` (all three pillars are in place).

    The SSE event name is always ``task.{video_id}.{status}`` regardless of the
    branch — this keeps the frontend subscription handler uniform across all
    three terminal states (L1#3).
    """
    if not hotspot_id or not note_path:
        status = JOB_STATUS_FAILED if error else JOB_STATUS_PARTIAL
        if not error:
            missing = []
            if not hotspot_id:
                missing.append("hotspot_id")
            if not note_path:
                missing.append("note_path")
            error = f"业务侧结果字段缺失：{', '.join(missing)} 未填"
    elif error:
        status = JOB_STATUS_PARTIAL
    else:
        status = JOB_STATUS_COMPLETED

    return FinalizedJob(
        status=status,
        error=error,
        event_name=f"task.{video_id}.{status}",
    )