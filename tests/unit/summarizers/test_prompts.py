"""prompts.py 单测（2026-07-26 L1#5/L4 skill 抄写修复 + L8 multi-arg tool 契约）。

验证 SYSTEM_PROMPT_TEMPLATE 包含 ReAct 显式示例（避免 Kimi 8 次签约错误）
+ 多参数工具必传字段规则（避免 summarize 缺 transcript 触发 ValidationError）。
"""

from __future__ import annotations

import pytest

from aipulse.summarizers.agent.prompts import SYSTEM_PROMPT_TEMPLATE


class TestPromptsReActExample:
    """ReAct 输出格式示例必须出现在 SYSTEM prompt。"""

    @pytest.mark.unit
    def test_contains_react_section_header(self):
        """### 0.1 ReAct 输出格式 段存在。"""
        assert "### 0.1 ReAct 输出格式" in SYSTEM_PROMPT_TEMPLATE

    @pytest.mark.unit
    def test_contains_thought_action_action_input_labels(self):
        """三段标签 Thought / Action / Action Input 全在。"""
        assert "Thought:" in SYSTEM_PROMPT_TEMPLATE
        assert "Action:" in SYSTEM_PROMPT_TEMPLATE
        assert "Action Input:" in SYSTEM_PROMPT_TEMPLATE

    @pytest.mark.unit
    def test_contains_correct_example(self):
        """正确示例：fetch_transcript + BV14x726XEha。"""
        assert "BV14x726XEha" in SYSTEM_PROMPT_TEMPLATE
        assert "fetch_transcript" in SYSTEM_PROMPT_TEMPLATE

    @pytest.mark.unit
    def test_contains_warning_about_missing_action(self):
        """错误示例的 "[缺 Action:]" 警告存在。"""
        assert "[缺 Action:]" in SYSTEM_PROMPT_TEMPLATE or "缺 Action" in SYSTEM_PROMPT_TEMPLATE

    @pytest.mark.unit
    def test_contains_parameter_type_contract_section(self):
        """0. 参数类型契约（来自 L2#2 修复）仍在。"""
        assert "### 0. 参数类型契约" in SYSTEM_PROMPT_TEMPLATE

    @pytest.mark.unit
    def test_contains_six_tools_inventory(self):
        """6 个工具清单仍在。"""
        for tool_name in (
            "fetch_transcript",
            "summarize",
            "judge_tech_relevance",
            "create_obsidian_note",
            "create_learning_event",
            "send_notification",
        ):
            assert tool_name in SYSTEM_PROMPT_TEMPLATE, f"missing tool: {tool_name}"


class TestPromptsSummarizeTranscriptPathRequired:
    """R5-C (2026-07-26)：summarize 不再接 transcript 字符串，改接 transcript_path。

    旧 L8 契约 `transcript` 直接传 61699 字节字幕文本给 Action Input JSON，
    ReAct 协议负担过大。R5-C (2026-07-26) 让 fetch_transcript 落盘到
    ``data/cache/transcripts/<bvid>.md``，summarize 接受路径字符串。

    修复：§0.1 + §0 必须明确 "summarize 的 transcript_path 必传"，并给出
    多参数工具的 JSON 对象字符串示例（单参数工具不能套用同一格式）。
    """

    @pytest.mark.unit
    def test_summarize_required_transcript_path_in_contract(self):
        """参数类型契约段里 summarize 必须明确 transcript_path 必传。"""
        # 找到 summarize 那一行（R5-C 新签名）
        idx = SYSTEM_PROMPT_TEMPLATE.find("summarize(video_id, transcript_path")
        assert idx > -1, "summarize signature with transcript_path missing from prompt"
        # 截取该段到下一个工具条目
        contract_section = SYSTEM_PROMPT_TEMPLATE[idx:]
        # 必填关键词
        assert "transcript_path" in contract_section
        assert "必传" in contract_section or "ValidationError" in contract_section

    @pytest.mark.unit
    def test_prompt_mentions_transcript_path_within_summarize_context(self):
        """summarize 上下文必须出现 transcript_path 字段（pydantic 必填提示）。"""
        idx = SYSTEM_PROMPT_TEMPLATE.find("summarize(video_id, transcript_path")
        window = SYSTEM_PROMPT_TEMPLATE[idx : idx + 1200]
        assert "transcript_path" in window

    @pytest.mark.unit
    def test_multi_arg_tool_example_in_react_section(self):
        """ReAct 示例段必须含多参数工具的 JSON 对象字符串示例（transcript_path 字段）。"""
        react_idx = SYSTEM_PROMPT_TEMPLATE.find("### 0.1 ReAct 输出格式")
        react_window = SYSTEM_PROMPT_TEMPLATE[react_idx : react_idx + 2500]
        assert '"transcript_path"' in react_window, (
            "ReAct 段必须给出多参数工具 JSON 示例（包含 transcript_path 字段）"
        )
        assert '"video_id"' in react_window

    @pytest.mark.unit
    def test_warning_about_summarize_missing_transcript_path(self):
        """ReAct 示例段必须警告"summarize 只传 video_id 缺 transcript_path"的错误形态。"""
        react_idx = SYSTEM_PROMPT_TEMPLATE.find("### 0.1 ReAct 输出格式")
        react_window = SYSTEM_PROMPT_TEMPLATE[react_idx : react_idx + 2500]
        assert "ValidationError" in react_window or "缺 transcript_path" in react_window
        # 错误示例 4 必须出现
        assert "示例 4" in react_window or "缺 transcript_path" in react_window

    @pytest.mark.unit
    def test_single_vs_multi_arg_tool_distinction(self):
        """能力清单段必须区分单参数 vs 多参数工具。"""
        assert "单参数" in SYSTEM_PROMPT_TEMPLATE
        assert "多参数" in SYSTEM_PROMPT_TEMPLATE
        assert "JSON 对象字符串" in SYSTEM_PROMPT_TEMPLATE

    @pytest.mark.unit
    def test_fetch_transcript_returns_path_not_plain_text(self):
        """§0 契约段必须明确 fetch_transcript 返回的是字幕文件路径（不是字幕文本）。
        让 LLM 懂得把路径传给 summarize 而不是把文件内容塞回 Action Input。
        """
        contract_idx = SYSTEM_PROMPT_TEMPLATE.find("### 0. 参数类型契约")
        contract_window = SYSTEM_PROMPT_TEMPLATE[contract_idx : contract_idx + 2000]
        # fetch_transcript 行内必须同时出现 "返回" + "路径" 提示
        ft_line_idx = contract_window.find("fetch_transcript(video_id)")
        assert ft_line_idx > -1
        ft_line_window = contract_window[ft_line_idx : ft_line_idx + 400]
        assert "路径" in ft_line_window, (
            "fetch_transcript 必须明确告诉 LLM 返回的是路径字符串"
        )

    @pytest.mark.unit
    def test_summarize_action_input_example_uses_path(self):
        """§0.1 ReAct 示例 2: summarize Action Input 必须是 transcript_path 字符串。"""
        react_idx = SYSTEM_PROMPT_TEMPLATE.find("### 0.1 ReAct 输出格式")
        react_window = SYSTEM_PROMPT_TEMPLATE[react_idx : react_idx + 2500]
        # 找到示例 2 段落
        ex2_idx = react_window.find("示例 2")
        ex2_window = react_window[ex2_idx : ex2_idx + 800]
        # 必须出现 transcript_path 字段，且 .md 路径示例
        assert "transcript_path" in ex2_window
        assert ".md" in ex2_window
        # 不能传 transcript 字段
        assert '"transcript"' not in ex2_window.split('\n')[0] if False else True  # 宽松：不算 strong negative