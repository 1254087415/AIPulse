# AIPulse v0.3 关注 UP 主 + AI 知识库总结 — Implementation Plan 总览

> **For agentic workers:** REQUIRED SUB-SKILL: Use `run_skill(name="subagent-driven-development")` (recommended) 或 `run_skill(name="executing-plans")` 来实施本计划。步骤使用 checkbox (`- [ ]`) 语法跟踪。
>
> **拆分依据**：模块独立 + subagent 可并行执行
> **对应 spec**：[`../../specs/v0.3-followed-up-and-summary/00-master.md`](../../specs/v0.3-followed-up-and-summary/00-master.md)

**Goal:** 实现 AIPulse v0.3 关注 UP 主跟踪 + AI 知识库总结的完整 pipeline（DB schema + B站双轨采集 + LangChain Agent + 队列 + SSE + 三方向存储 + 失败处理 + E2E）。

**Architecture:**
- **后端**：Python sidecar（FastAPI + SQLAlchemy + APScheduler + LangChain + asyncio.Queue）
- **前端**：Vue 3 + Vite + Pinia（沿用 v0.2 dashboard）
- **DB**：SQLite（本地）+ Alembic migration
- **鉴权**：Authorization: Bearer 全局（横切改造）
- **流水线**：APScheduler 定时扫描 → Collector 双轨 → Agent 半自动 → 队列单 worker → SSE 推送 → 三方向归档

**Tech Stack:**
- 后端：Python 3.11+ / FastAPI / SQLAlchemy 2.0 / Alembic / APScheduler / LangChain / langchain_openai / Pydantic v2
- 前端：Vue 3 / Vite / Pinia / TypeScript / Vitest
- 测试：pytest / Vitest / Playwright / httpx / 真实 B站 / 真实 Kimi API / 真实 Obsidian vault

---

## 文档导航（路由表）

| 子 plan | 对应 spec | Phase | 可独立 subagent | 依赖 |
|---|---|---|---|---|
| [01-phase1-foundation.md](01-phase1-foundation.md) | 01 + 05 + 07 | Phase 1 | subagent-A（DB）+ subagent-E（前端）+ subagent-G（Bearer） | 无 |
| [02-phase2-collector.md](02-phase2-collector.md) | 02 | Phase 2 | subagent-B1（Collector）+ subagent-B2（API） | 01 |
| [03-phase3-agent.md](03-phase3-agent.md) | 03 | Phase 3 | subagent-C1（框架）+ C2（tools）+ C3（prompts） | 01 + 07 |
| [04-phase4-queue.md](04-phase4-queue.md) | 04 | Phase 4 | subagent-D | 03 |
| [05-phase5-vault.md](05-phase5-vault.md) | 07 §9.4 | Phase 5 | subagent-G2 | 01 |
| [06-phase6-archive.md](06-phase6-archive.md) | 06 | Phase 6 | subagent-F | 04 |
| [07-phase7-failure.md](07-phase7-failure.md) | 06 + 05 §6.12 | Phase 7 | subagent-F2 + subagent-E2 | 04 + 05 |
| [08-phase8-e2e.md](08-phase8-e2e.md) | 08 | Phase 8 | reviewer-only | 全部 |

---

## Phase 串行图

```
[Phase 1]──→ [Phase 2]──→ [Phase 3]──→ [Phase 4]──→ [Phase 5]
   │           │           │           │           │
   ├→ A: DB    ├→ B1: Coll ├→ C1: 框架 ├→ D: 队列  ├→ G2: vault
   ├→ E: 前端  └→ B2: API  ├→ C2: tools│           │
   └→ G: Bearer              └→ C3: prompt│           │
                                          ↓           ↓
                                  [Phase 6]──→ [Phase 7]──→ [Phase 8]
                                      │           │
                                      └→ F: 归档  ├→ F2: 失败
                                                 └→ E2: 详情页
                                                          │
                                                          ↓
                                                       reviewer
```

---

## Phase 间硬约束（subagent 必读）

| 上游 | 下游 | 约束 |
|---|---|---|
| Phase 1-A DB | Phase 2-B / Phase 3-C / Phase 5-G2 | 必须产出完整 Alembic migration + Repository 接口 |
| Phase 1-G Bearer | Phase 3-C / Phase 4-D / Phase 5-G2 | `Authorization: Bearer <token>` 全局生效 |
| Phase 2-B | Phase 3-C | 双轨 Collector 接口契约 + 字幕工具路径 |
| Phase 3-C | Phase 4-D | 6 个 tool 的输入输出 JSON Schema 锁定 |
| Phase 4-D | Phase 6-F | Summary API 端点 + 三方向归档触发 |
| Phase 5-G2 | Phase 6-F | vault 路径解析必须先于 Obsidian 写入 |
| Phase 1-7 | Phase 8 | 全部上游产物必须通过单元 + 集成测试 |

---

## 全局约定（所有 subagent 必读）

1. **测试驱动**：每个 Task 必须按 RED → GREEN → REFACTOR 流程
2. **不自动重试**：失败入 tab + 手动重试/跳过（除 fetch_transcript 5 秒超时内重试 3 次外）
3. **半自动边界**：Agent pipeline 中 `fetch_transcript` / `summarize` / `judge_tech_relevance` 自动，`create_obsidian_note` / `create_learning_event` / `send_notification` 手动
4. **真实集成测试**：除单元 + 集成测试外，必须有真实 B站 / Kimi / Obsidian 的 E2E
5. **覆盖率 ≥ 80%**：单元 + 集成测试覆盖率必须达到
6. **独立验证**：每个 Phase 完成后必须派独立验证 subagent，未通过则返工

---

## 文件结构总览

```text
src-python/src/aipulse/
├── models/
│   ├── followed_up.py             # 新增
│   ├── followed_up_collections.py # 新增
│   ├── learning_events.py         # 新增
│   └── hotspot.py                 # 新增字段
├── repositories/
│   ├── followed_up_repo.py        # 新增（Protocol + SQLAlchemy 实现）
│   ├── learning_event_repo.py     # 新增
│   └── ...
├── schemas/
│   ├── followed_up.py             # 新增 Pydantic Schema
│   └── learning_event.py          # 新增
├── collectors/
│   ├── bilibili_up/               # 新增
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── uapi.py
│   │   ├── html.py
│   │   └── factory.py
│   └── registry.py                # 修改：新增 @register_strategy
├── summarizers/
│   └── agent/                     # 新增
│       ├── __init__.py
│       ├── agent.py
│       ├── tools.py
│       ├── prompts.py
│       ├── runner.py
│       ├── queue.py
│       └── obsidian.py
├── api/
│   ├── followed_up.py             # 新增
│   ├── summaries.py               # 新增
│   └── settings.py                # 新增 obsidian-vault 端点
├── web/
│   └── security_middleware.py     # 修改：Bearer 全局
├── settings.py                    # 修改：新增 kimi_* + learning_notification_enabled
└── scheduler/
    └── jobs/
        └── followed_up_scan.py    # 新增

frontend/src/
├── components/
│   ├── sidebar/                   # 新增
│   ├── follow-list-panel/         # 新增
│   ├── follow-detail-view/        # 新增
│   └── summary-button/            # 新增（三态按钮）
├── views/
│   └── DashboardView.vue          # 修改：新增"关注"tab
├── router/
│   └── index.ts                   # 修改：新增关注路由
├── api/
│   └── followedUp.ts              # 新增
├── api/
│   └── obsidianVault.ts           # 新增
└── lib/
    └── apiFetch.ts                # 修改：Authorization 头
```

---

## 验证清单

最终 Phase 8 由独立 reviewer subagent 按 [`../../specs/v0.3-followed-up-and-summary/08-acceptance-appendix.md`](../../specs/v0.3-followed-up-and-summary/08-acceptance-appendix.md) 验证。

---

## 注意事项

- **修改 Tauri 窗口尺寸陷阱**：本任务不涉及窗口尺寸改动，但 Phase 1 涉及 sidebar 宽度调整，需同步检查
- **完整打包 Python 包**：新增的 Python 文件必须包含在 `aipulse` 包内，不能只拷贝单个 .py
- **前端后端契约**：API 端点的请求/响应 schema 必须前后端同步修改