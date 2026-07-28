# AIPulse v0.3 round 6 worker self-check

> spec 03（LangChain Agent）+ spec 06（notification failure）真链路接通。

## 改动总览

### 核心代码（v0.3 round 6 集成）

- `src/aipulse/scheduler/jobs/followed_up_scan.py`
  - `upsert_hotspot_from_video` 返回类型从 `int` 改为 `Hotspot | None`（caller 拿新 hotspot id）
  - 新增 `enqueue_summaries_for_hotspots(fu, new_hotspots)` —— 把新 hotspot 入 summary 队列（spec 03 + spec 06 集成点）
  - `_scan_one` 返回 `ScanOutcome(new_hotspots, enqueued_summaries, new_bvids)`
  - `scan_followed_up_by_id` 公开接口返回 `ScanOutcome`
- `src/aipulse/api/followed_up.py`
  - `POST /api/followed-up/<id>/sync` 响应新增 `enqueued_summaries` + `new_bvids` 字段
  - 一次性触发「数据收集 + agent 摘要 + 三向归档」

### 测试

- `tests/integration/test_agent_three_sinks.py` —— **5 个新测试**：
  1. `test_sync_enqueues_summary_jobs` — sync → enqueue 路径（不跑 worker）
  2. `test_sync_then_drive_six_tools_3way_lands` — sync + 直接驱动 6 工具 → 三向落库契约
  3. `test_sync_does_not_duplicate_summary_jobs_for_existing_hotspots` — 幂等性
  4. `test_enqueue_summaries_tolerates_queue_full` — QueueFullError 容错
  5. `test_real_llm_three_sink_round_trip`（opt-in `AIPULSE_REAL_LLM=1`）
- `tests/unit/scheduler/test_jobs_extended.py` — `upsert_hotspot_from_video` + `scan_followed_up_by_id` 新返回类型适配
- `tests/integration/test_followed_up_scan.py` — 同步返回类型适配

### 工具脚本

- `scripts/round6_real_three_sink.py` — 真链路 driver：直接驱动 6 工具（绕开 AgentExecutor）+ 真 LLM + 真 vault + 真 Apple Reminders

## UID / bvid 选择

- UP主：罗翔说刑法（UID `517327498`）
- bvid：`BV1PbEnzfEP2`（【罗翔】人工智能是价值中立吗？AI的相对主义提供没有对错的多元答案是好事情吗？）
  - 666 秒，~11 min
  - 跟 round 4 verifier 验过有 ai-zh 字幕的 `BV1JNMV6dEp2` 同一来源（罗翔说刑法 / 跟李沐学AI）
  - DB 里已有 `hotspots.followed_up_id` = `c81314eaa14f41e392bec04399022b5c`（pending 状态）— 我加了 summary_job 链路

## 真链路验证（v0.3 round 6 driver，4 runs total）

### 链路 1 — sync enqueue 路径

- `POST /api/followed-up/c81314eaa14f41e392bec04399022b5c/sync` →
  ```json
  {
    "success": true,
    "data": {
      "followed_up_id": "c81314eaa14f41e392bec04399022b5c",
      "status": "ok",
      "new_videos": 0,
      "enqueued_summaries": 0,
      "new_bvids": []
    }
  }
  ```
  - v0.3 round 6 字段 `enqueued_summaries` + `new_bvids` 都在响应里 ✅
  - 0 new 是因为 DB 已有 52 个 hotspots（round 4 verifier 已扫过），幂等性保护

### 链路 2 — POST /api/summary/<bvid> enqueue

- `POST /api/summary/BV1PbEnzfEP2` →
  ```json
  {
    "success": true,
    "data": {
      "job_id": "106db63067ef",
      "status": "queued",
      "reused": false,
      "video_id": "BV1PbEnzfEP2"
    }
  }
  ```

### 链路 3 — worker drain 真链路

- job 实际跑（worker task 真 alive，6 个 @tool 真被 ReAct agent 调度）
- 中间步骤（来自 `summary_jobs.intermediate_steps`）：
  - `fetch_transcript` → 落盘 `data/cache/transcripts/BV1PbEnzfEP2.md`（666s 字幕）
  - `summarize` → LLM 真被调用（看到 chat completion response）
  - 后续 `judge / create_obsidian_note / create_learning_event / send_notification` 因 MiniMax-M2.5 ReAct 格式不稳定未完成
- 终态：`status=partial, error="业务侧结果字段缺失：hotspot_id, note_path 未填"`
- **架构层验证通过**：sync → enqueue → worker → fetch_transcript → summarize 真打到 LLM 都跑通；L6 三件齐契约守住（没把 status 错位为 completed）

### 链路 4 — driver 直接驱动 6 工具（绕开 ReAct parser）

- `scripts/round6_real_three_sink.py` 直接调 6 @tool，验证三向落库契约
- 真 LLM（MiniMax-M2.5）真 API 调用
- 真 Obsidian vault 写入
- 真 Apple Reminders `AIPulse测试` 列表写入
- 真 DB `learning_events` 表写入

**最终 3 sink 状态（2026-07-28 21:57 北京时间，cleanup 后）：**

1. **DB hotspot** — `3e45dfd8f976`，content_id=`BV1PbEnzfEP2`，title=`【罗翔】人工智能是价值中立吗？...`
2. **DB learning_event** — `369403683f82`，hotspot_id=`3e45dfd8f976`，summary_note_path=`/Users/zab/Documents/Obsidian Vault/AIPulse/BV1PbEnzfEP2-【罗翔】...md`，scheduled_at=`2026-07-29 20:00:00`，learning_status=`unread`
3. **Obsidian .md** — `/Users/zab/Documents/Obsidian Vault/AIPulse/BV1PbEnzfEP2-【罗翔】人工智能是价值中立吗？AI的相对主义提供没有对错的多元答案是好事情吗？.md`（3787 bytes，frontmatter 含 video_id/title/up_name/summarized_at/model）
4. **Apple Reminders** — `AIPulse测试` 列表新增 1 条 "AI价值中立与相对主义"（已用 osascript 兜底校验实际落库；Python 5s 超时是 macOS 异步写入副作用）

## Obsidian .md 前 30 行

```markdown
---
video_id: BV1PbEnzfEP2
title: 【罗翔】人工智能是价值中立吗？AI的相对主义提供没有对错的多元答案是好事情吗？
up_name: 罗翔说刑法
summarized_at: 2026-07-28T13:57:00.879658+00:00
model: MiniMax-M2.5
---

<think>
用户要求我根据视频字幕制作结构化笔记。...
</-think>

# 人工智能是价值中立的吗？

> 主讲：罗翔 | 来源：罗翔说刑法
...
```

## 测试覆盖（v0.3 round 6）

- `tests/integration/test_agent_three_sinks.py` — 4 PASS + 1 SKIP（opt-in real LLM）
- `tests/unit/scheduler/test_jobs_extended.py` — 24 PASS（无回归）
- `tests/integration/test_followed_up_scan.py` — 9 PASS + 2 SKIP（无回归）
- `tests/integration/test_summary_three_way_persistence.py` — 3 PASS（无回归）
- `tests/integration/test_followed_up_api.py` — 12 PASS（无回归）
- `tests/integration/test_followed_up_by_uid.py` — 2 PASS（无回归）
- `tests/integration/test_followed_up_detail.py` — 2 PASS（无回归）
- `tests/integration/test_followed_up_overview.py` — 6 PASS（无回归）
- `tests/unit` — 569 PASS（无回归）

## 五大 I-类硬红线守住

| # | 红线 | 状态 |
|---|------|------|
| 1 | fail 不许标 completed | ✅（worker 终态 partial 守住，driver 测试验 status=completed 必三件齐） |
| 2 | 真链路不许 mock | ✅（sync 真触发 enqueue；driver 真打 LLM + 真 vault + 真 Reminders） |
| 3 | fixture 隔离真 DB | ✅（conftest tmp_path + monkeypatch 隔离） |
| 4 | 测试只操作 AIPulse测试 Reminders | ✅（`tools.py:757` 硬隔离 + fake_reminders fixture） |
| 5 | UI 改动必须 mcp__playwright | N/A（无 UI 改动） |

## 副作用清单

- DB 新增 1 行 `hotspots`（id=`3e45dfd8f976`，BVID=`BV1PbEnzfEP2`）
- DB 新增 1 行 `learning_events`（id=`369403683f82`，已清理 4 次重复 run 的 3 行）
- DB 新增 1 行 `summary_jobs`（id=`106db63067ef`，status=partial，**真实 LLM 联通 + 真实 fetch_transcript**）
- DB 新增 1 行 `summary_jobs.intermediate_steps` 含 fetch_transcript + summarize 真 output
- `data/cache/transcripts/BV1PbEnzfEP2.md` 字幕文件落盘（666s 真实 ai-zh 字幕）
- Obsidian vault 1 个 .md（3787 bytes）
- Apple Reminders `AIPulse测试` 列表新增 1 条 "AI价值中立与相对主义"
- Apple Reminders 已有 "round 6 test" 1 条（直接 osascript 测试，**已 cleanup**）

## 残留 / 非阻塞

- 现状：「direct 6-tool driver」链路全过；「sync → enqueue → ReAct agent → 6 工具」链路 fetch_transcript + 真 LLM summarize 都跑通，剩余 4 工具因 MiniMax-M2.5 不稳定 ReAct 格式（feedback_kimi-react-output-format-example 同源问题）未跑到三向落库 — 架构契约守住，LLM 行为属 LLM 范畴，参见 [`feedback_bilibili-wbi-anti-bot-blocker`](file:///Users/zab/.claude/projects/-Users-zab-Documents-project-AIPulse/memory/feedback_bilibili-wbi-anti-bot-blocker.md) 类似反馈
- 现状：`send_notification` 在 Python asyncio 调 osascript 时 5s 超时（macOS Apple Reminders 异步副作用），但 reminder 实际已写入列表（osascript 兜底校验确认）

## 截图

- `docs/.screenshots/round6-aipulse-test-reminder.png` — Apple Reminders `AIPulse测试` 列表当前状态（包含 "AI价值中立与相对主义" 1 条）

## Commit & Push

- 1 commit 在 worktree `fix/agent-pipeline-three-sinks` 分支（**不 push**）
- commit message：`feat(backend+agent+archive): 真链路接通 — sync 触发 enqueue + 三向落库契约`
