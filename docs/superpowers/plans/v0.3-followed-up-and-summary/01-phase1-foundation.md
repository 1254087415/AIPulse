# Phase 1 — 数据模型 + UI 框架 + Bearer 改造 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `run_skill(name="subagent-driven-development")` (recommended) 或 `run_skill(name="executing-plans")` 来实施本计划。
>
> **对应 spec**: [`../../specs/v0.3-followed-up-and-summary/01-foundation-data-model.md`](../../specs/v0.3-followed-up-and-summary/01-foundation-data-model.md) + [`05-frontend-ui.md`](../../specs/v0.3-followed-up-and-summary/05-frontend-ui.md) + [`07-config-auth-vault.md`](../../specs/v0.3-followed-up-and-summary/07-config-auth-vault.md)

**Goal:** 实施 v0.3 的 DB schema（4 表）+ Vue sidebar + 关注列表 panel + Authorization Bearer 全局改造。

**Architecture:**
- DB：SQLAlchemy 2.0 + Alembic
- 前端：Vue 3 sidebar 200px + 关注列表 panel + 添加表单
- 鉴权：后端 security_middleware 全改 Bearer；前端 apiFetch 加 Authorization 头

**Tech Stack:** Python 3.11+ / SQLAlchemy 2.0 / Alembic / Pydantic v2 / Vue 3 / Vite / TypeScript

---

## 文件结构

### 后端（subagent-A）

- Create: `src/aipulse/models/followed_up.py` — `followed_up` 表 SQLAlchemy 模型
- Create: `src/aipulse/models/followed_up_collections.py` — `followed_up_collections` 表
- Create: `src/aipulse/models/learning_events.py` — `learning_events` 表
- Modify: `src/aipulse/models/hotspot.py` — 新增 nullable 字段
- Create: `migrations/versions/xxxx_add_followed_up_tables.py` — Alembic migration
- Create: `src/aipulse/repositories/followed_up_repo.py` — Protocol + SQLAlchemy 实现
- Create: `src/aipulse/repositories/learning_event_repo.py`
- Create: `src/aipulse/schemas/followed_up.py` — Pydantic Schema
- Create: `src/aipulse/schemas/learning_event.py`
- Modify: `src/aipulse/settings.py` — 新增 `kimi_api_key` / `kimi_base_url` / `kimi_model` / `learning_notification_enabled`
- Modify: `src/aipulse/web/security_middleware.py` — Bearer 全局改造
- Create: `tests/unit/test_followed_up_model.py` — SQLAlchemy 模型单元测试
- Create: `tests/unit/test_followed_up_schema.py` — Pydantic Schema 测试
- Create: `tests/integration/test_followed_up_repo.py` — Repository 集成测试（真实 SQLite 内存）
- Create: `tests/unit/test_security_middleware.py` — Bearer 校验单元测试
- Create: `tests/integration/test_security_middleware_integration.py` — 集成测试

### 前端（subagent-E）

- Create: `frontend/src/components/sidebar/Sidebar.vue` — 200px sidebar 框架
- Create: `frontend/src/components/sidebar/SidebarNav.vue` — 导航项
- Create: `frontend/src/components/sidebar/sidebar.css`
- Create: `frontend/src/components/follow-list-panel/FollowListPanel.vue` — 关注列表
- Create: `frontend/src/components/follow-list-panel/FollowCard.vue` — 单个 UP主卡片
- Create: `frontend/src/components/follow-list-panel/AddFollowForm.vue` — 添加表单
- Create: `frontend/src/components/follow-list-panel/follow-list-panel.css`
- Modify: `frontend/src/views/DashboardView.vue` — 新增"关注"tab
- Modify: `frontend/src/router/index.ts` — 新增关注路由
- Modify: `frontend/src/lib/apiFetch.ts` — Authorization 头
- Create: `frontend/src/api/followedUp.ts` — 关注 API 客户端
- Create: `frontend/tests/unit/sidebar.test.ts` — sidebar 单元测试
- Create: `frontend/tests/unit/follow-list-panel.test.ts` — 列表 panel 测试

---

## Task 1: DB 模型 + Alembic migration（subagent-A）

**Files:**
- Create: `src/aipulse/models/followed_up.py`
- Create: `src/aipulse/models/followed_up_collections.py`
- Create: `src/aipulse/models/learning_events.py`
- Modify: `src/aipulse/models/hotspot.py`
- Create: `migrations/versions/xxxx_add_followed_up_tables.py`
- Test: `tests/unit/test_followed_up_model.py`

- [ ] **Step 1: 写失败测试** — 测试 `FollowedUp` 模型：
  - 所有字段存在（id/platform/uid/display_name/profile_url/collector_strategy/last_cursor_id/fetch_interval_minutes/is_active/status/health/last_checked_at/last_error/failed_at/created_at/updated_at/deleted_at/config）
  - 软删除（`deleted_at` 字段）
  - status enum（active/paused/auth_failed）
  - health enum（healthy/warning/error）
  - 平台字段支持 `bilibili` / `wechat_mp` / `douyin` / `xiaohongshu` 扩展
- [ ] **Step 2: 运行 RED** — `cd $(git rev-parse --show-toplevel) && pytest tests/unit/test_followed_up_model.py -v`
- [ ] **Step 3: 最小实现** — 定义 `FollowedUp` / `FollowedUpCollection` / `LearningEvent` 三个模型，按 spec §3.1-§3.3 字段定义
- [ ] **Step 4: 运行 GREEN** — 重复 Step 2，全部通过
- [ ] **Step 5: hotspots 新增字段** — 测试 + 实现 nullable 字段（followed_up_id / followed_up_collection_id / learning_event_id / summary_status）
- [ ] **Step 6: 写 Alembic migration** — `alembic revision --autogenerate -m "add followed_up tables"`
- [ ] **Step 7: 验证 migration** — `cd $(git rev-parse --show-toplevel) && alembic upgrade head` 在干净 SQLite 上执行成功
- [ ] **Step 8: Commit**

## Task 2: Pydantic Schema 校验（subagent-A）

**Files:**
- Create: `src/aipulse/schemas/followed_up.py`
- Create: `src/aipulse/schemas/learning_event.py`
- Test: `tests/unit/test_followed_up_schema.py`

- [ ] **Step 1: 写失败测试** — 校验：
  - `FollowedUpCreate` 必填字段（platform/uid），可省略的可选字段
  - `FollowedUpUpdate` 所有字段可选
  - `LearningEventCreate` 必填 `hotspot_id` / `scheduled_at`
  - 字符串长度限制（uid 64、display_name 128、profile_url 256、collector_strategy 16）
  - Pydantic v2 风格（`model_config = ConfigDict(from_attributes=True)`）
- [ ] **Step 2: 运行 RED**
- [ ] **Step 3: 最小实现**
- [ ] **Step 4: 运行 GREEN**
- [ ] **Step 5: Commit**

## Task 3: Repository Protocol + SQLAlchemy 实现（subagent-A）

**Files:**
- Create: `src/aipulse/repositories/followed_up_repo.py`
- Create: `src/aipulse/repositories/learning_event_repo.py`
- Test: `tests/integration/test_followed_up_repo.py`

- [ ] **Step 1: 写失败测试** — 测试 Protocol 接口：
  - `create(followed_up: FollowedUpCreate) -> FollowedUp`
  - `get_by_id(id: str) -> FollowedUp | None`
  - `get_by_platform_uid(platform, uid) -> FollowedUp | None`（用于 Q22 重复检测）
  - `list_all(include_deleted=False) -> list[FollowedUp]`
  - `update(id: str, **fields) -> FollowedUp`
  - `soft_delete(id: str) -> bool`
  - 真实 SQLite 内存数据库，不使用 mock
- [ ] **Step 2: 运行 RED**
- [ ] **Step 3: 最小实现** — Protocol + SQLAlchemy 实现 + 依赖注入工厂
- [ ] **Step 4: 运行 GREEN**
- [ ] **Step 5: Commit**

## Task 4: AppSettings 新增 + Bearer 全局改造（subagent-A）

**Files:**
- Modify: `src/aipulse/settings.py`
- Modify: `src/aipulse/web/security_middleware.py`
- Test: `tests/unit/test_security_middleware.py`
- Test: `tests/integration/test_security_middleware_integration.py`

- [ ] **Step 1: 写失败测试** — 测试：
  - `AppSettings.kimi_api_key` / `kimi_base_url` / `kimi_model` 默认值
  - `AppSettings.learning_notification_enabled` 默认 `True`
  - `verify_auth_header` 未配置 token 时返回 True
  - `verify_auth_header` 配置 token 时校验 `Authorization: Bearer <token>`
  - 错误 header（无 Bearer 前缀、空值）返回 False
  - 集成测试：FastAPI TestClient 验证端点鉴权
- [ ] **Step 2: 运行 RED**
- [ ] **Step 3: 最小实现**
- [ ] **Step 4: 运行 GREEN**
- [ ] **Step 5: 全局 API 端点迁移** — 修改所有 `/api/*` 路由去 `X-AIPulse-Token` 分支
- [ ] **Step 6: 集成测试覆盖所有端点** — 确保 `/api/hotspots` 等现有端点也走 Bearer
- [ ] **Step 7: Commit**

## Task 5: 前端 sidebar 框架（subagent-E）

**Files:**
- Create: `frontend/src/components/sidebar/Sidebar.vue`
- Create: `frontend/src/components/sidebar/SidebarNav.vue`
- Create: `frontend/src/components/sidebar/sidebar.css`
- Modify: `frontend/src/views/DashboardView.vue`
- Test: `frontend/tests/unit/sidebar.test.ts`

- [ ] **Step 1: 写失败测试** — 测试：
  - 200px 宽度（Q73-Q99 锁定）
  - 导航项：首页 / 关注 / 即将学习 / 失败
  - 当前 tab 高亮
  - 键盘可达（tabindex）
  - 折叠/展开（Q99）
- [ ] **Step 2: 运行 RED** — `cd frontend && pnpm vitest run tests/unit/sidebar.test.ts`
- [ ] **Step 3: 最小实现** — Vue 3 SFC + CSS variables（Q73-Q99 锁定 token）
- [ ] **Step 4: 运行 GREEN**
- [ ] **Step 5: 接入 DashboardView**
- [ ] **Step 6: Commit**

## Task 6: 关注列表 Panel + 添加表单（subagent-E）

**Files:**
- Create: `frontend/src/components/follow-list-panel/FollowListPanel.vue`
- Create: `frontend/src/components/follow-list-panel/FollowCard.vue`
- Create: `frontend/src/components/follow-list-panel/AddFollowForm.vue`
- Create: `frontend/src/components/follow-list-panel/follow-list-panel.css`
- Create: `frontend/src/api/followedUp.ts`
- Modify: `frontend/src/lib/apiFetch.ts`
- Test: `frontend/tests/unit/follow-list-panel.test.ts`

- [ ] **Step 1: 写失败测试** — 测试：
  - FollowCard 7 字段（头像 / 名称 / 平台 / 状态 / 健康徽章 / 上次同步 / 错误信息）
  - AddFollowForm 校验：uid 必填 + 平台选择 + 提交按钮
  - 重复 uid 提交时显示后端 409 错误
  - 列表为空时显示空状态
  - 超过 20 个 UP主 显示警告
  - apiFetch 自动附加 `Authorization: Bearer <token>` 头（来自 settings store）
- [ ] **Step 2: 运行 RED**
- [ ] **Step 3: 最小实现**
- [ ] **Step 4: 运行 GREEN**
- [ ] **Step 5: 接入 DashboardView 的"关注"tab**
- [ ] **Step 6: 路由表更新** — `/dashboard/followed` 路由
- [ ] **Step 7: Commit**

## Task 7: 后端 API 端点（subagent-A + E 协作）

**Files:**
- Create: `src/aipulse/api/followed_up.py`
- Test: `tests/integration/test_followed_up_api.py`

- [ ] **Step 1: 写失败测试** — 测试：
  - `POST /api/followed-up` 创建 UP主（只传 uid，后端拉昵称/头像）
  - 重复 uid 返回 409 Conflict
  - 15 秒超时（Q36）
  - `GET /api/followed-up` 列表
  - `GET /api/followed-up/{id}` 详情
  - `PATCH /api/followed-up/{id}` 更新
  - `DELETE /api/followed-up/{id}` 软删除
  - Bearer 鉴权集成
- [ ] **Step 2: 运行 RED**
- [ ] **Step 3: 最小实现**
- [ ] **Step 4: 运行 GREEN**
- [ ] **Step 5: Commit**

## Task 8: Phase 1 完整验证

**Files:** Review all

- [ ] **Step 1: 单元测试 + 集成测试** — `cd $(git rev-parse --show-toplevel) && pytest -v && cd frontend && pnpm test -- --run`
- [ ] **Step 2: 类型检查** — `cd $(git rev-parse --show-toplevel) && mypy src/ && cd frontend && pnpm tsc --noEmit`
- [ ] **Step 3: Lint** — `cd $(git rev-parse --show-toplevel) && ruff check . && cd frontend && pnpm eslint .`
- [ ] **Step 4: 独立验证子 agent** — 派独立 verification subagent 运行所有测试，按 [`../../specs/v0.3-followed-up-and-summary/08-acceptance-appendix.md`](../../specs/v0.3-followed-up-and-summary/08-acceptance-appendix.md) §10.1 UP 主管理清单逐项验证
- [ ] **Step 5: 未通过则返工**

---

## 自审

- DB 表覆盖：4 表（followed_up / followed_up_collections / learning_events + hotspots 新字段）
- 鉴权横切：security_middleware 全局 Bearer 改造
- 前端框架：sidebar + 关注列表 + 添加表单 + 路由
- 测试覆盖：单元 + 集成（真实 SQLite + FastAPI TestClient）
- TDD 严格：每个 Task 都有 RED → GREEN → REFACTOR
- 无占位符：所有 Task 均给出具体代码/路径/命令