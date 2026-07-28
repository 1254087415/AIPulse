# Phase 6 — 归档与三方向存储 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `run_skill(name="subagent-driven-development")` 或 `run_skill(name="executing-plans")` 来实施本计划。
>
> **对应 spec**: [`../../specs/v0.3-followed-up-and-summary/06-notification-failure.md`](../../specs/v0.3-followed-up-and-summary/06-notification-failure.md)
> **上游依赖**: Phase 4 (Summary API) + Phase 5 (vault 路径)

**Goal:** 实施 hotspot 归档 API + 三方向独立 try/except（DB + Obsidian Tasks + Apple Reminders）+ notify API。

**Architecture:**
- `POST /api/hotspots/{id}/archive` 归档触发
- 三方向独立 try/except，单方向失败不影响其他
- `POST /api/hotspots/{id}/notify` 通知触发
- Apple Reminders 列表选择（工作学习 / 搞钱 / 琐碎生活）

**Tech Stack:** Python 3.11+ / apple-assistant-eventkit skill / PushStrategyRegistry

---

## 文件结构

- Modify: `src/aipulse/api/hotspots.py` — 新增 archive / notify 端点
- Create: `src/aipulse/services/learning_event_archiver.py`
- Create: `src/aipulse/services/apple_reminders.py`
- Create: `tests/unit/test_learning_event_archiver.py`
- Create: `tests/unit/test_apple_reminders.py`
- Create: `tests/integration/test_hotspot_archive_api.py`

---

## Task 1: learning_event_archiver 服务（subagent-F）

**Files:**
- Create: `src/aipulse/services/learning_event_archiver.py`
- Test: `tests/unit/test_learning_event_archiver.py`

- [ ] **Step 1: 写失败测试** — 三方向存储：
  - DB: `learning_events` 写入
  - Obsidian Tasks: 笔记末尾追加 `- [ ] ⏰ {scheduled_at}`
  - Apple Reminders: 通过 apple-assistant-eventkit 创建
  - 三方向独立 try/except
  - 任一失败：`obsidian_task_created=false` 或 `apple_reminder_id=null`
- [ ] **Step 2: 运行 RED**
- [ ] **Step 3: 最小实现**
- [ ] **Step 4: 运行 GREEN**
- [ ] **Step 5: Commit**

## Task 2: apple-assistant-eventkit 集成（subagent-F）

**Files:**
- Create: `src/aipulse/services/apple_reminders.py`
- Test: `tests/unit/test_apple_reminders.py`

- [ ] **Step 1: 写失败测试** — Apple Reminders：
  - 列表选择：工作学习 / 搞钱 / 琐碎生活（按 topic 分类）
  - 创建 reminder 并返回 id
  - macOS only：非 macOS 跳过 + 记录日志
- [ ] **Step 2: 运行 RED**
- [ ] **Step 3: 最小实现** — 调用现有 `apple-assistant-eventkit` skill
- [ ] **Step 4: 运行 GREEN**
- [ ] **Step 5: Commit**

## Task 3: archive API 端点（subagent-F）

**Files:**
- Modify: `src/aipulse/api/hotspots.py`
- Test: `tests/integration/test_hotspot_archive_api.py`

- [ ] **Step 1: 写失败测试** — `POST /api/hotspots/{id}/archive`：
  - 触发三方向存储
  - 返回每个方向的成功状态
  - Bearer 鉴权
- [ ] **Step 2: 运行 RED**
- [ ] **Step 3: 最小实现**
- [ ] **Step 4: 运行 GREEN**
- [ ] **Step 5: Commit**

## Task 4: notify API 端点（subagent-F）

**Files:**
- Modify: `src/aipulse/api/hotspots.py`

- [ ] **Step 1: 写失败测试** — `POST /api/hotspots/{id}/notify`：
  - 检查 `learning_notification_enabled` 开关
  - 检查 `notified=false`
  - 检查 `decision_status="worth_learning"`
  - 调用 PushStrategyRegistry 发送通知
  - 触发后置 `notified=true`
- [ ] **Step 2: 运行 RED**
- [ ] **Step 3: 最小实现**
- [ ] **Step 4: 运行 GREEN**
- [ ] **Step 5: Commit**

## Task 5: scheduled_at 选择（subagent-F）

**Files:**
- Modify: `src/aipulse/services/learning_event_archiver.py`

- [ ] **Step 1: 写失败测试** — scheduled_at：
  - 默认 20:00 当天
  - 用户可配置
  - estimated_minutes = max(15, video_duration × 2)
- [ ] **Step 2: 运行 RED**
- [ ] **Step 3: 最小实现**
- [ ] **Step 4: 运行 GREEN**
- [ ] **Step 5: Commit**

## Task 6: Phase 6 完整验证

- [ ] **Step 1: 单元测试 + 集成测试**
- [ ] **Step 2: 真实 Obsidian 写入测试** — 在临时 vault 下创建 + 验证文件
- [ ] **Step 3: 真实 Apple Reminders 测试** — macOS only
- [ ] **Step 4: 独立验证 subagent**
- [ ] **Step 5: 未通过则返工**

---

## 自审

- 三方向独立：DB / Obsidian / Apple 各自 try/except
- notify 触发条件严格：worth_learning + notified=false + enabled=true
- 真实集成：必须 macOS 下跑 Apple Reminders