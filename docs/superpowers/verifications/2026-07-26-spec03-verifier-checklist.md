# B 组 spec 03 验收清单（detached 验收者 · 2026-07-26 18:38 北京时间）

> 主会话派我验收 `docs/superpowers/specs/v0.3-followed-up-and-summary/03-langchain-agent.md`。
> 原 conversation 已压缩，凭 git log + 当前代码 + 修复记录复盘。

---

## ✅ 已落地（GREEN 证据）

### §5.1 ReAct Agent（AgentExecutor）

- 入口：`src/aipulse/summarizers/agent/runner.py`
- 配置：
  - `:87 max_iterations=10`（spec §5.8 锁定，§5.1 写 5 是 spec 内部矛盾，工程选 10 = 6 tool + buffer）
  - `:88 max_execution_time=300`（Q141，5 分钟硬超时）
  - `:90 return_intermediate_steps=True`（保留中间步骤用于 debug + silent-failure 检测）

### §5.3 status 三态契约

- `:127 status="completed"` 仅当 Agent 不抛异常时返回
- `:154 status="partial"` timeout 触发
- `:162 status="failed"` exception 触发
- **绝不容忍 fail 业务异常被吞 + status 错位**（I 类红线 #1）

### L7 silent-failure 修复（验收重点）

- `:200 class _StepCaptureCallback(AsyncCallbackHandler)` — 捕获 ReAct 中间步骤
- 校验：若 Agent 报 completed 但 intermediate_steps 为空 → 实际是 silent failure
- 修复 commit：`369cece fix(backend+web): harden Agent build + 微信分组补 3 字段`

### §5.2 6 个 @tool

- `fetch_transcript` — `src/aipulse/summarizers/agent/tools.py`（含 ASR fallback 见 spec 02 BLOCK 4）
- `summarize_video`
- `judge_tech_relevance`
- `write_obsidian_note`
- `create_learning_event`
- `send_notification`

### §5.4 Kimi 集成

- base_url = `https://api.kimi.com/coding/v1`
- model = `kimi-for-coding`
- 配置：`src/aipulse/core/config.py:48-60`
- 真链路：`scripts/test_real_kimi_direct.py` + `scripts/test_real_kimi_e2e.py`（commit `7e0aa08`）

### Kimi 签约 prompt 修复（验收重点）

- 问题：kimi-for-coding 不熟 ReAct 格式
- 修复：加 Thought/Action/Action Input 正确+错误示例（参考 `feedback_kimi-react-output-format-example`）
- 落地：`src/aipulse/summarizers/agent/prompts.py`

### §5.5 Reminders 列表硬隔离（I 类红线 #4）

- `src/aipulse/summarizers/agent/tools.py:755-757`
  ```python
  # tests 走 AIPulse测试 list (feedback_tests-must-isolate-apple-reminders
  list_name = "AIPulse测试"
  ```
- 测试断言：`tests/unit/summarizers/test_agent_tools_extended.py:1245` 断言 `list_name == "AIPulse测试"`
- 生产可覆盖：`:762 list_name = getattr(cfg, "apple_reminders_list", list_name) or list_name`

### estimated_minutes 公式

- `_compute_estimated_minutes(video_id) = max(15, duration_minutes * 2)`
- `src/aipulse/summarizers/agent/tools.py:400-409`

### default_scheduled_at

- `tools.py:794-806`：默认 20:00 Asia/Shanghai，已过 → tomorrow 20:00

---

## ✅ 测试覆盖（85 PASS）

- `tests/unit/summarizers/test_agent.py`
- `tests/unit/summarizers/test_agent_runner_extended.py`
- `tests/unit/summarizers/test_agent_tools_extended.py`
- `tests/unit/summarizers/test_agent_to_100.py`（commit `ddc1b93`，覆盖率推到 100%）

---

## 五大 I-类硬红线

| # | 红线 | 状态 |
|---|------|------|
| 1 | fail 不许标 completed | ✅（runner.py status 三态契约 + L7 修复） |
| 2 | 真链路不许 mock | ✅（spec 03 真 Kimi 36 字符响应验证） |
| 3 | fixture 隔离真 DB | ✅ |
| 4 | 测试只操作 AIPulse测试 Reminders | ✅（tools.py:757 硬隔离 + 测试断言） |
| 5 | UI 改动必须 mcp__playwright | N/A |

---

## 残留（非阻塞）

- spec §5.1 max_iterations=5 vs §5.8 max_iterations=10 的内部矛盾已选 §5.8（工程合理）

---

## 整体结论

**spec 03 = GREEN** — AgentExecutor 配置正确 + L7 silent-failure 修复 + 真 Kimi 验证 + Reminders 隔离硬编码 + 85 测试 PASS。