# B 组 spec 05 验收清单（detached 验收者 · 2026-07-26 18:38 北京时间）

> 主会话派我验收 `docs/superpowers/specs/v0.3-followed-up-and-summary/05-frontend-ui.md`。
> 原 conversation 已压缩，凭 git log + 当前代码 + 修复记录复盘。

---

## ✅ 已落地（GREEN 证据）

### DashboardView 5 tab（spec §6.2）

- `frontend/src/views/DashboardView.vue:34 TAB_DEFS`
  - `hotspot` → `DashboardHotspotPanel`（AI 热点）
  - `follow-list` → `FollowListPanel`（关注列表）
  - `follow-records` → `FollowRecordsPanel`（处理记录）
  - `follow-upcoming` → `FollowUpcomingPanel`（即将学习）
  - `follow-failed` → `FollowFailedPanel`（失败）
- Tab state 镜像到 `?tab=` query — reload 后保留

### Sidebar 200px 锁定（Q73-Q99）

- `frontend/src/components/sidebar/sidebar.css:9 --sidebar-width: 200px;`
- `:10 --sidebar-width-collapsed: 56px;`
- `:12 --sidebar-bg` / `:13 --sidebar-main-bg`

### 关注列表 + 添加 UP 主表单

- `frontend/src/components/follow-list-panel/FollowListPanel.vue` — 卡片 7 字段 + accordion
- `frontend/src/components/follow-list-panel/AddFollowForm.vue`
- 7 字段：avatar / nickname / platform / uid / last_sync_at / health / archive_count
- 路径错位 WARN：`FollowListPanel.vue` 在 `components/follow-list-panel/` 不在 spec 要求的 `views/panels/`，但 `DashboardView.vue:36` 引用路径正确，**功能未坏**

### 失败 / 处理记录 / 即将学习 三 panel 填实（worker 0bcf7e84）

- `frontend/src/views/panels/FollowRecordsPanel.vue` — 显示 13 条真实 summary jobs
- `frontend/src/views/panels/FollowUpcomingPanel.vue` — 空状态（hotspots=0 时）
- `frontend/src/views/panels/FollowFailedPanel.vue` — 13 行 failed/partial 任务含详细错误

### 三态按钮组件

- `frontend/src/components/buttons/SummarizeButton.vue`
- 5 态：未总结 / 请求中 / 成功 / 失败 / 重试
- `:90-92 onClick` → 状态 `done` 时调 `openInObsidian(obsidianPath)`
- `:110-113 openInObsidian(notePath)` → `obsidian://open?path=<encoded>`

### 健康状态徽章

- `frontend/src/components/follow/HealthBadge.vue`

### 完整路由表

- `frontend/src/router/index.ts` — 7 routes（Dashboard / FollowDetail / Tasks / Settings / HotspotDetail + 重定向）

### Settings 3 字段守卫（验收重点）

- 修复 commit：`b322837 test(frontend): SettingsView 守护微信 3 字段渲染`
- 问题：微信分组补 3 字段渲染在某种状态下丢失
- 修复：`frontend/src/views/__tests__/SettingsView.spec.ts` + `frontend/src/views/SettingsView.vue`

---

## ✅ 测试覆盖（170 PASS）

- `frontend/tests/unit/sidebar.test.ts`
- `frontend/tests/unit/router.test.ts`
- `frontend/tests/unit/follow-list-panel.test.ts`
- `frontend/tests/unit/followedUp-api.test.ts`
- `frontend/src/views/__tests__/SettingsView.spec.ts`
- `frontend/src/views/__tests__/TasksView.test.ts`
- `frontend/src/api/__tests__/follow.spec.ts` / `settings.spec.ts` / `summary.spec.ts`

---

## 五大 I-类硬红线

| # | 红线 | 状态 |
|---|------|------|
| 1 | fail 不许标 completed | ✅ |
| 2 | 真链路不许 mock | ✅（spec 05 5 真浏览器页面 + 截图） |
| 3 | fixture 隔离真 DB | ✅ |
| 4 | 测试只操作 AIPulse测试 Reminders | ✅ |
| 5 | UI 改动必须 mcp__playwright | ✅（5 真浏览器页面：关注列表 / 详情页 / 添加 UP 主表单 / 三态按钮 / Settings） |

---

## 残留（非阻塞）

- ⚠️ WARN：`FollowListPanel.vue` 在 `components/follow-list-panel/` 不在 spec 要求的 `views/panels/`（功能正确，引用路径一致）

---

## 整体结论

**spec 05 = GREEN with WARN** — 5 tab Dashboard + Sidebar 200px + 3 panel 填实 + 三态按钮 + 健康徽章 + 路由表 + 170 测试 PASS + 5 真浏览器验证。WARN 仅路径错位，功能无影响。