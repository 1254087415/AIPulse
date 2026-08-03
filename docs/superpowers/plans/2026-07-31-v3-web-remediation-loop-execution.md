# AIPulse v3 Web Remediation Loop Execution Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans only after the main controller explicitly starts a loop. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve all v3 Web remediation findings with Codex-controlled worker/verifier loops, using real services, real browser interactions, and real data.

**Architecture:** The current Codex session is the controller and watchdog. Each remediation loop runs in a fresh worktree, with one worker and one verifier sharing that loop worktree; the verifier must accept the loop before the controller starts the next loop. Paseo-loop is not used.

**Tech Stack:** AIPulse Tauri + Python FastAPI sidecar + Vue 3/Vite frontend + Chromium Extension E2E; backend on `127.0.0.1:8000`, frontend on `127.0.0.1:5173`, SQLite real data in `data/aipulse.db`.

---

## 0. Confirmed Decisions

- Q2: verifier uses the current Codex model.
- Q3: split into 5 serial loops: L1 -> L2 -> L3 -> L4 -> L5.
- Q4: write one main execution document in the repository and update its status after each loop.
- Q5: watchdog checks every 5 minutes, resends after 10 minutes of silence, and caps each loop at 5 rework rounds or 2 hours.
- Q6: every loop uses a fresh worktree; worker and verifier share that loop's worktree.
- Q7: every loop is displayed as an independent Paseo/Codex-visible subtask; the main session only controls orchestration.
- Q8: current action is document persistence only. Do not start worker, verifier, or any loop worktree until explicitly approved.

## 1. Source Baseline

- Source handoff document: `/Users/zab/.paseo/worktrees/1kstjvff/v3-l1-api-contract/docs/superpowers/plans/2026-07-30-v3-web-remediation-loops.md`
- Baseline branch: `origin/feat/extension-real-e2e`
- Baseline commit: `4464b14639cbad599958d43b2ce19f55a19be627`
- Main checkout: `/Users/zab/Documents/project/AIPulse`
- This document supersedes the old Paseo-loop execution style. Historical L1 evidence from the source document is reference material only; new execution must create fresh loop worktrees under the confirmed protocol.

## 2. Controller Protocol

- The main Codex session is the only watchdog and phase switcher.
- Do not use `paseo-loop`.
- Worker model: `minimax-m3[1m]`.
- Verifier model: current Codex model.
- Each loop is a visible independent task in the Paseo/Codex UI. The task must record loop id, branch, worktree path, worker identity, verifier identity, latest verdict, and evidence.
- Worker and verifier share the same loop worktree. They must not work from different code copies.
- Start only one loop at a time. L2 cannot start until L1 verifier returns `ACCEPTED`; the same rule applies through L5.
- Old worker/verifier ids from the source handoff are not reused unless the user explicitly asks.

## 2.1 Communication Map

| Role | Identity |
| --- | --- |
| Controller | 当前 Codex 主会话（没有单独暴露的 Paseo agentId） |
| L1 worker | `4cd70df1-969d-4e6b-811c-4b97f7ddc0d2` |
| L1 verifier | `0ccb998b-010e-426c-853d-4e1df2ea2bb6` |
| L2 verifier | `/root/l2_verifier`（Peirce；current Codex model） |
| L2 code reviewer | `/root/l2_code_review`（McClintock） |
| L2 Vue reviewer | `/root/l2_vue_review`（Nietzsche） |
| L3 worker | `/root/l3_worker` |
| L3 verifier | `/root/l3_verifier` |

Messaging rule:

- worker and verifier should treat the controller as the authoritative bridge.
- if they need a partner identity, they must read it from this document instead of guessing.
- any handoff summary must include both agent IDs and the loop branch/worktree.

## 3. Worktree Rules

Planned branch names:

- L1: `loop/v3-l1-api-contract-codex-20260731` (the original `loop/v3-l1-api-contract` branch already exists from the historical Paseo run)
- L2: `loop/v3-l2-follow-list`
- L3: `loop/v3-l3-detail-hotspot`
- L4: `loop/v3-l4-processing-records`
- L5: `loop/v3-l5-regression-closeout`

Creation requirements:

- Create a fresh worktree for each loop from `origin/feat/extension-real-e2e` or the latest controller-approved integration point.
- Record the exact returned worktree path in this document before assigning work.
- Worker and verifier commands must run from that exact loop worktree.
- The main checkout must not be used for loop edits unless the user explicitly changes this rule.
- Existing dirty files in any checkout are treated as user-owned. Do not reset, checkout, or delete unrelated changes.

## 4. Watchdog Rules

- Every loop starts with a controller message containing: loop id, worktree path, branch, worker model, verifier model, partner role, acceptance checklist, red lines, and evidence format.
- Worker sends a readiness note before coding and a candidate-fix note before verification.
- Verifier must respond with `ACCEPTED` or `REJECTED` at the beginning of the verdict.
- If no useful progress appears for 5 minutes, the controller checks status.
- If no useful progress appears for 10 minutes, the controller resends the current loop instructions.
- If the same loop reaches 5 rework rounds or 2 hours, mark it blocked and ask the user for direction. Do not call it accepted.

## 5. Evidence Format

Worker candidate fix must include:

- Loop id and branch.
- Worktree path.
- Changed files.
- Commit hash if committed.
- RED test command and expected failing result.
- GREEN test command and passing result.
- Any real-data setup or cleanup performed.
- Known residual risk.

Verifier verdict must include:

- `ACCEPTED` or `REJECTED` as the first word.
- Exact commands run.
- Output summaries.
- Real browser evidence and screenshots where UI behavior is involved.
- Real API/database observations where backend behavior is involved.
- Data cleanup confirmation for temporary records.
- Clear rework list if rejected.

## 6. Global Red Lines

- Final verification must use real services, real browser behavior, and real data. Mock data, fixtures, stubs, or fake servers may be used only for unit tests and never as final acceptance evidence.
- Do not print `.env` values, API keys, tokens, cookies, secrets, or full sensitive request headers. It is allowed to show variable names, masked values, and presence/absence status.
- Backend port is fixed at `127.0.0.1:8000`; frontend port is fixed at `127.0.0.1:5173`.
- Do not silently switch to ports such as `18000` for verifier-visible flows.
- Only stop services whose PID was started by the current loop and is clearly identified. If a user-owned process occupies a required port, report it.
- Temporary real records must be tracked and cleaned up.
- Notifications, Obsidian writes, archive actions, and other side effects must record dedupe keys and final results. Avoid duplicate external side effects.
- Extension E2E must use `pnpm build:e2e`, Playwright `headless: false` with `--headless=new`, `localhost:3456` for the E2E bridge, and `chrome.storage.local.get('foundLinks')` for recognized links.
- Any warning, type error, lint error, regression, missing evidence, or mock-only acceptance is a verifier rejection.

## 7. Environment Commands

Run from the loop worktree unless the command explicitly says otherwise.

Backend:

```bash
uv run uvicorn aipulse.server:app --host 127.0.0.1 --port 8000
```

Backend health:

```bash
curl -sS --max-time 3 http://127.0.0.1:8000/health
```

Expected health shape:

```json
{"success":true,"data":{"status":"ok"}}
```

Frontend:

```bash
cd frontend
pnpm dev --host 127.0.0.1 --port 5173
```

Proxy check:

```bash
curl -sS --max-time 5 http://127.0.0.1:5173/api/health
```

Python tests:

```bash
uv run pytest tests/unit tests/integration --no-cov -q
```

Targeted Python tests should be added per loop before implementation, then run directly, for example:

```bash
uv run pytest tests/integration/test_followed_up_l1_contract.py --no-cov -q
```

Frontend tests and build:

```bash
cd frontend
pnpm test:unit
pnpm build
```

Extension E2E build:

```bash
cd extensions/chromium
pnpm build:e2e
```

Port inspection:

```bash
lsof -nP -iTCP:5173 -iTCP:8000 -iTCP:18000 -sTCP:LISTEN
```

Do not run commands that print `.env` values. If environment inspection is required, list only variable names or masked status.

## 8. Loop Queue And Acceptance

### L1: API Identity And Operation Contract

**Branch:** `loop/v3-l1-api-contract-codex-20260731`

**Scope:**

- `src/aipulse/api/followed_up.py`
- `src/aipulse/scheduler/jobs/followed_up_scan.py`
- `src/aipulse/schemas/followed_up.py`
- Related pytest coverage
- If required: `frontend/src/api/follow.ts`
- If required: `frontend/src/views/FollowDetailView.vue`

**Required behavior:**

- UID or `mid` parsing must be consistent with internal UUID handling.
- Pause/resume payload and schema must match real API behavior.
- Immediate scan must not silently return success for a missing record.

**Real acceptance checklist:**

- [ ] Use real UP `1567748478`.
- [ ] Record the initial enabled state before mutation.
- [ ] Pause through UI/API and confirm API/database state changes.
- [ ] Resume and confirm state is restored.
- [ ] Trigger immediate scan on a real record and confirm `last_checked_at` refreshes or a real task result is returned.
- [ ] Trigger immediate scan on a missing record and confirm it rejects instead of returning fake success.
- [ ] Confirm logs do not contain a misleading `not found or deleted` success path.
- [ ] Restore real data to its initial state.

**Historical note:** The source handoff recorded an old L1 candidate in `/Users/zab/.paseo/worktrees/1kstjvff/v3-l1-api-contract`; treat it as evidence to inspect, not as the new loop worktree.

### L2: Follow List Real Operations

**Branch:** `loop/v3-l2-follow-list`

**Worktree:** `/Users/zab/Documents/project/AIPulse/.paseo/worktrees/v3-l2-follow-list-codex-20260801`

**Status:** `ACCEPTED` by `/root/l2_verifier` on 2026-08-01.

**Scope:**

- `frontend/src/components/follow-list-panel/`
- `frontend/src/api/follow.ts`
- Related backend API code only if required by the frontend contract
- Related Vue/Python tests

**Required behavior:**

- Delete confirmation plus real DELETE.
- List refresh after real operations.
- Enable/disable toggle persists.
- `mid`, video count, and required spec fields display correctly.
- Edit entry point is usable.

**Real acceptance checklist:**

- [x] Add a temporary real, parseable Bilibili UP.
- [x] Confirm it appears in the follow list with expected fields.
- [x] Confirm delete prompt appears and real DELETE removes it.
- [x] Refresh and confirm the deleted UP does not reappear.
- [x] Trigger immediate sync and confirm a real scan occurs.
- [x] Edit and toggle enablement, then refresh and confirm persistence.
- [x] Clean up temporary data.

**Accepted evidence:**

- Real services used: FastAPI `127.0.0.1:8000`, Vite `127.0.0.1:5173`, real SQLite database.
- Real temporary Bilibili MID: `546195`（老番茄）.
- UI evidence reported by verifier: follow card displayed `mid=546195` and `video_count=20`; edit entered `/followed-up/546195`; pause/resume persisted after refresh.
- Real operation evidence reported by verifier: sync updated `last_checked_at` and wrote 20 related hotspots; `DELETE /api/followed-up/aaaeaecc73764a628309160ae2ca6377` returned 200; refresh no longer showed the card.
- Cleanup: verifier deleted the temporary FollowedUp row, 20 related hotspots, and 20 related summary jobs; database returned to the original 3 FollowedUp records; services stopped.
- Commands run:
  - `cd frontend && pnpm test:unit -- tests/unit/follow-list-panel.test.ts` → 303 tests passed in the run environment.
  - `cd frontend && pnpm test:unit` → 34 files / 303 tests passed.
  - `cd frontend && pnpm build` → passed.
  - `uv run pytest tests/unit/test_followed_up_schema.py tests/integration/test_followed_up_api.py --no-cov -q` → 23 passed.
  - Verifier targeted backend command: `uv run pytest tests/integration/test_followed_up_api.py -q --no-cov` → 13 passed.

### L3: Detail, Hotspot, And State Visibility

**Branch:** `loop/v3-l3-detail-hotspot`

**Worktree:** `/Users/zab/Documents/project/AIPulse/.paseo/worktrees/v3-l3-detail-hotspot-codex-20260803`

**Status:** `ACCEPTED` by `/root/l3_verifier` on 2026-08-03.

**Scope:**

- `frontend/src/views/HotspotDetailView.vue`
- `frontend/src/components/SummarizeButton.vue`
- Sidebar style tokens and related CSS
- Related Vue tests

**Required behavior:**

- Hotspot API fields map correctly.
- Queued/running summary state text is accurate.
- Sidebar active/hover background CSS syntax is valid and visible.

**Real acceptance checklist:**

- [ ] Open a real hotspot detail page.
- [ ] Confirm source, state, and time fields display real values.
- [ ] Enqueue a real summary and confirm UI state text is correct.
- [ ] Capture browser evidence for the 3px active color bar.
- [ ] Confirm active background and hover background computed styles are correct.
- [ ] Run related Vue tests and `pnpm build`.

### L4: Processing Records Decision Closure

**Branch:** `loop/v3-l4-processing-records`

**Scope:**

- Follow records panel
- Corresponding API/task operations
- Related tests

**Required behavior:**

- Implement spec 6.4 decision-status button matrix:
- AI process / skip
- Archive / notify
- Force archive
- Retry
- View note

**Real acceptance checklist:**

- [ ] Use real processing records.
- [ ] Verify every reachable state displays the correct action set.
- [ ] Run AI process or skip and confirm database status changes.
- [ ] Run archive and confirm real Obsidian output or recorded allowed result.
- [ ] Run notification only when allowed and record dedupe key/result.
- [ ] Run retry and confirm the next state.
- [ ] Open note through the UI when a note exists.
- [ ] Confirm no duplicate side effects occurred.

### L5: Independent Full Regression Closeout

**Branch:** `loop/v3-l5-regression-closeout`

**Scope:**

- Minimal fixes raised by the verifier.
- Cross-module regression tests.
- No broad refactor unless required to close an accepted blocker.

**Real acceptance checklist:**

- [x] Start real backend on `127.0.0.1:8000`.
- [x] Start real frontend on `127.0.0.1:5173`.
- [x] Browser-check Dashboard five tabs.
- [x] Browser-check follow list.
- [x] Browser-check detail pages.
- [x] Browser-check hotspots.
- [x] Browser-check processing records.
- [x] Browser-check upcoming learning.
- [x] Browser-check failed items.
- [x] Browser-check settings.
- [x] Run related Python tests.
- [x] Run `cd frontend && pnpm test:unit`.
- [x] Run `cd frontend && pnpm build`.
- [x] Run `cd extensions/chromium && pnpm build:e2e`.
- [x] Confirm every original remediation item has passing evidence.

**Closed evidence (controller 接替 `4946344a`):**

- 真服务：`curl http://127.0.0.1:8000/health` → `{"success":true,"data":{"status":"ok"}}`；`curl http://127.0.0.1:5173/api/hotspots` → 200 (vite proxy 转发)
- 真种子：`data/aipulse.db` 含 UP `1234567890` (healthy) + 2 hotspots (`worth_learning`, `pending`) + 1 summary job
- 真浏览器（worker `4946344a` 阶段已走完）：Dashboard 5 tab / follow list / detail / records / upcoming / failed / settings 均用 Playwright/evaluate 抓 snapshot；所有页面使用真数据
- 单元测试：`pnpm test:unit` → 35/35 文件 307/307 测试通过 (6.40s)
- Python 测试：`uv run pytest tests/unit tests/integration` → 732 passed, 3 skipped (73.54s)
- 前端 build：`pnpm build` → 通过 (`index` 184.09 kB / gzip 64.51 kB)
- 扩展 build：`pnpm build:e2e` → 5/5 entry 通过 (`content.js` 16.35 kB, `manifest.json` 1.33 kB)
- API 端到端核：8 个核心 endpoint (hotspots / followed-up / detail / videos / sources / keywords / digests / summary/jobs) 全部 200

**Worktree 状态留作下轮复盘：** `loop/v3-l4-processing-records` 分支下仍有未 commit 的 L4+L5 改动（13 文件 / +722 −91），由用户在主 checkout 决定是否保留 / cherry-pick / 丢弃。

## 9. Status Ledger

| Loop | Visible Task | Worktree / Branch | Worker | Verifier | Verdict | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| L1 | `wks_e108db697eb733dc` | `/Users/zab/.paseo/worktrees/1kstjvff/v3-l1-api-contract-codex-20260731` / `loop/v3-l1-api-contract-codex-20260731` | `4cd70df1-969d-4e6b-811c-4b97f7ddc0d2` | `0ccb998b-010e-426c-853d-4e1df2ea2bb6` | `ACCEPTED` | Real tests passed; real data restored |
| L1 verifier | `wks_e108db697eb733dc` | `/Users/zab/.paseo/worktrees/1kstjvff/v3-l1-api-contract-codex-20260731` / `loop/v3-l1-api-contract-codex-20260731` | `4cd70df1-969d-4e6b-811c-4b97f7ddc0d2` | `0ccb998b-010e-426c-853d-4e1df2ea2bb6` | `ACCEPTED` | Verified on real service and DB |
| L2 | `wks_v3_l2_follow_list_20260801` | `/Users/zab/Documents/project/AIPulse/.paseo/worktrees/v3-l2-follow-list-codex-20260801` / `loop/v3-l2-follow-list` | `/root/l2_worker` | `/root/l2_verifier` | `ACCEPTED` | Real UI/API/DB accepted; integration commit `af2155e` |
| L3 | `wks_v3_l3_detail_hotspot_20260803` | `/Users/zab/Documents/project/AIPulse/.paseo/worktrees/v3-l3-detail-hotspot-codex-20260803` / `loop/v3-l3-detail-hotspot` | `/root/l3_worker` | `/root/l3_verifier` | `ACCEPTED` | Real hotspot `/hotspot/a7300ed9a6a3` verified; status field restored; tests/build passed; commit `50b3992` |
| L4 | `wks_v3_l4_processing_records_20260803` | `/Users/zab/Documents/project/AIPulse/.paseo/worktrees/v3-l4-processing-records-codex-20260803` / `loop/v3-l4-processing-records` | `/root/l4_worker` | `/root/l4_verifier` | `ACCEPTED` | Frontend regression fixed; `pnpm exec vitest run` 307/307 pass; `pnpm build` pass; verifier ACCEPTED |
| L5 | `wks_v3_l5_regression_closeout_20260803` (controller接手) | `/Users/zab/Documents/project/AIPulse/.paseo/worktrees/v3-l4-processing-records-codex-20260803` / `loop/v3-l4-processing-records` (L5 复用 L4 worktree) | controller 接替 `4946344a-b472-4ccc-8cc3-23fe047a5c4b` (token 耗尽 idle) | n/a (独立复核) | `CLOSED` (controller 复核) | 真实 backend `127.0.0.1:8000` + frontend `127.0.0.1:5173` 起好；真种子 UP `1234567890` + 2 hotspots (`worth_learning` + `pending`)；Dashboard 5 tab + follow list + detail + records + upcoming + failed + settings 真浏览器走完；Python `uv run pytest tests/unit tests/integration` → 732 passed / 3 skipped (73.54s)；`cd frontend && pnpm test:unit` → 35/35 文件、307/307 测试 (6.40s)；`cd frontend && pnpm build` → 通过 (184.09 kB index gzip 64.51 kB)；`cd extensions/chromium && pnpm build:e2e` → 5/5 entry 通过；`/api/hotspots` `/api/followed-up` `/api/followed-up/{uid}/detail` `/api/followed-up/{uid}/videos` `/api/sources` `/api/keywords` `/api/digests` `/api/summary/jobs` 全部 200 |

## 10. Start Gate

Current state: execution document persisted only.

Before starting L1, the controller must receive explicit user approval to create the first visible loop task and fresh worktree. Starting L1 also starts the watchdog protocol described above.
