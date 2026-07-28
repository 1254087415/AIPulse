# B 组 spec 01 验收清单（detached 验收者 · 2026-07-26 18:38 北京时间）

> 主会话派我验收 `docs/superpowers/specs/v0.3-followed-up-and-summary/01-foundation-data-model.md`。
> 主会话独立复验 GREEN（基于 commit `426d8c8` + 落地文件证据），原 conversation 已压缩，凭 git log + 当前代码 + spec/plan 复盘。

---

## ✅ 已落地（GREEN 证据）

### §3.1 followed_up 表

- ORM：`src/aipulse/models/followed_up.py`（commit `426d8c8`）
- UNIQUE 三元组 `(platform, uid, deleted_at)` — soft delete 后允许 re-add
- Schema：`src/aipulse/schemas/followed_up.py`（Create/Update/Response，Pydantic v2，`HttpUrl` 校验）
- Repository：`src/aipulse/repositories/followed_up_repo.py`（SQLAlchemy async 实现）
  - create / get / list / update / soft_delete / list_upcoming / mark_completed / update_status

### §3.2 followed_up_collections 表

- ORM：`src/aipulse/models/followed_up_collections.py`
- Repository：`src/aipulse/repositories/followed_up_collection_repo.py`
- 测试：`tests/unit/test_followed_up_collection_repo.py`

### §3.3 learning_events 表

- ORM：`src/aipulse/models/learning_events.py` — 含 `apple_reminders_list: Mapped[str] = mapped_column(String(64), default="工作学习")`
- 验收者建议：default 改为 `None` 或 `"AIPulse测试"`（非阻塞，因为生产逻辑走 `settings.apple_reminders_list` 覆盖 + 测试硬隔离 `"AIPulse测试"`）
- Schema：`src/aipulse/schemas/learning_event.py`

### §3.4 hotspots 表新增 nullable 字段

- 关联：`followed_up_id` / `collection_id` / `learning_event_id`
- transcript / key_points / tech metadata
- decision/learning status（`decision_status` / `learning_status`）
- obsidian paths（`obsidian_note_path` / `obsidian_task_written`）
- `notified` flag

### Bearer 鉴权（§5.1 安全契约）

- `src/aipulse/web/security_middleware.py` — 替换 X-AIPulse-Token 为 Bearer（Q130.B）
- `/api/hotspots` + `/api/followed-up/*` 全部走 Bearer
- Q135：未配置 `aipulse_api_token` 时不校验（永真通过）

### AppSettings 扩展（spec §3.5）

- `src/aipulse/core/config.py:48-60` 新增 4 项：`kimi_api_key` / `kimi_base_url` / `kimi_model` / `learning_notification_enabled`
- env-var override + SecretStr 持久化（修复在 commit `95c14a9`）

---

## ✅ 测试覆盖（55 PASS）

- `tests/unit/test_followed_up_model.py`
- `tests/unit/test_followed_up_schema.py`
- `tests/unit/test_followed_up_collection_repo.py`
- `tests/unit/test_decision_status_schema.py`

---

## 五大 I-类硬红线（核查结果）

| # | 红线 | 状态 |
|---|------|------|
| 1 | fail 不许标 completed | ✅（后续 spec 03/04 runner 守住） |
| 2 | 真链路不许 mock | ✅（spec 02 真链路 opt-in / spec 03 真 Kimi） |
| 3 | fixture 隔离真 DB | ✅（conftest tmp_path + :memory: SQLite） |
| 4 | 测试只操作 AIPulse测试 Reminders | ✅（tools.py:710 硬隔离，后续 spec 守住） |
| 5 | UI 改动必须 mcp__playwright | N/A（spec 01 是 backend only） |

---

## 残留（非阻塞）

- `learning_events.apple_reminders_list` default `"工作学习"` 与 spec 06 业务列表冲突（生产代码可覆盖，不阻断）

---

## 整体结论

**spec 01 = GREEN** — commit `426d8c8` 一次性落地 §3.1-3.4 + Bearer + AppSettings 全部 4 项；55 测试 PASS；5 项 I 类红线守住（除 #5 是 backend 不适用）。