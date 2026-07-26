"""L6 (2026-07-26) 业务侧终态分支契约单测。

参照 :class:`feedback_status-must-not-mask-failure`：

- completed → 三件齐（hotspot_id + note_path + 无 error）
- partial   → 任一缺失（无 error）或仅有 error
- failed    → 缺失且已有 error（最差路径）

覆盖 finalize 自身的 4 条 status 判定路径，并断言 SSE event_name 恒为
``task.{bvid}.{status}``，方便 L1#3 验收者 grep。
"""

from __future__ import annotations

import pytest

from aipulse.models.summary_jobs import (
    JOB_STATUS_COMPLETED,
    JOB_STATUS_FAILED,
    JOB_STATUS_PARTIAL,
)
from aipulse.summarizers.finalize import finalize_summary_job


pytestmark = pytest.mark.unit


class TestFinalizeSummaryJob:
    def test_completed_when_all_three_pillars_present(self) -> None:
        """三件齐（hotspot_id + note_path + 无 error）→ completed。"""
        fin = finalize_summary_job(
            video_id="BV1fA411Z772",
            hotspot_id="hs-abc",
            note_path="/vault/BV1fA411Z772.md",
            error=None,
        )
        assert fin.status == JOB_STATUS_COMPLETED
        assert fin.error is None
        assert fin.event_name == "task.BV1fA411Z772.completed"

    def test_failed_when_missing_fields_and_error_present(self) -> None:
        """缺字段 + 已 error → failed（保留原 error，不追加 default）。"""
        fin = finalize_summary_job(
            video_id="BV1fA411Z772",
            hotspot_id=None,
            note_path=None,
            error="Kimi API 5xx",
        )
        assert fin.status == JOB_STATUS_FAILED
        assert fin.error == "Kimi API 5xx"
        assert fin.event_name == "task.BV1fA411Z772.failed"

    def test_partial_when_missing_fields_and_no_error(self) -> None:
        """缺字段 + 无 error → partial（追加 default "字段缺失" error）。"""
        fin = finalize_summary_job(
            video_id="BV1fA411Z772",
            hotspot_id=None,
            note_path="/vault/note.md",  # note_path 在，但 hotspot_id 缺
            error=None,
        )
        assert fin.status == JOB_STATUS_PARTIAL
        assert fin.error is not None
        assert "hotspot_id" in fin.error
        assert "未填" in fin.error
        assert fin.event_name == "task.BV1fA411Z772.partial"

    def test_partial_when_error_with_pillars_present(self) -> None:
        """三件齐但有 error → partial（说明有副作用但不完全）。"""
        fin = finalize_summary_job(
            video_id="BV1fA411Z772",
            hotspot_id="hs-abc",
            note_path="/vault/BV1fA411Z772.md",
            error="Reminder 创建失败",
        )
        assert fin.status == JOB_STATUS_PARTIAL
        assert fin.error == "Reminder 创建失败"
        assert fin.event_name == "task.BV1fA411Z772.partial"

    def test_partial_lists_all_missing_fields(self) -> None:
        """hotspot_id 和 note_path 都缺 → default error 把两者都列出。"""
        fin = finalize_summary_job(
            video_id="BVxxx",
            hotspot_id=None,
            note_path=None,
            error=None,
        )
        assert fin.status == JOB_STATUS_PARTIAL
        assert "hotspot_id" in fin.error
        assert "note_path" in fin.error

    def test_event_name_is_canonical_task_dot_bvid_dot_status(self) -> None:
        """L1#3：event_name 必须 = ``task.{bvid}.{status}`` 形态。"""
        fin = finalize_summary_job(
            video_id="BV1abc",
            hotspot_id=None,
            note_path=None,
            error="boom",
        )
        # 即使是 failed 路径，event_name 也必须是 task.* 形态
        assert fin.event_name == "task.BV1abc.failed"
        assert fin.event_name.startswith("task.")
        assert fin.event_name.endswith(".failed")

    def test_sse_payload_includes_status_and_error(self) -> None:
        """L1#3：广播 payload 含 status + error，便于前端直接渲染。"""
        fin = finalize_summary_job(
            video_id="BV1abc",
            hotspot_id=None,
            note_path="/vault/x.md",
            error=None,
        )
        payload = fin.sse_payload(job_id="job-123", note_path="/vault/x.md")
        assert payload["type"] == JOB_STATUS_PARTIAL
        assert payload["status"] == JOB_STATUS_PARTIAL
        assert payload["job_id"] == "job-123"
        assert payload["note_path"] == "/vault/x.md"
        assert "hotspot_id" in payload["error"]

    def test_sse_payload_omits_error_field_when_none(self) -> None:
        """completed 路径下 error 为 None，不应出现在 payload 里。"""
        fin = finalize_summary_job(
            video_id="BV1abc",
            hotspot_id="hs",
            note_path="/vault/x.md",
            error=None,
        )
        payload = fin.sse_payload(job_id="job-123")
        assert "error" not in payload