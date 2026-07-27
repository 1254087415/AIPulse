# B 组 spec 06 验收清单（detached 验收者 · 2026-07-26 18:08 北京时间）

> 主会话派我验收 `docs/superpowers/specs/v0.3-followed-up-and-summary/06-notification-failure.md`。
> 直接读源码 + 跑相关 tests，事实如下。

---

## ✅ 已落地（GREEN 证据）

### §7.2 三方向存储 — DB + Obsidian Tasks + Apple Reminders

- **DB `learning_events`** — `src/aipulse/summarizers/agent/tools.py:611-666` `create_learning_event` 工具实现；schema `src/aipulse/models/learning_events.py`
- **Obsidian Tasks** — `src/aipulse/summarizers/agent/tools.py:686-698` 追加 `- [ ] ⏰ {YYYY-MM-DD HH:MM} {topic}\n`；同样逻辑在 `src/aipulse/archive/service.py:55-63` fallback 路径
- **Apple Reminders** — `src/aipulse/apple/reminders.py:17-98` `create_reminder` 调 osascript，非 darwin 抛 RuntimeError

### §7.2 三方向独立 try/except

- `src/aipulse/archive/service.py:113-166` `archive_three_way()` 三步走 + 独立 try/except
- `obsidian_note` 失败 → 整体 fail（`note_path=None + errors`）
- `learning_event` 失败 → 容错（`learning_event_id=None + errors.append("learning_event")`）
- `obsidian_task` 失败 → `obsidian_task_written=False + errors.append("obsidian_task")`
- `apple_reminders` 失败 → 不进 errors（line 165 注释明确「容错：不写进 errors」）

### §7.2 Apple Reminders 列表选择（I 类红线 #4 已采纳偏差）

- **生产可配置**：`tools.py:712-717` 读 `settings.apple_reminders_list`，覆盖 default
- **测试硬隔离**：`tools.py:710` 硬编码 `list_name = "AIPulse测试"`（与 spec 03 已采纳偏差一致，详见 `feedback_tests-must-isolate-apple-reminders`）
- 不动用户真业务列表（`工作学习` / `搞钱！！！` / `琐碎生活`）— spec 06 第 44-47 行原文要求"按 topic 分类选 list"的映射未实现（**RED 候选 #3**）

### §8 失败处理（Phase 7 + Phase 6）

- `POST /api/summary/job/{id}/retry` — `src/aipulse/api/summary.py` 实现（commit `6fbb6fa`）：202 + new_job_id；409 if 旧 job queued/running
- 6 步失败入列：`fetch_transcript / summarize / judge / obsidian / learning / notification` — 通过 Agent 工具链实现（每步抛错都进 `intermediate_steps` + `summary_jobs.error`）

### §7.1 通知触发条件

- `worth_learning` → `judge_tech_relevance.should_archive` 工具判定
- `notified=true` → 通过 `summary_jobs.reminder_id` 持久化触发后状态
- `learning_notification_enabled` 开关 → `src/aipulse/core/config.py:60` 已存在；但 **没有代码读它触发 send_notification**（**RED 候选 #2**）

### 集成测试（真链路 L9）

- `tests/integration/test_summary_three_way_persistence.py::test_short_bvid_e2e_three_way_lands` — **PASSED**
  - 显式跑 6 个工具 + `finalize_summary_job` + `repo.mark_finished`
  - 断言：DB hotspots + followed_up + summary_jobs + learning_events + Obsidian .md + Apple Reminders（fake 列表）三向齐
- `test_summary_three_way_persistence_on_real_bvid` — **PASSED**
- `test_summary_without_hotspot_yields_partial_status` — **PASSED**（L6 三件齐契约）

---

## ⚠️ RED 候选（spec 06 契约 vs 当前实现偏差）

### RED #1 — plan §Task 3 archive API 未调三方向存储

- `src/aipulse/web/routes.py:133` `POST /api/hotspots/{hotspot_id}/archive`
- 调用 `hotspot/service.archive_hotspot` (`src/aipulse/hotspot/service.py:281-310`) — **v0.2 旧实现**，仅 Obsidian 单方向
- **未调 `archive_three_way()`**（`src/aipulse/archive/service.py:93`）
- spec 06 plan §Task 3 明确要求触发三方向存储

### RED #2 — `POST /api/hotspots/{id}/notify` 端点未实现

- `src/aipulse/web/routes.py` grep `notify` 0 命中
- 通知完全通过 AgentExecutor 间接调 `send_notification` 工具
- 没有独立 `notify` API 让前端主动触发通知
- `learning_notification_enabled` 开关没人读

### RED #3 — Apple Reminders topic→list 映射未实现

- spec 06 §7.2 第 44-47 行原文：`工作学习` / `搞钱！！！` / `琐碎生活` 按 topic 分类
- 当前实现：单一 `list_name`（默认 `AIPulse测试`，可被 `settings.apple_reminders_list` 覆盖）
- **这是 I 类红线冲突点**（详见任务 prompt）：
  - 测试必须硬编码 `AIPulse测试`（红线 #4）
  - 生产应当按 spec 06 原文 3 业务列表
  - 当前实现**两边都没满足** — 既没硬隔离也没 topic 映射

### RED #4 — `estimated_minutes = max(15, video_duration × 2)` 未实现

- `tools.py:654` `create_learning_event` 内部硬编码 `estimated_minutes=15`
- `learning_events.py:30` default=15
- spec 06 §7.2 第 40 行明确要求 `max(15, video_duration × 2)`
- **当前 `video_duration` 完全没被读取**

### RED #5 — scheduled_at 默认 20:00 当天 vs now+24h

- spec 06 §7.2 第 39 行：默认 `scheduled_at = 20:00 当天`
- `tools.py:747-749` `default_scheduled_at = now + 24h`
- 差异：当前是 24 小时后任意时刻；spec 要求固定 20:00

### RED #6 — `tests/unit/archive/test_service.py::test_append_obsidian_task_writes_markdown_line` 失败

- **失败原因**：测试期望 `create_reminder` 不带 `list_name` 调用，实际带 `list_name='AIPulse测试'`
- **根因**：`tools.send_notification:710` 加 list_name 后，`archive/service.append_obsidian_task` fallback 路径调 `send_notification` 也带 list_name，但**测试断言未更新**
- **影响范围**：仅 `test_archive_service_extended.py`（cross-file run 触发）
- 单独跑 `tests/unit/test_archive_service_extended.py` 全 14 个 PASSED
- 跑 `tests/unit/test_archive_service_extended.py` 全 14 个 PASSED
- 跑 `tests/unit/archive/` 全 14 个 PASSED（含 test_service.py 那个失败的 — 但单跑 archive/ 目录时 PASS）

### GREEN/RED 标准

| 候选 | GREEN | RED |
|------|-------|-----|
| #1 archive API | `web/routes.py:133` 调 `archive_three_way()` 返回 `note_path/learning_event_id/reminder_id/obsidian_task_written` 四件 | 仍只调 `hotspot/service.archive_hotspot` 单方向 |
| #2 notify API | 新增 `POST /api/hotspots/{id}/notify`，检查 `learning_notification_enabled + notified=false + worth_learning`，调 `PushStrategyRegistry` 后置 `notified=true` | 无 |
| #3 topic→list 映射 | `apple_reminders.py` 增加 `pick_list_for_topic(topic)` 函数，按关键字匹配 3 个业务列表；测试仍硬隔离 `AIPulse测试` | 无 |
| #4 estimated_minutes | `create_learning_event` 工具读 `video_duration`（从 `fetch_transcript` 中间结果或 settings），计算 `max(15, video_duration × 2)` 写入 | 硬编码 15 |
| #5 scheduled_at 默认 | `default_scheduled_at()` 改为 `today 20:00 (Asia/Shanghai)` | 仍 `now + 24h` |
| #6 测试断言 | 更新 `test_append_obsidian_task_writes_markdown_line` 接受 `list_name='AIPulse测试'` 或重写断言 | 保留过期断言（FAIL） |

---

## 派 worker 做什么

让 worker 修复 RED #1-#6（按 GREEN 标准）：
1. 重构 `archive_hotspot_route` 调 `archive_three_way()`，返回四件齐
2. 新增 `POST /api/hotspots/{id}/notify` 端点（带 `learning_notification_enabled + notified=false + worth_learning` 三重 gate）
3. `apple_reminders.py` 加 `pick_list_for_topic(topic)` topic→list 映射；**测试保留 `AIPulse测试` 硬隔离**（红线 #4 不可破）
4. `create_learning_event` 读 video_duration 实现 `max(15, duration×2)`
5. `default_scheduled_at()` 改为 today 20:00 Asia/Shanghai
6. 更新 `test_append_obsidian_task_writes_markdown_line` 断言

### I 类硬红线（worker 必守）

1. fail 不许标 completed
2. 真链路不许 mock
3. fixture 隔离真 DB
4. **测试只操作 `AIPulse测试` Reminders 列表**（不许碰 `工作学习` / `搞钱！！！` / `琐碎生活` / 用户其他真列表）
5. UI 改动必须 mcp__playwright 真实浏览器

### 跑测试命令（worker 用）

```bash
python -m pytest tests/unit/archive/ tests/unit/apple/ tests/unit/test_archive_service_extended.py tests/unit/test_clean_reminders.py tests/integration/test_summary_three_way_persistence.py --no-cov -v
```

跨文件跑会触发 test ordering 问题（test_service.py 那个失败），需单跑 archive/ + 单独跑 test_archive_service_extended.py + 单独跑 integration/ 三段。

---

## 验收者独立复验（我自己）

跑上述 3 段 + 验证：
- DB 真值：跑一遍 `test_short_bvid_e2e_three_way_lands`，查 `learning_events` + `summary_jobs` 真行
- Apple Reminders fake fixture：跑 `test_short_bvid_e2e_three_way_lands` 验 `reminder["list"] == "AIPulse测试"`
- I 类红线：grep 验证无真业务列表操作