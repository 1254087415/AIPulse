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
    default_scheduled_at,
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


@pytest.fixture
def transcript_cache_dir(tmp_path, monkeypatch):
    """R5-C (2026-07-26)：让 fetch_transcript 落盘到 tmp_path/cache/transcripts/。

    每测独立 tmp_path 不污染；并返回路径对象供断言。
    """
    cache_dir = tmp_path / "cache" / "transcripts"
    cache_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        "aipulse.summarizers.agent.tools._transcript_cache_dir",
        lambda: cache_dir,
    )
    return cache_dir


def _read_cache_transcript(path_str):
    """R5-C：读 fetch_transcript 落盘文件，剥 frontmatter 返回纯字幕文本。"""
    raw = Path(path_str).read_text(encoding="utf-8")
    if not raw.startswith("---\n"):
        return raw.strip("\n")
    end = raw.find("\n---\n", 4)
    if end < 0:
        return raw.strip("\n")
    return raw[end + len("\n---\n"):].strip("\n")


# ---------------------------------------------------------------------------
# fetch_transcript
# ---------------------------------------------------------------------------
class TestFetchTranscriptErrors:
    """覆盖 fetch_transcript 各种 [ERROR] 失败路径。"""

    @pytest.fixture(autouse=True)
    def _no_obsidian_cookie(self, monkeypatch):
        """强制走无 cookie 公开接口（dm/view fallback）。

        L1#5/L4 (2026-07-26) 抄 skill 后 fetch_transcript 默认会先读
        Obsidian Media Extended cookie；旧测试期望 cookie=None。
        """
        monkeypatch.setattr(
            "aipulse.summarizers.agent.tools._bilibili_read_cookies",
            lambda: None,
        )

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
        """Step 2b: dm/view fallback 接口 code != 0 → 无字幕"""

        def handler(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            if "/x/web-interface/view" in url:
                return httpx.Response(200, json={"code": 0, "data": {"cid": 12345}})
            if "/x/v2/dm/view" in url:
                return httpx.Response(200, json={"code": -101, "message": "no auth"})
            return httpx.Response(404)

        with patch("httpx.AsyncClient", new=_make_async_client_mock(handler)):
            result = await fetch_transcript.ainvoke({"video_id": "BV1subbad"})
        assert "[ERROR] 该视频无字幕" in result

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_no_subtitles_list(self):
        """Step 2b: dm/view 返回 OK 但 sub_list 为空"""

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
        """Step 3: 所有字幕轨道均无 subtitle_url → 验证失败"""

        def handler(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            if "/x/web-interface/view" in url:
                return httpx.Response(200, json={"code": 0, "data": {"cid": 1}})
            return httpx.Response(200, json={"code": 0, "data": {"subtitle": {"subtitles": [{"lan": "zh-CN"}]}}})

        with patch("httpx.AsyncClient", new=_make_async_client_mock(handler)):
            result = await fetch_transcript.ainvoke({"video_id": "BV1nosuburl"})
        assert "[ERROR] 所有字幕轨道验证失败" in result

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_subtitle_body_empty(self):
        """Step 3 (skill 同款): body 为空 → helper 视为无效轨道 → 所有验证失败"""

        def handler(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            if "/x/web-interface/view" in url:
                return httpx.Response(200, json={"code": 0, "data": {"cid": 1}})
            if "/x/v2/dm/view" in url:
                return httpx.Response(200, json={"code": 0, "data": {"subtitle": {"subtitles": [{"lan": "zh-CN", "lan_doc": "中文（简体）", "subtitle_url": "https://x.test/subs.json"}]}}})
            return httpx.Response(200, json=[])

        with patch("httpx.AsyncClient", new=_make_async_client_mock(handler)):
            with patch(
                "urllib.request.urlopen",
                MagicMock(return_value=_FakeURLRead(b'{"body": []}')),
            ):
                result = await fetch_transcript.ainvoke({"video_id": "BV1emptybody"})
        assert "[ERROR] 所有字幕轨道验证失败" in result

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_subtitle_body_skips_blank_lines(self, transcript_cache_dir):
        """Step 3: 字幕 JSON body 有空字符串 → 跳过 + 落盘文件只含非空行"""

        def handler(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            if "/x/web-interface/view" in url:
                return httpx.Response(200, json={"code": 0, "data": {"cid": 1}})
            if "/x/v2/dm/view" in url:
                return httpx.Response(200, json={"code": 0, "data": {"subtitle": {"subtitles": [{"lan": "zh-CN", "lan_doc": "中文（简体）", "subtitle_url": "https://x.test/subs.json"}]}}})
            return httpx.Response(200, json=[])

        subtitle_payload = json.dumps(
            {
                "body": [
                    {"from": 0.0, "to": 5.0, "content": "  第一行  "},
                    {"from": 6.0, "to": 10.0, "content": ""},
                    {"from": 11.0, "to": 15.0, "content": "第二行"},
                    {"from": 16.0, "to": 20.0, "content": "第三行"},
                    {"from": 21.0, "to": 25.0, "content": "第四行"},
                    {"from": 26.0, "to": 30.0, "content": "第五行"},
                ]
            }
        ).encode("utf-8")

        with patch("httpx.AsyncClient", new=_make_async_client_mock(handler)):
            with patch(
                "urllib.request.urlopen",
                MagicMock(return_value=_FakeURLRead(subtitle_payload)),
            ):
                result = await fetch_transcript.ainvoke({"video_id": "BV1ok"})
        assert Path(result).exists(), f"落盘文件不存在：{result}"
        cached = _read_cache_transcript(result)
        assert "第一行" in cached
        assert "第二行" in cached
        # 5 行非空内容 → 4 个换行
        assert cached.count("\n") == 4

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_uses_first_subtitle_when_no_zh(self, transcript_cache_dir):
        """Step 3: 没有中文轨时回退到第一条（en-US 优先）"""

        def handler(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            if "/x/web-interface/view" in url:
                return httpx.Response(200, json={"code": 0, "data": {"cid": 1}})
            if "/x/v2/dm/view" in url:
                return httpx.Response(200, json={"code": 0, "data": {"subtitle": {"subtitles": [{"lan": "en-US", "lan_doc": "English", "subtitle_url": "https://x.test/en.json"}]}}})
            return httpx.Response(200, json=[])

        subtitle_payload = json.dumps(
            {
                "body": [
                    {"from": 0.0, "to": 5.0, "content": "English line 1"},
                    {"from": 6.0, "to": 10.0, "content": "English line 2"},
                    {"from": 11.0, "to": 15.0, "content": "English line 3"},
                    {"from": 16.0, "to": 20.0, "content": "English line 4"},
                    {"from": 21.0, "to": 25.0, "content": "English line 5"},
                    {"from": 26.0, "to": 30.0, "content": "English line"},
                ]
            }
        ).encode("utf-8")

        with patch("httpx.AsyncClient", new=_make_async_client_mock(handler)):
            with patch(
                "urllib.request.urlopen",
                MagicMock(return_value=_FakeURLRead(subtitle_payload)),
            ):
                result = await fetch_transcript.ainvoke({"video_id": "BV1en"})
        cached = _read_cache_transcript(result)
        assert "English line" in cached

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_subtitle_url_protocol_relative(self, transcript_cache_dir):
        """Step 3: sub_url 以 // 开头 → 自动补 https:"""

        def handler(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            if "/x/web-interface/view" in url:
                return httpx.Response(200, json={"code": 0, "data": {"cid": 1}})
            if "/x/v2/dm/view" in url:
                return httpx.Response(200, json={"code": 0, "data": {"subtitle": {"subtitles": [{"lan": "zh-CN", "lan_doc": "中文（简体）", "subtitle_url": "//x.test/subs.json"}]}}})
            return httpx.Response(200, json=[])

        subtitle_payload = json.dumps(
            {
                "body": [
                    {"from": 0.0, "to": 5.0, "content": "OK 1"},
                    {"from": 6.0, "to": 10.0, "content": "OK 2"},
                    {"from": 11.0, "to": 15.0, "content": "OK 3"},
                    {"from": 16.0, "to": 20.0, "content": "OK 4"},
                    {"from": 21.0, "to": 25.0, "content": "OK 5"},
                    {"from": 26.0, "to": 30.0, "content": "OK 6"},
                ]
            }
        ).encode("utf-8")

        with patch("httpx.AsyncClient", new=_make_async_client_mock(handler)):
            with patch(
                "urllib.request.urlopen",
                MagicMock(return_value=_FakeURLRead(subtitle_payload)),
            ):
                result = await fetch_transcript.ainvoke({"video_id": "BV1proto"})
        cached = _read_cache_transcript(result)
        assert "OK" in cached

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_generic_exception_returns_error_string(self):
        """fetch_transcript 中网络异常 → [ERROR] 字幕不可用"""

        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused")

        with patch("httpx.AsyncClient", new=_make_async_client_mock(handler)):
            result = await fetch_transcript.ainvoke({"video_id": "BV1err"})
        assert "[ERROR] 字幕不可用" in result

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_no_subtitles_no_cookie_returns_error(self):
        """Step 2c: 无字幕 + 无 cookie → 不触发 whisper，回退到 [ERROR] 该视频无字幕"""

        def handler(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            if "/x/web-interface/view" in url:
                return httpx.Response(200, json={"code": 0, "data": {"cid": 1}})
            return httpx.Response(200, json={"code": 0, "data": {"subtitle": {"subtitles": []}}})

        # 强制 cookies 为空：避免测试环境里真有 macOS Obsidian cookie 触发 whisper
        with patch(
            "aipulse.summarizers.agent.bilibili_subtitle.read_obsidian_media_extended_cookies",
            return_value=None,
        ):
            with patch("httpx.AsyncClient", new=_make_async_client_mock(handler)):
                result = await fetch_transcript.ainvoke({"video_id": "BV1noss"})

        assert "[ERROR] 该视频无字幕" in result

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_no_subtitles_with_cookie_no_audio_url_returns_error(
        self, transcript_cache_dir
    ):
        """Step 2c: 有 cookie + 无 dash.audio → whisper 跳过 → [ERROR] 该视频无字幕"""

        def handler(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            if "/x/web-interface/view" in url:
                # 无 dash.audio → whisper 内部 no-op
                return httpx.Response(
                    200,
                    json={"code": 0, "data": {"cid": 1, "title": "t"}},
                )
            return httpx.Response(200, json={"code": 0, "data": {"subtitle": {"subtitles": []}}})

        with patch(
            "aipulse.summarizers.agent.bilibili_subtitle.read_obsidian_media_extended_cookies",
            return_value={"SESSDATA": "fake-cookie"},
        ):
            with patch("httpx.AsyncClient", new=_make_async_client_mock(handler)):
                result = await fetch_transcript.ainvoke({"video_id": "BV1noaudio"})

        assert "[ERROR] 该视频无字幕" in result

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_whisper_fallback_success(
        self, transcript_cache_dir, monkeypatch
    ):
        """Step 2c: 无字幕 + cookie + dash.audio → 走 Whisper fallback，落盘 source=whisper。

        全链路 mock：httpx 返回 B 站接口 + dash.audio URL；
        WhisperSubtitleStrategy._transcriber.transcribe 替换成 AsyncMock 返回固定文本。
        """
        from aipulse.summarizers.agent.tools import _try_whisper_fallback

        audio_url = "https://upstream.test/audio.m4a"
        cookies = {"SESSDATA": "fake-cookie"}
        info = {"title": "test video", "dash": {"audio": [{"base_url": audio_url}]}}

        # 抓 audio URL 的下载 → 返回固定字节
        downloaded = b"FAKE_AUDIO_BYTES"

        def handler(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            if audio_url in url:
                return httpx.Response(200, content=downloaded)
            return httpx.Response(200, json={"code": 0})

        # 替换 WhisperSubtitleStrategy._transcriber.transcribe 为异步 mock
        from aipulse.video.subtitle import whisper as whisper_mod

        async def fake_transcribe(self, _path):
            return "这是 whisper 转写的文本"

        monkeypatch.setattr(
            whisper_mod.AudioTranscriber,
            "transcribe",
            fake_transcribe,
        )

        with patch("httpx.AsyncClient", new=_make_async_client_mock(handler)):
            result = await _try_whisper_fallback("BV1whisper", info, {}, cookies)

        assert result == "这是 whisper 转写的文本"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_whisper_fallback_no_cookie_returns_none(self):
        """Step 2c: 无 cookie → _try_whisper_fallback 返回 None（不发起请求）。"""
        from aipulse.summarizers.agent.tools import _try_whisper_fallback

        info = {"title": "x", "dash": {"audio": [{"base_url": "https://upstream.test/audio.m4a"}]}}
        result = await _try_whisper_fallback("BV1nc", info, {}, None)
        assert result is None

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_whisper_fallback_no_audio_url_returns_none(self):
        """Step 2c: 有 cookie 但 dash.audio 缺失 → 返回 None。"""
        from aipulse.summarizers.agent.tools import _try_whisper_fallback

        info = {"title": "x", "dash": {}}
        result = await _try_whisper_fallback(
            "BV1na", info, {}, {"SESSDATA": "fake"}
        )
        assert result is None


# ---------------------------------------------------------------------------
# summarize
# ---------------------------------------------------------------------------
class TestSummarizeToolSuccess:
    """覆盖 summarize 成功路径 + 超时 + LLM 异常。"""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_summarize_success(self, tmp_path):
        from aipulse.summarizers import llm as llm_mod

        # R5-C (2026-07-26)：summarize 接受 transcript_path（落盘后的字幕文件）。
        transcript = tmp_path / "BV1.md"
        transcript.write_text(
            "---\nbvid: BV1\nfetched_at: 2026-07-26T07:00:00Z\nsource: bilibili\n---\n\nreal text\n",
            encoding="utf-8",
        )

        class _FakeAdapter:
            def __init__(self, *args, **kwargs):
                pass

            async def complete(self, prompt, system=None):
                return "# Title\n\n## TL;DR\n- point"

        original = llm_mod.OpenAICompatibleAdapter
        llm_mod.OpenAICompatibleAdapter = _FakeAdapter  # type: ignore[assignment]
        try:
            result = await summarize.ainvoke(
                {
                    "video_id": "BV1",
                    "transcript_path": str(transcript),
                    "extra_context": "",
                }
            )
        finally:
            llm_mod.OpenAICompatibleAdapter = original  # type: ignore[assignment]

        assert result["ok"] is True
        assert "Title" in result["markdown"]
        assert result["model"]  # 不为空
        assert result["transcript_path"] == str(transcript)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_summarize_timeout_returns_error(self, tmp_path):
        import asyncio as _asyncio
        from aipulse.summarizers import llm as llm_mod

        transcript = tmp_path / "BV1.md"
        transcript.write_text(
            "---\nbvid: BV1\nfetched_at: 2026-07-26T07:00:00Z\nsource: bilibili\n---\n\ntext\n",
            encoding="utf-8",
        )

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
                result = await summarize.ainvoke(
                    {
                        "video_id": "BV1",
                        "transcript_path": str(transcript),
                        "extra_context": "",
                    }
                )
            finally:
                tools_mod.asyncio.wait_for = original_wait_for  # type: ignore[assignment]
        finally:
            llm_mod.OpenAICompatibleAdapter = original  # type: ignore[assignment]

        assert result["ok"] is False
        assert "180s" in result["error"]
        assert result["transcript_path"] == str(transcript)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_summarize_llm_exception_returns_error(self, tmp_path):
        from aipulse.summarizers import llm as llm_mod

        transcript = tmp_path / "BV1.md"
        transcript.write_text(
            "---\nbvid: BV1\nfetched_at: 2026-07-26T07:00:00Z\nsource: bilibili\n---\n\ntext\n",
            encoding="utf-8",
        )

        class _BoomAdapter:
            def __init__(self, *args, **kwargs):
                pass

            async def complete(self, prompt, system=None):
                raise RuntimeError("Kimi 502")

        original = llm_mod.OpenAICompatibleAdapter
        llm_mod.OpenAICompatibleAdapter = _BoomAdapter  # type: ignore[assignment]
        try:
            result = await summarize.ainvoke(
                {
                    "video_id": "BV1",
                    "transcript_path": str(transcript),
                    "extra_context": "",
                }
            )
        finally:
            llm_mod.OpenAICompatibleAdapter = original  # type: ignore[assignment]

        assert result["ok"] is False
        assert "Kimi 502" in result["error"]
        assert result["transcript_path"] == str(transcript)


# ---------------------------------------------------------------------------
# summarize 必传 transcript_path 契约（R5-C · 2026-07-26）
#   L8 (2026-07-26) 旧契约：summarize(video_id, transcript, extra_context)
#   R5-C (2026-07-26) 新契约：summarize(video_id, transcript_path, extra_context)
#   改字幕传文件路径避免 Action Input JSON 字符串过长。
# ---------------------------------------------------------------------------
class TestSummarizeRequiresTranscriptPath:
    """R5-C：summarize 必传 transcript_path（来自 fetch_transcript 落盘的文件）。

    验证 LangChain @tool 反推的 args_schema 必填项 + Pydantic 拒绝行为，
    并固化该契约（系统 prompt 必须告诉 LLM 不能漏）。
    """

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_summarize_dict_input_video_id_falls_back_to_str(self, tmp_path):
        """R5-C 续 (2026-07-26)：summarize 输入是 dict 时兜底成 .video_id 字符串。

        Kimi ReAct parser 不稳定时会把 ``{"video_id": "...", "transcript_path": "..."}``
        整个 dict 序列化成 Action.input 一个字段（典型：把 fetch_transcript 返回的
        字幕全文 + 标题 / UP主 拼成 ``{"video_id": "{...标题：；UP主：}"}`` 塞给
        summarize.video_id）。原 LangChain 默认 args_schema 会 ValidationError →
        parser 抛 ``Missing 'Action:'`` → 整个 pipeline 拖入 status 错位状态。
        现在 SummarizeInput Union 兜底让函数体拿到 str，链路继续跑通。
        """
        from aipulse.summarizers import llm as llm_mod

        # 落盘字幕文件
        transcript = tmp_path / "BV1dict.md"
        transcript.write_text(
            "---\nbvid: BV1dict\nfetched_at: 2026-07-26T08:00:00Z\nsource: bilibili\n---\n\n字幕文本\n",
            encoding="utf-8",
        )

        class _FakeAdapter:
            def __init__(self, *args, **kwargs):
                pass

            async def complete(self, prompt, system=None):
                return "# Title\n\n## TL;DR\n- from R5-C dict fallback test"

        original = llm_mod.OpenAICompatibleAdapter
        llm_mod.OpenAICompatibleAdapter = _FakeAdapter  # type: ignore[assignment]
        try:
            # 模拟 Kimi parser 错误输出：把 dict 整个塞给 video_id
            result = await summarize.ainvoke(
                {
                    "video_id": {"video_id": "BV1dict", "extra": "noise"},
                    "transcript_path": str(transcript),
                }
            )
        finally:
            llm_mod.OpenAICompatibleAdapter = original  # type: ignore[assignment]
        assert result.get("ok") is True, result
        assert "R5-C dict fallback test" in result["markdown"]
        assert result["transcript_path"] == str(transcript)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_summarize_without_transcript_path_returns_error(self):
        """R5-C 续 (2026-07-26)：summarize 显式传空 transcript_path → 函数体返 {ok: False}。

        之前 L8 契约：summarize 缺 transcript_path → Pydantic ValidationError
        → LangChain parser 抛 ``Missing 'Action:'`` → 整个 pipeline 拖入
        status 错位状态。R5-C 续改用 SummarizeInput (Union) 兜底 dict 输入，
        缺字段不再抛 ValidationError（LangChain @tool args_schema 用 Pydantic
        反推 required 字段，缺字段是 TypeError，不是 ValidationError），而是
        函数体显式返 ``{ok: False, error: ...}``。
        错误信息明确点名 transcript_path，方便 Agent 报告失败原因。
        """
        result = await summarize.ainvoke({"video_id": "BV1", "transcript_path": ""})
        assert result.get("ok") is False
        assert "transcript_path" in (result.get("error") or "")

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_summarize_with_video_id_and_transcript_path_succeeds(
        self, tmp_path
    ):
        """summarize video_id + transcript_path + extra_context → 成功路径。"""
        from aipulse.summarizers import llm as llm_mod

        # 落盘一份字幕文件（paths 来源于 fetch_transcript 落盘）
        transcript = tmp_path / "BV1ok.md"
        transcript.write_text(
            "---\n"
            "bvid: BV1ok\n"
            "fetched_at: 2026-07-26T07:00:00Z\n"
            "source: bilibili\n"
            "---\n\n"
            "完整字幕文本\n第二行\n",
            encoding="utf-8",
        )

        class _FakeAdapter:
            def __init__(self, *args, **kwargs):
                pass

            async def complete(self, prompt, system=None):
                return "# Title\n\n## TL;DR\n- from R5-C test"

        original = llm_mod.OpenAICompatibleAdapter
        llm_mod.OpenAICompatibleAdapter = _FakeAdapter  # type: ignore[assignment]
        try:
            result = await summarize.ainvoke(
                {
                    "video_id": "BV1ok",
                    "transcript_path": str(transcript),
                    "extra_context": "标题：test",
                }
            )
        finally:
            llm_mod.OpenAICompatibleAdapter = original  # type: ignore[assignment]

        assert result["ok"] is True
        assert "R5-C test" in result["markdown"]
        assert result["transcript_path"] == str(transcript)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_summarize_with_missing_path_file_returns_error(self):
        """summarize 传 transcript_path=不存在 → 函数体兜底返回 ok=False（不抛异常）。"""
        result = await summarize.ainvoke(
            {
                "video_id": "BV1missing",
                "transcript_path": "/tmp/this-definitely-does-not-exist-BV1missing.md",
                "extra_context": "",
            }
        )
        assert result["ok"] is False
        assert "字幕文件不存在或为空" in result["error"]
        assert result["transcript_path"] == "/tmp/this-definitely-does-not-exist-BV1missing.md"


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

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_estimated_minutes_fallback_to_15_when_no_transcript(
        self, db_session
    ):
        """video_duration 不可得 → fallback 15（保留原硬编码行为）"""

        from sqlalchemy import select

        from aipulse.hotspot.models import Hotspot, Source
        from aipulse.models.followed_up import FollowedUp
        from aipulse.models.learning_events import LearningEvent

        source = Source(
            id="src-bilibili-fb",
            name="bilibili-fb",
            source_type="bilibili",
            collector_class="aipulse.collectors.bilibili_up.factory.BilibiliUpCollectorFactory",
            config={},
        )
        db_session.add(source)
        await db_session.flush()

        fu = FollowedUp(
            platform="bilibili",
            uid="10002",
            display_name="TestUP-fb",
            profile_url="https://space.bilibili.com/10002",
        )
        db_session.add(fu)
        await db_session.flush()

        hotspot = Hotspot(
            title="Fallback",
            url="https://www.bilibili.com/video/BV1fb",
            canonical_url="https://www.bilibili.com/video/BV1fb",
            source_id=source.id,
            source_type="bilibili",
            content_id="BV1fb",
            followed_up_id=fu.id,
        )
        db_session.add(hotspot)
        await db_session.commit()

        # transcript 不存在 → _compute_estimated_minutes fallback 15
        result = await create_learning_event.ainvoke(
            {
                "video_id": "BV1fb",
                "note_path": "/tmp/note.md",
                "scheduled_at": "2026-07-26T20:00:00",
                "topic": "T",
            }
        )
        assert result["ok"] is True
        evt = (
            await db_session.execute(
                select(LearningEvent).where(
                    LearningEvent.hotspot_id == hotspot.id
                )
            )
        ).scalar_one()
        assert evt.estimated_minutes == 15

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_estimated_minutes_max_15_video_duration_x_2(
        self, db_session, monkeypatch
    ):
        """video_duration = 1800s (30min) → estimated_minutes = max(15, 60) = 60"""

        from sqlalchemy import select

        from aipulse.hotspot.models import Hotspot, Source
        from aipulse.models.followed_up import FollowedUp
        from aipulse.models.learning_events import LearningEvent

        source = Source(
            id="src-bilibili-dur",
            name="bilibili-dur",
            source_type="bilibili",
            collector_class="aipulse.collectors.bilibili_up.factory.BilibiliUpCollectorFactory",
            config={},
        )
        db_session.add(source)
        await db_session.flush()

        fu = FollowedUp(
            platform="bilibili",
            uid="10003",
            display_name="TestUP-dur",
            profile_url="https://space.bilibili.com/10003",
        )
        db_session.add(fu)
        await db_session.flush()

        hotspot = Hotspot(
            title="WithDuration",
            url="https://www.bilibili.com/video/BV1dur",
            canonical_url="https://www.bilibili.com/video/BV1dur",
            source_id=source.id,
            source_type="bilibili",
            content_id="BV1dur",
            followed_up_id=fu.id,
        )
        db_session.add(hotspot)
        await db_session.commit()

        # 落盘一个带 duration 的 transcript frontmatter（30 分钟）
        from aipulse.core.config import get_settings

        cache_dir = (
            __import__("pathlib").Path(get_settings().data_dir)
            / "cache"
            / "transcripts"
        )
        cache_dir.mkdir(parents=True, exist_ok=True)
        transcript_path = cache_dir / "BV1dur.md"
        transcript_path.write_text(
            "---\n"
            "bvid: BV1dur\n"
            "fetched_at: 2026-07-26T10:00:00+00:00\n"
            "source: bilibili\n"
            "duration_seconds: 1800\n"
            "---\n\n"
            "transcript body\n",
            encoding="utf-8",
        )

        result = await create_learning_event.ainvoke(
            {
                "video_id": "BV1dur",
                "note_path": "/tmp/note.md",
                "scheduled_at": "2026-07-26T20:00:00",
                "topic": "T",
            }
        )
        assert result["ok"] is True
        evt = (
            await db_session.execute(
                select(LearningEvent).where(
                    LearningEvent.hotspot_id == hotspot.id
                )
            )
        ).scalar_one()
        # 30 分钟 × 2 = 60；max(15, 60) = 60
        assert evt.estimated_minutes == 60

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_estimated_minutes_short_video_floors_at_15(
        self, db_session, monkeypatch
    ):
        """video_duration 短到 × 2 < 15 → 仍然 15"""

        from sqlalchemy import select

        from aipulse.hotspot.models import Hotspot, Source
        from aipulse.models.followed_up import FollowedUp
        from aipulse.models.learning_events import LearningEvent

        source = Source(
            id="src-bilibili-short",
            name="bilibili-short",
            source_type="bilibili",
            collector_class="aipulse.collectors.bilibili_up.factory.BilibiliUpCollectorFactory",
            config={},
        )
        db_session.add(source)
        await db_session.flush()

        fu = FollowedUp(
            platform="bilibili",
            uid="10004",
            display_name="TestUP-short",
            profile_url="https://space.bilibili.com/10004",
        )
        db_session.add(fu)
        await db_session.flush()

        hotspot = Hotspot(
            title="ShortVid",
            url="https://www.bilibili.com/video/BV1short",
            canonical_url="https://www.bilibili.com/video/BV1short",
            source_id=source.id,
            source_type="bilibili",
            content_id="BV1short",
            followed_up_id=fu.id,
        )
        db_session.add(hotspot)
        await db_session.commit()

        from aipulse.core.config import get_settings

        cache_dir = (
            __import__("pathlib").Path(get_settings().data_dir)
            / "cache"
            / "transcripts"
        )
        cache_dir.mkdir(parents=True, exist_ok=True)
        transcript_path = cache_dir / "BV1short.md"
        # 60 秒 = 1 分钟 × 2 = 2 < 15 → max(15, 2) = 15
        transcript_path.write_text(
            "---\n"
            "bvid: BV1short\n"
            "fetched_at: 2026-07-26T10:00:00+00:00\n"
            "source: bilibili\n"
            "duration_seconds: 60\n"
            "---\n\n"
            "transcript body\n",
            encoding="utf-8",
        )

        result = await create_learning_event.ainvoke(
            {
                "video_id": "BV1short",
                "note_path": "/tmp/note.md",
                "scheduled_at": "2026-07-26T20:00:00",
                "topic": "T",
            }
        )
        assert result["ok"] is True
        evt = (
            await db_session.execute(
                select(LearningEvent).where(
                    LearningEvent.hotspot_id == hotspot.id
                )
            )
        ).scalar_one()
        assert evt.estimated_minutes == 15


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
# ---------------------------------------------------------------------------
# fetch_transcript — L2#2 签约校验 (2026-07-26)
# ---------------------------------------------------------------------------
class TestFetchTranscriptSignatureGuard:
    """L2#2：Kimi ReAct 偶尔把 ``{"video_id": "BV..."}`` dict 传进来当 bvid。

    之前：LangChain parser 抛 ``Missing 'Action:' after 'Thought:'`` 然后
    pipeline 返回 ``status=failed``、但上层仍标 completed（status 错位）。
    """

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_dict_video_id_with_video_id_field_is_extracted(self, transcript_cache_dir) -> None:
        """dict 输入含 video_id 字段 → 视作 str 继续（不直接终止）。"""
        async def _handler(request: httpx.Request) -> httpx.Response:
            if "/x/web-interface/view" in str(request.url):
                return httpx.Response(200, json={"code": 0, "data": {"cid": 999}})
            if "/x/v2/dm/view" in str(request.url):
                return httpx.Response(
                    200,
                    json={
                        "code": 0,
                        "data": {
                            "subtitle": {
                                "subtitles": [
                                    {
                                        "lan": "zh-CN",
                                        "lan_doc": "中文（简体）",
                                        "subtitle_url": "https://x/y.json",
                                    }
                                ]
                            }
                        },
                    },
                )
            return httpx.Response(404)

        from aipulse.summarizers.agent.tools import fetch_transcript

        subtitle_payload = json.dumps(
            {
                "body": [
                    {"from": 0.0, "to": 5.0, "content": "字幕行 A"},
                    {"from": 6.0, "to": 10.0, "content": "字幕行 B"},
                    {"from": 11.0, "to": 15.0, "content": "字幕行 C"},
                    {"from": 16.0, "to": 20.0, "content": "字幕行 D"},
                    {"from": 21.0, "to": 25.0, "content": "字幕行 E"},
                    {"from": 26.0, "to": 30.0, "content": "字幕行 F"},
                ]
            }
        ).encode("utf-8")

        with patch(
            "aipulse.summarizers.agent.tools.httpx.AsyncClient",
            new=_make_async_client_mock(_handler),
        ):
            with patch(
                "aipulse.summarizers.agent.tools._bilibili_read_cookies",
                return_value=None,
            ):
                with patch(
                    "urllib.request.urlopen",
                    MagicMock(return_value=_FakeURLRead(subtitle_payload)),
                ):
                    path_str = await fetch_transcript.ainvoke({"video_id": "BV1fallback01"})
        assert Path(path_str).exists()
        cached = _read_cache_transcript(path_str)
        assert cached.startswith("字幕行 A")
        assert "字幕行 B" in cached
        assert "字幕行 F" in cached

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_dict_without_video_field_returns_error(self) -> None:
        from aipulse.summarizers.agent.tools import fetch_transcript

        # 当 LLM 误传 {"video_id": {"foo": "bar"}} 时（video_id 字段本身是 dict
        # 而不是字符串），函数体兜底后应该返回 [ERROR]。
        text = await fetch_transcript.ainvoke({"video_id": {"foo": "bar"}})
        assert text.startswith("[ERROR]")
        assert "video_id" in text

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_non_string_video_id_returns_error(self) -> None:
        from aipulse.summarizers.agent.tools import fetch_transcript

        # Kimi ReAct 把 Action.input 序列化进 tool_input 时一定是 dict；
        # 这里覆盖 video_id 字段是 None / int / list 的真实签约错误形态。
        for bad in (None, 12345, ["BV1abc"], {"nested": "BV1abc"}):
            text = await fetch_transcript.ainvoke({"video_id": bad})
            assert text.startswith("[ERROR]"), f"bad input {bad!r} should error"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_string_without_bv_prefix_returns_error(self) -> None:
        from aipulse.summarizers.agent.tools import fetch_transcript

        text = await fetch_transcript.ainvoke("AV12345")
        assert text.startswith("[ERROR]")
        assert "BV" in text



class TestSendNotificationAppleRemindersList:
    """send_notification 工具必须调 create_reminder(..., list_name='AIPulse测试')。

    feedback_tests-must-isolate-apple-reminders 硬约束：tests 只能往
    AIPulse测试 list 写，永远不污染真实业务列表（"工作学习"/"提醒"等）。
    """

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_send_notification_uses_aipulse_test_list(self) -> None:
        from unittest.mock import AsyncMock, patch

        from aipulse.summarizers.agent.tools import send_notification

        captured: dict[str, object] = {}

        async def fake_cr(*args, **kwargs):
            captured["args"] = args
            captured["kwargs"] = kwargs
            return "rem-captured"

        # 必须先创建 note 文件（Obsidian Task 写入需要文件存在）
        from pathlib import Path
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            note_path = Path(td) / "test-note.md"
            note_path.write_text("---\nvideo_id: BV\n---\n", encoding="utf-8")

            with patch("aipulse.apple.reminders.create_reminder", new=fake_cr):
                result = await send_notification.ainvoke(
                    {
                        "note_path": str(note_path),
                        "scheduled_at": "2026-07-27T00:00:00Z",
                        "topic": "测试主题",
                    }
                )

        assert captured["kwargs"].get("list_name") == "AIPulse测试"
        assert "测试主题" in (captured["kwargs"].get("title") or captured["args"][0])
        assert result["reminder_id"] == "rem-captured"


# ---------------------------------------------------------------------------
# fetch_transcript: 浏览器 UA + Referer + cookie + 多字幕轨道
# (L1#5/L4 2026-07-26 抄 obsidian-clip-summary skill 设计)
# ---------------------------------------------------------------------------
class TestFetchTranscriptBrowserHeaders:
    """skill 抄写：浏览器伪装 UA + Referer 头（避免 412 风控）。"""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_fetch_transcript_sets_user_agent_and_referer(self, transcript_cache_dir):
        """所有 httpx 调用都带 User-Agent + Referer（不传 → 412 风控）。"""

        captured_headers: list[dict] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured_headers.append(dict(request.headers))
            url = str(request.url)
            if "/x/web-interface/view" in url:
                # 注意：不返 duration 让 helper lenient 通过
                return httpx.Response(200, json={"code": 0, "data": {"cid": 1}})
            # dm/view fallback 接口返回字幕列表
            return httpx.Response(
                200,
                json={
                    "code": 0,
                    "data": {
                        "subtitle": {
                            "subtitles": [
                                {
                                    "lan": "zh-CN",
                                    "lan_doc": "中文（简体）",
                                    "subtitle_url": "https://x.test/subs.json",
                                }
                            ]
                        }
                    },
                },
            )

        with patch("httpx.AsyncClient", new=_make_async_client_mock(handler)):
            # 拦掉字幕 JSON 拉取（避免走真实网络）
            with patch(
                "urllib.request.urlopen",
                MagicMock(
                    return_value=_FakeURLRead(
                        json.dumps(
                            {
                                "body": [
                                    {"from": 0.0, "to": 5.0, "content": "字幕行 1"},
                                    {"from": 6.0, "to": 10.0, "content": "字幕行 2"},
                                    {"from": 11.0, "to": 15.0, "content": "字幕行 3"},
                                    {"from": 16.0, "to": 20.0, "content": "字幕行 4"},
                                    {"from": 21.0, "to": 25.0, "content": "字幕行 5"},
                                    {"from": 26.0, "to": 30.0, "content": "字幕行 6"},
                                ]
                            }
                        ).encode("utf-8")
                    )
                ),
            ):
                result = await fetch_transcript.ainvoke({"video_id": "BV1ua"})

        assert Path(result).exists()
        cached = _read_cache_transcript(result)
        assert "字幕行" in cached
        # 至少 web-interface/view + dm/view 两个 httpx 调用都应带 header
        assert len(captured_headers) >= 2
        for h in captured_headers:
            assert h.get("user-agent", "").startswith("Mozilla/5.0")
            assert "Chrome/126" in h.get("user-agent", "")
            assert h.get("referer") == "https://www.bilibili.com/video/BV1ua"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_fetch_transcript_uses_cookie_when_available(self, transcript_cache_dir):
        """macOS Obsidian Media Extended cookie 自动读取 → Cookie 头被加上。"""

        captured_headers: list[dict] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured_headers.append(dict(request.headers))
            url = str(request.url)
            if "/x/web-interface/view" in url:
                return httpx.Response(200, json={"code": 0, "data": {"cid": 2}})
            if "/x/player/v2" in url:
                # 模拟 cookie 路径返回字幕
                return httpx.Response(
                    200,
                    json={
                        "code": 0,
                        "data": {
                            "subtitle": {
                                "subtitles": [
                                    {
                                        "lan": "zh-CN",
                                        "lan_doc": "中文（简体）",
                                        "subtitle_url": "https://x.test/subs.json",
                                    }
                                ]
                            }
                        },
                    },
                )
            return httpx.Response(200, json=[])

        with patch("httpx.AsyncClient", new=_make_async_client_mock(handler)):
            with patch(
                "aipulse.summarizers.agent.tools._bilibili_read_cookies",
                return_value={"SESSDATA": "abc123", "DedeUserID": "42"},
            ):
                with patch(
                    "urllib.request.urlopen",
                    MagicMock(
                        return_value=_FakeURLRead(
                            json.dumps(
                                {
                                    "body": [
                                        {"from": 0.0, "to": 5.0, "content": "cookie-path 行 1"},
                                        {"from": 6.0, "to": 10.0, "content": "cookie-path 行 2"},
                                        {"from": 11.0, "to": 15.0, "content": "cookie-path 行 3"},
                                        {"from": 16.0, "to": 20.0, "content": "cookie-path 行 4"},
                                        {"from": 21.0, "to": 25.0, "content": "cookie-path 行 5"},
                                        {"from": 26.0, "to": 30.0, "content": "cookie-path 行 6"},
                                    ]
                                }
                            ).encode("utf-8")
                        )
                    ),
                ):
                    result = await fetch_transcript.ainvoke(
                        {"video_id": "BV1ck"}
                    )

        cached = _read_cache_transcript(result)
        assert "cookie-path 行" in cached
        # 第一个 player/v2 请求应当带 Cookie
        cookie_present = any(
            "SESSDATA=abc123" in (h.get("cookie") or "") for h in captured_headers
        )
        assert cookie_present, f"no Cookie header set; got: {captured_headers}"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_fetch_transcript_falls_back_to_dm_view_without_cookie(self, transcript_cache_dir):
        """无 cookie → 走公开 /x/v2/dm/view 接口（不调 player/v2）。"""

        hit_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            hit_urls.append(str(request.url))
            url = str(request.url)
            if "/x/web-interface/view" in url:
                return httpx.Response(200, json={"code": 0, "data": {"cid": 9}})
            if "/x/v2/dm/view" in url:
                return httpx.Response(
                    200,
                    json={
                        "code": 0,
                        "data": {
                            "subtitle": {
                                "subtitles": [
                                    {
                                        "lan": "zh-CN",
                                        "lan_doc": "中文",
                                        "subtitle_url": "https://x.test/subs.json",
                                    }
                                ]
                            }
                        },
                    },
                )
            return httpx.Response(200, json=[])

        with patch("httpx.AsyncClient", new=_make_async_client_mock(handler)):
            with patch(
                "aipulse.summarizers.agent.tools._bilibili_read_cookies",
                return_value=None,
            ):
                with patch(
                    "urllib.request.urlopen",
                    MagicMock(
                        return_value=_FakeURLRead(
                            json.dumps(
                                {
                                    "body": [
                                        {"from": 0.0, "to": 5.0, "content": "fallback 行 1"},
                                        {"from": 6.0, "to": 10.0, "content": "fallback 行 2"},
                                        {"from": 11.0, "to": 15.0, "content": "fallback 行 3"},
                                        {"from": 16.0, "to": 20.0, "content": "fallback 行 4"},
                                        {"from": 21.0, "to": 25.0, "content": "fallback 行 5"},
                                        {"from": 26.0, "to": 30.0, "content": "fallback 行 6"},
                                    ]
                                }
                            ).encode("utf-8")
                        )
                    ),
                ):
                    result = await fetch_transcript.ainvoke(
                        {"video_id": "BV1fb"}
                    )

        cached = _read_cache_transcript(result)
        assert "fallback 行" in cached
        # player/v2 不该被命中（无 cookie 路径跳过）
        assert not any("/x/player/v2" in u for u in hit_urls)
        assert any("/x/v2/dm/view" in u for u in hit_urls)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_fetch_transcript_prefers_zh_over_ai_en_over_other(self, transcript_cache_dir):
        """多字幕轨道：中文优先 → 英文 → 其它（skill _order_and_verify 行为）。"""

        def handler(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            if "/x/web-interface/view" in url:
                return httpx.Response(200, json={"code": 0, "data": {"cid": 10}})
            # dm/view fallback 返回 3 个轨道：英文优先（非预期）但应被中文顶掉
            return httpx.Response(
                200,
                json={
                    "code": 0,
                    "data": {
                        "subtitle": {
                            "subtitles": [
                                {"lan": "ai-en", "lan_doc": "英文", "subtitle_url": "https://x.test/en.json"},
                                {"lan": "zh-CN", "lan_doc": "中文", "subtitle_url": "https://x.test/zh.json"},
                                {"lan": "ja", "lan_doc": "日文", "subtitle_url": "https://x.test/ja.json"},
                            ]
                        }
                    },
                },
            )

        # 准备 mock urlopen：每个 subtitle_url 对应不同 body（每条 ≥3 行过
        # helper 的"过短轨道"过滤）
        url_to_body = {
            "https://x.test/en.json": {
                "body": [
                    {"from": 0.0, "to": 5.0, "content": "english rejected 1"},
                    {"from": 6.0, "to": 10.0, "content": "english rejected 2"},
                    {"from": 11.0, "to": 15.0, "content": "english rejected 3"},
                    {"from": 16.0, "to": 20.0, "content": "english rejected 4"},
                    {"from": 21.0, "to": 25.0, "content": "english rejected 5"},
                    {"from": 26.0, "to": 30.0, "content": "english rejected 6"},
                ]
            },
            "https://x.test/zh.json": {
                "body": [
                    {"from": 0.0, "to": 5.0, "content": "中文首选 1"},
                    {"from": 6.0, "to": 10.0, "content": "中文首选 2"},
                    {"from": 11.0, "to": 15.0, "content": "中文首选 3"},
                    {"from": 16.0, "to": 20.0, "content": "中文首选 4"},
                    {"from": 21.0, "to": 25.0, "content": "中文首选 5"},
                    {"from": 26.0, "to": 30.0, "content": "中文首选 6"},
                ]
            },
            "https://x.test/ja.json": {
                "body": [
                    {"from": 0.0, "to": 5.0, "content": "japanese fallback 1"},
                    {"from": 6.0, "to": 10.0, "content": "japanese fallback 2"},
                    {"from": 11.0, "to": 15.0, "content": "japanese fallback 3"},
                    {"from": 16.0, "to": 20.0, "content": "japanese fallback 4"},
                    {"from": 21.0, "to": 25.0, "content": "japanese fallback 5"},
                    {"from": 26.0, "to": 30.0, "content": "japanese fallback 6"},
                ]
            },
        }
        visited: list[str] = []

        def fake_urlopen(req, **kwargs):  # noqa: ARG001
            visited.append(str(req.full_url))
            return _FakeURLRead(
                json.dumps(url_to_body.get(str(req.full_url), [])).encode("utf-8")
            )

        with patch("httpx.AsyncClient", new=_make_async_client_mock(handler)):
            with patch(
                "aipulse.summarizers.agent.tools._bilibili_read_cookies",
                return_value=None,
            ):
                with patch("urllib.request.urlopen", side_effect=fake_urlopen):
                    result = await fetch_transcript.ainvoke(
                        {"video_id": "BV1multi"}
                    )

        cached = _read_cache_transcript(result)
        assert "中文首选" in cached
        # 中文轨道应被首先访问（其它未被拉）
        assert "https://x.test/zh.json" in visited
        assert "https://x.test/en.json" not in visited
        assert "https://x.test/ja.json" not in visited


# ---------------------------------------------------------------------------
# fetch_transcript: R5-C (2026-07-26) 字幕落盘契约
# ---------------------------------------------------------------------------
class TestFetchTranscriptCacheWrite:
    """R5-C: fetch_transcript 必须把字幕写到 ``data/cache/transcripts/<bvid>.md``。

    落盘格式（frontmatter + 正文）：
        ---
        bvid: <video_id>
        fetched_at: <ISO8601>
        source: bilibili
        ---
        <完整字幕文本>
    """

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_fetch_transcript_writes_to_cache_file(self, transcript_cache_dir):
        """mock HTTP → 落盘 .md 文件 + frontmatter 正确 + return 路径字符串。"""

        def handler(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            if "/x/web-interface/view" in url:
                return httpx.Response(200, json={"code": 0, "data": {"cid": 42}})
            if "/x/v2/dm/view" in url:
                return httpx.Response(
                    200,
                    json={
                        "code": 0,
                        "data": {
                            "subtitle": {
                                "subtitles": [
                                    {
                                        "lan": "zh-CN",
                                        "lan_doc": "中文（简体）",
                                        "subtitle_url": "https://x.test/subs.json",
                                    }
                                ]
                            }
                        },
                    },
                )
            return httpx.Response(200, json=[])

        subtitle_payload = json.dumps(
            {
                "body": [
                    {"from": 0.0, "to": 5.0, "content": "落盘行 1"},
                    {"from": 6.0, "to": 10.0, "content": "落盘行 2"},
                    {"from": 11.0, "to": 15.0, "content": "落盘行 3"},
                    {"from": 16.0, "to": 20.0, "content": "落盘行 4"},
                    {"from": 21.0, "to": 25.0, "content": "落盘行 5"},
                    {"from": 26.0, "to": 30.0, "content": "落盘行 6"},
                ]
            }
        ).encode("utf-8")

        with patch("httpx.AsyncClient", new=_make_async_client_mock(handler)):
            with patch(
                "aipulse.summarizers.agent.tools._bilibili_read_cookies",
                return_value=None,
            ):
                with patch(
                    "urllib.request.urlopen",
                    MagicMock(return_value=_FakeURLRead(subtitle_payload)),
                ):
                    path_str = await fetch_transcript.ainvoke({"video_id": "BV1r5c"})

        # 1. 返回值是落盘文件绝对路径字符串
        assert isinstance(path_str, str)
        assert path_str.endswith("BV1r5c.md")
        # 2. 文件存在
        cache_file = Path(path_str)
        assert cache_file.exists(), f"落盘文件不存在：{path_str}"
        # 3. 验证父目录就是 transcript_cache_dir fixture
        assert cache_file.parent == transcript_cache_dir
        # 4. 读 frontmatter + 正文 + 断言
        raw = cache_file.read_text(encoding="utf-8")
        assert raw.startswith("---\n")
        assert "bvid: BV1r5c" in raw
        assert "fetched_at:" in raw
        assert "source: bilibili" in raw
        # frontmatter + 正文都被写入
        assert "落盘行 1" in raw
        assert "落盘行 6" in raw
        # 正文被 frontmatter 与 --- 分隔
        assert "\n---\n" in raw

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_fetch_transcript_cache_dir_default_under_data_dir(
        self, tmp_path, monkeypatch
    ):
        """不 patch _transcript_cache_dir 时，落盘目录 = settings.data_dir/cache/transcripts/。

        验证 _transcript_cache_dir() helper 拼装 settings.data_dir 路径正确。
        """
        from aipulse.summarizers.agent.tools import _transcript_cache_dir

        # 把 get_settings cache clear 后构造 settings（data_dir = tmp_path/data）
        from aipulse.core.config import AppSettings, reset_settings

        reset_settings()
        settings = AppSettings(
            data_dir=tmp_path / "data",
            download_dir=tmp_path / "data" / "downloads",
            database_url=f"sqlite+aiosqlite:///{tmp_path}/aipulse.db",
        )
        monkeypatch.setattr(
            "aipulse.summarizers.agent.tools.get_settings", lambda: settings
        )

        cache_dir = _transcript_cache_dir()
        # 默认目录 = settings.data_dir/cache/transcripts/
        assert cache_dir == tmp_path / "data" / "cache" / "transcripts"
        # helper 返回 Path 对象
        assert isinstance(cache_dir, Path)


class _FakeURLRead:
    """urllib.request.urlopen 返回的最小 context manager。"""

    def __init__(self, payload: bytes):
        self._payload = payload

    def read(self) -> bytes:
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


# ---------------------------------------------------------------------------
# default_scheduled_at (spec 06 §7.2)
# ---------------------------------------------------------------------------
class TestDefaultScheduledAt:
    """spec 06 §7.2：默认 today 20:00 Asia/Shanghai（已过则明天 20:00）。"""

    @pytest.mark.unit
    def test_default_scheduled_at_today_20_00_before_evening(self):
        """now_cn 上午时 → today 20:00 +08:00。"""
        from datetime import datetime, timedelta, timezone

        from unittest.mock import patch

        cn_tz = timezone(timedelta(hours=8))
        fake_now = cn_tz.localize(  # type: ignore[attr-defined]
            datetime(2026, 7, 26, 10, 0, 0)
        ) if hasattr(cn_tz, "localize") else datetime(2026, 7, 26, 10, 0, 0, tzinfo=cn_tz)
        with patch("aipulse.summarizers.agent.tools.datetime") as mock_dt:
            mock_dt.now.return_value = fake_now
            from aipulse.summarizers.agent import tools as tools_mod

            s = tools_mod.default_scheduled_at()
        parsed = datetime.fromisoformat(s)
        assert parsed == datetime(2026, 7, 26, 20, 0, 0, tzinfo=cn_tz)

    @pytest.mark.unit
    def test_default_scheduled_at_today_20_00_after_evening(self):
        """now_cn 已过 20:00 → tomorrow 20:00 +08:00。"""
        from datetime import datetime, timedelta, timezone

        from unittest.mock import patch

        cn_tz = timezone(timedelta(hours=8))
        fake_now = (
            datetime(2026, 7, 26, 22, 0, 0, tzinfo=cn_tz)
            if not hasattr(cn_tz, "localize")
            else cn_tz.localize(datetime(2026, 7, 26, 22, 0, 0))  # type: ignore[attr-defined]
        )
        with patch("aipulse.summarizers.agent.tools.datetime") as mock_dt:
            mock_dt.now.return_value = fake_now
            from aipulse.summarizers.agent import tools as tools_mod

            s = tools_mod.default_scheduled_at()
        parsed = datetime.fromisoformat(s)
        assert parsed == datetime(2026, 7, 27, 20, 0, 0, tzinfo=cn_tz)

    @pytest.mark.unit
    def test_default_scheduled_at_returns_iso_with_tz_offset(self):
        """返回值 ISO8601 带 +08:00 时区偏移。"""
        from datetime import datetime, timedelta

        s = default_scheduled_at()
        parsed = datetime.fromisoformat(s)
        assert parsed.tzinfo is not None
        # 偏移必须是 +08:00 (28800 seconds)
        assert parsed.utcoffset() == timedelta(hours=8)
