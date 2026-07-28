# 09 — v0.3 完整测试用例（验收用）

> **来源**：v0.3 spec 全集（00–08）的可验收条目集中翻译为可执行测试用例。
> **定位**：本文件是 reviewer/QA 的「对账表」——任何 §6 UI、§10 验收清单、§3–§9 业务规则有偏差都必须在对应测试用例处失败。
> **配套执行**：
> - 前端：`vitest` 组件测试 + `@vue/test-utils` + `happy-dom`
> - 后端：`pytest`（同步 + `pytest-asyncio`）
> - E2E：`@playwright/test` 跑真实 sidecar
>
> **编写原则**（与 SPEC §10 一致）：
> 1. **每条 UI 用例必须能在浏览器里跑出 PASS/FAIL**，不能仅看 snapshot。
> 2. **每条 UI 用例必须有可视断言**（截图 + 像素对比 / `toMatchSnapshot` / DOM 选择器断言）。
> 3. **数据驱动**用真实 fixture（4 个 UP 主的中文名 / UID 与 spec §1.1 一致）。
> 4. **回归保护**：UI 视觉回归 baseline 必须包含深浅色主题。
>
> **范围**：本文件覆盖 v0.3 全部 8 个 Phase 的端到端验收，包含但不限于 §10 验收清单中所有勾选项。

---

## 0. 用例总览与编号

| 编号前缀 | 模块 | 用例数 | 来源 spec |
|---|---|---|---|
| `TC-UI-SIDEBAR-*` | Sidebar 200px 单层平铺 6 项入口 | 12 | §6.9, §10.1 UI 布局 |
| `TC-UI-DASHBOARD-*` | DashboardView 5 个 tab + ?tab= 持久化 + 懒加载 + SSE 失效 | 10 | §6.1, §6.10 |
| `TC-UI-FOLLOW-LIST-*` | FollowListPanel 关注列表 + 添加表单 + 删除二次确认 + 排序 | 18 | §6.3, §6.11, §10.1 |
| `TC-UI-FOLLOW-DETAIL-*` | FollowDetailView 详情页 + 合集 accordion + 视频分页 + 元数据 | 15 | §6.5, §6.12, §10.1 |
| `TC-UI-RECORDS-*` | FollowRecordsPanel 处理记录 tab | 6 | §6.2 |
| `TC-UI-UPCOMING-*` | FollowUpcomingPanel 即将学习 tab | 8 | §6.2, §10.1 |
| `TC-UI-FAILED-*` | FollowFailedPanel 失败 tab + 重试/跳过 | 10 | §8, §10.1 |
| `TC-UI-BTN-SUMMARIZE-*` | SummarizeButton 6 态状态机（idle/pending/queued/running/done/failed） | 14 | §6.4, §6.13, §10.1 Agent |
| `TC-UI-HEALTH-*` | HealthDot / HealthBadge 健康状态徽章 | 8 | §6.7 |
| `TC-UI-ROUTER-*` | 路由表 + ?tab= 持久化 + 鉴权 | 12 | §6.14, §10.1 鉴权 |
| `TC-UI-ADD-FORM-*` | AddFollowForm 添加 UP 主表单（粘贴 URL + 校验 + 错误提示） | 9 | §6.6, §10.1 |
| `TC-UI-TOAST-*` | 添加/删除/通知 等动作的 toast 三处反馈 | 5 | §10.1 |
| `TC-API-FOLLOWED-UP-*` | `POST/GET/PATCH/DELETE /api/followed-up*` REST 契约 | 14 | §10.1 UP 主管理 |
| `TC-API-AGENT-*` | `POST /api/agent/process` 入队 + 队列上限 20 + 429 | 8 | §10.1 Agent |
| `TC-API-SUMMARIES-*` | `POST /api/summaries` + SSE 进度端到端 | 8 | §4 |
| `TC-API-ARCHIVE-*` | `POST /api/hotspots/{id}/archive` 三方向 try/except | 9 | §10.1 三方向存储 |
| `TC-API-NOTIFY-*` | `POST /api/hotspots/{id}/notify` 通知触发 | 6 | §7 |
| `TC-API-OBSIDIAN-VAULT-*` | Obsidian vault 扫描 + 选择器 + 持久化 | 7 | §10.1 配置 |
| `TC-API-AUTH-*` | Bearer 全局鉴权 + 未配置 token 放行 | 7 | §10.1 鉴权 |
| `TC-BACKEND-AGENT-*` | Agent Pipeline（6 tool + 5min 超时 + 不自动重试） | 16 | §5, §10.1 |
| `TC-BACKEND-COLLECTOR-*` | B站双轨采集 + 增量同步 + 字幕获取 + 存在性校验 | 14 | §4, §10.1 |
| `TC-BACKEND-DATA-MODEL-*` | 4 张表 schema + Repository + soft delete | 18 | §3 |
| `TC-BACKEND-LEARNING-*` | learning_events 三方向存储 + estimated_minutes 规则 | 10 | §7.2 |
| `TC-BACKEND-FAILURE-*` | 失败入列 + 不自动重试 + 手动重试/跳过 | 12 | §8, §10.1 |
| `TC-BACKEND-KIMI-*` | Kimi `kimi_*` 配置命名 + 向后兼容 | 8 | §10.1 配置 |
| `TC-BACKEND-SCHEDULER-*` | APScheduler 30 分钟扫描 + 单 worker + 错误处理 | 6 | §4.4 |
| `TC-E2E-PATH-A-*` | E2E 路径 A：添加 UP 主 → 自动同步 | 6 | §10.3 |
| `TC-E2E-PATH-B-*` | E2E 路径 B：手动触发总结 → 三方向归档 | 7 | §10.3 |
| `TC-E2E-PATH-C-*` | E2E 路径 C：失败重试 | 5 | §10.3 |
| `TC-E2E-PATH-D-*` | E2E 路径 D：队列限流 | 4 | §10.3 |
| `TC-E2E-PATH-E-*` | E2E 路径 E：Obsidian vault 自动扫描 | 5 | §10.3 |
| `TC-E2E-PATH-F-*` | E2E 路径 F：鉴权 | 6 | §10.3 |
| `TC-PERF-*` | 性能验收（响应时间 / 资源占用 / SSE 延迟） | 10 | §10.2 |
| `TC-COVERAGE-*` | 测试覆盖率 ≥80% | 6 | §10.4 |
| **合计** | | **303** | |

> **注**：上述条数只是粗估，每条用例有 1–3 个断言（视觉/行为/数据），实际断言总数会更多（≈ 800+）。

---

## 1. 测试前置条件（Setup & Fixtures）

> 这部分不是测试本身，但所有后续用例都依赖这套前置条件。验收 agent 必须先确认它全部就绪。

### 1.1 全局 fixture（`frontend/tests/setup/` + `backend/tests/conftest.py`）

```ts
// frontend/tests/setup/follow-fixtures.ts
export const FOLLOW_FIXTURES = {
  // 与 spec §1.1 完全一致：4 个基线 UP 主
  li_mu: {
    mid: '1567748478',
    name: '跟李沐学 AI',
    avatarUrl: 'https://i0.hdslb.com/bfs/face/...',
    health: 'healthy',
    enabled: true,
    lastCheckedAgoMinutes: 10,
  },
  shuzi_heimofa: {
    mid: '1235535223',
    name: '数字黑魔法',
    avatarUrl: 'https://i0.hdslb.com/bfs/face/...',
    health: 'healthy',
    enabled: true,
    lastCheckedAgoMinutes: 12,
  },
  manxue_ai: {
    mid: '28321599',
    name: '慢学 AI',
    avatarUrl: 'https://i0.hdslb.com/bfs/face/...',
    health: 'warning',
    enabled: true,
    lastCheckedAgoMinutes: 90,
  },
  alpha_quant: {
    mid: '437555998',
    name: '阿尔法量化价格行为',
    avatarUrl: 'https://i0.hdslb.com/bfs/face/...',
    health: 'error',
    enabled: true,
    lastCheckedAgoMinutes: 5,
    lastError: 'UP 主不存在或账号已注销',
  },
}
```

### 1.2 启动检查清单

- [ ] 后端：`uv run pytest --collect-only` 能收集到所有 v0.3 测试用例
- [ ] 前端：`pnpm vitest --run --reporter=verbose` 能跑全部组件测试
- [ ] Sidecar 真启动：`uv run aipulse-server` 监听 `127.0.0.1:8765`（或当前端口）
- [ ] Playwright chromium 已安装：`pnpm playwright install chromium`
- [ ] 浏览器扩展 `.output/chromium-mv3` 已构建（Phase 7+ 才需要）

---

## 2. 前端 UI 测试用例（§6）

> **本节是用户最关心的部分**——「界面没改、布局不对」主要从这里验收。
> **每条用例**必须能在 `localhost:5173` 或 Tauri webview 里跑出可视结果。

### 2.1 Sidebar（`TC-UI-SIDEBAR-*`）

#### `TC-UI-SIDEBAR-01` Sidebar 宽度精确为 200px

- **优先级**：P0（spec §6.8 锁死）
- **前置**：`pnpm dev` 启动 frontend
- **步骤**：
  1. 打开 `/dashboard`
  2. `getComputedStyle(document.querySelector('.app-sidebar')).width`
- **断言**：
  - `width === '200px'`
  - 不是 `201px`、不是 `15%`、不是 `12rem`
- **视觉**：截图 sidebar 区域，宽度尺标注 ±1px

#### `TC-UI-SIDEBAR-02` 渲染 6 个导航项且文本与 spec §6.9 NAV_ITEMS 完全一致

- **断言**：
  - `.app-sidebar__item` 数量 === 6
  - 6 个 label 文本依次为：`AI 热点` / `来源` / `关键词` / `定时任务` / `摘要` / `系统`
  - 顺序固定，不允许 `AI 热点` 排在 `来源` 之后
- **反例（应失败）**：当前实现可能错把 `关注列表 / 处理记录 / 即将学习 / 失败` 也当 sidebar 一级入口

#### `TC-UI-SIDEBAR-03` 选中态有 3px 左色条

- **步骤**：
  1. 进入 `/dashboard`
  2. `getComputedStyle(document.querySelector('.app-sidebar__item.is-active'), '::before').width`
- **断言**：
  - `width === '3px'`
  - `background-color` 等于 `--sidebar-active-bar-color`（取 `--signal` token）

#### `TC-UI-SIDEBAR-04` 选中态字色加深（`--ink`）+ 背景填充 6% signal

- **断言**：
  - `color` 解析为 `var(--ink)`（非 `--slate`）
  - `background` 解析为 `rgba(var(--signal-rgb), 0.06)`

#### `TC-UI-SIDEBAR-05` Hover 反馈 4% ink 背景 + 150ms transition

- **步骤**：`await page.hover('.app-sidebar__item:not(.is-active)')`
- **断言**：
  - `background-color` === `rgba(27,26,23,0.04)`（约等于 `rgba(var(--ink-rgb), 0.04)`）
  - `transition-duration` === `150ms`

#### `TC-UI-SIDEBAR-06` 选中态切换「瞬时无过渡」

- **步骤**：
  1. 点 sidebar 上 `AI 热点`
  2. 点 `来源`
  3. 测量 `.app-sidebar__item.is-active` 的 transition 持续时间
- **断言**：`transition-duration` === `0s` 或不存在 transition（spec §6.9 「瞬时切换，不加过渡」）

#### `TC-UI-SIDEBAR-07` 路由 `/sources` 触发 sources 高亮（非 exact match）

- **步骤**：`router.push('/sources/123/edit')`
- **断言**：`.app-sidebar__item[href="/sources"]` 拥有 `.is-active`（spec §6.9 NAV_ITEMS 标 `exact: false`）

#### `TC-UI-SIDEBAR-08` 路由 `/dashboard` 触发 hotspot 高亮（exact match）

- **步骤**：`router.push('/dashboard')`
- **断言**：仅 `.app-sidebar__item[href="/dashboard"]` 高亮，`sources/keywords` 全部不高亮

#### `TC-UI-SIDEBAR-09` footer 文本格式严格匹配 `v{x.y.z} · N sources · {rel} 同步`

- **断言**：`document.querySelector('.app-sidebar__footer').textContent` 匹配正则 `/^v\d+\.\d+\.\d+\s·\s\d+\s+sources\s·\s.+同步$/`

#### `TC-UI-SIDEBAR-10` 路由切换瞬时（无 fade 动画）

- **断言**：在切换 router 时 sidebar 不带 `transition` 动画（点击后 16ms 内可见目标高亮）

#### `TC-UI-SIDEBAR-11` 键盘可达：Tab 顺序与视觉顺序一致

- **步骤**：按 Tab 6 次
- **断言**：每次聚焦的 sidebar item 在视觉顺序中（`AI 热点 → 来源 → ...`）

#### `TC-UI-SIDEBAR-12` :focus-visible 描边为 signal 25% inset 2px

- **断言**：`box-shadow` === `inset 0 0 0 2px rgba(var(--signal-rgb), 0.25)`

### 2.2 DashboardView 5 tab + 路由（`TC-UI-DASHBOARD-*`）

#### `TC-UI-DASHBOARD-01` 默认 tab 为 `hotspot`

- **步骤**：访问 `/dashboard` 无 `?tab=`
- **断言**：
  - `currentKey === 'hotspot'`
  - 仅 `.dashboard-tab[data-testid="dashboard-tab-hotspot"]` 有 `aria-selected="true"`
  - 渲染的是 `DashboardHotspotPanel`（非 `FollowListPanel`）

#### `TC-UI-DASHBOARD-02` `?tab=follow-list` 渲染 FollowListPanel

- **断言**：组件树含 `FollowListPanel`（实际项目可能在 `components/follow-list-panel/`，文件名以实现为准）
- **反例**：当前实现若仍指向占位 Panel，应报 FAIL

#### `TC-UI-DASHBOARD-03` `?tab=junk`（非法值）回退到 hotspot

- **断言**：无报错，`currentKey === 'hotspot'`

#### `TC-UI-DASHBOARD-04` tab 切换通过 `router.replace`（不污染历史栈）

- **断言**：连切 5 个 tab 后，浏览器后退按钮只回退到进 `/dashboard` 之前的状态

#### `TC-UI-DASHBOARD-05` tab 切换后 `?tab=` 反映当前 key

- **断言**：连点 `关注列表 → 处理记录 → 即将学习 → 失败`，地址栏依次为 `?tab=follow-list&tab=follow-records&tab=follow-upcoming&tab=follow-failed`

#### `TC-UI-DASHBOARD-06` F5 刷新后 tab 持久

- **步骤**：在 `?tab=follow-failed` 刷新
- **断言**：仍渲染 `FollowFailedPanel`

#### `TC-UI-DASHBOARD-07` 懒加载：首次切到 follow-* tab 触发 dynamic import

- **断言**：`vi.spyOn(import.meta, 'glob')` 或 `vi.fn()` 包裹 `defineAsyncComponent` 后，切到 `follow-records` 时 `import('./panels/FollowRecordsPanel.vue')` 被调用
- **反例**：当前实现若直接 static import 全部 Panel，懒加载失败

#### `TC-UI-DASHBOARD-08` SSE `hotspot.new` 触发 TanStack Query 失效

- **步骤**：mock `subscribeSse`，触发 `hotspot.new` 回调
- **断言**：
  - `queryClient.invalidateQueries({ queryKey: ['hotspots'] })` 被调用
  - `queryClient.invalidateQueries({ queryKey: ['follow-records'] })` 被调用

#### `TC-UI-DASHBOARD-09` SSE `agent.queue.updated` 触发 queue + records 失效

- **断言**：mock 触发 `agent.queue.updated` 后两个 queryKey 都被 invalidate

#### `TC-UI-DASHBOARD-10` SSE `follow.updated` 触发 follows + upcoming + failed 失效

- **断言**：mock 触发 `follow.updated` 后三个 queryKey 都被 invalidate

### 2.3 FollowListPanel（`TC-UI-FOLLOW-LIST-*`）

#### `TC-UI-FOLLOW-LIST-01` 渲染 4 个 fixture UP 主卡片

- **步骤**：`followApi.list()` 返回 4 条 fixture
- **断言**：DOM 出现 4 张 UP 主卡片，每张含 name + mid + 健康状态

#### `TC-UI-FOLLOW-LIST-02` 按 `updated_at` 倒序

- **断言**：卡片顺序与 fixture 倒序一致（最 update 在最上）

#### `TC-UI-FOLLOW-LIST-03` `health === 'error'` 强制置顶

- **断言**：即使 `alpha_quant` 是最新 update，也排在最前（与其它排序规则并列时优先）

#### `TC-UI-FOLLOW-LIST-04` `enabled === false` 卡片 opacity 0.55

- **断言**：`.up-master-card.is-disabled` 的 `opacity` 计算值 === `0.55`

#### `TC-UI-FOLLOW-LIST-05` 「➕ 添加 UP 主」按钮打开 modal

- **断言**：点击按钮后 `AddFollowForm` / `AddUpMasterModal` 渲染到 DOM

#### `TC-UI-FOLLOW-LIST-06` modal 粘贴合法 B 站 URL 后允许提交

- **步骤**：粘贴 `https://space.bilibili.com/1567748478`
- **断言**：
  - 提交按钮可点
  - 调 `POST /api/followed-up`，返回 200/201

#### `TC-UI-FOLLOW-LIST-07` modal 粘贴非 B 站 URL 拒收

- **步骤**：粘贴 `https://example.com/foo`
- **断言**：提交按钮 disabled，或弹字段错误「请粘贴 B 站主页链接」

#### `TC-UI-FOLLOW-LIST-08` modal 粘贴不存在 mid（404）显示「该 UP主不存在或账号已注销」

- **步骤**：mock 后端返回 404
- **断言**：modal 内显示 spec §6.6 的原文错误文案

#### `TC-UI-FOLLOW-LIST-09` 添加成功后三处反馈齐全

- **断言**（spec §10.1 Q27）：
  1. modal 关闭
  2. 顶部绿色 toast 出现并自动消失
  3. 新卡片插入到列表顶部

#### `TC-UI-FOLLOW-LIST-10` 删除 UP 主走二次确认 modal

- **断言**：点删除按钮 → `ConfirmModal` 出现，文案含「确定删除「{name}」？所有未处理的历史视频将一并归档为 skipped」，点确认后才发 `DELETE /api/followed-up/{uid}`

#### `TC-UI-FOLLOW-LIST-11` 加载中显示「加载中…」

- **断言**：`isLoading` 时仅渲染 `.state.state-loading` 文案

#### `TC-UI-FOLLOW-LIST-12` 加载失败显示重试按钮

- **步骤**：mock API 抛错
- **断言**：渲染 `.state.state-error` + 「重试」按钮，点击触发 `refetch()`

#### `TC-UI-FOLLOW-LIST-13` 空列表显示空状态文案

- **断言**：`sortedFollows.length === 0` 时显示「还没有关注的 UP 主。点击「添加 UP 主」开始。」

#### `TC-UI-FOLLOW-LIST-14` 列表头显示「N 个 UP 主」实时计数

- **断言**：fixture 4 条 → 渲染「4 个 UP 主」；新增后变 5

#### `TC-UI-FOLLOW-LIST-15` 启用开关切换后立即调 API 并失效缓存

- **断言**：
  - 切换开关 → `followApi.setEnabled(uid, false)` 被调用
  - 成功后 `queryClient.invalidateQueries(['follows'])`

#### `TC-UI-FOLLOW-LIST-16` 「立即同步」按钮触发 scan

- **断言**：点击 → `followApi.scanNow(uid)` 被调用，UI 显示「扫描中…」或 spinner

#### `TC-UI-FOLLOW-LIST-17` 健康状态小红点渲染（alpha_quant fixture）

- **断言**：`health === 'error'` 卡片右上角出现红色 `<HealthDot />`

#### `TC-UI-FOLLOW-LIST-18` 元数据展示：mid / 策略 / 间隔 / 上次扫描

- **断言**：每张卡片至少包含这 4 项，文案可读

### 2.4 FollowDetailView（`TC-UI-FOLLOW-DETAIL-*`）

> **当前实现是占位**（"该页面将在 Phase 2 完整实现"），本节全部用例预期 FAIL 直到 Phase 7 完成。

#### `TC-UI-FOLLOW-DETAIL-01` 头部：头像 + 昵称 + 健康徽章

- **断言**：访问 `/followed-up/{uid}`，DOM 含 `<img>` 头像（64x64）、`<h1>` 昵称、`<HealthDot>` / `<HealthBadge>`

#### `TC-UI-FOLLOW-DETAIL-02` 元数据 dl 显示 mid / URL / 策略 / 间隔 / last_checked_at / last_error

- **断言**：6 个 dt-dd 对齐全，`last_error` 不为空时显示红色 `state-error` 文字

#### `TC-UI-FOLLOW-DETAIL-03` 合集区域：`CollectionAccordion` 列表渲染

- **前置**：`detail.collections` 长度 ≥ 1
- **断言**：每个合集渲染一个 `<CollectionAccordion>` 组件（spec §6.12）

#### `TC-UI-FOLLOW-DETAIL-04` 合集点击展开视频列表

- **断言**：点 accordion header → 内部视频列表展开，aria-expanded 切换

#### `TC-UI-FOLLOW-DETAIL-05` 视频列表 `VideoListItem` 渲染最近 20 条

- **断言**：默认分页 limit=20，多出条数不渲染

#### `TC-UI-FOLLOW-DETAIL-06` 「加载更多历史」翻页

- **断言**：点按钮 → `fetchNextPage` 被调用，loading 期间按钮文案变「加载中…」，disabled

#### `TC-UI-FOLLOW-DETAIL-07` 「立即扫描」按钮调 `scanNow`

- **断言**：点击 → `followApi.scanNow(uid)` 被调用

#### `TC-UI-FOLLOW-DETAIL-08` 「暂停 / 恢复」切换启用状态

- **断言**：点击 → `followApi.setEnabled(uid, !enabled)` 被调用；按钮文案随之翻转

#### `TC-UI-FOLLOW-DETAIL-09` 「删除」走二次确认 modal，确认后跳回关注列表

- **断言**：删除成功后 `router.push('/dashboard?tab=follow-list')`

#### `TC-UI-FOLLOW-DETAIL-10` 散落视频区块：orphanVideos 列表（`variant="orphan"`）

- **断言**：未归属合集的视频单独列在「散落视频」区块，h3 含「散落视频（不在合集内，N 条）」

#### `TC-UI-FOLLOW-DETAIL-11` `useInfiniteQuery` 的 `getNextPageParam` 解析 `nextOffset`

- **断言**：mock `followApi.listVideos` 返回 `{ items, nextOffset: 20 }` → 第二次翻页传 `offset=20`

#### `TC-UI-FOLLOW-DETAIL-12` `enabled: !!uid.value` 防止空 uid 触发请求

- **断言**：`uid=''` 时 query 不发请求

#### `TC-UI-FOLLOW-DETAIL-13` `← 返回` 按钮调 `router.back()`

- **断言**：点击后退到上一页

#### `TC-UI-FOLLOW-DETAIL-14` 时间渲染：`new Date(last_checked_at).toLocaleString('zh-CN')`

- **断言**：DOM 含形如 `2026/7/25 14:32:18` 的格式

#### `TC-UI-FOLLOW-DETAIL-15` 「在 B 站打开」按钮调 `window.open(bilibili_url)`

- **断言**：`window.open` 被以 `https://www.bilibili.com/video/{bvid}` 为参数调用，target=`_blank`

### 2.5 FollowRecordsPanel / UpcomingPanel / FailedPanel（`TC-UI-RECORDS-*` / `TC-UI-UPCOMING-*` / `TC-UI-FAILED-*`）

#### `TC-UI-RECORDS-01` 渲染 `hotspots` 列表（按 `created_at` 倒序）

- **断言**：访问 `?tab=follow-records`，DOM 出现 hotspot 行；空状态显示「暂无处理记录」

#### `TC-UI-RECORDS-02` 每条记录显示视频标题 + UP 主 + 当前 decision_status

- **断言**：DOM 含 status tag：`pending` / `worth_learning` / `skipped` / `failed` / `archived`

#### `TC-UI-RECORDS-03` 行内操作按钮按 spec §6.4 表切换

- **断言矩阵**：
  - `pending` → 显示「AI 处理」+「跳过」
  - `worth_learning` → 显示「归档到 Obsidian」+「通知」
  - `skipped` → 显示「强制归档」
  - `failed` → 显示「重试」+「跳过」
  - `archived` → 显示「已归档 ✓」+「查看笔记」

#### `TC-UI-RECORDS-04` 「AI 处理」按钮点击触发 `agentApi.enqueueProcess`

- **断言**：mutationFn 入参 `{ bvid }` 被调用

#### `TC-UI-RECORDS-05` 「归档到 Obsidian」触发 `archiveApi.archive`

- **断言**：mutationFn 调用 `/api/hotspots/{id}/archive`

#### `TC-UI-RECORDS-06` 「通知」触发 `notifyApi.notify`

- **断言**：mutationFn 调用 `/api/hotspots/{id}/notify`，且 `decision_status === 'worth_learning'` 才允许点（否则 disabled）

#### `TC-UI-UPCOMING-01` 渲染 `learning_events` 列表（按 `scheduled_at` 升序）

- **断言**：DOM 含学习事件卡片：标题 + 计划时间 + 估计时长

#### `TC-UI-UPCOMING-02` 「今天 / 明天 / 本周 / 更晚」分组或时间标签可见

- **断言**：日期分隔或标签文本含上述分类

#### `TC-UI-UPCOMING-03` `estimated_minutes` 显示「N 分钟」

- **断言**：`max(15, video_duration × 2)` 在卡片上可见

#### `TC-UI-UPCOMING-04` 标记完成

- **断言**：点完成 → `learning_events.completed_at` 更新；按钮文案变「已完成 ✓」

#### `TC-UI-UPCOMING-05` Obsidian Task / Apple Reminders 创建状态徽章

- **断言**：每条显示 `obsidian_task_created` 与 `apple_reminder_id` 状态（如「✓ Obsidian / ✓ Apple / ⚠ Apple 失败」）

#### `TC-UI-UPCOMING-06` 空状态文案

- **断言**：`learning_events.length === 0` 时显示「暂无即将学习的内容」

#### `TC-UI-UPCOMING-07` `learning_status` 切换 unread / learning / mastered / review

- **断言**：4 种状态可点切换，UI 立即反映

#### `TC-UI-UPCOMING-08` 跨天事件按日期分组

- **断言**：fixture 含今天/明天/三天后的 3 条 → DOM 含 3 个分组标题

#### `TC-UI-FAILED-01` 渲染失败 hotspot 列表

- **断言**：访问 `?tab=follow-failed`，DOM 出现 `decision_status === 'failed'` 行

#### `TC-UI-FAILED-02` 每条显示失败步骤 + 错误信息

- **断言**：行内含步骤（`fetch_transcript` / `summarize` / `judge` / `archive` / `learning` / `notify`）+ 红色错误文本

#### `TC-UI-FAILED-03` 「重试」按钮重入队列

- **断言**：点击 → `agentApi.enqueueProcess({ bvid })` 或等价重试端点被调

#### `TC-UI-FAILED-04` 「跳过」按钮改为 `skipped`

- **断言**：调 `PATCH /api/hotspots/{id}` 将 `decision_status='skipped'`

#### `TC-UI-FAILED-05` 「强制决策」可手工覆盖为 `worth_learning` 或 `skipped`

- **断言**：弹出 `decision_status` 选择器，选中后写入 DB

#### `TC-UI-FAILED-06` 「重试」成功后自动从失败 tab 移除

- **断言**：mock 重试 SSE done → 该条从 DOM 消失（query 失效 + refetch）

#### `TC-UI-FAILED-07` 「跳过」成功后从失败 tab 移除

- **断言**：mutation onSuccess 后 query 失效，行消失

#### `TC-UI-FAILED-08` 失败步骤筛选

- **断言**：顶部 chip 筛选器（全部 / 字幕失败 / 总结失败 / 判断失败 / 归档失败）可点击过滤

#### `TC-UI-FAILED-09` 空状态文案

- **断言**：「没有失败项 🎉」或类似（spec 未锁文案，但必须是友好提示）

#### `TC-UI-FAILED-10` 失败项元数据：bvid / UP 主 / 时间

- **断言**：每条显示来源 UP 主 + 失败时间

### 2.6 SummarizeButton 三态按钮（`TC-UI-BTN-SUMMARIZE-*`）

> spec §6.13 锁定 6 态：idle / pending / queued / running / done / failed

#### `TC-UI-BTN-SUMMARIZE-01` 默认 `idle` 状态文案为「总结」

- **断言**：`<button>.summarize-btn--idle` 含 `总结`

#### `TC-UI-BTN-SUMMARIZE-02` 点击 → `pending` → 调 `agentApi.enqueueProcess`

- **断言**：mutationFn 被调，按钮文案 `提交中…`

#### `TC-UI-BTN-SUMMARIZE-03` 入队成功 → `queued` + 显示队列位置

- **断言**：mock 返回 `{ queue_position: 3 }` → 文案 `队列 #3`，按钮 disabled

#### `TC-UI-BTN-SUMMARIZE-04` `queued` 缺 `queue_position` 时文案「排队中…」

- **断言**：返回 `{ queue_position: null }` → 显示 `排队中…`

#### `TC-UI-BTN-SUMMARIZE-05` SSE `agent.task.{bvid}.started` 切换到 `running`

- **断言**：mock 触发后按钮 className 含 `summarize-btn--running`，文案初始为 `拉字幕…`

#### `TC-UI-BTN-SUMMARIZE-06` SSE `agent.task.{bvid}.step` 步骤文案切换

- **断言矩阵**：
  - `step='fetch_transcript'` → `拉字幕…`
  - `step='summarize'` → `总结中…`
  - `step='judge'` → `判断中…`
  - 其它 → `运行中…`

#### `TC-UI-BTN-SUMMARIZE-07` SSE `agent.task.{bvid}.done` → `done` 绿色 + 「查看总结」

- **断言**：
  - className `summarize-btn--done`
  - 文案 `查看总结`
  - 按钮变可点击
  - 图标含 `✓`

#### `TC-UI-BTN-SUMMARIZE-08` `done` 状态下点击跳转 `obsidian://open?path={obsidianPath}`

- **断言**：mock `window.location.href` setter → 写入 `obsidian://open?path={encodeURIComponent(obsidianPath)}`

#### `TC-UI-BTN-SUMMARIZE-09` SSE `agent.task.{bvid}.failed` → `failed` 红色「重试」

- **断言**：
  - className `summarize-btn--failed`
  - 文案 `重试`
  - 按钮可点击

#### `TC-UI-BTN-SUMMARIZE-10` `failed` 点击重置为 `idle` 后再次入队

- **断言**：mock mutationFn 重新调用

#### `TC-UI-BTN-SUMMARIZE-11` `running` / `queued` / `pending` 期间按钮 disabled

- **断言**：3 个状态下 `:disabled` 属性为 true，`aria-busy=true`

#### `TC-UI-BTN-SUMMARIZE-12` `errorMessage` 出现在 `title` 属性（hover tooltip）

- **断言**：`button.title === errorMessage`

#### `TC-UI-BTN-SUMMARIZE-13` SSE 订阅在 unmount 时清理

- **断言**：`onBeforeUnmount` 调用 cleanup，subscribeSse 的 unsubscribe 被触发

#### `TC-UI-BTN-SUMMARIZE-14` spinner 在 `running` 显示，reduced-motion 时停用

- **断言**：
  - `running` 状态下 DOM 含 `.summarize-spinner`
  - `@media (prefers-reduced-motion: reduce)` 下 animation: none

### 2.7 HealthDot / HealthBadge（`TC-UI-HEALTH-*`）

#### `TC-UI-HEALTH-01` 三种颜色与 spec §6.7 表一致

- **断言矩阵**：
  - `healthy` → CSS `background` === `#16a34a`（`--state-healthy`）
  - `warning` → `background` === `#d97706`（`--state-warning`）
  - `error` → `background` === `var(--signal)`（红色）

#### `TC-UI-HEALTH-02` `healthy` 计算规则

- **断言**：`last_checked_at < interval × 3` 且无 `last_error` → status='healthy'

#### `TC-UI-HEALTH-03` `warning` 计算规则

- **断言**：`interval × 3 ≤ last_checked_at < interval × 6` → status='warning'

#### `TC-UI-HEALTH-04` `error` 计算规则

- **断言**：`last_error` 不为空 或 `failed_at` 不为空 → status='error'

#### `TC-UI-HEALTH-05` fixture 中 `manxue_ai` (90 分钟前, interval=30) 显示 warning

- **断言**：fixture 触发 → badge 颜色 `#d97706`

#### `TC-UI-HEALTH-06` fixture 中 `alpha_quant` (last_error 非空) 显示 error

- **断言**：badge 颜色 === signal 红

#### `TC-UI-HEALTH-07` SSE `follow.updated` 后徽章自动重算

- **断言**：mock SSE 事件 → 徽章颜色在 200ms 内更新

#### `TC-UI-HEALTH-08` badge 内嵌 aria-label 描述当前状态

- **断言**：`aria-label === '健康' / '警告' / '错误'`

### 2.8 AddFollowForm（`TC-UI-ADD-FORM-*`）

#### `TC-UI-ADD-FORM-01` 表单含「粘贴主页 URL」输入框

- **断言**：`<input type="url">` 或等价 `<textarea>` 存在，placeholder 含 spec §6.3 文案

#### `TC-UI-ADD-FORM-02` 实时校验 URL scheme + 域名

- **断言**：
  - 非 `https://space.bilibili.com/{mid}` → 提交按钮 disabled
  - 输入框边框变红 + 错误提示「请粘贴 B 站主页链接」

#### `TC-UI-ADD-FORM-03` 提交期间按钮文案「添加中…」+ disabled

- **断言**：`isPending` 期间 button disabled + loading spinner

#### `TC-UI-ADD-FORM-04` 成功后关闭 modal + 触发 `success` 事件

- **断言**：modal 关闭事件 `onSuccess` 被调用

#### `TC-UI-ADD-FORM-05` 失败显示错误（沿用 modal 内 inline 错误，不弹 alert）

- **断言**：DOM 含 `.state-error` 块

#### `TC-UI-ADD-FORM-06` Esc 关闭 modal

- **断言**：按 Escape → modal 消失，未提交请求

#### `TC-UI-ADD-FORM-07` 点击遮罩关闭 modal

- **断言**：点击 modal 外层遮罩 → 关闭

#### `TC-UI-ADD-FORM-08` Enter 提交表单

- **断言**：输入框聚焦 + Enter → 等同点击提交

#### `TC-UI-ADD-FORM-09` 输入框 trim 空白

- **断言**：粘贴 `  https://space.bilibili.com/1567748478  ` 后等价粘贴干净 URL

### 2.9 Router（`TC-UI-ROUTER-*`）

#### `TC-UI-ROUTER-01` 路由表与 spec §6.14 一致

- **断言**：枚举 `router.getRoutes()`，路径必须包含：
  - `/` → redirect `/dashboard`
  - `/dashboard`
  - `/followed-up/:uid`
  - `/hotspot/:id`
  - `/keywords` / `/sources` / `/jobs` / `/digests` / `/settings`

#### `TC-UI-ROUTER-02` `/` 重定向到 `/dashboard`

- **断言**：访问 `/` → 地址栏变 `/dashboard`，渲染 `DashboardView`

#### `TC-UI-ROUTER-03` history 模式（spec §6.14 锁 `createWebHistory`）

- **断言**：`router.options.history` 是 `createWebHistory` 实例，不是 `createWebHashHistory`
- **反例**：当前实现使用 `createWebHashHistory`（已与 spec 偏离，验收时该条 FAIL）

#### `TC-UI-ROUTER-04` `/dashboard` 渲染 DashboardView

- **断言**：访问 `/dashboard` → DOM 含 `[data-testid="dashboard-view"]`

#### `TC-UI-ROUTER-05` `/dashboard?tab=follow-list` 渲染 FollowListPanel

#### `TC-UI-ROUTER-06` `/followed-up/:uid` props 透传 uid

- **断言**：`FollowDetailView` 的 props.uid === 路由参数 uid

#### `TC-UI-ROUTER-07` `scrollBehavior` 切页时滚到顶

- **断言**：滚到 `scrollY=1000` 后点 sidebar → scroll 回到 0

#### `TC-UI-ROUTER-08` 不存在的路径不渲染（404 fallback）

- **断言**：访问 `/nonexistent` → 不崩溃

#### `TC-UI-ROUTER-09` 路由懒加载（动态 import）

- **断言**：`router.resolve('/dashboard').matched[0].components.default` 是动态 import 包裹的组件

#### `TC-UI-ROUTER-10` 浏览器后退按钮回到上一个 tab

- **断言**：从 `?tab=follow-failed` 后退 → 回到上一个 tab 或上一个页面

#### `TC-UI-ROUTER-11` `/hotspot/:id` 渲染 HotspotDetailView

- **断言**：DOM 含热点详情（spec §10.1「归档到 Obsidian 按钮」复用）

#### `TC-UI-ROUTER-12` `/settings` 渲染 SettingsView（含 Obsidian vault 选择器）

- **断言**：DOM 含 `<button>选择 vault</button>` 入口（Q149-Q153）

### 2.10 Toast 三处反馈（`TC-UI-TOAST-*`）

#### `TC-UI-TOAST-01` 添加 UP 主成功 → 顶部 toast「已添加 {name}」

- **断言**：toast 出现 + 3s 自动消失 + ARIA `role="status"`

#### `TC-UI-TOAST-02` 删除 UP 主成功 → toast「已删除 {name}」

#### `TC-UI-TOAST-03` 归档成功 → toast「已归档到 Obsidian」

#### `TC-UI-TOAST-04` 失败 toast 持久显示直到关闭

- **断言**：失败 toast 不自动消失，含「重试」按钮

#### `TC-UI-TOAST-05` toast 队列：多条依次垂直堆叠

- **断言**：快速触发 3 条 toast → 同时显示 3 条

---

## 3. 后端 API 契约测试（`TC-API-*`）

> **接口可能有了，但用户没说明是否完整**。本节以 spec 为准穷举所有端点，确保「接口 + 行为 + 错误码」一致。

### 3.1 FollowedUp REST（`TC-API-FOLLOWED-UP-*`）

#### `TC-API-FOLLOWED-UP-01` `POST /api/followed-up` 入库新 UP 主

- **请求**：`{ url: 'https://space.bilibili.com/1567748478' }`
- **断言**：
  - 201 + 返回 `{ uid, mid, name, avatar_url, health, enabled }`
  - DB `followed_up` 表新增 1 行
  - 触发 backfill 50 条历史视频（`is_backfill=true`, `decision_status='pending'`）

#### `TC-API-FOLLOWED-UP-02` `POST /api/followed-up` 重复 uid → 409 Conflict

- **断言**：第二次提交相同 URL → 409 + body `{ error: 'ALREADY_EXISTS' }`

#### `TC-API-FOLLOWED-UP-03` `POST /api/followed-up` 不存在 mid → 400 + 文案

- **断言**：mock B 站 `card` 接口 `code != 0` → 400 + body `{ error: 'UP_NOT_FOUND', message: '该 UP主不存在或账号已注销' }`

#### `TC-API-FOLLOWED-UP-04` `POST /api/followed-up` 超过 20 个 → 422 + 警告

- **断言**：先入 20 个，再 POST 第 21 个 → 422 + 文案「已达 UP 主上限 20 个」

#### `TC-API-FOLLOWED-UP-05` `GET /api/followed-up` 列表

- **断言**：返回 `{ items: [...] }`，每项含 `uid, mid, name, avatar_url, health, enabled, last_checked_at, last_error, video_count, updated_at`

#### `TC-API-FOLLOWED-UP-06` `GET /api/followed-up/{uid}` 详情

- **断言**：返回含 `collections[]`（合集列表）+ 元数据全部字段

#### `TC-API-FOLLOWED-UP-07` `GET /api/followed-up/{uid}/videos?offset=0&limit=20` 分页

- **断言**：返回 `{ items, nextOffset }`，nextOffset 在末尾时为 `null`

#### `TC-API-FOLLOWED-UP-08` `PATCH /api/followed-up/{uid}` 更新 enabled

- **断言**：`{ enabled: false }` → 200 + `updated_at` 推进

#### `TC-API-FOLLOWED-UP-09` `PATCH /api/followed-up/{uid}` 更新 collector_strategy

- **断言**：`{ collector_strategy: 'html' }` → 200

#### `TC-API-FOLLOWED-UP-10` `PATCH /api/followed-up/{uid}` 更新 fetch_interval_minutes

- **断言**：`{ fetch_interval_minutes: 60 }` → 200

#### `TC-API-FOLLOWED-UP-11` `DELETE /api/followed-up/{uid}` 软删除

- **断言**：返回 204；DB `deleted_at` 不为空；list 接口不再返回

#### `TC-API-FOLLOWED-UP-12` 软删除后重新添加相同 mid 允许

- **断言**：删除后再 POST 同 mid → 201（不报 ALREADY_EXISTS）

#### `TC-API-FOLLOWED-UP-13` `POST /api/followed-up/{uid}/scan` 立即扫描

- **断言**：200 + 触发后台 scan，扫描完成后推送 `follow.updated` SSE

#### `TC-API-FOLLOWED-UP-14` 添加接口 15 秒超时（Q36）

- **断言**：mock B 站 API 响应慢于 15s → 返回 504 + `error: 'TIMEOUT'`

### 3.2 Agent / Summary（`TC-API-AGENT-*` / `TC-API-SUMMARIES-*`）

#### `TC-API-AGENT-01` `POST /api/agent/process` 入队

- **断言**：返回 202 + `{ task_id, queue_position }`

#### `TC-API-AGENT-02` 队列上限 20 超出 → 429

- **断言**：mock 队列已满 → 429 + `{ error: 'QUEUE_FULL', message: '队列已满' }`

#### `TC-API-AGENT-03` `task_id` 唯一且可追踪

- **断言**：返回的 task_id 通过 SSE `agent.task.{task_id}.*` 事件找到

#### `TC-API-AGENT-04` `POST /api/agent/process` 幂等性（同一 bvid 多次）

- **断言**：第二次 POST 同 bvid → 若已存在 task 则返回原 task_id + queue_position（不重复入队）

#### `TC-API-AGENT-05` 5 分钟硬超时（Q141）

- **断言**：mock agent 运行超过 5min → SSE 推送 `agent.task.{id}.failed` 含 `error: 'TIMEOUT'`

#### `TC-API-AGENT-06` 工具级独立超时（Q141）

- **断言**：mock 单个 tool > 60s → tool 抛 `ToolTimeoutError`，agent 记录失败步骤

#### `TC-API-AGENT-07` judge score < 0.6 → 不写 Obsidian / DB / Notification

- **断言**：mock judge 返回 `{ score: 0.4 }` → hotspot 仍保持 `decision_status='skipped'`，无 learning_event 创建

#### `TC-API-AGENT-08` 单 worker 串行（Q124）

- **断言**：并发提交 5 条 → `concurrency=1`（任意时刻只有 1 条 running）

#### `TC-API-SUMMARIES-01` `POST /api/summaries` 入队

- **断言**：返回 202 + `{ task_id }`

#### `TC-API-SUMMARIES-02` `GET /api/summaries/{video_id}/progress` SSE 端点

- **断言**：
  - Content-Type: `text/event-stream`
  - 三态事件：`agent.task.{id}.started` / `step` / `done` / `failed`

#### `TC-API-SUMMARIES-03` SSE 事件 data 字段为合法 JSON

- **断言**：解析 `event.data` 为 JSON 后字段齐全

#### `TC-API-SUMMARIES-04` SSE 心跳间隔 15s

- **断言**：长连接空闲时每 15s 收到 `:heartbeat` 注释行

#### `TC-API-SUMMARIES-05` SSE 断连自动清理订阅（服务端）

- **断言**：客户端断开后服务端 30s 内清理该 task 的订阅集合

#### `TC-API-SUMMARIES-06` `POST /api/summaries` 入队不阻塞（p95 < 100ms）

- **断言**：100 次请求 p95 < 100ms（性能验收 §10.2）

#### `TC-API-SUMMARIES-07` `GET /api/summaries/{video_id}/progress` 端到端延迟 < 500ms

- **断言**：从 SSE 事件触发到客户端收到消息 < 500ms

#### `TC-API-SUMMARIES-08` 总结完成写入 hotspot 表（`summary_text`, `summary_path`）

- **断言**：`decision_status='worth_learning'`、`summary_text` 非空、`obsidian_path` 非空

### 3.3 Archive 三方向存储（`TC-API-ARCHIVE-*`）

#### `TC-API-ARCHIVE-01` `POST /api/hotspots/{id}/archive` 触发三方向写入

- **断言**：返回 200 + `{ learning_event_id, obsidian_task_created, apple_reminder_id }`

#### `TC-API-ARCHIVE-02` DB `learning_events` 写入成功

- **断言**：表中新增 1 行，`scheduled_at` 默认当天 20:00

#### `TC-API-ARCHIVE-03` Obsidian 笔记末尾追加 `- [ ] ⏰ {ISO} {topic}`

- **断言**：读取目标笔记最后一行匹配正则 `^- \[ \] ⏰ \d{4}-\d{2}-\d{2}T\d{2}:\d{2}.* \{topic 截断 30 字\}$`

#### `TC-API-ARCHIVE-04` Apple Reminders 创建并回填 `apple_reminder_id`

- **断言**：`learning_events.apple_reminder_id` 不为空

#### `TC-API-ARCHIVE-05` Apple Reminders 失败不影响 DB

- **断言**：mock Apple Reminders 抛错 → DB 仍有 learning_events，`apple_reminder_id` 为空，但响应 200 + warning

#### `TC-API-ARCHIVE-06` Obsidian Task 失败仅 warning

- **断言**：mock Obsidian 写失败 → DB + Apple 仍成功；响应 warning

#### `TC-API-ARCHIVE-07` DB 写入失败 → 整体失败

- **断言**：mock DB 抛错 → 502 + `{ error: 'DB_WRITE_FAILED' }`，Obsidian / Apple 回滚

#### `TC-API-ARCHIVE-08` `estimated_minutes = max(15, video_duration × 2)`

- **断言矩阵**：
  - video_duration=5min → 15
  - video_duration=30min → 60

#### `TC-API-ARCHIVE-09` 已归档的 hotspot 重复归档 → 409

- **断言**：`decision_status='archived'` 再 POST archive → 409

### 3.4 Notify（`TC-API-NOTIFY-*`）

#### `TC-API-NOTIFY-01` `POST /api/hotspots/{id}/notify` 触发通知

- **断言**：返回 200 + `{ notified: true }`

#### `TC-API-NOTIFY-02` 仅 `worth_learning` 允许触发

- **断言矩阵**：
  - `decision_status='pending'` → 400 + 文案「请先完成总结」
  - `decision_status='worth_learning'` → 200

#### `TC-API-NOTIFY-03` `notified=false` 才允许触发

- **断言**：第二次 notify 同一 hotspot → 400 + 文案「已通知过」

#### `TC-API-NOTIFY-04` `learning_notification_enabled=false` 关闭

- **断言**：设置开关为 false → POST notify 返回 200 但实际不发送

#### `TC-API-NOTIFY-05` 触发后 `notified=true` 写入 DB

- **断言**：`hotspots.notified` 字段被更新

#### `TC-API-NOTIFY-06` 复用 `PushStrategyRegistry` 渠道

- **断言**：mock registry 收到 `{ channel: 'wechat' | 'feishu' }` 调用

### 3.5 Obsidian Vault（`TC-API-OBSIDIAN-VAULT-*`）

#### `TC-API-OBSIDIAN-VAULT-01` `GET /api/settings/obsidian-vault/candidates` 返回扫描结果

- **断言**：返回 `[{ path, mtime, contains_obsidian_dir: true }]`，至少含 macOS 标准路径 + CWD 上扫路径

#### `TC-API-OBSIDIAN-VAULT-02` 候选路径中含 `.obsidian/` 标记

- **断言**：每个 candidate 都有 `contains_obsidian_dir` 布尔字段

#### `TC-API-OBSIDIAN-VAULT-03` `POST /api/settings/obsidian-vault` 持久化路径

- **请求**：`{ path: '/Users/zab/Documents/MyVault' }`
- **断言**：返回 200；重启 sidecar 后 `OBSIDIAN_VAULT_PATH` 环境变量被持久化到 .env

#### `TC-API-OBSIDIAN-VAULT-04` 路径不存在 → 422

- **断言**：POST 一个不存在的路径 → 422 + 文案

#### `TC-API-OBSIDIAN-VAULT-05` `GET /api/settings/obsidian-vault` 返回当前值

- **断言**：返回 `{ path, mtime, contains_obsidian_dir }`

#### `TC-API-OBSIDIAN-VAULT-06` macOS 标准路径优先级最高

- **断言**：`~/Documents`、`~/Obsidian`、`~/Library/Mobile Documents/iCloud~md~obsidian` 优先于其他路径

#### `TC-API-OBSIDIAN-VAULT-07` `POST /api/settings/obsidian-vault/scan` 手动触发扫描

- **断言**：返回 200 + candidates 列表

### 3.6 鉴权（`TC-API-AUTH-*`）

#### `TC-API-AUTH-01` 未配置 token 时所有 API 放行

- **断言**：`.env` 中无 `aipulse_api_token` → 所有 API 不要求 header

#### `TC-API-AUTH-02` 配置 token 后请求必带 `Authorization: Bearer <token>`

- **断言**：`Authorization: Bearer test123` → 200；缺 header → 401

#### `TC-API-AUTH-03` `X-AIPulse-Token` 旧方式 → 401（已废弃）

- **断言**：带旧 header → 401（即使值正确）

#### `TC-API-AUTH-04` token 值错误 → 401

- **断言**：`Authorization: Bearer wrong` → 401

#### `TC-API-AUTH-05` SSE 端点同样鉴权

- **断言**：`GET /api/summaries/{id}/progress` 无 header → 401

#### `TC-API-AUTH-06` secrets 持久化保留掩码（UI 回填空值不覆盖）

- **断言**：settings UI 上 Kimi API key 留空 → PATCH 后原值保留

#### `TC-API-AUTH-07` 全局中间件一致（不是每个端点单独装饰器）

- **断言**：新增端点不写 `@requires_auth` 也应被鉴权

---

## 4. 后端业务测试（`TC-BACKEND-*`）

### 4.1 Agent Pipeline（`TC-BACKEND-AGENT-*`）

#### `TC-BACKEND-AGENT-01` LangChain `create_react_agent` 初始化成功

- **断言**：mock `kimi_*` 配置 → `agent_executor` 可创建

#### `TC-BACKEND-AGENT-02` 6 个 tool 全部注册

- **断言**：tool 列表含 `fetch_transcript` / `summarize` / `judge_tech_relevance` / `create_obsidian_note` / `create_learning_event` / `send_notification`

#### `TC-BACKEND-AGENT-03` `@tool` 装饰器可被 Agent 调用

- **断言**：mock tool → agent 调用 history 中可见 tool name

#### `TC-BACKEND-AGENT-04` system prompt 含半自动边界

- **断言**：prompt 文本含「fetch_transcript / summarize / judge 自动调用」+「create_obsidian_note / create_learning_event / send_notification 需用户手动」

#### `TC-BACKEND-AGENT-05` 半自动：fetch_transcript / summarize / judge 自动调用

- **断言**：mock agent 行为 → 3 个 tool 自动出现

#### `TC-BACKEND-AGENT-06` 半自动：obsidian / learning / notification 不自动调用

- **断言**：mock agent → 3 个 tool 不出现在自动调用记录

#### `TC-BACKEND-AGENT-07` fetch_transcript 优先 AI 字幕（Q10）

- **断言**：mock 字幕接口 → 调 `aisubtitle.hdslb.com` 优先

#### `TC-BACKEND-AGENT-08` 字幕 fallback 到本地 whisper ASR

- **断言**：mock AI 字幕 404 → 调本地 whisper

#### `TC-BACKEND-AGENT-09` 字幕完全失败 → decision_status='failed'

- **断言**：mock 所有字幕源失败 → hotspot 标 failed

#### `TC-BACKEND-AGENT-10` summarize tool 调 `VideoSummarizer`

- **断言**：mock summarizer → 收到 `text + title` 参数

#### `TC-BACKEND-AGENT-11` judge 输出 JSON 含 `score` + `reason`

- **断言**：mock judge 返回 → DB 写入 `judge_score` 字段

#### `TC-BACKEND-AGENT-12` 不自动重试（Q128+Q142）

- **断言**：连续失败 3 次后不自动重试，只入失败 tab

#### `TC-BACKEND-AGENT-13` 5min 硬超时（Q141）

- **断言**：mock agent run 超过 300s → 抛 `asyncio.TimeoutError` → hotspot 标 failed

#### `TC-BACKEND-AGENT-14` SSE 三色进度（Q126）

- **断言矩阵**：
  - `queued` → 黄色 `#d97706`
  - `running` → 蓝色 `#2563eb`
  - `done` → 绿色 `#16a34a`

#### `TC-BACKEND-AGENT-15` Kimi 模型 `kimi-for-coding`

- **断言**：`ChatOpenAI` 构造时 `model='kimi-for-coding'`

#### `TC-BACKEND-AGENT-16` LangChain temperature 0.3

- **断言**：`ChatOpenAI(temperature=0.3)`

### 4.2 B站双轨采集（`TC-BACKEND-COLLECTOR-*`）

#### `TC-BACKEND-COLLECTOR-01` `BilibiliUpCollectorFactory.create('uapi')` 返回 uapi 实例

#### `TC-BACKEND-COLLECTOR-02` `BilibiliUpCollectorFactory.create('html')` 返回 html 实例

#### `TC-BACKEND-COLLECTOR-03` 未知 strategy 抛 `ValueError`

- **断言**：`create('unknown')` → ValueError 含「unknown strategy」

#### `TC-BACKEND-COLLECTOR-04` uapi 走 uapis.cn（无需 Cookie）

- **断言**：mock HTTP → URL 含 `uapis.cn`

#### `TC-BACKEND-COLLECTOR-05` html 走 space.bilibili.com 抓取

- **断言**：mock HTTP → URL 含 `space.bilibili.com`

#### `TC-BACKEND-COLLECTOR-06` 增量同步：cursor 之后才入库（Q4+Q121）

- **断言**：第二次同步相同 mid → DB 视频数无增长（已存在跳过）

#### `TC-BACKEND-COLLECTOR-07` backfill=50 条历史视频

- **断言**：添加 UP 主后 → 该 UP 主 hotspot 数 = 50（全部 `is_backfill=true`）

#### `TC-BACKEND-COLLECTOR-08` UP 主存在性校验

- **断言**：mock `card` API 返回 `code=0, data.user.name` 非空 → 校验通过

#### `TC-BACKEND-COLLECTOR-09` UP 主不存在 → 校验失败

- **断言**：`code != 0` 或 `name=''` → 返回 False

#### `TC-BACKEND-COLLECTOR-10` 合集列表抓取

- **断言**：`fetch_collections(mid)` 返回 `[{ id, title, video_count }]`

#### `TC-BACKEND-COLLECTOR-11` `POST /api/followed-up/{id}/sync` 手动触发

- **断言**：调对应 collector + 写 DB

#### `TC-BACKEND-COLLECTOR-12` APScheduler 30 分钟触发

- **断言**：mock APScheduler → `scan_all_followed_up()` 每 30min 被调

#### `TC-BACKEND-COLLECTOR-13` UP 主被封禁：记录日志、不停用、UI 小红点

- **断言**：mock 403 → `last_error` 写入，`is_active` 不变，UI 红点显示

#### `TC-BACKEND-COLLECTOR-14` 头像磁盘缓存 + URL 变了才更新

- **断言**：连续两次同头像 URL → 第二次不发 HTTP 请求

### 4.3 数据模型（`TC-BACKEND-DATA-MODEL-*`）

#### `TC-BACKEND-DATA-MODEL-01` 4 张表迁移成功

- **断言**：`alembic upgrade head` → `followed_up` / `followed_up_collections` / `learning_events` / `hotspots` 新字段全部创建

#### `TC-BACKEND-DATA-MODEL-02` `followed_up` 字段齐全

- **断言**：表含 `id / platform / uid / display_name / profile_url / collector_strategy / last_cursor_id / fetch_interval_minutes / is_active / status / health / last_checked_at / last_error / failed_at / created_at / updated_at / deleted_at / config`

#### `TC-BACKEND-DATA-MODEL-03` `followed_up_collections` 字段齐全

#### `TC-BACKEND-DATA-MODEL-04` `learning_events` 字段齐全

#### `TC-BACKEND-DATA-MODEL-05` `hotspots` 新增 nullable 字段

- **断言**：表含 `followed_up_id` / `collection_id` / `summary_text` / `summary_path` / `judge_score` / `decision_status` / `notified`

#### `TC-BACKEND-DATA-MODEL-06` ER 关系约束

- **断言**：FK `followed_up_collections.followed_up_id` → `followed_up.id`

#### `TC-BACKEND-DATA-MODEL-07` Repository 接口齐全

- **断言**：`FollowedUpRepository` 含 `find_all / find_by_id / create / update / soft_delete / list_videos / list_collections`

#### `TC-BACKEND-DATA-MODEL-08` Pydantic Schema 校验

- **断言**：`FollowedUpCreate` schema 拒绝 `url=''` 或 `mid='abc'`

#### `TC-BACKEND-DATA-MODEL-09` soft delete 后 list 过滤

- **断言**：`deleted_at` 不为空 → `find_all` 不返回

#### `TC-BACKEND-DATA-MODEL-10` 软删除允许同名 mid 重新入

#### `TC-BACKEND-DATA-MODEL-11` `is_active=false` 暂停但保留数据

#### `TC-BACKEND-DATA-MODEL-12` 部分索引（Q107）

- **断言**：`hotspots(decision_status)` / `followed_up(is_active, deleted_at)` 含索引

#### `TC-BACKEND-DATA-MODEL-13` Repository 单元测试 30 条通过（spec §10.4）

#### `TC-BACKEND-DATA-MODEL-14` Alembic 迁移可回滚

- **断言**：`alembic downgrade -1` → 4 张表 / 字段全部移除

#### `TC-BACKEND-DATA-MODEL-15` `config` 字段存平台特定 JSON

- **断言**：插入 `{ 'bilibili': { 'sessdata': '...' } }` → 读回一致

#### `TC-BACKEND-DATA-MODEL-16` `decision_status` enum 约束

- **断言**：写入非法值（`"foo"`）→ IntegrityError

#### `TC-BACKEND-DATA-MODEL-17` `learning_status` enum 约束

- **断言**：仅 `unread / learning / mastered / review` 合法

#### `TC-BACKEND-DATA-MODEL-18` `hotspots.learning_event_id` 自引用

- **断言**：插入循环引用 → FK 约束报错

### 4.4 learning_events 三方向存储（`TC-BACKEND-LEARNING-*`）

#### `TC-BACKEND-LEARNING-01` 默认 `scheduled_at` 为当天 20:00

- **断言**：mock 当前时间 14:00 → 创建 learning_event 时 `scheduled_at = today 20:00`

#### `TC-BACKEND-LEARNING-02` `estimated_minutes = max(15, duration × 2)`

- **断言矩阵**：
  - duration=0 → 15
  - duration=10 → 20
  - duration=120 → 240

#### `TC-BACKEND-LEARNING-03` Apple Reminders 列表自动分类（Q22）

- **断言矩阵**：
  - topic 含「AI / 技术 / 编程 / 面试」 → list=`工作学习`
  - topic 含「副业 / 创业 / 变现」 → list=`搞钱！！！`
  - 其它 → list=`琐碎生活`

#### `TC-BACKEND-LEARNING-04` DB 失败 → 整体回滚

#### `TC-BACKEND-LEARNING-05` Obsidian 失败 → 仅 warning

#### `TC-BACKEND-LEARNING-06` Apple 失败 → 仅 warning

#### `TC-BACKEND-LEARNING-07` Obsidian Task 格式精确

- **断言**：`^- \[ \] ⏰ \d{4}-\d{2}-\d{2}T\d{2}:\d{2}.{topic 截断 30 字}$`

#### `TC-BACKEND-LEARNING-08` `apple_reminder_id` 回填

- **断言**：创建后 `learning_events.apple_reminder_id` 非空

#### `TC-BACKEND-LEARNING-09` `obsidian_task_created=true` 标记

- **断言**：成功路径下该字段为 true

#### `TC-BACKEND-LEARNING-10` 三方向独立 try/except 单元测试

- **断言**：分别 mock 单方向失败 → 其它方向仍成功

### 4.5 失败处理（`TC-BACKEND-FAILURE-*`）

#### `TC-BACKEND-FAILURE-01` 6 步失败均可入列

- **断言矩阵**：
  - `fetch_transcript` 失败 → hotspot `decision_status='failed'` + `failed_step='fetch_transcript'`
  - 同上其它 5 步

#### `TC-BACKEND-FAILURE-02` 不自动重试（Q128+Q142）

#### `TC-BACKEND-FAILURE-03` 失败 tab 数据源 `decision_status='failed'`

- **断言**：API 返回所有 `failed` 行

#### `TC-BACKEND-FAILURE-04` 手动重试 → 重新入队列

- **断言**：`POST /api/agent/retry/{hotspot_id}` → 重新入队

#### `TC-BACKEND-FAILURE-05` 手动跳过 → `decision_status='skipped'`

#### `TC-BACKEND-FAILURE-06` 强制决策 → 手工覆盖

#### `TC-BACKEND-FAILURE-07` 重试成功后自动从失败 tab 移除

#### `TC-BACKEND-FAILURE-08` 失败步骤筛选 chip

- **断言**：GET `/api/failed-hotspots?step=fetch_transcript` → 仅返回字幕失败

#### `TC-BACKEND-FAILURE-09` `failed_step` 字段写入

#### `TC-BACKEND-FAILURE-10` 失败时间 `failed_at` 字段写入

#### `TC-BACKEND-FAILURE-11` 失败文案分类

- **断言**：错误信息分「字幕缺失 / 总结超时 / 判断阈值过低 / 归档失败 / 提醒失败」

#### `TC-BACKEND-FAILURE-12` `failed_at` 与 `last_error` 触发 health=error

### 4.6 Kimi 配置（`TC-BACKEND-KIMI-*`）

#### `TC-BACKEND-KIMI-01` AppSettings 含 `kimi_api_key`

#### `TC-BACKEND-KIMI-02` AppSettings 含 `kimi_base_url = 'https://api.kimi.com/coding/v1'`

#### `TC-BACKEND-KIMI-03` AppSettings 含 `kimi_model = 'kimi-for-coding'`

#### `TC-BACKEND-KIMI-04` `kimi_*` 与 `llm_*` 并存向后兼容

- **断言**：`getattr(settings, 'kimi_api_key')` 优先；不存在时 fallback `llm_api_key`

#### `TC-BACKEND-KIMI-05` settings UI 显示 kimi_* 与 llm_* 两组字段

#### `TC-BACKEND-KIMI-06` `AppSettings.save()` 写 secrets 时保留掩码

- **断言**：UI 回填空字符串 → 原值不丢

#### `TC-BACKEND-KIMI-07` `learning_notification_enabled` 默认 True

#### `TC-BACKEND-KIMI-08` `learning_notification_enabled=false` 关闭所有通知

### 4.7 Scheduler（`TC-BACKEND-SCHEDULER-*`）

#### `TC-BACKEND-SCHEDULER-01` 30 分钟定时触发（Q15）

- **断言**：mock `apscheduler.add_job` → trigger='interval', minutes=30

#### `TC-BACKEND-SCHEDULER-02` 单 worker 串行

#### `TC-BACKEND-SCHEDULER-03` 扫描失败不中断后续 UP 主

- **断言**：mock 一条 UP 主抛错 → 其它 UP 主仍扫描

#### `TC-BACKEND-SCHEDULER-04` 扫描日志可查询

- **断言**：`GET /api/scheduler/logs` 返回最近 N 条日志

#### `TC-BACKEND-SCHEDULER-05` 手动 `sync_now` 与定时任务互斥

- **断言**：手动触发时跳过该 UP 主，避免重复扫描

#### `TC-BACKEND-SCHEDULER-06` 应用启动时自动注册扫描任务

---

## 5. E2E 用户路径（`TC-E2E-*`）

### 5.1 路径 A：添加 UP 主 → 自动同步（`TC-E2E-PATH-A-*`）

#### `TC-E2E-PATH-A-01` 添加合法 UP 主 → 卡片出现

- **步骤**：粘贴 `1567748478` → 提交
- **断言**：新卡片出现在关注列表顶部（spec §10.3）

#### `TC-E2E-PATH-A-02` 头像 + 昵称正确显示

#### `TC-E2E-PATH-A-03` 详情页合集列表（折叠）+ 最近 20 条视频

#### `TC-E2E-PATH-A-04` 等 30 分钟（或手动触发）→ hotspot 数 +N

#### `TC-E2E-PATH-A-05` 三处反馈齐全：modal 关闭 + toast + 新卡片插入

#### `TC-E2E-PATH-A-06` UP 主详情页 `Back` 按钮回到关注列表

### 5.2 路径 B：手动总结 → 三方向归档（`TC-E2E-PATH-B-*`）

#### `TC-E2E-PATH-B-01` 点「总结」按钮 → 黄色排队

#### `TC-E2E-PATH-B-02` SSE 推送 started → step → done 事件

#### `TC-E2E-PATH-B-03` 按钮变绿色「查看总结」+ `obsidian://open` 跳转

#### `TC-E2E-PATH-B-04` Obsidian vault 出现 `BVxxx-标题.md` 笔记

#### `TC-E2E-PATH-B-05` DB `summaries` 表新增 + `learning_events` 新增

#### `TC-E2E-PATH-B-06` Obsidian 笔记末尾追加 `- [ ] ⏰ {+24h} {topic}`

#### `TC-E2E-PATH-B-07` macOS 提醒事项出现对应 reminder

### 5.3 路径 C：失败重试（`TC-E2E-PATH-C-*`）

#### `TC-E2E-PATH-C-01` 故意改错 Kimi API key → 点「总结」

#### `TC-E2E-PATH-C-02` 按钮变红色「失败」

#### `TC-E2E-PATH-C-03` 失败 tab 出现对应记录

#### `TC-E2E-PATH-C-04` 改回正确 API key → 点「重试」→ 重新入队

#### `TC-E2E-PATH-C-05` 重试完成后从失败 tab 移除

### 5.4 路径 D：队列限流（`TC-E2E-PATH-D-*`）

#### `TC-E2E-PATH-D-01` 同时点 25 个不同视频的「总结」

#### `TC-E2E-PATH-D-02` 前 20 个返回 202 + queue_position

#### `TC-E2E-PATH-D-03` 后 5 个返回 429 + 「队列已满」

#### `TC-E2E-PATH-D-04` worker 完成后 queue 释放 → 新请求可入队

### 5.5 路径 E：Obsidian vault 自动扫描（`TC-E2E-PATH-E-*`）

#### `TC-E2E-PATH-E-01` 在 ~/Documents 建 vault（含 `.obsidian/`）

#### `TC-E2E-PATH-E-02` 重启 sidecar → `/candidates` 返回该路径

#### `TC-E2E-PATH-E-03` 前端点「选择 vault」→ 选另一目录 → POST

#### `TC-E2E-PATH-E-04` 重启后 .env 中 `OBSIDIAN_VAULT_PATH` 已更新

#### `TC-E2E-PATH-E-05` 设置页显示当前 vault 路径 + 「重新扫描」按钮

### 5.6 路径 F：鉴权（`TC-E2E-PATH-F-*`）

#### `TC-E2E-PATH-F-01` 配置 token → 重启 → 必带 Authorization

#### `TC-E2E-PATH-F-02` 不带 Authorization → 401

#### `TC-E2E-PATH-F-03` 旧 `X-AIPulse-Token` → 401（废弃）

#### `TC-E2E-PATH-F-04` token 值错误 → 401

#### `TC-E2E-PATH-F-05` 清空 token 重启 → 不校验（本地开发友好）

#### `TC-E2E-PATH-F-06` SSE 端点同样鉴权

---

## 6. 性能验收（`TC-PERF-*`）

> spec §10.2 列了 8 个性能目标，逐条写测试。

#### `TC-PERF-01` UP 主详情页首屏 < 500ms

- **步骤**：Lighthouse 测 `/followed-up/{uid}` 首屏
- **断言**：LCP < 500ms

#### `TC-PERF-02` 单次扫描 < 60s（4 个 UP 主 + backfill 50 条 × 4 = 200 条）

- **断言**：CI 计时 < 60s

#### `TC-PERF-03` Agent pipeline 单次总结 < 300s

#### `TC-PERF-04` SSE 心跳间隔 15s

- **断言**：mock 长连接 60s → 收到 4 次 `:heartbeat`

#### `TC-PERF-05` SSE 断连自动清理订阅（30s 内）

#### `TC-PERF-06` 头像磁盘缓存命中率 > 95%

- **断言**：重复请求 100 次 → 实际下载 ≤ 5 次

#### `TC-PERF-07` 队列 worker 内存占用 < 50MB

- **断言**：`psutil` 测量 worker RSS < 50MB

#### `TC-PERF-08` `/api/summaries` POST p95 < 100ms

- **断言**：locust 100 并发 → p95 < 100ms

#### `TC-PERF-09` SSE 端到端延迟 < 500ms

- **断言**：从事件触发到客户端 onmessage < 500ms

#### `TC-PERF-10` Tab 切换瞬时（< 100ms）

- **断言**：`performance.now()` 测从点击到面板渲染 < 100ms

---

## 7. 测试覆盖率（`TC-COVERAGE-*`）

#### `TC-COVERAGE-01` 后端总体覆盖率 ≥80%

- **断言**：`pytest --cov=src/aipulse --cov-fail-under=80`

#### `TC-COVERAGE-02` 前端总体覆盖率 ≥80%

- **断言**：`vitest --coverage --coverage.thresholds.lines=80`

#### `TC-COVERAGE-03` Agent 模块 100% 覆盖（spec §10.4）

- **断言**：`--cov-fail-under=100` on `summarizers/agent/`

#### `TC-COVERAGE-04` summarizers/ 100%

#### `TC-COVERAGE-05` collectors/bilibili_up/ 100%

#### `TC-COVERAGE-06` 前端 `views/panels/` + `components/follow/` ≥80%

---

## 8. 验收红线（Hard Failures）

> 这些红线**任一未通过**即视为 v0.3 不合格。验收 agent 在所有用例跑完后必须额外勾选以下清单。

### 8.1 路由硬性正确性

- [ ] **路由 history 模式**：使用 `createWebHistory`，不是 `createWebHashHistory`（当前实现 FAIL）
- [ ] **路由表 6 项 sidebar 一级入口**：AI 热点 / 来源 / 关键词 / 定时任务 / 摘要 / 系统（spec §6.9 锁定 6 项，`关注列表 / 处理记录 / 即将学习 / 失败` 是 DashboardView tab，不在 sidebar 一级）
- [ ] **`/hotspot/:id` 指向真实 HotspotDetailView**，不是占位 TasksView（当前实现 FAIL）
- [ ] **`/sources` / `/keywords` / `/jobs` / `/digests` / `/settings` 都指向各自真实 View**（当前实现全部错配到 SettingsView/TasksView）

### 8.2 DashboardView 5 tab + 路由参数

- [ ] **5 个 tab 全部实现**，不是只有 2 个（`AI 热点 / 关注列表 / 处理记录 / 即将学习 / 失败`）
- [ ] **`?tab=` 持久化 + F5 后保留**
- [ ] **SSE 订阅真实接入**（不是 mock 占位）

### 8.3 关注列表 + 详情页 + 三态按钮 + 健康徽章

- [ ] **FollowListPanel 在 `views/panels/FollowListPanel.vue`**（spec 路径），不是 `components/follow-list-panel/`
- [ ] **FollowDetailView 完整实现**（当前是占位）
- [ ] **SummarizeButton 6 态组件存在**（不是 inline 按钮）
- [ ] **HealthBadge 三色正确渲染**
- [ ] **AddFollowForm 含粘贴 URL + 校验 + 错误提示**

### 8.4 样式 token

- [ ] **`sidebar-tokens.css` 引入并应用**
- [ ] **`--sidebar-width: 200px`** 真正生效（不是 `220px` 或其它）
- [ ] **3px 左色条 + 6% 信号色背景**

### 8.5 数据契约

- [ ] **后端 API 路径与 spec §10.1 一致**：`/api/followed-up` / `/api/followed-up/{uid}/scan` / `/api/agent/process` / `/api/summaries` / `/api/hotspots/{id}/archive` / `/api/hotspots/{id}/notify` / `/api/settings/obsidian-vault`
- [ ] **Bearer 鉴权全局一致**
- [ ] **`decision_status` 5 个值**：`pending / worth_learning / skipped / failed / archived`

### 8.6 测试可执行性

- [ ] **`pnpm vitest --run` 在 frontend/ 下能跑出 ≥80% 通过**
- [ ] **`uv run pytest` 在 src/ 下能跑出 ≥80% 通过**
- [ ] **`pnpm playwright test` 在 e2e/ 下能跑出所有 6 条路径**

---

## 9. 验收执行流程（给 reviewer subagent）

```bash
# Step 1: 装依赖
pnpm install
uv sync

# Step 2: 静态检查
pnpm vue-tsc --noEmit
uv run ruff check src/
uv run mypy --strict src/aipulse/

# Step 3: 单元测试
pnpm vitest --run
uv run pytest --cov=src/aipulse --cov-report=term-missing

# Step 4: E2E（需要真实 sidecar + 真实 Obsidian vault）
pnpm playwright test e2e/specs/follow-up.spec.ts

# Step 5: 对照本文件 8.1-8.6 红线清单逐条勾选
```

### 9.1 输出格式

reviewer subagent 必须输出结构化报告：

```markdown
## v0.3 验收报告

**通过**：[N] / [Total]
**失败**：[N]
**红线**：是否触发

### 路由硬性正确性
- 路由 history 模式：✅ / ❌（细节）
- ...

### UI tab 完整性
- AI 热点 / 关注列表 / 处理记录 / 即将学习 / 失败：✅ / ❌
- ...

### 关键 FAIL 项（必须修复后再验收）
1. FollowDetailView 是占位符，未实现合集 / 视频列表
2. /hotspot/:id 指向 TasksView（错误）
3. SummarizeButton 6 态组件未实现
4. ...
```

---

## 10. 与现有实现的差异清单（给开发 agent）

> 把 spec 与当前实现直接对照，让开发 agent 一眼知道要补哪些。

| 维度 | spec 要求 | 当前实现 | 差距 | 优先级 |
|---|---|---|---|---|
| 路由 history 模式 | `createWebHistory` | `createWebHashHistory` | 需改 | P0 |
| `/hotspot/:id` | `HotspotDetailView` | `TasksView` | 需改 | P0 |
| `/sources` `/keywords` 等 | 各自 View | 全部指向 `SettingsView` | 需改 | P0 |
| FollowListPanel 路径 | `views/panels/FollowListPanel.vue` | `components/follow-list-panel/FollowListPanel.vue` | 需迁 | P1 |
| FollowDetailView | 合集 + 视频 + 元数据 + 操作 | 占位文案 | 需完整实现 | P0 |
| SummarizeButton | `components/buttons/SummarizeButton.vue` 6 态 | 不存在 | 需新建 | P0 |
| HealthBadge 三色 | healthy/warning/error | 需确认 | 需核对 | P1 |
| AddFollowForm | `components/follow/AddUpMasterModal.vue` | 已在 `follow-list-panel/AddFollowForm.vue` | 需迁 | P2 |
| Sidebar 200px 6 项 | `components/sidebar/AppSidebar.vue` | `components/sidebar/Sidebar.vue` | 需核对 | P1 |
| Sidebar 设计 token | `styles/sidebar-tokens.css` | 未确认 | 需核对 | P1 |
| 5 tab 全部实现 | hotspot / follow-list / records / upcoming / failed | 5 个文件均在 `views/panels/` | 需核对内容 | P0 |
| SSE 真实接入 | subscribeSse 4 个事件 | 需核对 | 需核对 | P1 |
| 鉴权 Bearer 全局 | middleware | 需核对 | 需核对 | P0 |
| 队列上限 20 + 429 | 实现 + 测试 | 需核对 | 需核对 | P0 |

---

**END**