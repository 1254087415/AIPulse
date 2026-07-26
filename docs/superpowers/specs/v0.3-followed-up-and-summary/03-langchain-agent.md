# 03 — LangChain Agent + Kimi（半自动 ReAct + 6 个 Tool）

> **⚠️ 2026-07-25 文档与代码一致性说明**
>
> 本文档中 Kimi 模型配置为：
> - 模型名：`kimi-for-coding`（v0.3 final 2026-07-25 锁定）
> - Base URL：`https://api.kimi.com/coding/v1`
>
> **代码侧**（`src/aipulse/summarizers/llm.py` + `src/aipulse/core/config.py`）已使用上述值，无需修改。
> **本文档 2026-07-25 已对齐代码**，如未来代码侧再次变更，需同步本文档。
> **历史背景**：v0.3 早期 spec 锁定 `kimi-k2.6` + `https://api.moonshot.cn/v1`，但实际项目代码自始即采用 `kimi-for-coding` + `https://api.kimi.com/coding/v1`，本轮以代码为准修订文档。

> **来源**：原文档 §5.1-§5.8（Agent Pipeline 主体）
> **上游依赖**：01 数据模型 + 02 字幕工具 + 07 Bearer 鉴权
> **下游交付物**：
> - `src/aipulse/summarizers/agent/agent.py` — ReAct Agent 主体
> - `src/aipulse/summarizers/agent/tools.py` — 6 个 @tool 装饰的工具
> - `src/aipulse/summarizers/agent/prompts.py` — System Prompt + ReAct 模板
> - `src/aipulse/summarizers/agent/runner.py` — Agent 初始化 + 运行入口
> - Kimi 集成（`kimi-for-coding` + `langchain_openai.ChatOpenAI`）
> - 半自动边界定义（fetch_transcript/summarize/judge 自动，其他手动）
>
> **subagent 边界**：本模块产出 Agent 核心（不含队列和 API），队列和 Summary API 在 04 单独产出。
> **执行模式**：Phase 3 内 subagent-C1（Agent 框架）/ C2（tools）/ C3（prompts）可并行。

---



### 5.1 LangChain ReAct Agent + Tool Calling（Q4）

**最终方案**：`create_react_agent` + `@tool` 装饰器 + ReAct 风格 prompt。

```python
# src/aipulse/summarizers/agent/agent.py
from langchain.agents import create_react_agent, AgentExecutor
from langchain_openai import ChatOpenAI
from langchain.tools import tool
from src.aipulse.core.config import get_settings

settings = get_settings()

llm = ChatOpenAI(
    base_url=settings.kimi_base_url,  # kimi_* 优先（与 llm_* 并存向后兼容）
    api_key=settings.kimi_api_key.get_secret_value(),
    model=settings.kimi_model,  # "kimi-for-coding"
    temperature=0.3,
)

# Tool 集合（@tool 装饰器）
@tool
def fetch_transcript_tool(bvid: str) -> str: ...
@tool
def summarize_tool(text: str, title: str) -> str: ...
@tool
def judge_tech_relevance_tool(summary: str) -> str: ...
# 以下三个 tool 仅手动触发（半自动模式），Agent pipeline 不自动调用
@tool
def create_obsidian_note_tool(hotspot_id: str) -> str: ...
@tool
def create_learning_event_tool(hotspot_id: str) -> str: ...
@tool
def send_notification_tool(hotspot_id: str) -> str: ...

# ReAct Agent：create_react_agent + @tool（ReAct 风格 prompt）
prompt = PromptTemplate.from_template(SYSTEM_PROMPT)  # 复用 obsidian-clip-summary 核心规则（Q139）
agent = create_react_agent(llm, tools, prompt)
executor = AgentExecutor(
    agent=agent,
    tools=tools,
    max_iterations=5,
    max_execution_time=300,  # 5 分钟硬超时（Q141）
    handle_parsing_errors=True,
    return_intermediate_steps=False,
)
```

**关键约束（Q141-Q142）**：
- 5 分钟硬超时（`max_execution_time=300`）
- 工具级独立超时（每个 `@tool` 函数内部 `asyncio.wait_for`）
- **不自动回滚**，失败时记录 `partial` 状态，下次重试时清理

### 5.2 半自动边界（Q8）

| 步骤 | 触发方式 | 重试策略 |
|---|---|---|
| `fetch_transcript` | Agent 自动（pipeline 入口） | 指数退避 3 次 |
| `summarize` | Agent 自动 | 指数退避 3 次 |
| `judge_tech_relevance` | Agent 自动 | 不重试 |
| `create_obsidian_note` | UI 手动触发 | 不重试 |
| `create_learning_event` | UI 手动触发 | 不重试 |
| `send_notification` | UI 手动触发 | 不重试 |

### 5.3 Kimi 集成（Q4 + Q145-Q146）

**最终方案**：新增 `kimi_*` 前缀配置项，与现有 `llm_*` 并存，向后兼容。

**新增到 `AppSettings` 顶层**：

| 配置项 | 用途 | 默认值 | 环境变量 |
|---|---|---|---|
| `kimi_api_key` | Kimi API key | `""`（SecretStr） | `KIMI_API_KEY` |
| `kimi_base_url` | Kimi endpoint | `https://api.kimi.com/coding/v1` | `KIMI_BASE_URL` |
| `kimi_model` | 模型名 | `kimi-for-coding` | `KIMI_MODEL` |

**与 `llm_*` 关系**：
- `OpenAICompatibleAdapter` 默认走 `kimi_*`（v0.3 新行为）
- `llm_*` 作为 fallback：未配置 `kimi_*` 时回退到 `llm_*`，保证向后兼容
- `llm_api_key` / `llm_base_url` / `llm_model` 保留在 AppSettings，不删除

**模型选型（Q144）**：
- 默认 `kimi-for-coding`（v0.3 final 2026-07-25 锁定；Q144 评估：编程专用模型对结构化 prompt ReAct 协议响应更稳定）
- 国内版 base_url：`https://api.kimi.com/coding/v1`
- OpenAI 协议兼容：`langchain_openai.ChatOpenAI` 直接对接

### 5.4 手动触发入口（Q13 + Q14）

```python
@router.post("/agent/process")
async def agent_process_route(hotspot_id: str, ...):
    """手动触发 Agent pipeline（同步执行，立即返回）"""
    ...
```

### 5.5 三方向存储（Q22）

UI "归档"按钮触发，**同时写入三个方向**（任一失败不影响其他）：

| 方向 | 存储位置 | 用途 |
|---|---|---|
| **数据库** | `learning_events` 表 | Dashboard"即将学习" tab 数据源 |
| **Obsidian Tasks** | 总结笔记末尾 `- [ ] ⏰ {scheduled_at}` | 用户日常查看 |
| **Apple Reminders** | 通过 `apple-assistant-eventkit` skill | macOS 通知中心 |

### 5.6 Tool 实现（Q137-Q140 + Q147）

实现位置：`src/aipulse/summarizers/agent/tools.py`，**复用** `summarizers/`（复数）已有目录，在其下新增 `agent/` 子包（与 `base.py` / `llm.py` / `factory.py` 并列，零迁移成本）。

工具清单（6 个 `@tool` 装饰器函数）：

```python
# src/aipulse/summarizers/agent/tools.py
from __future__ import annotations
import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from langchain_core.tools import tool

from aipulse.summarizers.llm import get_llm_client
from aipulse.summarizers.agent.prompts import build_summary_prompt, build_judge_prompt
from aipulse.summarizers.agent.obsidian import (
    ensure_archive_folder,
    write_summary_note,
    append_obsidian_task,
)
from aipulse.db.repositories.learning_events import LearningEventRepository
from aipulse.db.repositories.summaries import SummaryRepository
from aipulse.config import settings

logger = logging.getLogger(__name__)

# Tool 1: 拉取字幕（人工注入或复用 B 站已有）
@tool
async def fetch_transcript(video_id: str) -> str:
    """从 B 站拉取视频 AI 字幕文本。

    Args:
        video_id: B 站视频 avid（如 "BV1xx411c7mD"）或带 aid 的 URL。

    Returns:
        字幕文本（含时间戳前缀），失败时返回错误信息字符串（Agent 看到后会调整 prompt）。
    """
    from aipulse.collectors.bilibili.subtitles import fetch_subtitle_text
    try:
        return await asyncio.wait_for(
            fetch_subtitle_text(video_id),
            timeout=30.0,
        )
    except asyncio.TimeoutError:
        return f"[ERROR] 字幕拉取超时（30s）：{video_id}"
    except Exception as exc:
        logger.warning("fetch_transcript failed for %s: %s", video_id, exc)
        return f"[ERROR] 字幕不可用：{exc!s}"

# Tool 2: 调用 Kimi 生成结构化总结
@tool
async def summarize(video_id: str, transcript: str, extra_context: str = "") -> dict[str, Any]:
    """根据字幕文本调用 Kimi 生成结构化总结笔记（Markdown）。

    Args:
        video_id: B 站视频 avid。
        transcript: fetch_transcript 返回的字幕文本。
        extra_context: 额外上下文（如视频标题、UP 主名、tags）。

    Returns:
        {"ok": bool, "markdown": str, "model": str, "usage": dict, "error"?: str}
    """
    if not transcript or transcript.startswith("[ERROR]"):
        return {"ok": False, "error": "字幕不可用，无法生成总结"}
    try:
        client = get_llm_client(
            api_key=settings.kimi_api_key,
            base_url=settings.kimi_base_url,
            model=settings.kimi_model,
        )
        prompt = build_summary_prompt(
            transcript=transcript,
            extra_context=extra_context,
        )
        result = await asyncio.wait_for(
            client.generate(prompt=prompt),
            timeout=180.0,  # 单次总结 3 分钟硬超时
        )
        return {
            "ok": True,
            "markdown": result.text,
            "model": settings.kimi_model,
            "usage": result.usage,
        }
    except asyncio.TimeoutError:
        return {"ok": False, "error": "Kimi 调用超时（180s）"}
    except Exception as exc:
        logger.exception("summarize failed for %s", video_id)
        return {"ok": False, "error": f"Kimi 调用失败：{exc!s}"}

# Tool 3: 判定视频是否与技术学习相关
@tool
async def judge_tech_relevance(markdown: str) -> dict[str, Any]:
    """基于已生成的总结 Markdown 判定视频是否值得归档学习。

    评分阈值：>= 0.6 视为相关，< 0.6 视为娱乐/科普向（不归档）。

    Args:
        markdown: summarize 返回的总结 Markdown。

    Returns:
        {"ok": bool, "score": float, "reason": str, "should_archive": bool}
    """
    try:
        client = get_llm_client(
            api_key=settings.kimi_api_key,
            base_url=settings.kimi_base_url,
            model=settings.kimi_model,
        )
        prompt = build_judge_prompt(markdown=markdown)
        result = await asyncio.wait_for(
            client.generate(prompt=prompt),
            timeout=60.0,
        )
        parsed = json.loads(result.text)
        score = float(parsed.get("score", 0.0))
        return {
            "ok": True,
            "score": score,
            "reason": parsed.get("reason", ""),
            "should_archive": score >= 0.6,
        }
    except Exception as exc:
        # 判定失败时**保守归档**（score=0.7 + should_archive=True），让用户决定
        logger.warning("judge_tech_relevance failed, defaulting to archive: %s", exc)
        return {"ok": False, "score": 0.7, "reason": "判定失败", "should_archive": True}

# Tool 4: 写 Obsidian 笔记
@tool
async def create_obsidian_note(
    video_id: str,
    markdown: str,
    title: str,
    up_name: str,
) -> dict[str, Any]:
    """将总结 Markdown 写入 Obsidian vault 的归档文件夹。

    Args:
        video_id: B 站视频 avid（用作文件名前缀）。
        markdown: 总结内容。
        title: 视频标题。
        up_name: UP 主昵称。

    Returns:
        {"ok": bool, "note_path": str, "error"?: str}
    """
    vault = settings.obsidian_vault_path
    if not vault:
        return {"ok": False, "error": "未配置 obsidian_vault_path"}
    try:
        archive_dir = ensure_archive_folder(vault, settings.obsidian_archive_folder)
        safe_title = "".join(c for c in title if c not in r'\\/*?:"<>|')[:80]
        note_path = archive_dir / f"{video_id}-{safe_title}.md"
        write_summary_note(
            note_path=note_path,
            markdown=markdown,
            frontmatter={
                "video_id": video_id,
                "title": title,
                "up_name": up_name,
                "summarized_at": datetime.utcnow().isoformat() + "Z",
                "model": settings.kimi_model,
            },
        )
        return {"ok": True, "note_path": str(note_path)}
    except Exception as exc:
        logger.exception("create_obsidian_note failed")
        return {"ok": False, "error": f"写入 Obsidian 失败：{exc!s}"}

# Tool 5: 创建 learning_event（数据库记录）
@tool
async def create_learning_event(
    video_id: str,
    note_path: str,
    scheduled_at: str,
    topic: str,
) -> dict[str, Any]:
    """在 learning_events 表插入一条"即将学习"记录。

    Args:
        video_id: B 站视频 avid。
        note_path: Obsidian 笔记绝对路径。
        scheduled_at: ISO8601 时间字符串（"2026-07-26T20:00:00"）。
        topic: 简短主题（用于 dashboard 卡片标题）。

    Returns:
        {"ok": bool, "event_id": str, "error"?: str}
    """
    try:
        repo = LearningEventRepository()
        event = await repo.create({
            "video_id": video_id,
            "note_path": note_path,
            "scheduled_at": scheduled_at,
            "topic": topic,
            "status": "pending",
        })
        return {"ok": True, "event_id": event.id}
    except Exception as exc:
        logger.exception("create_learning_event failed")
        return {"ok": False, "error": f"DB 写入失败：{exc!s}"}

# Tool 6: 在 Obsidian 笔记末尾追加 Tasks checkbox + Apple Reminders
@tool
async def send_notification(
    note_path: str,
    scheduled_at: str,
    topic: str,
) -> dict[str, Any]:
    """追加 Obsidian Task checkbox（- [ ] ⏰ {time} {topic}）+ 调用 Apple Reminders。

    Args:
        note_path: 笔记绝对路径。
        scheduled_at: ISO8601 时间字符串。
        topic: 任务主题。

    Returns:
        {"ok": bool, "obsidian_task": bool, "reminder_id"?: str, "error"?: str}
    """
    results: dict[str, Any] = {"ok": True, "obsidian_task": False}
    # Obsidian Task 写入（必须成功，否则整体失败）
    try:
        await asyncio.to_thread(
            append_obsidian_task,
            note_path=Path(note_path),
            scheduled_at=scheduled_at,
            topic=topic,
        )
        results["obsidian_task"] = True
    except Exception as exc:
        results["ok"] = False
        results["error"] = f"Obsidian Task 写入失败：{exc!s}"
        return results
    # Apple Reminders 调用（失败不影响整体，只记 warning）
    try:
        from aipulse.skills.apple_assistant_eventkit import create_reminder
        reminder_id = await create_reminder(
            title=topic,
            due_date=scheduled_at,
            notes=f"AIPulse 学习提醒\n笔记：{note_path}",
        )
        results["reminder_id"] = reminder_id
    except Exception as exc:
        logger.warning("Apple Reminders 创建失败（不影响整体）: %s", exc)
        results["reminder_error"] = str(exc)
    return results

# 工具列表（供 Agent 初始化时注入）
ALL_TOOLS = [
    fetch_transcript,
    summarize,
    judge_tech_relevance,
    create_obsidian_note,
    create_learning_event,
    send_notification,
]
```

### 5.7 System Prompt（Q139）

完整复用 obsidian-clip-summary 核心规则，叠加 agent pipeline 调度指令。位置：`src/aipulse/summarizers/agent/prompts.py`

```python
# src/aipulse/summarizers/agent/prompts.py
SYSTEM_PROMPT_TEMPLATE = """你是 AIPulse 的视频学习助手，负责把 B 站视频字幕转换成可归档的学习笔记。

## 你的能力

你可以按顺序调用以下 6 个工具完成一次总结：

1. `fetch_transcript(video_id)` — 拉取视频字幕
2. `summarize(video_id, transcript, extra_context)` — 调用 Kimi 生成结构化总结
3. `judge_tech_relevance(markdown)` — 判定视频是否值得学习归档
4. `create_obsidian_note(video_id, markdown, title, up_name)` — 写入 Obsidian
5. `create_learning_event(video_id, note_path, scheduled_at, topic)` — 写 DB
6. `send_notification(note_path, scheduled_at, topic)` — 追加 Tasks + Apple Reminders

## 必须遵守的核心规则

### 1. 严格按顺序调用（除非有明确理由跳过）

普通流程是 1→2→3→4→5→6。但如果：
- 字幕拉取失败（fetch_transcript 返回 [ERROR]）：**直接终止**，告诉用户"字幕不可用"
- judge_tech_relevance 返回 should_archive=False：**终止**，只把 markdown 返回给用户（不写 Obsidian / DB / Notification）

### 2. 总结结构（复用于 obsidian-clip-summary）

```markdown
---
video_id: {video_id}
title: {title}
up_name: {up_name}
summarized_at: {ISO timestamp}
model: kimi-for-coding
---

# {title}

## TL;DR
3-5 个 bullet，**用具体结论而非空话**（禁止"本文介绍了…" / "本文分析了…"）。

## 核心观点
分 3-6 个小节，每节：
- **观点**：一句话结论
- **证据**：字幕原文引用（带时间戳）

## 关键术语
表格：`术语 | 解释 | 出现位置`

## 行动项（Action Items）
- [ ] {可执行的具体动作}（按时间或优先级排序）

## 待澄清问题
- {看不懂 / 想深入的点}
```

### 3. 反空话硬约束

禁止出现的表达：
- "本文介绍了 / 分析了 / 探讨了"
- "作者认为 / 笔者觉得"
- "综上所述 / 总而言之"
- 任何不带具体信息的概括句

所有 TL;DR 必须是**可操作的具体结论**。

### 4. 错误处理

- 工具返回 `ok=False`：把 `error` 字段告诉用户，**不要尝试自己修复**（除非 prompt 中明确指示）
- 工具超时（5 分钟整体超时）：自动终止，标记 partial 状态，**不自动回滚**

### 5. scheduled_at 选择

调用 `create_learning_event` 时，`scheduled_at` 默认值为**当前时间 + 24 小时**（ISO8601）。
用户可在 UI 二次编辑。

### 6. topic 命名

调用 `create_learning_event` 和 `send_notification` 时，`topic` 取自总结 TL;DR 第一行（去掉 markdown 标记后截断到 30 字）。

## 输出规范

最终回复用户时必须包含：
1. 成功/失败状态
2. 关键路径（笔记绝对路径、learning_event ID、reminder ID）
3. 下一步建议（如有失败，列出失败原因）

不要复述工具调用的中间过程，只在最终回复时呈现结果。
"""

def build_summary_prompt(transcript: str, extra_context: str = "") -> str:
    """用户 prompt：把 transcript + context 交给 Kimi 生成结构化总结。"""
    return f"""请按 SYSTEM 规则把以下视频字幕转成结构化总结笔记。

## 视频上下文
{extra_context or "(无)"}

## 字幕正文
```
{transcript}
```

直接输出 Markdown，**不要任何开场白**。"""

def build_judge_prompt(markdown: str) -> str:
    """用户 prompt：让 Kimi 判定总结是否值得学习归档，返回 JSON。"""
    return f"""请按以下标准判定下面这篇视频总结是否值得用户花时间学习归档。

## 判定标准
- score >= 0.6：相关（涉及具体技术/方法/案例/数据）
- score < 0.6：不相关（纯娱乐 / 简单科普 / 营销内容 / 无具体信息）

## 输出格式（严格 JSON，不要 markdown code fence）
{{
  "score": 0.0-1.0,
  "reason": "一句话说明判定理由",
  "should_archive": true/false
}}

## 待判定总结
```
{markdown[:3000]}
```

只输出 JSON。"""
```

### 5.8 Agent 初始化（Q138 + Q140）

位置：`src/aipulse/summarizers/agent/runner.py`

```python
# src/aipulse/summarizers/agent/runner.py
from __future__ import annotations
import asyncio
import json
import logging
from typing import Any

from langchain.agents import create_react_agent, AgentExecutor
from langchain_core.prompts import PromptTemplate

from aipulse.summarizers.agent.prompts import SYSTEM_PROMPT_TEMPLATE
from aipulse.summarizers.agent.tools import ALL_TOOLS
from aipulse.summarizers.llm import get_llm_client
from aipulse.config import settings

logger = logging.getLogger(__name__)

# ReAct 风格的 prompt 模板（含 Thought/Action/Observation 槽位）
REACT_PROMPT = PromptTemplate.from_template("""{system_prompt}

## 可用工具
{tools}

## 工具名称列表
{tool_names}

## 之前的对话
{chat_history}

## 用户输入
{input}

## Agent 思考过程
Thought: {agent_scratchpad}""")


def build_agent_executor() -> AgentExecutor:
    """构建 ReAct Agent + AgentExecutor，单例复用。"""
    client = get_llm_client(
        api_key=settings.kimi_api_key,
        base_url=settings.kimi_base_url,
        model=settings.kimi_model,
    )
    # ChatOpenAI 适配 ReAct（LangChain 自动处理 chat 格式转换）
    llm = client.as_langchain_chat_model()
    prompt = REACT_PROMPT.partial(system_prompt=SYSTEM_PROMPT_TEMPLATE)
    agent = create_react_agent(
        llm=llm,
        tools=ALL_TOOLS,
        prompt=prompt,
    )
    return AgentExecutor(
        agent=agent,
        tools=ALL_TOOLS,
        verbose=True,
        max_iterations=10,  # 6 个 tool + buffer
        max_execution_time=300,  # 5 分钟硬超时（Q141）
        handle_parsing_errors=True,
        return_intermediate_steps=True,  # 用于 partial 状态恢复
    )


async def run_summary_pipeline(
    video_id: str,
    title: str,
    up_name: str,
    extra_context: str = "",
) -> dict[str, Any]:
    """一次完整的总结 pipeline 调用入口。

    Returns:
        {
            "status": "completed" | "failed" | "partial",
            "note_path": str | None,
            "event_id": str | None,
            "reminder_id": str | None,
            "error": str | None,
            "intermediate_steps": list[dict],
        }
    """
    executor = build_agent_executor()
    user_input = f"请对视频 {video_id}（标题：{title}，UP主：{up_name}）执行完整总结 pipeline。{extra_context}"
    try:
        result = await asyncio.wait_for(
            executor.ainvoke({"input": user_input, "chat_history": []}),
            timeout=300.0,  # 5 分钟硬超时（Q141）
        )
        return {
            "status": "completed",
            "note_path": _extract_step(result, "create_obsidian_note", "note_path"),
            "event_id": _extract_step(result, "create_learning_event", "event_id"),
            "reminder_id": _extract_step(result, "send_notification", "reminder_id"),
            "error": None,
            "intermediate_steps": [
                {"tool": step[0].tool, "output": step[1]}
                for step in result.get("intermediate_steps", [])
            ],
        }
    except asyncio.TimeoutError:
        logger.error("Agent pipeline timeout for %s", video_id)
        return {
            "status": "partial",
            "error": "5 分钟超时，已记录 intermediate_steps",
            "intermediate_steps": [],
        }
    except Exception as exc:
        logger.exception("Agent pipeline failed for %s", video_id)
        return {
            "status": "failed",
            "error": f"{exc!s}",
            "intermediate_steps": [],
        }


def _extract_step(result: dict, tool_name: str, field: str) -> str | None:
    """从 AgentExecutor 的 intermediate_steps 中提取指定工具的输出字段。"""
    for action, output in result.get("intermediate_steps", []):
        if action.tool == tool_name:
            try:
                parsed = json.loads(output) if isinstance(output, str) else output
                return parsed.get(field)
            except (json.JSONDecodeError, AttributeError):
                return None
    return None
```

