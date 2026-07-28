# Phase 4 — 总结队列 + SSE 进度 + Summary API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `run_skill(name="subagent-driven-development")` 或 `run_skill(name="executing-plans")` 来实施本计划。
>
> **对应 spec**: [`../../specs/v0.3-followed-up-and-summary/04-summary-queue-api.md`](../../specs/v0.3-followed-up-and-summary/04-summary-queue-api.md)
> **上游依赖**: Phase 3 (Agent)

**Goal:** 实施 asyncio.Queue 单 worker + 队列上限 20 + SSE 推送三态进度 + Summary API。

**Architecture:**
- FastAPI lifespan 启动单 worker
- 队列上限 20，超出返回 429
- SSE 推送三态：黄色排队 / 蓝色进行 / 绿色完成
- `obsidian://open?path=...` 协议跳转

**Tech Stack:** Python 3.11+ / asyncio / FastAPI SSE / sse-starlette

---

## 文件结构

- Create: `src/aipulse/summarizers/agent/queue.py` — 队列 + worker
- Create: `src/aipulse/api/summaries.py` — Summary API
- Create: `src/aipulse/api/sse.py` — SSE 端点
- Create: `tests/unit/test_summary_queue.py`
- Create: `tests/integration/test_summary_api.py`

---

## Task 1: asyncio.Queue 单 worker（subagent-D）

**Files:**
- Create: `src/aipulse/summarizers/agent/queue.py`
- Test: `tests/unit/test_summary_queue.py`

- [ ] **Step 1: 写失败测试** — 队列：
  - `enqueue(hotspot_id, bvid) -> position`
  - `queue_size() -> int` 上限 20
  - `worker_loop()` 单 worker，串行处理
  - 进度状态：queued / running / completed / failed
  - 持久化：进度写入 DB 或内存 dict（subagent 选择）
- [ ] **Step 2: 运行 RED**
- [ ] **Step 3: 最小实现** — `asyncio.Queue(maxsize=20)` + worker task
- [ ] **Step 4: 运行 GREEN**
- [ ] **Step 5: Commit**

## Task 2: Summary API 端点（subagent-D）

**Files:**
- Create: `src/aipulse/api/summaries.py`
- Test: `tests/integration/test_summary_api.py`

- [ ] **Step 1: 写失败测试** — 端点：
  - `POST /api/summaries` 提交总结请求（hotspot_id）
  - 队列满返回 429
  - 立即返回 `job_id` + 当前队列位置
  - Bearer 鉴权
- [ ] **Step 2: 运行 RED**
- [ ] **Step 3: 最小实现**
- [ ] **Step 4: 运行 GREEN**
- [ ] **Step 5: Commit**

## Task 3: SSE 进度推送（subagent-D）

**Files:**
- Create: `src/aipulse/api/sse.py`

- [ ] **Step 1: 写失败测试** — SSE：
  - `GET /api/summaries/{job_id}/progress` SSE 流
  - 推送三态：`{"status": "queued"}` / `{"status": "running"}` / `{"status": "completed", "obsidian_path": "..."}`
  - 完成后关闭流
- [ ] **Step 2: 运行 RED**
- [ ] **Step 3: 最小实现** — `sse-starlette.EventSourceResponse`
- [ ] **Step 4: 运行 GREEN**
- [ ] **Step 5: Commit**

## Task 4: obsidian:// 跳转协议（subagent-D）

**Files:**
- Modify: `src/aipulse/api/summaries.py`

- [ ] **Step 1: 写失败测试** — 完成响应：
  - Summary 完成时返回 `obsidian_path`
  - 前端跳转：`obsidian://open?path={obsidian_path}`
- [ ] **Step 2: 运行 RED**
- [ ] **Step 3: 最小实现** — 返回 path
- [ ] **Step 4: 运行 GREEN**
- [ ] **Step 5: Commit**

## Task 5: FastAPI lifespan 集成（subagent-D）

**Files:**
- Modify: `src/aipulse/main.py`

- [ ] **Step 1: 启动时启动 worker** — lifespan startup
- [ ] **Step 2: 关闭时停止 worker** — lifespan shutdown
- [ ] **Step 3: 集成测试** — `pytest tests/integration/test_app_lifespan.py -v`
- [ ] **Step 4: Commit**

## Task 6: Phase 4 完整验证

- [ ] **Step 1: 单元测试 + 集成测试**
- [ ] **Step 2: 真实 Kimi API 跑一个总结** — 验证队列 + SSE + 完成响应
- [ ] **Step 3: 独立验证 subagent**
- [ ] **Step 4: 未通过则返工**

---

## 自审

- 队列上限 20 严格执行
- SSE 三态推送正确
- obsidian:// 协议完整
- 真实集成测试必须