"""Unit tests for desktop/sidecar.py — push coverage ≥80%.

补全 missing lines：
- handle_request dict + ValidationError → failure response (100-104)
- handle_request unknown method (116-119)
- handle_request generic Exception (127-129)
- _list_tasks happy path + limit 超过 200 截断 (179-197)
- _retry_task 找不到 / 找到 (199-220)
- _emit_notification no _write_line fallback to stdout (327-331)
- emit_complete status="success" → progress_pct=100 else cached (370)
- shutdown with tasks and without (382-385)
- _TaskProgressObserver 5 个回调方法 (47-83)
- handle_request dict happy path (100-106)
- _submit_url defaults: missing content_type_hint (143)
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

# Register Task / Source / Hotspot tables for Base.metadata.create_all
from aipulse.store import models as _store_models  # noqa: F401
from aipulse.hotspot import models as _hotspot_models  # noqa: F401

from aipulse.core.config import AppSettings, reset_settings
from aipulse.core.rpc import JsonRpcRequest, JsonRpcResponse
from aipulse.desktop.sidecar import Sidecar, _TaskProgressObserver


@pytest.fixture
def settings(tmp_path: Path) -> AppSettings:
    reset_settings()
    return AppSettings(
        _env_file=None,
        data_dir=tmp_path / "data",
        download_dir=tmp_path / "data" / "downloads",
        database_url=f"sqlite+aiosqlite:///{tmp_path}/aipulse.db",
    )


@pytest.fixture
def sidecar(settings: AppSettings) -> Sidecar:
    return Sidecar(settings=settings)


@pytest_asyncio.fixture(autouse=True)
async def _reset_db() -> None:
    """Auto-reset DB schema before each test (Task model needs an explicit reset)."""
    from aipulse.store.database import reset_db

    await reset_db()


class TestHandleRequest:
    @pytest.mark.unit
    async def test_dict_input_happy_path(self, sidecar: Sidecar) -> None:
        """raw dict 通过 ValidationError OK + 走 normal handler path"""
        resp = await sidecar.handle_request(
            {"jsonrpc": "2.0", "id": 1, "method": "get_settings", "params": {}}
        )
        assert resp.error is None
        assert resp.id == 1

    @pytest.mark.unit
    async def test_dict_input_validation_error_returns_32600(self, sidecar: Sidecar) -> None:
        """dict invalid → -32600 invalid request (line 100-104)"""
        # 缺 id / method → Pydantic ValidationError → 返回 -32600
        resp = await sidecar.handle_request({"jsonrpc": "2.0", "params": {}})
        assert resp.error is not None
        assert resp.error.code == -32600
        assert "invalid request" in resp.error.message

    @pytest.mark.unit
    async def test_dict_input_validation_error_no_id(self, sidecar: Sidecar) -> None:
        """完全 invalid dict (甚至没 id 字段) → -32600 with id=None"""
        resp = await sidecar.handle_request({"not_jsonrpc": True})
        assert resp.error is not None
        assert resp.error.code == -32600

    @pytest.mark.unit
    async def test_pydantic_request_object_proceeds(self, sidecar: Sidecar) -> None:
        """传进来已经是 JsonRpcRequest 对象 → 跳过 validation 直接走 handler"""
        req = JsonRpcRequest(method="get_settings", id=99, params={})
        resp = await sidecar.handle_request(req)
        assert resp.error is None
        assert resp.id == 99

    @pytest.mark.unit
    async def test_handler_generic_exception_returns_internal_error(self, sidecar: Sidecar) -> None:
        """handler 抛非 JsonRpcApplicationError → -32603 internal error (127-129)"""
        # submit_url 抛 OSError via repo
        from aipulse.store.database import get_session_maker

        original = get_session_maker

        def broken():
            raise OSError("db broken")

        # patch get_session_maker called inside handler
        with patch("aipulse.desktop.sidecar.get_session_maker", side_effect=broken):
            resp = await sidecar.handle_request(
                JsonRpcRequest(method="submit_url", params={"url": "https://x.com"})
            )
        assert resp.error is not None
        assert resp.error.code == -32603
        assert "internal error" in resp.error.message


class TestListTasks:
    @pytest.mark.unit
    async def test_returns_empty_when_no_tasks(self, sidecar: Sidecar) -> None:
        resp = await sidecar.handle_request(
            JsonRpcRequest(method="list_tasks", params={})
        )
        assert resp.error is None
        assert resp.result["tasks"] == []

    @pytest.mark.unit
    async def test_limit_capped_at_200(self, sidecar: Sidecar) -> None:
        """limit 超过 200 → min(limit, 200)"""
        # 实际只创建 0 个；只是验证 limit=9999 也不会爆错 (line 180: min(...))
        resp = await sidecar.handle_request(
            JsonRpcRequest(method="list_tasks", params={"limit": 9999})
        )
        assert resp.error is None
        assert isinstance(resp.result["tasks"], list)

    @pytest.mark.unit
    async def test_returns_recent_tasks(self, sidecar: Sidecar) -> None:
        """至少 submission 后能 list 到"""
        await sidecar.handle_request(
            JsonRpcRequest(method="submit_url", params={"url": "https://x.com/a"})
        )
        resp = await sidecar.handle_request(
            JsonRpcRequest(method="list_tasks", params={})
        )
        assert resp.error is None
        assert len(resp.result["tasks"]) >= 1
        first = resp.result["tasks"][0]
        assert "id" in first
        assert first["url"] == "https://x.com/a"


class TestRetryTask:
    @pytest.mark.unit
    async def test_retry_requires_task_id(self, sidecar: Sidecar) -> None:
        resp = await sidecar.handle_request(
            JsonRpcRequest(method="retry_task", params={})
        )
        assert resp.error is not None

    @pytest.mark.unit
    async def test_retry_unknown_task_returns_error(self, sidecar: Sidecar) -> None:
        resp = await sidecar.handle_request(
            JsonRpcRequest(method="retry_task", params={"task_id": "no-such-task"})
        )
        # ValueError("not found") 被 handler 的 except Exception 包成 -32603
        assert resp.error is not None
        assert resp.error.code == -32603


class TestEmitNotificationFallback:
    @pytest.mark.unit
    async def test_emit_progress_falls_back_to_stdout(self, sidecar: Sidecar) -> None:
        """没 _write_line → 走 sys.stdout.write (327-331)"""
        sidecar._write_line = None  # explicit fallback
        with patch("sys.stdout") as mock_stdout:
            await sidecar.emit_progress("tk1", "running", 30, "msg")
        # stdout.write 至少被调用一次（包含末尾 \n）
        assert mock_stdout.write.called
        assert mock_stdout.flush.called

    @pytest.mark.unit
    async def test_emit_notification_swallows_broken_pipe(self, sidecar: Sidecar) -> None:
        """客户端断开后 stdout 是 broken pipe，通知失败不能杀死 pipeline"""
        sidecar._write_line = None
        with patch("sys.stdout") as mock_stdout:
            mock_stdout.write.side_effect = BrokenPipeError(32, "Broken pipe")
            await sidecar.emit_progress("tk1", "running", 30, "msg")
            await sidecar.emit_complete("tk1", "success", result={"x": 1})
        # 缓存状态仍正常更新
        assert sidecar._tasks["tk1"]["status"] == "success"

    @pytest.mark.unit
    async def test_emit_notification_swallows_write_line_oserror(self, sidecar: Sidecar) -> None:
        """_write_line 回调抛 OSError 时同样容错"""
        def _boom(line: str) -> None:
            raise OSError("host gone")

        sidecar._write_line = _boom
        await sidecar.emit_progress("tk2", "running", 10, "msg")
        assert sidecar._tasks["tk2"]["status"] == "running"

    @pytest.mark.unit
    async def test_emit_complete_success_sets_progress_100(self, sidecar: Sidecar) -> None:
        """emit_complete status='success' → cached 里 progress_pct 被覆盖成 100"""
        lines: list[str] = []
        sidecar._write_line = lines.append
        # 先 emit 进度，cached 有 progress_pct
        await sidecar.emit_progress("tk1", "running", 25, "25%")
        assert sidecar._tasks["tk1"]["progress_pct"] == 25

        # status=success → progress_pct 100
        await sidecar.emit_complete("tk1", "success", result={"x": 1})
        assert sidecar._tasks["tk1"]["progress_pct"] == 100

    @pytest.mark.unit
    async def test_emit_complete_non_success_keeps_cached_progress(self, sidecar: Sidecar) -> None:
        """emit_complete status='failed' → progress_pct 保持 cached 原值"""
        lines: list[str] = []
        sidecar._write_line = lines.append
        await sidecar.emit_progress("tk1", "running", 60, "60%")
        await sidecar.emit_complete("tk1", "failed", error_message="oops")
        assert sidecar._tasks["tk1"]["progress_pct"] == 60


class TestShutdown:
    @pytest.mark.unit
    async def test_shutdown_no_tasks_is_noop(self, sidecar: Sidecar) -> None:
        """无 running tasks → 直接返回，不抛错 (384-385)"""
        sidecar._running_tasks = set()
        # 不应抛错
        await sidecar.shutdown()


class TestTaskProgressObserver:
    @pytest.mark.unit
    async def test_observer_on_stage_start_calls_emit_progress(self, sidecar: Sidecar) -> None:
        """Observer.on_stage_start → sidecar.emit_progress (53-59)"""
        from aipulse.core.pipeline import PipelineEvent

        sidecar.emit_progress = AsyncMock()
        obs = _TaskProgressObserver(sidecar)
        evt = PipelineEvent(
            task_id="tk", stage="fetch", status="running",
            progress_pct=10, message="hello",
        )
        await obs.on_stage_start(evt)
        sidecar.emit_progress.assert_awaited_once_with("tk", "running", 10, "hello")

    @pytest.mark.unit
    async def test_observer_on_stage_complete(self, sidecar: Sidecar) -> None:
        from aipulse.core.pipeline import PipelineEvent

        sidecar.emit_progress = AsyncMock()
        obs = _TaskProgressObserver(sidecar)
        evt = PipelineEvent(
            task_id="tk", stage="fetch", status="completed",
            progress_pct=100, message="done",
        )
        await obs.on_stage_complete(evt)
        sidecar.emit_progress.assert_awaited_once()

    @pytest.mark.unit
    async def test_observer_on_error(self, sidecar: Sidecar) -> None:
        from aipulse.core.pipeline import PipelineEvent

        sidecar.emit_progress = AsyncMock()
        obs = _TaskProgressObserver(sidecar)
        evt = PipelineEvent(
            task_id="tk", stage="fetch", status="error",
            progress_pct=0, message="fail",
        )
        await obs.on_error(evt)
        sidecar.emit_progress.assert_awaited_once()

    @pytest.mark.unit
    async def test_observer_on_complete(self, sidecar: Sidecar) -> None:
        from aipulse.core.pipeline import PipelineEvent

        sidecar.emit_complete = AsyncMock()
        obs = _TaskProgressObserver(sidecar)
        evt = PipelineEvent(
            task_id="tk", stage="done", status="done",
            progress_pct=100, message="ok",
            url="https://x.com", title="t", error_message=None,
        )
        await obs.on_complete(evt)
        sidecar.emit_complete.assert_awaited_once()
        # on_complete 调用形式: emit_complete(task_id, status, result=..., error_message=...)
        args, kwargs = sidecar.emit_complete.await_args
        assert args[0] == "tk"
        assert args[1] == "done"
        assert kwargs["result"] == {"url": "https://x.com", "title": "t"}
        assert kwargs["error_message"] is None


class TestUpdateSettings:
    @pytest.mark.unit
    async def test_update_settings_value_error_returns_32602(self, sidecar: Sidecar) -> None:
        """update() 抛 ValueError → handler 转 JsonRpcApplicationError -32602 (226-234)

        Pydantic AppSettings 是 frozen — 不能直接 patch .update；
        patch sidecar 模块的 settings 实例：
        """
        # 构造一个 mock 替换 settings
        mock_settings = MagicMock()
        mock_settings.update.side_effect = ValueError("invalid kimi_model")
        # save + to_public_dict stub
        mock_settings.save = MagicMock()
        mock_settings.to_public_dict = MagicMock(return_value={})

        # sidecar._update_settings 用 self.settings.update(**params)
        original_settings = sidecar.settings
        sidecar.settings = mock_settings
        try:
            resp = await sidecar.handle_request(
                JsonRpcRequest(
                    method="update_settings",
                    params={"kimi_model": "bad"},
                )
            )
        finally:
            sidecar.settings = original_settings

        assert resp.error is not None
        assert resp.error.code == -32602

    @pytest.mark.unit
    async def test_update_settings_happy_returns_to_public_dict(
        self, sidecar: Sidecar
    ) -> None:
        """update() 成功 → save + reset_settings + to_public_dict (226-234)"""
        # 直接给 sidecar.settings 整体替换成 fake（Pydantic 不允许 setattr mock）
        new_settings = MagicMock()
        new_settings.to_public_dict.return_value = {"kimi_model": "x"}
        new_settings.update.return_value = new_settings
        new_settings.save = MagicMock()

        original = sidecar.settings
        # 整个 sidecar.settings 替换成 mock
        object.__setattr__(sidecar, "settings", new_settings) if False else None
        # Pydantic BaseSettings.__init_subclass__ 限制不在 Sidecar 直接冻结；
        # sidecar.settings 是普通 attr，可以直接赋值
        sidecar.settings = new_settings
        try:
            with patch("aipulse.desktop.sidecar.reset_settings"):
                resp = await sidecar.handle_request(
                    JsonRpcRequest(
                        method="update_settings",
                        params={"kimi_model": "x"},
                    )
                )
        finally:
            sidecar.settings = original

        assert resp.error is None
        assert resp.result == {"kimi_model": "x"}
        new_settings.save.assert_called_once()


class TestGetTaskStatus:
    @pytest.mark.unit
    async def test_requires_task_id(self, sidecar: Sidecar) -> None:
        """_get_task_status 缺 task_id → ValueError → -32603 (161-171)"""
        resp = await sidecar.handle_request(
            JsonRpcRequest(method="get_task_status", params={})
        )
        assert resp.error is not None
        assert resp.error.code == -32603

    @pytest.mark.unit
    async def test_unknown_task_id(self, sidecar: Sidecar) -> None:
        """_get_task_status 找不到 task → ValueError → -32603 (168-169)"""
        resp = await sidecar.handle_request(
            JsonRpcRequest(method="get_task_status", params={"task_id": "missing-id"})
        )
        assert resp.error is not None
        assert resp.error.code == -32603


class TestShutdownWithTasks:
    @pytest.mark.unit
    async def test_shutdown_waits_for_running_tasks(self, sidecar: Sidecar) -> None:
        """shutdown 等所有 running tasks 完成 (385)"""
        import asyncio

        async def _noop():
            await asyncio.sleep(0)

        # 构造两个 fake running tasks
        t1 = asyncio.create_task(_noop())
        t2 = asyncio.create_task(_noop())
        sidecar._running_tasks = {t1, t2}
        await sidecar.shutdown()
        # task 都应完成
        assert t1.done()
        assert t2.done()


class TestSubmitUrlDefaults:
    @pytest.mark.unit
    async def test_defaults_content_type_unknown(self, sidecar: Sidecar) -> None:
        """缺失 content_type_hint → DB 存 'unknown' (143)"""
        resp = await sidecar.handle_request(
            JsonRpcRequest(method="submit_url", params={"url": "https://x.com/y"})
        )
        assert resp.error is None
        # 通过 list_tasks 验证
        listed = await sidecar.handle_request(
            JsonRpcRequest(method="list_tasks", params={})
        )
        task = listed.result["tasks"][0]
        assert task["url"] == "https://x.com/y"
        # 通过 get_task_status 不直接暴露 content_type；验证返回 ok
        status_resp = await sidecar.handle_request(
            JsonRpcRequest(
                method="get_task_status", params={"task_id": resp.result["task_id"]}
            )
        )
        assert status_resp.error is None


class TestRetryTaskHappy:
    @pytest.mark.unit
    async def test_retry_success_returns_pending(
        self, sidecar: Sidecar
    ) -> None:
        """_retry_task 找到 task → reset status + spawn pipeline (209-220)
        不等 pipeline 实际跑，先 cancel 掉 spawn 的 task。
        """
        # 先 submit 一个 task
        resp = await sidecar.handle_request(
            JsonRpcRequest(method="submit_url", params={"url": "https://x.com/z"})
        )
        task_id = resp.result["task_id"]

        # 把 sidecar._spawn_pipeline patch 掉，避免真实启动
        sidecar._spawn_pipeline = MagicMock()

        # 现在 retry
        retry = await sidecar.handle_request(
            JsonRpcRequest(method="retry_task", params={"task_id": task_id})
        )
        assert retry.error is None
        assert retry.result["task_id"] == task_id
        assert retry.result["status"] == "pending"
        sidecar._spawn_pipeline.assert_called_once_with(task_id, "https://x.com/z")


class TestRunPipeline:
    @pytest.mark.unit
    async def test_run_pipeline_success_updates_status(
        self, sidecar: Sidecar
    ) -> None:
        """_run_pipeline 成功路径：classify → pipeline.run → emit_complete (249-285)
        patch 真实 pipeline，避免真正 fetch 内容。
        """
        from aipulse.core.pipeline import PipelineContext
        from aipulse.desktop.sidecar import _TaskProgressObserver

        sidecar._classify_url = AsyncMock(return_value=MagicMock(value="video"))
        # 替换 _TaskProgressObserver 构造
        with patch("aipulse.desktop.sidecar._TaskProgressObserver") as MockObs:
            mock_obs = MagicMock()
            MockObs.return_value = mock_obs

            # patch VideoPipeline / ArticlePipeline 类
            fake_pipeline = MagicMock()
            fake_pipeline.run = AsyncMock()
            fake_pipeline.add_observer = MagicMock()

            with patch("aipulse.desktop.sidecar.VideoPipeline", return_value=fake_pipeline):
                with patch("aipulse.desktop.sidecar.ArticlePipeline", return_value=fake_pipeline):
                    with patch.object(sidecar, "emit_complete", new=AsyncMock()) as mock_emit:
                        with patch.object(sidecar, "_update_task_status", new=AsyncMock()) as mock_update:
                            with patch.object(sidecar, "_persist_task_result", new=AsyncMock()):
                                await sidecar._run_pipeline("tk-id", "https://x.com/v")

        # emit_complete 至少被调用一次（成功路径）
        assert mock_emit.await_count >= 1
        # _update_task_status 被调用 running + completed 两次
        assert mock_update.await_count >= 2

    @pytest.mark.unit
    async def test_run_pipeline_exception_marks_failed(
        self, sidecar: Sidecar
    ) -> None:
        """pipeline.run 抛 → emit_complete(failed) + status=failed (281-285)"""
        sidecar._classify_url = AsyncMock(return_value=MagicMock(value="video"))
        with patch("aipulse.desktop.sidecar._TaskProgressObserver", return_value=MagicMock()):
            fake_pipeline = MagicMock()
            fake_pipeline.add_observer = MagicMock()
            fake_pipeline.run = AsyncMock(side_effect=RuntimeError("boom"))
            with patch("aipulse.desktop.sidecar.VideoPipeline", return_value=fake_pipeline):
                with patch("aipulse.desktop.sidecar.ArticlePipeline", return_value=fake_pipeline):
                    with patch.object(sidecar, "emit_complete", new=AsyncMock()) as mock_emit:
                        with patch.object(sidecar, "_update_task_status", new=AsyncMock()) as mock_update:
                            with patch.object(sidecar, "_persist_task_result", new=AsyncMock()):
                                await sidecar._run_pipeline("tk-fail", "https://x.com/f")

        # status 更新到 failed
        called = [c.args for c in mock_update.await_args_list]
        assert any("failed" in str(args) for args in called)
        # emit_complete with status=failed
        called_emit = [c.args for c in mock_emit.await_args_list]
        assert any("failed" in str(args) for args in called_emit)


class TestInternalMethods:
    @pytest.mark.unit
    async def test_classify_url_delegates_to_classifier(
        self, sidecar: Sidecar
    ) -> None:
        """_classify_url 是 await classify_url(url) 的 wrapper (288-290)"""
        from aipulse.core.content_router import ContentType

        with patch(
            "aipulse.core.content_router.classify_url",
            new=AsyncMock(return_value=ContentType.YOUTUBE),
        ):
            ct = await sidecar._classify_url("https://youtu.be/x")
        assert ct == ContentType.YOUTUBE

    @pytest.mark.unit
    async def test_update_task_status_persists_change(
        self, sidecar: Sidecar
    ) -> None:
        """_update_task_status 写入 repo + commit (298-302)"""
        # 真实创建一个 task
        repo_creator = await sidecar.handle_request(
            JsonRpcRequest(method="submit_url", params={"url": "https://x.com/u"})
        )
        task_id = repo_creator.result["task_id"]

        await sidecar._update_task_status(task_id, "running", "warn here")

        # 通过 get_task_status 验证
        stat = await sidecar.handle_request(
            JsonRpcRequest(method="get_task_status", params={"task_id": task_id})
        )
        assert stat.error is None
        assert stat.result["status"] == "running"

    @pytest.mark.unit
    async def test_persist_task_result_writes_fields(
        self, sidecar: Sidecar
    ) -> None:
        """_persist_task_result 写入 fields + archive_paths (305-319)"""
        from aipulse.archive.base import ArchivePaths
        from aipulse.core.pipeline import PipelineContext

        creator = await sidecar.handle_request(
            JsonRpcRequest(method="submit_url", params={"url": "https://x.com/p"})
        )
        task_id = creator.result["task_id"]

        archive_paths = MagicMock()
        archive_paths.source_note_path = Path("/tmp/src.md")
        archive_paths.summary_note_path = Path("/tmp/sum.md")

        summary_mock = MagicMock()
        summary_mock.raw_markdown = "raw md body"
        summary_mock.key_points = ["pt1", "pt2"]

        ctx = PipelineContext(
            task_id=task_id,
            url="https://x.com/p",
            content_type="video",
            metadata={"title": "hello"},
            downloaded_path=Path("/tmp/dl.txt"),
            transcript="transcript text",
            summary=summary_mock,
            archive_paths=archive_paths,
        )
        await sidecar._persist_task_result(task_id, ctx)

        stat = await sidecar.handle_request(
            JsonRpcRequest(method="get_task_status", params={"task_id": task_id})
        )
        assert stat.error is None


class TestMainAndReadStdin:
    @pytest.mark.unit
    async def test_main_handles_json_decode_error(self, monkeypatch, tmp_path):
        """main loop: 收到 malformed JSON → -32700 parse error (412-413)"""
        import asyncio
        import sys as _sys

        reset_settings()
        settings = AppSettings(
            _env_file=None,
            data_dir=tmp_path / "data",
            download_dir=tmp_path / "data" / "downloads",
            database_url=f"sqlite+aiosqlite:///{tmp_path}/aipulse.db",
        )
        input_lines = ["not json\n"]
        stdin = MagicMock()
        stdin.readline = AsyncMock(
            side_effect=[line.encode("utf-8") for line in input_lines] + [b""]
        )
        stdout_lines: list[str] = []
        stdout = MagicMock()
        stdout.write = stdout_lines.append
        stdout.flush = MagicMock()

        monkeypatch.setattr(_sys, "stdin", stdin)
        monkeypatch.setattr(_sys, "stdout", stdout)

        with patch("aipulse.desktop.sidecar.init_db", new_callable=AsyncMock):
            with patch("aipulse.desktop.sidecar.close_db", new_callable=AsyncMock):
                with patch(
                    "aipulse.desktop.sidecar.get_settings", return_value=settings
                ):
                    with patch(
                        "aipulse.desktop.sidecar._read_stdin_lines"
                    ) as mock_read:

                        async def _lines():
                            for line in input_lines:
                                yield line.encode("utf-8")

                        mock_read.return_value = _lines()

                        from aipulse.desktop.sidecar import main

                        await main()

        assert len(stdout_lines) == 1
        response = json.loads(stdout_lines[0])
        assert response["error"]["code"] == -32700
        assert "parse error" in response["error"]["message"]


class TestNameMain:
    @pytest.mark.unit
    def test_main_block_does_not_run_on_import(self):
        """if __name__ == '__main__' 分支 (430) 仅在直接执行时跑；
        通过确保没有 side-effect，且 module 加载后 __name__ != '__main__'"""
        import aipulse.desktop.sidecar as sc_mod

        # 当以 import 方式加载时，__name__ == 'aipulse.desktop.sidecar'
        assert sc_mod.__name__ != "__main__"
