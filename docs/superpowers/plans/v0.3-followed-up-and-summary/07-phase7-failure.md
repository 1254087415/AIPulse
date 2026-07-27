# Phase 7 — 失败处理 + UP主详情页 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `run_skill(name="subagent-driven-development")` 或 `run_skill(name="executing-plans")` 来实施本计划。
>
> **对应 spec**: [`../../specs/v0.3-followed-up-and-summary/06-notification-failure.md`](../../specs/v0.3-followed-up-and-summary/06-notification-failure.md) §8 + [`05-frontend-ui.md`](../../specs/v0.3-followed-up-and-summary/05-frontend-ui.md) §6.12
> **上游依赖**: Phase 4 + Phase 5 + Phase 6

**Goal:** 实施失败 tab + 重试/跳过/强制决策 + UP主详情页（合集列表 + 视频列表）+ 健康状态徽章。

**Architecture:**
- 失败入列：fetch_transcript / summarize / judge / obsidian / learning / notification 各自独立失败
- 不自动重试（除 fetch_transcript 5 秒超时内 3 次）
- UP主详情页：合集 accordion + 视频列表 accordion + 健康徽章

**Tech Stack:** Python 3.11+ / Vue 3

---

## 文件结构

### 后端（subagent-F2）

- Modify: `src/aipulse/api/hotspots.py` — 新增失败 tab 端点
- Create: `src/aipulse/api/failures.py` — 失败重试/跳过 API
- Create: `tests/integration/test_failure_api.py`

### 前端（subagent-E2）

- Create: `frontend/src/components/failure-tab/FailureTab.vue`
- Create: `frontend/src/components/failure-tab/FailureCard.vue`
- Create: `frontend/src/components/follow-detail-view/FollowDetailView.vue`（增强）
- Create: `frontend/src/components/follow-detail-view/CollectionsAccordion.vue`
- Create: `frontend/src/components/follow-detail-view/VideosAccordion.vue`
- Create: `frontend/src/components/health-badge/HealthBadge.vue`
- Test: `frontend/tests/unit/failure-tab.test.ts`
- Test: `frontend/tests/unit/follow-detail-view.test.ts`

---

## Task 1: 失败 tab 后端 API（subagent-F2）

**Files:**
- Create: `src/aipulse/api/failures.py`
- Test: `tests/integration/test_failure_api.py`

- [ ] **Step 1: 写失败测试** — `GET /api/failures`：
  - 返回所有失败任务（按 step 分组）
  - `POST /api/failures/{id}/retry`
  - `POST /api/failures/{id}/skip`
  - `POST /api/failures/{id}/force` 强制决策（仅 judge 步骤）
- [ ] **Step 2: 运行 RED**
- [ ] **Step 3: 最小实现**
- [ ] **Step 4: 运行 GREEN**
- [ ] **Step 5: Commit**

## Task 2: 失败 tab 前端（subagent-E2）

**Files:**
- Create: `frontend/src/components/failure-tab/FailureTab.vue`
- Create: `frontend/src/components/failure-tab/FailureCard.vue`
- Test: `frontend/tests/unit/failure-tab.test.ts`

- [ ] **Step 1: 写失败测试** — 失败 UI：
  - 按 step 分组（fetch_transcript / summarize / judge / obsidian / learning / notification）
  - 每张卡片：失败步骤 / 错误信息 / 重试 / 跳过 / 强制（judge 时）
  - 接入 DashboardView "失败" tab
- [ ] **Step 2: 运行 RED**
- [ ] **Step 3: 最小实现**
- [ ] **Step 4: 运行 GREEN**
- [ ] **Step 5: Commit**

## Task 3: UP主详情页增强（subagent-E2）

**Files:**
- Modify: `frontend/src/components/follow-detail-view/FollowDetailView.vue`
- Create: `frontend/src/components/follow-detail-view/CollectionsAccordion.vue`
- Create: `frontend/src/components/follow-detail-view/VideosAccordion.vue`

- [ ] **Step 1: 写失败测试** — 详情页：
  - 合集列表 accordion（Q20）：展开显示合集内视频
  - 视频列表 accordion：展开显示字幕预览 + 总结按钮 + 失败状态
  - 健康徽章：healthy / warning / error
- [ ] **Step 2: 运行 RED**
- [ ] **Step 3: 最小实现**
- [ ] **Step 4: 运行 GREEN**
- [ ] **Step 5: Commit**

## Task 4: 健康状态徽章（subagent-E2）

**Files:**
- Create: `frontend/src/components/health-badge/HealthBadge.vue`
- Test: `frontend/tests/unit/health-badge.test.ts`

- [ ] **Step 1: 写失败测试** — 徽章：
  - `healthy` 绿色
  - `warning` 黄色
  - `error` 红色
- [ ] **Step 2: 运行 RED**
- [ ] **Step 3: 最小实现**
- [ ] **Step 4: 运行 GREEN**
- [ ] **Step 5: Commit**

## Task 5: Phase 7 完整验证

- [ ] **Step 1: 单元测试 + 集成测试**
- [ ] **Step 2: 失败注入测试** — 模拟 Kimi API 失败 / B站限流
- [ ] **Step 3: 独立验证 subagent**
- [ ] **Step 4: 未通过则返工**

---

## 自审

- 失败 tab 覆盖 6 个步骤
- 重试/跳过/强制决策正确
- 详情页：合集 + 视频 accordion + 健康徽章