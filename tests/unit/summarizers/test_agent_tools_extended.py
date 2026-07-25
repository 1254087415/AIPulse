"""Extended unit tests for v0.3 agent tools (spec §5.6).

覆盖未达 80% 的边界场景：
- fetch_transcript 各种 [ERROR] 路径
- summarize 成功路径 + 超时 + LLM 异常
- judge_tech_relevance 成功路径 + 边界 0.6
- create_obsidian_note 缺 vault / 写文件异常
- create_learning_event hotspot/followed_up 不存在 / 成功
- send_notification 笔记不存在 / Obsidian 写失败 / Apple Reminders 失败
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from aipulse.summarizers.agent.tools import (
    create_learning_event,
    create_obsidian_note,
    fetch_transcript,
    judge_tech_relevance,
    send_notification,
    summarize,
)


def _make_async_client_mock(handler):
    """构建一个 mock httpx.AsyncClient，通过替换 .get() 方法来拦截 HTTP 请求。

    返回一个 callable，调用时返回 mock client 实例。
    使用 httpx.MockTransport + 注入真实 AsyncClient（绕过 patch 避免递归）。
    """
    transport = httpx.MockTransport(handler)
    real_async_client = httpx.AsyncClient  # 抓取真实类，绕过 patch

    def factory(timeout=None, **kwargs):
        kwargs.pop("transport", None)
        return real_async_client(timeout=timeout, transport=transport)

    return factory


# ---------------------------------------------------------------------------
# fetch_transcript
# ---------------------------------------------------------------------------
class TestFetchTranscriptErrors:
    """覆盖 fetch_transcript 各种 [ERROR] 失败路径。"""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_view_api_returns_nonzero_code(self):
        """Step 1: view 接口 code != 0 → [ERROR] 解析 video_id 失败"""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"code": -404, "message": "not found"})

        with patch("httpx.AsyncClient", new=_make_async_client_mock(handler)):
            result = await fetch_transcript.ainvoke({"video_id": "BV1bad"})
        assert "[ERROR] 解析 video_id 失败" in result

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_view_api_no_cid(self):
        """Step 1: view 接口 code=0 但 data.cid 为空"""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"code": 0, "data": {}})

        with patch("httpx.AsyncClient", new=_make_async_client_mock(handler)):
            result = await fetch_transcript.ainvoke({"video_id": "BV1nocid"})
        assert "[ERROR] 拿不到 cid" in result

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_subtitle_api_returns_nonzero_code(self):
        """Step 2: subtitle 接口 code != 0"""

        def handler(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            if "/x/web-interface/view" in url:
                return httpx.Response(200, json={"code": 0, "data": {"cid": 12345}})
            if "/x/player/v2" in url:
                return httpx.Response(200, json={"code": -101, "message": "no auth"})
            return httpx.Response(404)

        with patch("httpx.AsyncClient", new=_make_async_client_mock(handler)):
            result = await fetch_transcript.ainvoke({"video_id": "BV1subbad"})
        assert "[ERROR] 字幕接口返回错误" in result

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_no_subtitles_list(self):
        """Step 2: subtitle 接口 OK 但 sub_list 为空"""

        def handler(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            if "/x/web-interface/view" in url:
                return httpx.Response(200, json={"code": 0, "data": {"cid": 1}})
            return httpx.Response(200, json={"code": 0, "data": {"subtitle": {"subtitles": []}}})

        with patch("httpx.AsyncClient", new=_make_async_client_mock(handler)):
            result = await fetch_transcript.ainvoke({"video_id": "BV1nosubs"})
        assert "[ERROR] 该视频无字幕" in result

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_subtitle_url_missing(self):
        """Step 2: 字幕条目缺 sub_url"""

        def handler(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            if "/x/web-interface/view" in url:
                return httpx.Response(200, json={"code": 0, "data": {"cid": 1}})
            return httpx.Response(200, json={"code": 0, "data": {"subtitle": {"subtitles": [{"lan": "zh-CN"}]}}})

        with patch("httpx.AsyncClient", new=_make_async_client_mock(handler)):
            result = await fetch_transcript.ainvoke({"video_id": "BV1nosuburl"})
        assert "[ERROR] 字幕 URL 缺失" in result

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_subtitle_body_empty(self):
        """Step 3: 字幕 JSON body 为空 → 字幕解析为空"""

        def handler(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            if "/x/web-interface/view" in url:
                return httpx.Response(200, json={"code": 0, "data": {"cid": 1}})
            if "/x/player/v2" in url:
                return httpx.Response(200, json={"code": 0, "data": {"subtitle": {"subtitles": [{"lan": "zh-CN", "sub_url": "https://x.test/subs.json"}]}}})
            # subtitle JSON
            return httpx.Response(200, json=[])

        with patch("httpx.AsyncClient", new=_make_async_client_mock(handler)):
            result = await fetch_transcript.ainvoke({"video_id": "BV1emptybody"})
        assert "[ERROR] 字幕解析为空" in result

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_subtitle_body_skips_blank_lines(self):
        """Step 3: 字幕 JSON body 有空字符串 → 跳过 + 返回剩余行"""

        def handler(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            if "/x/web-interface/view" in url:
                return httpx.Response(200, json={"code": 0, "data": {"cid": 1}})
            if "/x/player/v2" in url:
                return httpx.Response(200, json={"code": 0, "data": {"subtitle": {"subtitles": [{"lan": "zh-CN", "sub_url": "https://x.test/subs.json"}]}}})
            return httpx.Response(200, json=[{"content": "  第一行  "}, {"content": ""}, {"content": "第二行"}])

        with patch("httpx.AsyncClient", new=_make_async_client_mock(handler)):
            result = await fetch_transcript.ainvoke({"video_id": "BV1ok"})
        assert "第一行" in result
        assert "第二行" in result
        # 空行被 strip 后丢弃
        assert result.count("\n") == 1

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_uses_first_subtitle_when_no_zh(self):
        """Step 2: 没有中文轨时回退到第一条"""

        def handler(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            if "/x/web-interface/view" in url:
                return httpx.Response(200, json={"code": 0, "data": {"cid": 1}})
            if "/x/player/v2" in url:
                return httpx.Response(200, json={"code": 0, "data": {"subtitle": {"subtitles": [{"lan": "en-US", "sub_url": "https://x.test/en.json"}]}}})
            return httpx.Response(200, json=[{"content": "English line"}])

        with patch("httpx.AsyncClient", new=_make_async_client_mock(handler)):
            result = await fetch_transcript.ainvoke({"video_id": "BV1en"})
        assert result == "English line"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_subtitle_url_protocol_relative(self):
        """Step 3: sub_url 以 // 开头 → 自动补 https:"""

        def handler(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            if "/x/web-interface/view" in url:
                return httpx.Response(200, json={"code": 0, "data": {"cid": 1}})
            if "/x/player/v2" in url:
                return httpx.Response(200, json={"code": 0, "data": {"subtitle": {"subtitles": [{"lan": "zh-CN", "sub_url": "//x.test/subs.json"}]}}})
            return httpx.Response(200, json=[{"content": "OK"}])

        with patch("httpx.AsyncClient", new=_make_async_client_mock(handler)):
            result = await fetch_transcript.ainvoke({"video_id": "BV1proto"})
        assert result == "OK"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_generic_exception_returns_error_string(self):
        """fetch_transcript 中网络异常 → [ERROR] 字幕不可用"""

        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused")

        with patch("httpx.AsyncClient", new=_make_async_client_mock(handler)):
            result = await fetch_transcript.ainvoke({"video_id": "BV1err"})
        assert "[ERROR] 字幕不可用" in result


# ---------------------------------------------------------------------------
# summarize
# ---------------------------------------------------------------------------
class TestSummarizeToolSuccess:
    """覆盖 summarize 成功路径 + 超时 + LLM 异常。"""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_summarize_success(self):
        from aipulse.summarizers import llm as llm_mod

        class _FakeAdapter:
            def __init__(self, *args, **kwargs):
                pass

            async def complete(self, prompt, system=None):
                return "# Title\n\n## TL;DR\n- point"

        original = llm_mod.OpenAICompatibleAdapter
        llm_mod.OpenAICompatibleAdapter = _FakeAdapter  # type: ignore[assignment]
        try:
            result = await summarize.ainvoke({"video_id": "BV1", "transcript": "real text", "extra_context": ""})
        finally:
            llm_mod.OpenAICompatibleAdapter = original  # type: ignore[assignment]

        assert result["ok"] is True
        assert "Title" in result["markdown"]
        assert result["model"]  # 不为空

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_summarize_timeout_returns_error(self):
        import asyncio as _asyncio
        from aipulse.summarizers import llm as llm_mod

        class _SlowAdapter:
            def __init__(self, *args, **kwargs):
                pass

            async def complete(self, prompt, system=None):
                await _asyncio.sleep(10)
                return "should not reach"

        original = llm_mod.OpenAICompatibleAdapter
        llm_mod.OpenAICompatibleAdapter = _SlowAdapter  # type: ignore[assignment]
        try:
            # monkeypatch asyncio.wait_for to short-circuit timeout
            import aipulse.summarizers.agent.tools as tools_mod
            original_wait_for = tools_mod.asyncio.wait_for

            async def _short_wait_for(awaitable, timeout):
                raise _asyncio.TimeoutError()

            tools_mod.asyncio.wait_for = _short_wait_for  # type: ignore[assignment]
            try:
                result = await summarize.ainvoke({"video_id": "BV1", "transcript": "text", "extra_context": ""})
            finally:
                tools_mod.asyncio.wait_for = original_wait_for  # type: ignore[assignment]
        finally:
            llm_mod.OpenAICompatibleAdapter = original  # type: ignore[assignment]

        assert result["ok"] is False
        assert "180s" in result["error"]

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_summarize_llm_exception_returns_error(self):
        from aipulse.summarizers import llm as llm_mod

        class _BoomAdapter:
            def __init__(self, *args, **kwargs):
                pass

            async def complete(self, prompt, system=None):
                raise RuntimeError("Kimi 502")

        original = llm_mod.OpenAICompatibleAdapter
        llm_mod.OpenAICompatibleAdapter = _BoomAdapter  # type: ignore[assignment]
        try:
            result = await summarize.ainvoke({"video_id": "BV1", "transcript": "text", "extra_context": ""})
        finally:
            llm_mod.OpenAICompatibleAdapter = original  # type: ignore[assignment]

        assert result["ok"] is False
        assert "Kimi 502" in result["error"]


# ---------------------------------------------------------------------------
# judge_tech_relevance
# ---------------------------------------------------------------------------
class TestJudgeToolSuccess:
    """覆盖 judge_tech_relevance 成功路径。"""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_judge_high_score_should_archive(self):
        from aipulse.summarizers import llm as llm_mod

        class _FakeAdapter:
            def __init__(self, *args, **kwargs):
                pass

            async def complete(self, prompt, system=None):
                return json.dumps({"score": 0.85, "reason": "深度技术讲解"})

        original = llm_mod.OpenAICompatibleAdapter
        llm_mod.OpenAICompatibleAdapter = _FakeAdapter  # type: ignore[assignment]
        try:
            result = await judge_tech_relevance.ainvoke({"markdown": "deep tech"})
        finally:
            llm_mod.OpenAICompatibleAdapter = original  # type: ignore[assignment]

        assert result["ok"] is True
        assert result["score"] == 0.85
        assert result["should_archive"] is True
        assert "深度" in result["reason"]

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_judge_low_score_should_not_archive(self):
        from aipulse.summarizers import llm as llm_mod

        class _FakeAdapter:
            def __init__(self, *args, **kwargs):
                pass

            async def complete(self, prompt, system=None):
                return json.dumps({"score": 0.4, "reason": "娱乐向"})

        original = llm_mod.OpenAICompatibleAdapter
        llm_mod.OpenAICompatibleAdapter = _FakeAdapter  # type: ignore[assignment]
        try:
            result = await judge_tech_relevance.ainvoke({"markdown": "vlog"})
        finally:
            llm_mod.OpenAICompatibleAdapter = original  # type: ignore[assignment]

        assert result["ok"] is True
        assert result["score"] == 0.4
        assert result["should_archive"] is False

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_judge_boundary_score_0_6_should_archive(self):
        """边界值 0.6 → should_archive=True"""

        from aipulse.summarizers import llm as llm_mod

        class _FakeAdapter:
            def __init__(self, *args, **kwargs):
                pass

            async def complete(self, prompt, system=None):
                return json.dumps({"score": 0.6, "reason": "刚好阈值"})

        original = llm_mod.OpenAICompatibleAdapter
        llm_mod.OpenAICompatibleAdapter = _FakeAdapter  # type: ignore[assignment]
        try:
            result = await judge_tech_relevance.ainvoke({"markdown": "tech"})
        finally:
            llm_mod.OpenAICompatibleAdapter = original  # type: ignore[assignment]

        assert result["should_archive"] is True


# ---------------------------------------------------------------------------
# create_obsidian_note
# ---------------------------------------------------------------------------
class TestCreateObsidianNote:
    """覆盖 create_obsidian_note 各分支。"""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_missing_vault_path_returns_error(self, tmp_path):
        """vault 路径不存在 → 创建时 PermissionError → ok=False"""

        # 直接 patch tools.py 模块里的 get_settings 引用
        settings = MagicMock()
        settings.obsidian_vault_path = Path("/Users/xxx/Documents/Obsidian Vault")  # 不存在路径
        settings.obsidian_archive_folder = "AIPulse"
        settings.kimi_model = "kimi-for-coding"

        with patch("aipulse.summarizers.agent.tools.get_settings", return_value=settings):
            result = await create_obsidian_note.ainvoke(
                {
                    "video_id": "BV1",
                    "markdown": "hello",
                    "title": "T",
                    "up_name": "U",
                }
            )
        # mkdir 失败 → ok=False
        assert result["ok"] is False
        assert "Obsidian" in result["error"] or "写入" in result["error"]

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_creates_note_with_frontmatter_injection(self, tmp_path):
        """vault 存在 + markdown 无 frontmatter → 自动注入 frontmatter"""

        settings = MagicMock()
        settings.obsidian_vault_path = tmp_path
        settings.obsidian_archive_folder = "AIPulse"
        settings.kimi_model = "kimi-for-coding"

        with patch("aipulse.summarizers.agent.tools.get_settings", return_value=settings):
            result = await create_obsidian_note.ainvoke(
                {
                    "video_id": "BV1abc",
                    "markdown": "# Hello",
                    "title": "T/\\*?<>|",  # 含非法字符
                    "up_name": "U",
                }
            )

        assert result["ok"] is True, result
        note_path = Path(result["note_path"])
        assert note_path.exists()
        # 非法字符被剔除
        for ch in '\\/*?<>|"':
            assert ch not in note_path.name, f"{ch} in {note_path.name}"
        # frontmatter 注入
        content = note_path.read_text(encoding="utf-8")
        assert content.startswith("---\n")
        assert "video_id: BV1abc" in content
        assert "model: kimi-for-coding" in content
        # 原始 markdown 保留
        assert "# Hello" in content

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_skips_frontmatter_injection_when_present(self, tmp_path):
        """markdown 已有 frontmatter → 不重复注入"""

        settings = MagicMock()
        settings.obsidian_vault_path = tmp_path
        settings.obsidian_archive_folder = "AIPulse"
        settings.kimi_model = "kimi-for-coding"

        with patch("aipulse.summarizers.agent.tools.get_settings", return_value=settings):
            existing = "---\nfoo: bar\n---\n\n# Body"
            result = await create_obsidian_note.ainvoke(
                {
                    "video_id": "BV1has",
                    "markdown": existing,
                    "title": "T",
                    "up_name": "U",
                }
            )

        assert result["ok"] is True, result
        content = Path(result["note_path"]).read_text(encoding="utf-8")
        # 没有重复注入 video_id
        assert "video_id: BV1has" not in content
        # 原内容保留
        assert "foo: bar" in content

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_long_title_truncated_to_80_chars(self, tmp_path):
        settings = MagicMock()
        settings.obsidian_vault_path = tmp_path
        settings.obsidian_archive_folder = "AIPulse"
        settings.kimi_model = "kimi-for-coding"

        with patch("aipulse.summarizers.agent.tools.get_settings", return_value=settings):
            long_title = "A" * 200
            result = await create_obsidian_note.ainvoke(
                {
                    "video_id": "BV1long",
                    "markdown": "x",
                    "title": long_title,
                    "up_name": "U",
                }
            )

        assert result["ok"] is True, result
        # 文件名部分（去掉 .md）不超过 80 + BV 号 + -
        name = Path(result["note_path"]).stem
        suffix_len = len("-BV1long")
        assert len(name) <= 80 + suffix_len

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_empty_title_becomes_untitled(self, tmp_path):
        settings = MagicMock()
        settings.obsidian_vault_path = tmp_path
        settings.obsidian_archive_folder = "AIPulse"
        settings.kimi_model = "kimi-for-coding"

        with patch("aipulse.summarizers.agent.tools.get_settings", return_value=settings):
            result = await create_obsidian_note.ainvoke(
                {
                    "video_id": "BV1notitle",
                    "markdown": "x",
                    "title": "",
                    "up_name": "U",
                }
            )

        assert result["ok"] is True, result
        assert "untitled" in Path(result["note_path"]).name


# ---------------------------------------------------------------------------
# create_learning_event
# ---------------------------------------------------------------------------
class TestCreateLearningEvent:
    """覆盖 create_learning_event 各分支。"""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_hotspot_not_found_returns_error(self, db_session):
        result = await create_learning_event.ainvoke(
            {
                "video_id": "BV1unknown",
                "note_path": "/tmp/note.md",
                "scheduled_at": "2026-07-26T20:00:00",
                "topic": "Test",
            }
        )
        assert result["ok"] is False
        assert "未找到" in result["error"]

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_hotspot_without_followed_up_returns_error(self, db_session):
        """hotspot 存在但没有 followed_up_id → 报错"""

        from aipulse.hotspot.models import Hotspot, Source

        # 需要一个 Source 才能 FK
        source = Source(
            id="src-bilibili",
            name="bilibili-test",
            source_type="bilibili",
            collector_class="aipulse.collectors.bilibili_up.factory.BilibiliUpCollectorFactory",
            config={},
        )
        db_session.add(source)
        await db_session.flush()

        # 创建 hotspot 但不关联 followed_up
        hotspot = Hotspot(
            title="No FU",
            url="https://www.bilibili.com/video/BV1nofu",
            canonical_url="https://www.bilibili.com/video/BV1nofu",
            source_id=source.id,
            source_type="bilibili",
            content_id="BV1nofu",
            followed_up_id=None,
        )
        db_session.add(hotspot)
        await db_session.commit()

        result = await create_learning_event.ainvoke(
            {
                "video_id": "BV1nofu",
                "note_path": "/tmp/n.md",
                "scheduled_at": "2026-07-26T20:00:00",
                "topic": "T",
            }
        )
        assert result["ok"] is False
        assert "followed_up" in result["error"]

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_success_creates_event(self, db_session):
        """hotspot + followed_up 齐全 → 创建成功"""

        from aipulse.hotspot.models import Hotspot, Source
        from aipulse.models.followed_up import FollowedUp

        source = Source(
            id="src-bilibili-ok",
            name="bilibili-ok",
            source_type="bilibili",
            collector_class="aipulse.collectors.bilibili_up.factory.BilibiliUpCollectorFactory",
            config={},
        )
        db_session.add(source)
        await db_session.flush()

        fu = FollowedUp(
            platform="bilibili",
            uid="10001",
            display_name="TestUP",
            profile_url="https://space.bilibili.com/10001",
        )
        db_session.add(fu)
        await db_session.flush()

        hotspot = Hotspot(
            title="Success",
            url="https://www.bilibili.com/video/BV1success",
            canonical_url="https://www.bilibili.com/video/BV1success",
            source_id=source.id,
            source_type="bilibili",
            content_id="BV1success",
            followed_up_id=fu.id,
        )
        db_session.add(hotspot)
        await db_session.commit()

        result = await create_learning_event.ainvoke(
            {
                "video_id": "BV1success",
                "note_path": "/tmp/note.md",
                "scheduled_at": "2026-07-26T20:00:00",
                "topic": "Topic",
            }
        )
        assert result["ok"] is True
        assert result["event_id"]


# ---------------------------------------------------------------------------
# send_notification
# ---------------------------------------------------------------------------
class TestSendNotification:
    """覆盖 send_notification 各分支。"""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_note_path_missing(self):
        result = await send_notification.ainvoke(
            {
                "note_path": "/tmp/does-not-exist-note.md",
                "scheduled_at": "2026-07-26T20:00:00",
                "topic": "T",
            }
        )
        assert result["ok"] is False
        assert "笔记不存在" in result["error"]

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_obsidian_task_appended_success(self, tmp_path):
        """笔记存在 + Apple Reminders 模块不可用 → ok=True, obsidian_task=True"""

        note = tmp_path / "note.md"
        note.write_text("---\nfoo: bar\n---\n\n# Body", encoding="utf-8")

        with patch.dict("sys.modules", {"aipulse.apple.reminders": None}):
            # sys.modules 设 None → import 会抛 ImportError → 走 ImportError 分支
            result = await send_notification.ainvoke(
                {
                    "note_path": str(note),
                    "scheduled_at": "2026-07-26T20:00:00",
                    "topic": "Math",
                }
            )

        assert result["ok"] is True
        assert result["obsidian_task"] is True
        # 笔记末尾追加了 task
        content = note.read_text(encoding="utf-8")
        assert "- [ ] ⏰ 2026-07-26 20:00 Math" in content

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_obsidian_write_failure_short_circuits(self, tmp_path):
        """写入失败 → 直接返回错误，不调 Apple Reminders"""

        note = tmp_path / "note.md"
        note.write_text("orig", encoding="utf-8")

        # monkey-patch asyncio.to_thread 让它抛 OSError
        async def _broken(*args, **kwargs):
            raise OSError("disk full")

        with patch("aipulse.summarizers.agent.tools.asyncio.to_thread", new=_broken):
            result = await send_notification.ainvoke(
                {
                    "note_path": str(note),
                    "scheduled_at": "2026-07-26T20:00:00",
                    "topic": "T",
                }
            )

        assert result["ok"] is False
        assert "Obsidian Task 写入失败" in result["error"]

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_apple_reminders_failure_does_not_fail_overall(self, tmp_path):
        """Apple Reminders 失败 → ok 仍为 True, reminder_error 存在"""

        note = tmp_path / "note.md"
        note.write_text("orig", encoding="utf-8")

        # fake module with create_reminder that raises
        fake_module = MagicMock()
        async def _boom(*args, **kwargs):
            raise RuntimeError("EventKit denied")
        fake_module.create_reminder = _boom

        with patch.dict("sys.modules", {"aipulse.apple.reminders": fake_module}):
            # tools.py 用 `from aipulse.apple.reminders import create_reminder`
            # patch 已经设了 module，但 `from X import Y` 不会重新 import — 需要 patch 单点
            with patch("aipulse.apple.reminders.create_reminder", new=_boom):
                result = await send_notification.ainvoke(
                    {
                        "note_path": str(note),
                        "scheduled_at": "2026-07-26T20:00:00",
                        "topic": "T",
                    }
                )

        assert result["ok"] is True
        assert result["obsidian_task"] is True
        assert "reminder_error" in result
        assert "EventKit" in result["reminder_error"]