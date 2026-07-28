# Phase 3 — LangChain Agent + Kimi Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `run_skill(name="subagent-driven-development")` 或 `run_skill(name="executing-plans")` 来实施本计划。
>
> **对应 spec**: [`../../specs/v0.3-followed-up-and-summary/03-langchain-agent.md`](../../specs/v0.3-followed-up-and-summary/03-langchain-agent.md)
> **上游依赖**: Phase 1 (DB + Bearer) + Phase 2 (字幕工具)

**Goal:** 实施 LangChain ReAct Agent + Kimi (kimi-for-coding) + 6 个 @tool + 半自动边界。

**Architecture:**
- `summarizers/agent/` 完整模块（agent / tools / prompts / runner）
- 半自动边界：fetch_transcript / summarize / judge 自动；obsidian / learning / notification 手动
- Kimi 集成：`langchain_openai.ChatOpenAI` + `base_url=https://api.kimi.com/coding/v1`

**Tech Stack:** Python 3.11+ / LangChain / langchain_openai / Pydantic v2

---

## 文件结构

- Create: `src/aipulse/summarizers/agent/__init__.py`
- Create: `src/aipulse/summarizers/agent/agent.py` — ReAct Agent
- Create: `src/aipulse/summarizers/agent/tools.py` — 6 个 @tool
- Create: `src/aipulse/summarizers/agent/prompts.py` — System Prompt + ReAct 模板
- Create: `src/aipulse/summarizers/agent/runner.py` — Agent 初始化
- Create: `src/aipulse/summarizers/agent/obsidian.py` — Obsidian 写入工具
- Create: `tests/unit/agent/test_agent.py`
- Create: `tests/unit/agent/test_tools.py`
- Create: `tests/unit/agent/test_prompts.py`
- Create: `tests/integration/test_kimi_integration.py` — 真实 Kimi API

---

## Task 1: System Prompt + ReAct 模板（subagent-C3）

**Files:**
- Create: `src/aipulse/summarizers/agent/prompts.py`
- Test: `tests/unit/agent/test_prompts.py`

- [ ] **Step 1: 写失败测试** — 测试：
  - `SYSTEM_PROMPT` 包含核心规则（严格顺序、反空话硬约束、错误处理、scheduled_at 选择、topic 命名）
  - 总结结构模板：TL;DR / 核心观点 / 关键术语 / 行动项 / 待澄清问题
  - `judge_tech_relevance` JSON 输出格式（严格 JSON，无 markdown code fence）
  - `REACT_TEMPLATE` 包含 Thought/Action/Observation 槽位
- [ ] **Step 2: 运行 RED**
- [ ] **Step 3: 最小实现** — 完整字符串模板 + Pydantic 校验
- [ ] **Step 4: 运行 GREEN**
- [ ] **Step 5: Commit**

## Task 2: 6 个 @tool 装饰的工具（subagent-C2）

**Files:**
- Create: `src/aipulse/summarizers/agent/tools.py`
- Test: `tests/unit/agent/test_tools.py`

- [ ] **Step 1: 写失败测试** — 6 个工具：
  - Tool 1: `fetch_transcript(bvid) -> str` — 拉取字幕（复用 Phase 2 字幕工具）
  - Tool 2: `summarize(transcript, title) -> Summary` — 调用 Kimi
  - Tool 3: `judge_tech_relevance(transcript, title) -> DecisionStatus` — JSON 输出
  - Tool 4: `create_obsidian_note(summary, hotspot_id) -> str` — 写 Obsidian
  - Tool 5: `create_learning_event(hotspot_id, scheduled_at, duration) -> str` — DB 记录
  - Tool 6: `send_notification(hotspot_id, message) -> bool` — 调用 PushStrategyRegistry
- [ ] **Step 2: 运行 RED**
- [ ] **Step 3: 最小实现** — `@tool` 装饰器 + 每个工具的输入输出 schema
- [ ] **Step 4: 运行 GREEN**
- [ ] **Step 5: 半自动边界** — 标记 fetch_transcript / summarize / judge 为 AUTO，其他为 MANUAL
- [ ] **Step 6: Commit**

## Task 3: Obsidian 笔记写入（subagent-C2）

**Files:**
- Create: `src/aipulse/summarizers/agent/obsidian.py`

- [ ] **Step 1: 写失败测试** — Obsidian 写入：
  - 文件名格式：`{topic}.md`（topic 从 prompts 规则生成）
  - 路径：`{vault}/{archive_folder}/`
  - 文件结构：TL;DR / 核心观点 / 关键术语 / 行动项 / 待澄清问题 + Obsidian Tasks checkbox
  - 追加 `- [ ] ⏰ {scheduled_at}` 到末尾
  - 失败重试：Q142 不自动重试
- [ ] **Step 2: 运行 RED**
- [ ] **Step 3: 最小实现**
- [ ] **Step 4: 运行 GREEN**
- [ ] **Step 5: Commit**

## Task 4: Agent 主体（subagent-C1）

**Files:**
- Create: `src/aipulse/summarizers/agent/agent.py`
- Test: `tests/unit/agent/test_agent.py`

- [ ] **Step 1: 写失败测试** — Agent 主体：
  - `create_react_agent(llm, tools, prompt)` 调用
  - ReAct prompt 模板 + 6 个 tool 注入
  - `agent.invoke({"input": ...})` 输入输出契约
  - max_iterations=10 防止死循环
- [ ] **Step 2: 运行 RED**
- [ ] **Step 3: 最小实现** — `build_agent(tools, llm) -> AgentExecutor`
- [ ] **Step 4: 运行 GREEN**
- [ ] **Step 5: Commit**

## Task 5: Kimi 集成 + Runner（subagent-C1）

**Files:**
- Create: `src/aipulse/summarizers/agent/runner.py`
- Test: `tests/integration/test_kimi_integration.py`

- [ ] **Step 1: 写失败测试** — Runner：
  - `ChatOpenAI(base_url="https://api.kimi.com/coding/v1", model="kimi-for-coding", api_key=settings.kimi_api_key)`
  - `run_summary(hotspot_id, bvid) -> SummaryResult` 主入口
  - 真实 Kimi API 测试：用 `kimi-for-coding` 调用一次总结，验证返回结构
- [ ] **Step 2: 运行 RED**
- [ ] **Step 3: 最小实现**
- [ ] **Step 4: 运行 GREEN**
- [ ] **Step 5: Commit**

## Task 6: 半自动边界落实（subagent-C1）

**Files:**
- Modify: `src/aipulse/summarizers/agent/agent.py`
- Modify: `src/aipulse/summarizers/agent/runner.py`

- [ ] **Step 1: 写失败测试** — 半自动：
  - Agent pipeline 自动调用 fetch_transcript / summarize / judge
  - Agent pipeline **不**自动调用 obsidian / learning / notification
  - runner 返回 `partial_result` 状态（auto 部分完成 + manual 部分待触发）
- [ ] **Step 2: 运行 RED**
- [ ] **Step 3: 最小实现** — System Prompt 中明确工具边界 + runner 状态机
- [ ] **Step 4: 运行 GREEN**
- [ ] **Step 5: Commit**

## Task 7: Phase 3 完整验证

- [ ] **Step 1: 单元测试** — `cd $(git rev-parse --show-toplevel) && pytest tests/unit/agent -v`
- [ ] **Step 2: Kimi 真实集成测试** — `pytest tests/integration/test_kimi_integration.py -v`（必须有真实 API key）
- [ ] **Step 3: 独立验证 subagent** — 派独立 reviewer 验证半自动边界
- [ ] **Step 4: 未通过则返工**

---

## 自审

- 6 个 tool 覆盖：fetch_transcript / summarize / judge / obsidian / learning / notification
- 半自动边界明确：3 自动 + 3 手动
- Kimi 真实集成：kimi-for-coding + ChatOpenAI
- Prompt 完整：含核心规则 + ReAct 模板