# Phase 2 — B站采集 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `run_skill(name="subagent-driven-development")` 或 `run_skill(name="executing-plans")` 来实施本计划。
>
> **对应 spec**: [`../../specs/v0.3-followed-up-and-summary/02-bilibili-collector.md`](../../specs/v0.3-followed-up-and-summary/02-bilibili-collector.md)
> **上游依赖**: Phase 1（DB schema + Bearer 鉴权）

**Goal:** 实施 B站 UP主双轨采集（UAPI + HTML）+ 字幕获取 + APScheduler 定时 + sync API。

**Architecture:**
- 策略模式 + 工厂：`BaseBilibiliUpCollector` + `BilibiliUpUapiCollector` + `BilibiliUpHtmlCollector` + `BilibiliUpCollectorFactory`
- `@register_strategy` 装饰器接入现有 `collectors/registry.py`
- APScheduler 30 分钟定时扫描
- 字幕获取：官方字幕优先 + SESSDATA 从 Obsidian Media Extended 读 + ASR 兜底

**Tech Stack:** Python 3.11+ / aiohttp / httpx / APScheduler / SQLite（hotspots）

---

## 文件结构

- Create: `src/aipulse/collectors/bilibili_up/__init__.py`
- Create: `src/aipulse/collectors/bilibili_up/base.py`
- Create: `src/aipulse/collectors/bilibili_up/uapi.py`
- Create: `src/aipulse/collectors/bilibili_up/html.py`
- Create: `src/aipulse/collectors/bilibili_up/factory.py`
- Modify: `src/aipulse/collectors/registry.py` — 新增 `@register_strategy`
- Create: `src/aipulse/collectors/bilibili_up/subtitle.py` — 字幕获取
- Create: `src/aipulse/scheduler/jobs/followed_up_scan.py`
- Modify: `src/aipulse/api/followed_up.py` — 新增 sync 端点
- Create: `tests/unit/collectors/test_bilibili_up_base.py`
- Create: `tests/unit/collectors/test_bilibili_up_uapi.py`
- Create: `tests/unit/collectors/test_bilibili_up_html.py`
- Create: `tests/unit/collectors/test_factory.py`
- Create: `tests/integration/test_followed_up_scan.py`
- Create: `tests/integration/test_subtitle.py` — 真实 B站 AI 字幕（v.douyin.com 已在 CLAUDE.md 中提到的 aisubtitle.hdslb.com）

---

## Task 1: BaseBilibiliUpCollector 抽象（subagent-B1）

**Files:**
- Create: `src/aipulse/collectors/bilibili_up/base.py`
- Create: `src/aipulse/collectors/bilibili_up/__init__.py`
- Test: `tests/unit/collectors/test_bilibili_up_base.py`

- [ ] **Step 1: 写失败测试** — `BaseBilibiliUpCollector` 抽象方法：
  - `fetch_videos(mid: str, count: int) -> list[UpVideo]`
  - `fetch_collections(mid: str) -> list[UpCollection]`
  - `validate_up_exists(mid: str) -> bool`
  - `strategy: str` 属性
  - `source_type: str = "bilibili_up"`
- [ ] **Step 2: 运行 RED**
- [ ] **Step 3: 最小实现** — 抽象基类 + UpVideo / UpCollection 数据类
- [ ] **Step 4: 运行 GREEN**
- [ ] **Step 5: Commit**

## Task 2: BilibiliUpUapiCollector（subagent-B1）

**Files:**
- Create: `src/aipulse/collectors/bilibili_up/uapi.py`
- Test: `tests/unit/collectors/test_bilibili_up_uapi.py`

- [ ] **Step 1: 写失败测试** — UAPI 线路：
  - 调用 `https://uapis.cn/api/v1/bilibili/user/videos?uid={mid}` （mock）
  - 返回 `UpVideo` 列表，包含 bvid / title / pubdate / duration
  - 增量同步：`last_cursor_id` 之前的视频跳过
  - 异常处理：uid 不存在返回空列表
- [ ] **Step 2: 运行 RED**
- [ ] **Step 3: 最小实现** — `@register_strategy("uapi")`
- [ ] **Step 4: 运行 GREEN**
- [ ] **Step 5: Commit**

## Task 3: BilibiliUpHtmlCollector（subagent-B1）

**Files:**
- Create: `src/aipulse/collectors/bilibili_up/html.py`
- Test: `tests/unit/collectors/test_bilibili_up_html.py`

- [ ] **Step 1: 写失败测试** — HTML 线路：
  - 抓取 `https://space.bilibili.com/{mid}/`
  - 解析 HTML 提取视频列表（响应式加载）
  - 反爬 header（User-Agent / Referer / Cookie）
  - 异常处理：UP主不存在 / 被封禁 / 限流
- [ ] **Step 2: 运行 RED**
- [ ] **Step 3: 最小实现** — `@register_strategy("html")`
- [ ] **Step 4: 运行 GREEN**
- [ ] **Step 5: Commit**

## Task 4: BilibiliUpCollectorFactory（subagent-B1）

**Files:**
- Create: `src/aipulse/collectors/bilibili_up/factory.py`
- Test: `tests/unit/collectors/test_factory.py`

- [ ] **Step 1: 写失败测试** — 工厂：
  - `create(strategy="uapi")` 返回 UAPI 实现
  - `create(strategy="html")` 返回 HTML 实现
  - 未知 strategy 抛 ValueError
  - 全局注册表可查询所有 strategy
- [ ] **Step 2: 运行 RED**
- [ ] **Step 3: 最小实现** — `BilibiliUpCollectorFactory.create()`
- [ ] **Step 4: 运行 GREEN**
- [ ] **Step 5: Commit**

## Task 5: registry.py 装饰器接入（subagent-B1）

**Files:**
- Modify: `src/aipulse/collectors/registry.py`

- [ ] **Step 1: 验证现有 `@register` 装饰器** — 读 `registry.py` 现有实现
- [ ] **Step 2: 新增 `@register_strategy` 或复用** — 确认 UAPI / HTML 实现都注册到全局表
- [ ] **Step 3: 写测试** — import `bilibili_up.uapi` 和 `bilibili_up.html` 后全局表包含两条记录
- [ ] **Step 4: 运行 GREEN**
- [ ] **Step 5: Commit**

## Task 6: 字幕获取完整实现（subagent-B2）

**Files:**
- Create: `src/aipulse/collectors/bilibili_up/subtitle.py`
- Test: `tests/integration/test_subtitle.py`

- [ ] **Step 1: 写失败测试** — 字幕获取 3 步：
  - Step 1：官方字幕 `https://api.bilibili.com/x/player/v2?bvid=...&cid=...`
  - Step 2：从 Obsidian Media Extended SQLite 读 SESSDATA
  - Step 3：ASR 兜底（whisper API 或可配置）
  - 集成测试：真实 B站视频（如 https://www.bilibili.com/video/BVxxxxxxxxx）拿到字幕（按 CLAUDE.md 用 `credentials: 'omit'` + `Access-Control-Allow-Origin: *`）
- [ ] **Step 2: 运行 RED**
- [ ] **Step 3: 最小实现**
- [ ] **Step 4: 运行 GREEN**
- [ ] **Step 5: Commit**

## Task 7: APScheduler 定时任务（subagent-B2）

**Files:**
- Create: `src/aipulse/scheduler/jobs/followed_up_scan.py`

- [ ] **Step 1: 写失败测试** — 定时任务：
  - 每 30 分钟扫描所有 active UP主
  - 单 UP主失败不影响其他
  - `last_checked_at` 更新
  - 增量游标：`last_cursor_id` 更新为最新视频 bvid
  - 失败入 hotspots `pending` 状态
- [ ] **Step 2: 运行 RED** — `pytest tests/integration/test_followed_up_scan.py -v`
- [ ] **Step 3: 最小实现** — `followed_up_scan_job()` 异步函数 + APScheduler 注册
- [ ] **Step 4: 运行 GREEN**
- [ ] **Step 5: Commit**

## Task 8: sync API 端点（subagent-B2）

**Files:**
- Modify: `src/aipulse/api/followed_up.py`
- Test: `tests/integration/test_sync_api.py`

- [ ] **Step 1: 写失败测试** — `POST /api/followed-up/{id}/sync`：
  - 触发单 UP主立即同步
  - 15 秒超时
  - 返回同步结果（新增视频数 / 失败原因）
  - Bearer 鉴权
- [ ] **Step 2: 运行 RED**
- [ ] **Step 3: 最小实现**
- [ ] **Step 4: 运行 GREEN**
- [ ] **Step 5: Commit**

## Task 9: UP主存在性校验端点（subagent-B2）

**Files:**
- Modify: `src/aipulse/api/followed_up.py`

- [ ] **Step 1: 写失败测试** — `POST /api/followed-up/validate`：
  - 入参 `{ platform, uid }`
  - 调用 B站 `https://api.bilibili.com/x/web-interface/card?mid={mid}`
  - 返回 `code != 0` 或 `data.user.name` 为空 → 不存在
  - 真实 B站测试：1567748478（跟李沐学 AI）应存在
- [ ] **Step 2: 运行 RED**
- [ ] **Step 3: 最小实现**
- [ ] **Step 4: 运行 GREEN**
- [ ] **Step 5: Commit**

## Task 10: Phase 2 完整验证

- [ ] **Step 1: 单元测试 + 集成测试** — `cd $(git rev-parse --show-toplevel) && pytest tests/unit/collectors tests/integration -v`
- [ ] **Step 2: 真实 B站 E2E** — 用 `1567748478` 跑 sync，验证返回真实视频数据
- [ ] **Step 3: 独立验证 subagent** — 派独立 reviewer 验证双轨稳定性（各运行 10 次，对比成功率）
- [ ] **Step 4: 未通过则返工**

---

## 自审

- 双轨覆盖：UAPI + HTML + 工厂
- 字幕覆盖：官方 + SESSDATA + ASR 3 步
- 调度覆盖：APScheduler 30min + 手动 sync
- 真实集成：必须真实 B站，不能 mock