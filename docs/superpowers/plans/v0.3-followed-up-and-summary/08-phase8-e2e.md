# Phase 8 — E2E 验证 + TDD Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `run_skill(name="subagent-driven-development")` 或 `run_skill(name="executing-plans")` 来实施本计划。本 Phase 派独立 reviewer subagent 执行。
>
> **对应 spec**: [`../../specs/v0.3-followed-up-and-summary/08-acceptance-appendix.md`](../../specs/v0.3-followed-up-and-summary/08-acceptance-appendix.md)
> **上游依赖**: 全部 Phase 1-7

**Goal:** 跑通 6 条 E2E 用户路径 + 覆盖率 ≥80% + 全栈集成测试 + 独立 reviewer 验证。

**Architecture:**
- 真实 B站 / Kimi / Obsidian 集成（无 mock）
- Playwright + pytest 跨端测试
- 覆盖率门禁：pytest-cov ≥80%
- 独立 reviewer subagent 复审全部代码

**Tech Stack:** Playwright / pytest / pytest-cov / httpx / 真实外部服务

---

## Task 1: E2E 路径 A — 添加 UP主 → 自动同步（reviewer-only）

**Files:**
- Create: `tests/e2e/test_path_a_add_followed_up.py`

- [ ] **Step 1: 写 E2E** — 完整链路：
  - 启动完整服务（FastAPI + APScheduler）
  - 通过前端添加 `1567748478`（跟李沐学 AI）
  - 触发 sync，等待 APScheduler 或手动
  - 验证 hotspots 表新增视频
- [ ] **Step 2: 运行 E2E** — 真实 B站，无 mock
- [ ] **Step 3: Commit**

## Task 2: E2E 路径 B — 手动触发总结 → 三方向归档（reviewer-only）

**Files:**
- Create: `tests/e2e/test_path_b_summary.py`

- [ ] **Step 1: 写 E2E** — 完整链路：
  - 取一个 hotspot
  - 调用 `POST /api/summaries`
  - 通过 SSE 监听进度（queued → running → completed）
  - 验证三方向：DB learning_events + Obsidian 文件 + Apple Reminders（macOS only）
- [ ] **Step 2: 运行 E2E** — 真实 Kimi + 真实 Obsidian
- [ ] **Step 3: Commit**

## Task 3: E2E 路径 C — 失败重试（reviewer-only）

**Files:**
- Create: `tests/e2e/test_path_c_failure.py`

- [ ] **Step 1: 写 E2E** — 完整链路：
  - 注入 Kimi API 失败（mock kimi endpoint 返回 500）
  - 验证失败入 tab
  - 用户点击"重试"
  - 修复后重试成功
- [ ] **Step 2: 运行 E2E**
- [ ] **Step 3: Commit**

## Task 4: E2E 路径 D — 限流（reviewer-only）

**Files:**
- Create: `tests/e2e/test_path_d_rate_limit.py`

- [ ] **Step 1: 写 E2E** — 队列上限 20：
  - 并发提交 25 个总结请求
  - 前 20 个入队，后 5 个返回 429
- [ ] **Step 2: 运行 E2E**
- [ ] **Step 3: Commit**

## Task 5: E2E 路径 E — Obsidian vault 自动扫描（reviewer-only）

**Files:**
- Create: `tests/e2e/test_path_e_vault_scan.py`

- [ ] **Step 1: 写 E2E** — vault 扫描：
  - 在 `~/Documents` 下创建临时 vault（带 `.obsidian` 目录）
  - 调用 `POST /api/settings/obsidian-vault/scan`
  - 验证候选列表包含该 vault
- [ ] **Step 2: 运行 E2E** — 真实 macOS 路径
- [ ] **Step 3: Commit**

## Task 6: E2E 路径 F — 鉴权（reviewer-only）

**Files:**
- Create: `tests/e2e/test_path_f_auth.py`

- [ ] **Step 1: 写 E2E** — Bearer 鉴权：
  - 未配置 token：所有端点可访问
  - 配置 token：必须 `Authorization: Bearer <token>`
  - 错误 token 返回 401
- [ ] **Step 2: 运行 E2E**
- [ ] **Step 3: Commit**

## Task 7: 全栈覆盖率 ≥80%（reviewer-only）

**Files:**
- Modify: `pyproject.toml` — pytest-cov 配置
- Modify: `frontend/package.json` — vitest coverage 配置

- [ ] **Step 1: 后端覆盖率** — `cd $(git rev-parse --show-toplevel) && pytest --cov=aipulse --cov-report=term-missing`，要求 ≥80%
- [ ] **Step 2: 前端覆盖率** — `cd frontend && pnpm vitest run --coverage`，要求 ≥80%
- [ ] **Step 3: 覆盖率报告** — 生成 `htmlcov/index.html` + `coverage/index.html`
- [ ] **Step 4: 未达标模块返工** — 列出覆盖率最低的 5 个模块，逐个补测试

## Task 8: 独立 reviewer 复审（reviewer-only）

- [ ] **Step 1: 全 diff 复审** — `git diff main...HEAD --stat`
- [ ] **Step 2: 调用 code-reviewer agent** — 列出 Critical/High/Medium/Low 问题
- [ ] **Step 3: 调用 security-reviewer agent** — 鉴权 / 输入校验 / SQL 注入 / XSS
- [ ] **Step 4: 调用 typescript-reviewer agent** — 前端类型 + 性能
- [ ] **Step 5: 修复所有 Critical + High**
- [ ] **Step 6: 复审确认无问题**

## Task 9: 最终验证（reviewer-only）

- [ ] **Step 1: 完整测试套件** — `cd $(git rev-parse --show-toplevel) && pytest && cd frontend && pnpm test -- --run && cd extensions/chromium && pnpm test -- --run`
- [ ] **Step 2: 类型检查** — `cd $(git rev-parse --show-toplevel) && mypy src/ && cd frontend && pnpm tsc --noEmit`
- [ ] **Step 3: Lint** — `cd $(git rev-parse --show-toplevel) && ruff check . && cd frontend && pnpm eslint .`
- [ ] **Step 4: Build** — `pnpm build` (前后端) + Tauri build
- [ ] **Step 5: 6 条 E2E 全跑** — `pytest tests/e2e -v`
- [ ] **Step 6: 提交 + 推送** — 见 CLAUDE.md git 流程

## Task 10: 验收清单签字

**Files:**
- Review: [`../../specs/v0.3-followed-up-and-summary/08-acceptance-appendix.md`](../../specs/v0.3-followed-up-and-summary/08-acceptance-appendix.md)

- [ ] **Step 1: 功能验收** — UP 主管理 + 定时采集 + Agent Pipeline + 三方向存储 + UI 布局 + 配置与鉴权 全部勾选
- [ ] **Step 2: 性能验收** — 响应时间 / 资源占用
- [ ] **Step 3: E2E 验收** — 6 条路径全跑通
- [ ] **Step 4: 测试覆盖** — 单元 + 集成 ≥80%
- [ ] **Step 5: 文档** — 更新 README + 部署文档
- [ ] **Step 6: 最终签字** — 项目可以 merge 到 main

---

## 自审

- 6 条 E2E 路径全覆盖
- 覆盖率门禁严格：≥80%
- 独立 reviewer 复审：code / security / typescript 三 agent
- 最终验收清单逐项勾选