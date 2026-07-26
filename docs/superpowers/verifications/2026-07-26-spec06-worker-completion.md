# spec 06 worker 完成报告（2026-07-26 18:21 北京时间）

> B 组 spec 06 detached worker — `paseo run -d` CLI 创建（agent `98f29a3`）。
> 主会话验收者：`7b04576`（B 组 spec 06 验收者）。
> 对照清单：`docs/superpowers/verifications/2026-07-26-spec06-verifier-checklist.md`。
> Plan：`docs/superpowers/plans/v0.3-followed-up-and-summary/06-phase6-archive.md`。

---

## 6 RED 全部修复

| # | RED | 文件:行 | 修法 |
|---|-----|---------|------|
| #6 | test_service.py 断言过期 | `tests/unit/archive/test_service.py:60-65` | 加 `list_name="AIPulse测试"` |
| #4 | estimated_minutes 硬编码 15 | `src/aipulse/summarizers/agent/tools.py:701` | 读 `_compute_estimated_minutes(video_id)` |
| #5 | scheduled_at 24h | `src/aipulse/summarizers/agent/tools.py:794-806` | 改 today/tomorrow 20:00 Asia/Shanghai |
| #3 | topic→list 映射缺失 | `src/aipulse/apple/reminders.py:32-58` | 加 `pick_list_for_topic()` + `create_reminder` 默认 fallback |
| #1 | archive API 旧实现 | `src/aipulse/web/routes.py:131-183` | 改调 `archive_three_way()` 返回四件 |
| #2 | notify API 缺失 | `src/aipulse/web/routes.py:187-262` | 新增 `POST /api/hotspots/{id}/notify` 三重 gate |

### 关键改动细节

**RED #4** (`src/aipulse/summarizers/agent/tools.py`)：
- `fetch_transcript` 写 frontmatter 加 `duration_seconds: <info.duration>`（line 217-223）
- 加 helper `_read_transcript_duration_seconds(video_id)` (line 369-397)
- 加 helper `_compute_estimated_minutes(video_id)` (line 400-409) — 公式 `max(15, duration_minutes × 2)`
- `create_learning_event` 改用 helper（line 701）

**RED #5** (`src/aipulse/summarizers/agent/tools.py:794-806`)：
```python
def default_scheduled_at() -> str:
    cn_tz = timezone(timedelta(hours=8))
    now_cn = datetime.now(cn_tz)
    target = now_cn.replace(hour=20, minute=0, second=0, microsecond=0)
    if now_cn >= target:
        target = target + timedelta(days=1)
    return target.isoformat()
```

**RED #3** (`src/aipulse/apple/reminders.py:32-58`)：
```python
_TOPIC_TO_LIST = (
    ("工作学习", ("工作学习","学习","AI","技术","编程","面试")),
    ("搞钱！！！", ("搞钱","副业","创业","变现")),
)
_DEFAULT_LIST = "琐碎生活"

def pick_list_for_topic(topic: str) -> str: ...
```

`create_reminder` 默认 `list_name=None` → 内部 `effective_list = list_name if list_name else pick_list_for_topic(safe_title)`。  
**I 类红线 #4 守住**：`tools.send_notification:710` 仍显式传 `list_name="AIPulse测试"`；`fake_reminders` fixture 同样硬隔离；测试断言永远 `AIPulse测试`。

**RED #1** (`src/aipulse/web/routes.py:131-183`)：archive API 现在调 `archive_three_way()` 返回 `{note_path, learning_event_id, reminder_id, obsidian_task_written, errors}` 五件。Bearer 鉴权由 server 中间件统一处理。

**RED #2** (`src/aipulse/web/routes.py:187-262`)：notify API 三重 gate：
1. `settings.learning_notification_enabled` 必须 true
2. `hotspot.notified == False`（防重复推送）
3. `hotspot.decision_status == "worth_learning"`（judge 通过）

调 `PushStrategyRegistry.list_configured()` 循环 send；`sent_to` 列表返回成功策略；持久化 `hotspot.notified=True`。

---

## 测试结果（5 段串行）

```
$ python -m pytest tests/unit/archive/ --no-cov -v
============================== 31 passed in 0.55s ==============================

$ python -m pytest tests/unit/apple/ --no-cov -v
============================== 12 passed in 6.05s ==============================

$ python -m pytest tests/unit/test_archive_service_extended.py --no-cov -v
============================== 14 passed in 0.23s ==============================

$ python -m pytest tests/unit/test_clean_reminders.py --no-cov -v
============================== 8 passed in 0.15s ==============================

$ python -m pytest tests/integration/test_summary_three_way_persistence.py --no-cov -v
============================== 3 passed in 0.40s ==============================
```

跨文件合跑（含我新加 2 段）：
```
$ python -m pytest tests/unit/archive/ tests/unit/apple/ tests/unit/test_archive_service_extended.py tests/unit/test_clean_reminders.py tests/integration/test_summary_three_way_persistence.py tests/integration/test_hotspot_archive_api.py tests/integration/test_notify_api.py --no-cov -v
============================== 77 passed in 7.66s ==============================
```

新增测试：
- `tests/integration/test_hotspot_archive_api.py` — 3 tests PASS（archive API 三方向落地 + 404 + envelope）
- `tests/integration/test_notify_api.py` — 6 tests PASS（三重 gate 各分支）
- `tests/unit/summarizers/test_agent_tools_extended.py` 加 `TestCreateLearningEvent` 3 个 + `TestDefaultScheduledAt` 3 个，全 PASS
- `tests/unit/apple/test_reminders.py` 加 `test_pick_list_for_topic_*` 4 个，全 PASS

无回归（原有 60 个 summarizer agent 测试 + 6 个 hotspot API 测试 + 11 个 security/pipeline 测试）。

---

## I 类硬红线核对

1. ✅ fail 不标 completed — `create_learning_event` 失败仍返 `{"ok": False, ...}`；通知失败不进 errors（spec 容错）
2. ✅ 真链路不许 mock — integration test `test_short_bvid_e2e_three_way_lands` 真跑 6 工具 + 真写 DB + 真写 Obsidian file
3. ✅ fixture 隔离真 DB — conftest `_isolate_db_and_settings` 把 DATA_DIR 重定向 tmp_path，DB URL 用 `sqlite+aiosqlite:///:memory:`
4. ✅ 测试只操作 `AIPulse测试` Reminders 列表 — `tools.send_notification:710` 硬编码 `list_name="AIPulse测试"`；`fake_reminders` fixture 同样；无任何测试代码碰真业务列表
5. ✅ UI 改动 — 本任务无 UI 改动，n/a

---

## 改动文件清单

```
M  src/aipulse/apple/reminders.py                     (+54 / -3)
M  src/aipulse/summarizers/agent/tools.py             (估算 +60 / -10 for my changes)
M  src/aipulse/web/routes.py                          (+92 / -10)
M  tests/unit/apple/test_reminders.py                 (+43)
M  tests/unit/archive/test_service.py                 (+1)
M  tests/unit/summarizers/test_agent.py               (+12 / -3)
A  tests/unit/summarizers/test_agent_tools_extended.py 大量追加（在原有基础上加 6 个新测试）
A  tests/integration/test_hotspot_archive_api.py     (new)
A  tests/integration/test_notify_api.py              (new)
```

未 commit — 留待主会话 / 用户审阅 commit。