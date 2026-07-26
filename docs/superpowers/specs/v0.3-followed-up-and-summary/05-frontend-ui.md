# 05 — 前端 UI（Sidebar + 关注列表 + 详情页 + 三态按钮 + 路由）

> **来源**：原文档 §6（UI 设计）
> **上游依赖**：01 数据模型字段名（前端 API 契约）+ 03 Agent 输出格式 + 04 Summary API
> **下游交付物**：
> - DashboardView 内嵌 tab + Sidebar 200px（Q73-Q99 锁定）
> - FollowListPanel（关注列表卡片 7 字段 + accordion）
> - FollowDetailView（合集列表 + 视频列表）
> - 三态按钮组件（未总结/请求中/成功/失败/重试）
> - 添加 UP主 表单
> - 健康状态徽章
> - 路由表
> - 完整测试用例清单
>
> **subagent 边界**：本模块产出 Vue 3 组件 + 路由 + 样式 token，不产出 API 后端（API 在 02/04/06）。
> **执行模式**：Phase 1 内可与 01 数据模型并行（仅依赖 schema 字段名清单）。

---



### 6.1 DashboardView 内嵌 tab（Q6 + Q17）

```vue
<!-- DashboardView.vue -->
<template>
  <div class="dashboard">
    <nav class="tabs">
      <button :class="{ active: tab === 'dashboard' }" @click="setTab('dashboard')">AI 热点</button>
      <button :class="{ active: tab === 'follow-list' }" @click="setTab('follow-list')">关注列表</button>
      <button :class="{ active: tab === 'follow-records' }" @click="setTab('follow-records')">处理记录</button>
      <button :class="{ active: tab === 'follow-upcoming' }" @click="setTab('follow-upcoming')">即将学习</button>
      <button :class="{ active: tab === 'follow-failed' }" @click="setTab('follow-failed')">失败</button>
    </nav>
    <component :is="currentPanel" />
  </div>
</template>
```

### 6.2 Panel 组件（懒加载）

```text
web/src/views/panels/
├── DashboardHotspotPanel.vue        # 现有 AI 热点（不变）
├── FollowListPanel.vue              # 关注列表
├── FollowRecordsPanel.vue           # 处理记录
├── FollowUpcomingPanel.vue          # 即将学习
└── FollowFailedPanel.vue            # 失败
```

### 6.3 关注列表 UI（Q20）

```
┌────────────────────────────────────────────────────────┐
│ AIPulse                              [⚙] 信号正常 │
├────────────────────────────────────────────────────────┤
│ AI 热点 │ 关注列表 │ 处理记录 │ 即将学习 │ 失败 │
├────────────────────────────────────────────────────────┤
│ ╭─ 关注列表 ────────────────────────────────╮  │
│ │  ➕ 添加 UP 主  [粘贴主页 URL]           │  │
│ │  ─────────────────────────────────────  │  │
│ │  ✅ 跟李沐学 AI 🟢       mid:1567748478  │  │
│ │     uapi · 30 分钟/次 · 上次 10 分钟前   │  │
│ │     最新 BV:1x...  [详情][编辑][暂停]    │  │
│ │  ─────────────────────────────────────  │  │
│ │  ✅ 数字黑魔法 🟢         mid:1235535223  │  │
│ │  ✅ 慢学 AI 🟡            mid:28321599    │  │
│ │  ✅ 阿尔法量化价格行为 🟢 mid:437555998   │  │
│ ╰────────────────────────────────────────╯  │
│ 4 个 UP 主 · 全部启用                         │
└────────────────────────────────────────────────────────┘
```

### 6.4 行内按钮（Q14）

| `decision_status` | 主按钮 | 次按钮 |
|---|---|---|
| `pending` | "AI 处理" | "跳过" |
| `worth_learning` | "归档到 Obsidian" | "通知" / "..." |
| `skipped` | "强制归档" | "..." |
| `failed` | "重试" | "跳过" / "..." |
| `archived` | "已归档 ✓" | "查看笔记" |

### 6.5 UP主详情页（Q20）

- **头部卡片**：头像 + 昵称 + 状态徽章
- **元数据**：mid / URL / 策略 / 间隔 / last_checked_at / last_error
- **合集区块**：`followed_up_collections` 列表（点击展开视频）
- **视频区块**：最近 20 条视频，每条带 hotspot 状态
- **操作**：编辑 / 暂停 / 删除 / 立即扫描 / 加载更多历史

### 6.6 添加流程（Q18）

1. 用户粘贴 `https://space.bilibili.com/{mid}?...`
2. 后端解析 mid → 调存在性校验
3. 不存在 → 弹错误"该 UP主不存在或账号已注销"
4. 存在 → 自动创建 UP主 + backfill 50 条历史视频（`is_backfill=true`，`decision_status="pending"`）
5. 默认配置：strategy=uapi / interval=30 / backfill=50

### 6.7 健康状态徽章（Q20）

| 颜色 | 含义 |
|---|---|
| 🟢 healthy | `last_checked_at < interval × 3` 且无错误 |
| 🟡 warning | `last_checked_at < interval × 6` 或扫描频次低于期望 |
| 🔴 error | `last_error` 不为空 或 `failed_at` 不为空 |

### 6.8 Sidebar 设计 token（Q73-Q99）

完整 CSS 设计 token 写入 `web/src/styles/sidebar-tokens.css`，并由 `main.ts` 引入：

```css
:root {
  /* sidebar 框架 */
  --sidebar-width: 200px;
  --sidebar-bg: var(--paper);          /* 与卡片同色，浮于心电图网格之上 */
  --sidebar-main-bg: var(--paper);     /* 主区域背景；与 sidebar 一致 */
  --sidebar-item-height: 36px;
  --sidebar-item-gap: 4px;
  --sidebar-item-padding-x: 16px;
  --sidebar-item-padding-y: 8px;
  --sidebar-item-radius: 4px;

  /* 选中态：左色条 + 字色加深 + 背景填充 */
  --sidebar-active-bar-width: 3px;
  --sidebar-active-bar-color: var(--signal);
  --sidebar-active-text-color: var(--ink);
  --sidebar-active-bg: rgba(var(--signal-rgb), 0.06);

  /* hover 反馈 */
  --sidebar-hover-bg: rgba(var(--ink-rgb), 0.04);
  --sidebar-transition: 150ms ease-out;

  /* icon / 文字 */
  --sidebar-icon-size: 18px;
  --sidebar-icon-stroke: 1.5;
  --sidebar-text-size: 14px;
  --sidebar-text-weight: 400;

  /* 底部版本信息 */
  --sidebar-bottom-text-size: 11px;
  --sidebar-bottom-text-color: var(--slate);

  /* 顶部 tab（在主区域上方） */
  --tab-padding-y: 16px;
  --tab-underline-color: var(--signal);
  --tab-active-text-color: var(--ink);
  --tab-inactive-text-color: var(--slate);

  /* 状态色（用于卡片小红点 / 启用徽章 / 三态按钮） */
  --state-healthy: #16a34a;
  --state-warning: #d97706;
  --state-error: var(--signal);
  --state-queued: #d97706;
  --state-running: #2563eb;
  --state-done: #16a34a;
}
```

### 6.9 Sidebar 组件（Q73-Q99 锁定）

文件：`web/src/components/sidebar/AppSidebar.vue`

```vue
<script setup lang="ts">
/**
 * AppSidebar — 单层平铺 6 项入口（Q73-Q99）
 *
 * 路由与 6 项入口：
 *  1. AI 热点    -> /dashboard
 *  2. 来源       -> /sources
 *  3. 关键词     -> /keywords
 *  4. 定时任务   -> /jobs
 *  5. 摘要       -> /digests
 *  6. 系统       -> /settings
 *
 * 选中态：左色条 3px + 字色加深 + 背景色从色条右侧填充
 * hover：背景色微变 4% + 字色加深，150ms 过渡
 * 瞬时更新选中态（无过渡）
 */
import { useRoute, useRouter } from 'vue-router'
import {
  Flame, Database, Tag, Clock, FileText, Settings,
} from 'lucide-vue-next'
import { computed } from 'vue'

interface NavItem {
  key: string
  label: string
  emoji: string
  icon: typeof Flame
  to: string
  /** 完全匹配路径生效 */
  exact: boolean
}

const NAV_ITEMS: NavItem[] = [
  { key: 'hotspot',   label: 'AI 热点',  emoji: '🔥', icon: Flame,     to: '/dashboard', exact: true  },
  { key: 'sources',   label: '来源',     emoji: '🗄', icon: Database,  to: '/sources',   exact: false },
  { key: 'keywords',  label: '关键词',   emoji: '🏷', icon: Tag,       to: '/keywords',  exact: false },
  { key: 'jobs',      label: '定时任务', emoji: '⏰', icon: Clock,     to: '/jobs',      exact: false },
  { key: 'digests',   label: '摘要',     emoji: '📄', icon: FileText,  to: '/digests',   exact: false },
  { key: 'settings',  label: '系统',     emoji: '⚙',  icon: Settings,  to: '/settings',  exact: false },
]

const route = useRoute()
const router = useRouter()

const isActive = (item: NavItem): boolean => {
  if (item.exact) return route.path === item.to
  return route.path.startsWith(item.to)
}

const footerInfo = computed(() => ({
  version: 'v0.2.0',
  sourceCount: 4,
  lastSync: '2 分钟前',
}))

const onItemClick = (item: NavItem) => {
  // 瞬时切换，不加过渡
  router.push(item.to)
}
</script>

<template>
  <aside class="app-sidebar" aria-label="主导航">
    <nav class="app-sidebar__nav" role="navigation">
      <ul class="app-sidebar__list">
        <li
          v-for="item in NAV_ITEMS"
          :key="item.key"
          class="app-sidebar__item-wrap"
        >
          <router-link
            :to="item.to"
            :class="[
              'app-sidebar__item',
              { 'is-active': isActive(item) },
            ]"
            @click="onItemClick(item)"
          >
            <component
              :is="item.icon"
              :size="18"
              :stroke-width="1.5"
              class="app-sidebar__icon"
              aria-hidden="true"
            />
            <span class="app-sidebar__label">{{ item.label }}</span>
          </router-link>
        </li>
      </ul>
    </nav>

    <div class="app-sidebar__footer" aria-label="版本信息">
      {{ footerInfo.version }} · {{ footerInfo.sourceCount }} sources · {{ footerInfo.lastSync }} 同步
    </div>
  </aside>
</template>

<style scoped>
.app-sidebar {
  width: var(--sidebar-width);
  height: 100vh;
  position: sticky;
  top: 0;
  background: var(--sidebar-bg);
  border-right: 1px solid var(--mist);
  display: flex;
  flex-direction: column;
  padding: 16px 0;
  /* 浮于心电图网格之上；与主区域同色，避免割裂感 */
}

.app-sidebar__nav {
  flex: 1;
  overflow-y: auto;
}

.app-sidebar__list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: var(--sidebar-item-gap);
  padding: 0 8px;
}

.app-sidebar__item-wrap {
  /* 让 ::before 的左色条锚定到 item 本体 */
  position: relative;
}

.app-sidebar__item {
  display: flex;
  align-items: center;
  gap: 10px;
  height: var(--sidebar-item-height);
  padding: var(--sidebar-item-padding-y) var(--sidebar-item-padding-x);
  border-radius: var(--sidebar-item-radius);
  color: var(--slate);
  font-size: var(--sidebar-text-size);
  font-weight: var(--sidebar-text-weight);
  text-decoration: none;
  transition:
    background-color var(--sidebar-transition),
    color var(--sidebar-transition);
  position: relative;
}

.app-sidebar__item:hover {
  background: var(--sidebar-hover-bg);
  color: var(--ink);
}

.app-sidebar__item:focus-visible {
  outline: none;
  box-shadow: inset 0 0 0 2px rgba(var(--signal-rgb), 0.25);
}

.app-sidebar__icon {
  flex-shrink: 0;
  /* 微调与文字基线对齐 */
  transform: translateY(-1px);
}

.app-sidebar__label {
  flex: 1;
  line-height: 1;
}

/* 选中态：左色条 + 字色加深 + 背景填充 */
.app-sidebar__item.is-active {
  color: var(--sidebar-active-text-color);
  background: var(--sidebar-active-bg);
  font-weight: 500;
  /* 瞬时切换，无 transition */
}

.app-sidebar__item.is-active::before {
  content: '';
  position: absolute;
  left: -8px; /* 抵消父 ul padding */
  top: 0;
  bottom: 0;
  width: var(--sidebar-active-bar-width);
  background: var(--sidebar-active-bar-color);
  border-radius: 0 2px 2px 0;
}

.app-sidebar__footer {
  padding: 12px var(--sidebar-item-padding-x) 0;
  font-size: var(--sidebar-bottom-text-size);
  color: var(--sidebar-bottom-text-color);
  font-family: var(--font-mono);
  border-top: 1px solid var(--mist);
  margin-top: 12px;
}
</style>
```

### 6.10 DashboardView 完整代码（Q6 + Q17）

文件：`web/src/views/DashboardView.vue`

```vue
<script setup lang="ts">
/**
 * DashboardView — AI 热点首页（默认）
 *
 * 5 个 tab：
 *  - AI 热点     (默认，/?tab=hotspot)
 *  - 关注列表    (/?tab=follow-list)
 *  - 处理记录    (/?tab=follow-records)
 *  - 即将学习    (/?tab=follow-upcoming)
 *  - 失败        (/?tab=follow-failed)
 *
 * tab 状态通过 hash 路由 ?tab=... 持久化（Q6 + Q17）
 * 切换瞬时，无过渡；子组件懒加载
 * 订阅 SSE hotspot.new / hotspot.updated / agent.queue.updated
 * 触发 TanStack Query 缓存失效
 */
import { defineAsyncComponent, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useQueryClient } from '@tanstack/vue-query'
import { subscribeSse } from '@/lib/sse-client'

interface TabDef {
  key: string
  label: string
  panel: ReturnType<typeof defineAsyncComponent>
}

const TAB_DEFS: TabDef[] = [
  { key: 'hotspot',         label: 'AI 热点',     panel: defineAsyncComponent(() => import('@/views/panels/DashboardHotspotPanel.vue')) },
  { key: 'follow-list',     label: '关注列表',    panel: defineAsyncComponent(() => import('@/views/panels/FollowListPanel.vue')) },
  { key: 'follow-records',  label: '处理记录',    panel: defineAsyncComponent(() => import('@/views/panels/FollowRecordsPanel.vue')) },
  { key: 'follow-upcoming', label: '即将学习',    panel: defineAsyncComponent(() => import('@/views/panels/FollowUpcomingPanel.vue')) },
  { key: 'follow-failed',   label: '失败',        panel: defineAsyncComponent(() => import('@/views/panels/FollowFailedPanel.vue')) },
]

const VALID_KEYS = TAB_DEFS.map((t) => t.key)
const DEFAULT_TAB = 'hotspot'

const route = useRoute()
const router = useRouter()
const qc = useQueryClient()

const currentKey = computed<string>(() => {
  const tab = route.query.tab
  if (typeof tab === 'string' && VALID_KEYS.includes(tab)) return tab
  return DEFAULT_TAB
})

const currentPanel = computed(() =>
  TAB_DEFS.find((t) => t.key === currentKey.value)?.panel
)

const setTab = (key: string) => {
  router.replace({ query: { ...route.query, tab: key } })
}

/* SSE 订阅：实时让 TanStack Query 失效 */
let cleanup: (() => void) | null = null
onMounted(() => {
  cleanup = subscribeSse([
    {
      event: 'hotspot.new',
      onMessage: () => {
        qc.invalidateQueries({ queryKey: ['hotspots'] })
        qc.invalidateQueries({ queryKey: ['follow-records'] })
      },
    },
    {
      event: 'hotspot.updated',
      onMessage: () => {
        qc.invalidateQueries({ queryKey: ['hotspots'] })
      },
    },
    {
      event: 'agent.queue.updated',
      onMessage: () => {
        qc.invalidateQueries({ queryKey: ['agent-queue'] })
        qc.invalidateQueries({ queryKey: ['follow-records'] })
      },
    },
    {
      event: 'follow.updated',
      onMessage: () => {
        qc.invalidateQueries({ queryKey: ['follows'] })
        qc.invalidateQueries({ queryKey: ['follow-upcoming'] })
        qc.invalidateQueries({ queryKey: ['follow-failed'] })
      },
    },
  ])
})

onBeforeUnmount(() => {
  cleanup?.()
})

watch(
  () => route.query.tab,
  () => {
    /* 路由变化时 currentKey 自动重算，无需额外动作 */
  }
)
</script>

<template>
  <div class="dashboard-view">
    <nav class="dashboard-tabs" role="tablist" aria-label="Dashboard tabs">
      <button
        v-for="tab in TAB_DEFS"
        :key="tab.key"
        role="tab"
        :aria-selected="currentKey === tab.key"
        :class="[
          'dashboard-tab',
          { 'is-active': currentKey === tab.key },
        ]"
        @click="setTab(tab.key)"
      >
        {{ tab.label }}
      </button>
    </nav>

    <section class="dashboard-panel" role="tabpanel">
      <component :is="currentPanel" />
    </section>
  </div>
</template>

<style scoped>
.dashboard-view {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.dashboard-tabs {
  display: flex;
  align-items: stretch;
  gap: 0;
  padding: 0 var(--tab-padding-y);
  border-bottom: 1px solid var(--mist);
  background: var(--sidebar-main-bg);
  position: sticky;
  top: 0;
  z-index: 10;
}

.dashboard-tab {
  appearance: none;
  background: transparent;
  border: 0;
  padding: var(--tab-padding-y) 16px;
  font-size: 14px;
  font-weight: 500;
  color: var(--tab-inactive-text-color);
  cursor: pointer;
  position: relative;
  transition: color 150ms ease-out;
}

.dashboard-tab:hover {
  color: var(--ink);
}

.dashboard-tab:focus-visible {
  outline: none;
  box-shadow: inset 0 0 0 2px rgba(var(--signal-rgb), 0.25);
}

.dashboard-tab.is-active {
  color: var(--tab-active-text-color);
  font-weight: 600;
}

.dashboard-tab.is-active::after {
  content: '';
  position: absolute;
  left: 16px;
  right: 16px;
  bottom: -1px;
  height: 2px;
  background: var(--tab-underline-color);
  border-radius: 2px 2px 0 0;
}

.dashboard-panel {
  flex: 1;
  padding: 24px;
  min-height: 0;
}
</style>
```

### 6.11 FollowListPanel 完整代码（Q20）

文件：`web/src/views/panels/FollowListPanel.vue`

```vue
<script setup lang="ts">
/**
 * FollowListPanel — 关注 UP 主列表 tab
 *
 * 功能：
 *  - 添加 UP 主按钮 → 弹 modal（粘贴 B 站主页 URL，详见 §6.6）
 *  - UP 主卡片列表：头像 / 名称 / UID / 启用开关 / 立即同步 / 最后同步时间 / 视频数量
 *  - 按最近更新时间倒序
 *  - 停用 UP 主：半透明 + 启用状态徽章
 *  - 失败 UP 主：UI 卡片小红点提示
 *  - 删除：二次确认 modal
 */
import { computed, ref } from 'vue'
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import { AddUpMasterModal } from '@/components/follow'
import { ConfirmModal } from '@/components/ui'
import { followApi } from '@/api/follow'
import { UpMasterCard } from '@/components/follow/UpMasterCard.vue'
import { HealthDot } from '@/components/follow/HealthDot.vue'

interface UpMaster {
  uid: string
  mid: string
  name: string
  avatar: string
  enabled: boolean
  health: 'healthy' | 'warning' | 'error'
  last_checked_at: string | null
  last_error: string | null
  video_count: number
  updated_at: string
}

const qc = useQueryClient()
const showAddModal = ref(false)
const deleteTarget = ref<UpMaster | null>(null)

const { data, isLoading, isError, refetch } = useQuery({
  queryKey: ['follows'],
  queryFn: () => followApi.list(),
  staleTime: 30_000,
})

const sortedFollows = computed<UpMaster[]>(() => {
  const items = data.value?.items ?? []
  return [...items].sort((a, b) => {
    // 失败的优先在顶部
    if (a.health === 'error' && b.health !== 'error') return -1
    if (b.health === 'error' && a.health !== 'error') return 1
    // 然后按 updated_at 倒序
    return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
  })
})

const toggleEnable = useMutation({
  mutationFn: (vars: { uid: string; enabled: boolean }) =>
    followApi.setEnabled(vars.uid, vars.enabled),
  onSuccess: () => qc.invalidateQueries({ queryKey: ['follows'] }),
})

const syncNow = useMutation({
  mutationFn: (uid: string) => followApi.scanNow(uid),
  onSuccess: () => qc.invalidateQueries({ queryKey: ['follows'] }),
})

const deleteMut = useMutation({
  mutationFn: (uid: string) => followApi.remove(uid),
  onSuccess: () => {
    qc.invalidateQueries({ queryKey: ['follows'] })
    deleteTarget.value = null
  },
})

const onAddSuccess = () => {
  showAddModal.value = false
  qc.invalidateQueries({ queryKey: ['follows'] })
}

const onConfirmDelete = () => {
  if (deleteTarget.value) deleteMut.mutate(deleteTarget.value.uid)
}
</script>

<template>
  <div class="follow-list-panel">
    <header class="follow-list-header">
      <h2>关注列表</h2>
      <div class="follow-list-meta">
        <span class="slate">{{ sortedFollows.length }} 个 UP 主</span>
        <button class="btn" @click="showAddModal = true">
          ➕ 添加 UP 主
        </button>
      </div>
    </header>

    <div v-if="isLoading" class="state state-loading">加载中…</div>

    <div v-else-if="isError" class="state state-error">
      加载失败
      <button class="btn btn-ghost" @click="refetch()">重试</button>
    </div>

    <div v-else-if="sortedFollows.length === 0" class="state state-empty">
      还没有关注的 UP 主。点击「添加 UP 主」开始。
    </div>

    <ul v-else class="follow-list">
      <UpMasterCard
        v-for="item in sortedFollows"
        :key="item.uid"
        :upmaster="item"
        :class="{ 'is-disabled': !item.enabled }"
        @toggle="(enabled: boolean) => toggleEnable.mutate({ uid: item.uid, enabled })"
        @sync="syncNow.mutate(item.uid)"
        @delete="deleteTarget = item"
      >
        <template #health>
          <HealthDot :status="item.health" />
        </template>
      </UpMasterCard>
    </ul>

    <AddUpMasterModal
      v-if="showAddModal"
      @close="showAddModal = false"
      @success="onAddSuccess"
    />

    <ConfirmModal
      v-if="deleteTarget"
      title="删除 UP 主？"
      :message="`确定删除「${deleteTarget.name}」？所有未处理的历史视频将一并归档为 skipped。`"
      confirm-text="删除"
      :loading="deleteMut.isPending.value"
      @cancel="deleteTarget = null"
      @confirm="onConfirmDelete"
    />
  </div>
</template>

<style scoped>
.follow-list-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.follow-list-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.follow-list-header h2 {
  margin: 0;
  font-size: 18px;
}

.follow-list-meta {
  display: flex;
  align-items: center;
  gap: 12px;
}

.follow-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: grid;
  grid-template-columns: 1fr;
  gap: 12px;
}

.is-disabled {
  opacity: 0.55;
}
</style>
```

### 6.12 FollowDetailView 完整代码（Q20）

文件：`web/src/views/FollowDetailView.vue`

```vue
<script setup lang="ts">
/**
 * FollowDetailView — UP 主详情页
 *
 * 路由：/followed-up/:uid
 *
 *  - 头部：UP 主基本信息卡（头像 + 昵称 + 状态徽章）
 *  - 元数据：mid / URL / 策略（uapi/html）/ 间隔 / last_checked_at / last_error
 *  - 合集区块：accordion 折叠列表（每个合集一个 group，散落视频置底）
 *  - 视频区块：最近 20 条视频，每条带 hotspot 状态
 *  - 视频条目右侧：「在 B 站打开」+「总结」两个独立按钮
 *  - 操作：编辑 / 暂停 / 删除 / 立即扫描 / 加载更多历史
 */
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useQuery, useMutation, useQueryClient, useInfiniteQuery } from '@tanstack/vue-query'
import { followApi } from '@/api/follow'
import { VideoListItem } from '@/components/follow/VideoListItem.vue'
import { CollectionAccordion } from '@/components/follow/CollectionAccordion.vue'
import { HealthDot } from '@/components/follow/HealthDot.vue'
import { ConfirmModal } from '@/components/ui'

const route = useRoute()
const router = useRouter()
const qc = useQueryClient()
const uid = computed(() => String(route.params.uid))

const showDeleteModal = ref(false)

const { data: detail, isLoading } = useQuery({
  queryKey: ['follows', uid],
  queryFn: () => followApi.detail(uid.value),
  enabled: computed(() => !!uid.value),
})

const { data: videos, fetchNextPage, hasNextPage, isFetchingNextPage } =
  useInfiniteQuery({
    queryKey: ['follows', uid, 'videos'],
    queryFn: ({ pageParam = 0 }) =>
      followApi.listVideos(uid.value, { offset: pageParam, limit: 20 }),
    initialPageParam: 0,
    getNextPageParam: (last) => last.nextOffset ?? null,
  })

const scanNow = useMutation({
  mutationFn: () => followApi.scanNow(uid.value),
  onSuccess: () => qc.invalidateQueries({ queryKey: ['follows', uid] }),
})

const toggleEnabled = useMutation({
  mutationFn: (enabled: boolean) =>
    followApi.setEnabled(uid.value, enabled),
  onSuccess: () => qc.invalidateQueries({ queryKey: ['follows', uid] }),
})

const removeMut = useMutation({
  mutationFn: () => followApi.remove(uid.value),
  onSuccess: () => router.push('/dashboard?tab=follow-list'),
})

const allVideos = computed(() =>
  (videos.value?.pages ?? []).flatMap((p) => p.items)
)

const collections = computed(() => detail.value?.collections ?? [])
const orphanVideos = computed(() =>
  allVideos.value.filter((v) => !v.collection_id)
)

/* 立即扫描 */
const onScanNow = () => scanNow.mutate()

/* 加载更多历史 */
const onLoadMore = () => {
  if (hasNextPage.value && !isFetchingNextPage.value) fetchNextPage()
}

/* 在 B 站打开 */
const onOpenInBilibili = (bvid: string) => {
  window.open(`https://www.bilibili.com/video/${bvid}`, '_blank', 'noopener')
}
</script>

<template>
  <div class="follow-detail-view">
    <button class="btn btn-ghost back-btn" @click="router.back()">
      ← 返回
    </button>

    <div v-if="isLoading" class="state state-loading">加载中…</div>

    <template v-else-if="detail">
      <!-- 头部：基本信息卡 -->
      <header class="follow-detail-header">
        <img
          :src="detail.avatar"
          :alt="detail.name"
          class="follow-detail-avatar"
        />
        <div class="follow-detail-id">
          <h1>{{ detail.name }}</h1>
          <div class="follow-detail-status">
            <HealthDot :status="detail.health" />
            <span class="tag" :class="`tag-${detail.health}`">
              {{ detail.health }}
            </span>
            <span v-if="!detail.enabled" class="tag">已停用</span>
          </div>
        </div>
        <div class="follow-detail-actions">
          <button
            class="btn btn-ghost"
            :disabled="scanNow.isPending.value"
            @click="onScanNow"
          >
            {{ scanNow.isPending.value ? '扫描中…' : '立即扫描' }}
          </button>
          <button
            class="btn btn-ghost"
            @click="toggleEnabled.mutate(!detail.enabled)"
          >
            {{ detail.enabled ? '暂停' : '恢复' }}
          </button>
          <button class="btn btn-ghost">编辑</button>
          <button class="btn btn-ghost danger" @click="showDeleteModal = true">
            删除
          </button>
        </div>
      </header>

      <!-- 元数据 -->
      <section class="follow-detail-meta panel">
        <dl>
          <dt>mid</dt><dd><code>{{ detail.mid }}</code></dd>
          <dt>主页 URL</dt>
          <dd><a :href="detail.url" target="_blank" rel="noopener">{{ detail.url }}</a></dd>
          <dt>策略</dt><dd><code>{{ detail.strategy }}</code></dd>
          <dt>间隔</dt><dd><code>{{ detail.interval_minutes }} 分钟</code></dd>
          <dt>上次扫描</dt>
          <dd>
            <time v-if="detail.last_checked_at">
              {{ new Date(detail.last_checked_at).toLocaleString('zh-CN') }}
            </time>
            <span v-else class="slate">尚未扫描</span>
          </dd>
          <dt v-if="detail.last_error">最近错误</dt>
          <dd v-if="detail.last_error" class="state state-error">
            {{ detail.last_error }}
          </dd>
        </dl>
      </section>

      <!-- 合集区块 -->
      <section
        v-if="collections.length > 0"
        class="follow-detail-collections"
      >
        <h2>合集（{{ collections.length }}）</h2>
        <CollectionAccordion
          v-for="grp in collections"
          :key="grp.id"
          :collection="grp"
        />
      </section>

      <!-- 视频区块 -->
      <section class="follow-detail-videos">
        <h2>
          视频（最近 {{ allVideos.length }} 条）
          <span class="slate">·</span>
          <button
            v-if="hasNextPage"
            class="btn btn-ghost"
            :disabled="isFetchingNextPage"
            @click="onLoadMore"
          >
            {{ isFetchingNextPage ? '加载中…' : '加载更多历史' }}
          </button>
        </h2>
        <ul class="follow-detail-video-list">
          <VideoListItem
            v-for="v in allVideos"
            :key="v.bvid"
            :video="v"
            @open-bilibili="onOpenInBilibili(v.bvid)"
          />
        </ul>

        <div v-if="orphanVideos.length > 0" class="follow-detail-orphan">
          <h3>散落视频（不在合集内，{{ orphanVideos.length }} 条）</h3>
          <ul>
            <VideoListItem
              v-for="v in orphanVideos"
              :key="v.bvid"
              :video="v"
              variant="orphan"
              @open-bilibili="onOpenInBilibili(v.bvid)"
            />
          </ul>
        </div>
      </section>
    </template>

    <ConfirmModal
      v-if="showDeleteModal"
      title="删除该 UP 主？"
      :message="`「${detail?.name}」及其所有关注历史将被删除，此操作不可恢复。`"
      confirm-text="删除"
      :loading="removeMut.isPending.value"
      @cancel="showDeleteModal = false"
      @confirm="removeMut.mutate()"
    />
  </div>
</template>

<style scoped>
.follow-detail-view {
  display: flex;
  flex-direction: column;
  gap: 20px;
  max-width: 960px;
  margin: 0 auto;
}

.back-btn { align-self: flex-start; }

.follow-detail-header {
  display: grid;
  grid-template-columns: auto 1fr auto;
  gap: 16px;
  align-items: center;
  background: var(--paper);
  border: 1px solid var(--mist);
  border-radius: var(--radius-md);
  padding: 16px;
}

.follow-detail-avatar {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  object-fit: cover;
  background: var(--mist);
}

.follow-detail-id h1 {
  margin: 0 0 8px;
  font-size: 22px;
}

.follow-detail-status {
  display: flex;
  align-items: center;
  gap: 8px;
}

.follow-detail-actions {
  display: flex;
  gap: 8px;
}

.danger {
  color: var(--signal);
}

.follow-detail-meta dl {
  display: grid;
  grid-template-columns: 120px 1fr;
  gap: 8px 16px;
  margin: 0;
  font-size: 13px;
}

.follow-detail-meta dt {
  color: var(--slate);
  font-weight: 500;
}

.follow-detail-meta dd {
  margin: 0;
  word-break: break-all;
}

.follow-detail-collections h2,
.follow-detail-videos h2 {
  margin: 0 0 12px;
  font-size: 16px;
}

.follow-detail-video-list,
.follow-detail-orphan ul {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.follow-detail-orphan {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px dashed var(--mist);
}
</style>
```

### 6.13 三态按钮组件（Q13 + Q14）

文件：`web/src/components/buttons/SummarizeButton.vue`

```vue
<script setup lang="ts">
/**
 * SummarizeButton — 视频条目右侧的"总结"按钮（半自动模式，Q13 + Q14）
 *
 * 状态机：
 *   idle    -> 未处理
 *   pending -> 用户点击 → POST /api/agent/process
 *   queued  -> 已入队（黄色，显示队列位置 #N）
 *   running -> 运行中（蓝色 + SSE 步骤进度）
 *   done    -> 完成（绿色，变 "查看总结" 按钮，点击跳 obsidian://open?path=...）
 *   failed  -> 失败（红色 toast + 分类错误信息）→ 用户手动重试
 */
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useMutation, useQueryClient } from '@tanstack/vue-query'
import { agentApi } from '@/api/agent'
import { subscribeSse } from '@/lib/sse-client'

interface Props {
  bvid: string
  /** 是否已有完成的总结笔记（用于按钮文案与跳转） */
  hasSummary?: boolean
  obsidianPath?: string | null
}
const props = withDefaults(defineProps<Props>(), {
  hasSummary: false,
  obsidianPath: null,
})

const emit = defineEmits<{
  (e: 'queued'): void
  (e: 'failed', reason: string): void
}>()

const qc = useQueryClient()

/* 当前任务状态：idle / pending / queued / running / done / failed */
const status = ref<'idle' | 'pending' | 'queued' | 'running' | 'done' | 'failed'>(
  props.hasSummary ? 'done' : 'idle'
)
const queuePosition = ref<number | null>(null)
const currentStep = ref<string | null>(null)
const errorMessage = ref<string | null>(null)

const enqueue = useMutation({
  mutationFn: () => agentApi.enqueueProcess({ bvid: props.bvid }),
  onSuccess: (res) => {
    status.value = 'queued'
    queuePosition.value = res.queue_position ?? null
    emit('queued')
  },
  onError: (err: Error) => {
    status.value = 'failed'
    errorMessage.value = err.message
    emit('failed', err.message)
  },
})

/* SSE 进度跟踪 */
let cleanup: (() => void) | null = null
onMounted(() => {
  cleanup = subscribeSse([
    {
      event: 'agent.queue.updated',
      onMessage: () => qc.invalidateQueries({ queryKey: ['agent-queue'] }),
    },
    {
      event: `agent.task.${props.bvid}.started`,
      onMessage: () => {
        status.value = 'running'
        queuePosition.value = null
        currentStep.value = 'fetch_transcript'
      },
    },
    {
      event: `agent.task.${props.bvid}.step`,
      onMessage: (ev: MessageEvent) => {
        try {
          const payload = JSON.parse(ev.data)
          currentStep.value = payload.step
        } catch {
          /* ignore */
        }
      },
    },
    {
      event: `agent.task.${props.bvid}.done`,
      onMessage: () => {
        status.value = 'done'
        currentStep.value = null
        qc.invalidateQueries({ queryKey: ['video', props.bvid] })
      },
    },
    {
      event: `agent.task.${props.bvid}.failed`,
      onMessage: (ev: MessageEvent) => {
        status.value = 'failed'
        try {
          errorMessage.value = JSON.parse(ev.data).message ?? '未知错误'
        } catch {
          errorMessage.value = '未知错误'
        }
      },
    },
  ])
})

onBeforeUnmount(() => cleanup?.())

const label = computed(() => {
  switch (status.value) {
    case 'idle':     return '总结'
    case 'pending':  return '提交中…'
    case 'queued':
      return queuePosition.value != null
        ? `队列 #${queuePosition.value}`
        : '排队中…'
    case 'running':
      return currentStep.value === 'fetch_transcript' ? '拉字幕…'
        : currentStep.value === 'summarize'           ? '总结中…'
        : currentStep.value === 'judge'               ? '判断中…'
        : '运行中…'
    case 'done':     return '查看总结'
    case 'failed':   return '重试'
  }
})

const onClick = () => {
  if (status.value === 'done' && props.obsidianPath) {
    window.location.href = `obsidian://open?path=${encodeURIComponent(props.obsidianPath)}`
    return
  }
  if (status.value === 'failed') {
    status.value = 'idle'
    errorMessage.value = null
  }
  if (status.value === 'idle') {
    status.value = 'pending'
    enqueue.mutate()
  }
}
</script>

<template>
  <button
    :class="[
      'btn',
      'summarize-btn',
      `summarize-btn--${status}`,
    ]"
    :disabled="status === 'pending' || status === 'queued' || status === 'running'"
    :aria-busy="status === 'pending' || status === 'queued' || status === 'running'"
    :title="errorMessage ?? label"
    @click="onClick"
  >
    <span v-if="status === 'done'" aria-hidden="true">✓</span>
    <span v-else-if="status === 'failed'" aria-hidden="true">!</span>
    <span v-else-if="status === 'running'" class="summarize-spinner" aria-hidden="true" />
    {{ label }}
  </button>
</template>

<style scoped>
.summarize-btn {
  min-width: 88px;
  justify-content: center;
}

.summarize-btn--idle {
  background: var(--ink);
  color: var(--paper);
}

.summarize-btn--pending,
.summarize-btn--queued {
  background: var(--state-queued);
  color: white;
  cursor: default;
}

.summarize-btn--running {
  background: var(--state-running);
  color: white;
  cursor: default;
}

.summarize-btn--done {
  background: var(--state-done);
  color: white;
}

.summarize-btn--failed {
  background: var(--state-error);
  color: white;
}

.summarize-btn:focus-visible {
  outline: none;
  box-shadow: 0 0 0 3px rgba(var(--signal-rgb), 0.25);
}

.summarize-spinner {
  width: 12px;
  height: 12px;
  border: 2px solid rgba(255, 255, 255, 0.4);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

@media (prefers-reduced-motion: reduce) {
  .summarize-spinner { animation: none; }
}
</style>
```

### 6.14 路由表（Q6 + Q17）

由 `web/src/router/index.ts` 导出。鉴权：本地开发 `Authorization` 可选（见 §6.15 测试用例）。

| 路径 | 组件 | 鉴权 | 说明 |
|---|---|---|---|
| `/dashboard` | `DashboardView.vue` | 无（默认 tab=hotspot） | AI 热点首页 |
| `/dashboard?tab=follow-list` | `DashboardView.vue` + `FollowListPanel.vue` | 无 | 关注列表 tab |
| `/dashboard?tab=follow-records` | `DashboardView.vue` + `FollowRecordsPanel.vue` | 无 | 处理记录 tab |
| `/dashboard?tab=follow-upcoming` | `DashboardView.vue` + `FollowUpcomingPanel.vue` | 无 | 即将学习 tab |
| `/dashboard?tab=follow-failed` | `DashboardView.vue` + `FollowFailedPanel.vue` | 无 | 失败 tab |
| `/followed-up/:uid` | `FollowDetailView.vue` | 无 | UP 主详情页 |
| `/hotspot/:id` | `HotspotDetailView.vue` | 无 | 热点详情（现有） |
| `/keywords` | `KeywordsView.vue` | 无 | 关键词（现有） |
| `/sources` | `SourcesView.vue` | 无 | 来源（现有） |
| `/jobs` | `JobsView.vue` | 无 | 定时任务（现有） |
| `/digests` | `DigestsView.vue` | 无 | 摘要（现有） |
| `/settings` | `SettingsView.vue` | 无 | 系统设置（新增，保留 emoji 入口） |

```ts
// web/src/router/index.ts
import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  { path: '/', redirect: '/dashboard' },
  { path: '/dashboard', name: 'dashboard',
    component: () => import('@/views/DashboardView.vue') },
  { path: '/followed-up/:uid', name: 'follow-detail',
    component: () => import('@/views/FollowDetailView.vue'), props: true },
  { path: '/hotspot/:id', name: 'hotspot-detail',
    component: () => import('@/views/HotspotDetailView.vue'), props: true },
  { path: '/keywords',  name: 'keywords',  component: () => import('@/views/KeywordsView.vue') },
  { path: '/sources',   name: 'sources',   component: () => import('@/views/SourcesView.vue') },
  { path: '/jobs',      name: 'jobs',      component: () => import('@/views/JobsView.vue') },
  { path: '/digests',   name: 'digests',   component: () => import('@/views/DigestsView.vue') },
  { path: '/settings',  name: 'settings',  component: () => import('@/views/SettingsView.vue') },
]

export const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior() { return { top: 0 } },
})
```

### 6.15 测试用例清单

覆盖 §6 所有用户面的 vitest + Playwright 用例。

**vitest 单元 / 组件测试（`web/src/views/__tests__/`、`web/src/components/__tests__/`、`web/tests/component/`）**：

1. `test_sidebar_renders_6_entries` — 渲染后断言 6 个 `.app-sidebar__item` 且 label 与 NAV_ITEMS 一致
2. `test_sidebar_active_state_has_3px_left_bar` — 当前路由命中某项 → 该项 `is-active` + `::before` 宽度 `var(--sidebar-active-bar-width) === 3px`
3. `test_sidebar_hover_background_4_percent` — hover 触发 → computed `background-color` 等于 `rgba(27,26,23,0.04)`
4. `test_sidebar_transition_duration_150ms` — 断言 `.app-sidebar__item` 的 `transition-duration: 150ms`
5. `test_sidebar_active_changes_instantly_no_transition` — 选中态变化时无 `transition` / 无动画
6. `test_sidebar_footer_shows_version_sources_sync` — 渲染 `v0.2.0 · 4 sources · 2 分钟前 同步`
7. `test_dashboard_default_tab_is_hotspot` — 无 `?tab=` query → `currentKey === 'hotspot'`
8. `test_dashboard_tab_switch_via_query_param` — `?tab=follow-list` → 渲染 `FollowListPanel`
9. `test_dashboard_invalid_query_falls_back_to_default` — `?tab=junk` → 回到 `hotspot`
10. `test_dashboard_lazy_loads_panels` — 切换 tab 时动态 `import()` 触发（spy）
11. `test_dashboard_sse_invalidate_on_hotspot_new` — mock `subscribeSse` 收到 `hotspot.new` → `qc.invalidateQueries(['hotspots'])`
12. `test_follow_list_panel_renders_upmaster_cards` — API 返回 3 条 → 渲染 3 个 `UpMasterCard`
13. `test_follow_list_panel_sorted_by_recent_update` — 列表按 `updated_at` 倒序
14. `test_follow_list_panel_failed_pinned_to_top` — `health==='error'` 优先置顶
15. `test_follow_list_panel_disabled_card_50_percent_opacity` — `enabled=false` → 卡片 opacity 0.5
16. `test_follow_list_modal_validates_bilibili_url` — 非 `space.bilibili.com/{mid}` 提交被拒
17. `test_follow_list_delete_requires_confirmation` — 点击删除 → `ConfirmModal` 打开，确认后才发 API
18. `test_follow_detail_view_shows_collections_accordion` — 详情页 collections > 0 → `CollectionAccordion` 列表渲染
19. `test_follow_detail_load_more_fetches_next_page` — 触发 `fetchNextPage` → 下一页 API 被调用
20. `test_summarize_button_pending_to_queued` — 点击 → `agentApi.enqueueProcess` → status=`queued`
21. `test_summarize_button_queues_position_displayed` — `queue_position=3` → label=`队列 #3`
22. `test_summarize_button_running_step_progress` — SSE `agent.task.{bvid}.step` → 切换 currentStep & label
23. `test_summarize_button_done_jumps_to_obsidian` — status=done + obsidianPath → 点击产生 `obsidian://open?path=...`
24. `test_summarize_button_failed_shows_retry_state` — status=failed → label=`重试`、title 显示 errorMessage

**Playwright E2E（`e2e/specs/follow-up.spec.ts`，需真实 Tauri 启 sidecar）**：

25. `test_authorization_bearer_header_sent_to_api` — 任一带鉴权 API 请求 headers 含 `Authorization: Bearer <token>`
26. `test_no_auth_token_works_for_local_dev` — 未配置 token 时 axios 不发 Authorization header（local dev）；真实后端放行
27. `test_obsidian_open_protocol_jumps_to_note` — stub `window.location.href` → 完成总结后点击 → 跳 `obsidian://open?path=...` 且 path 与 obsidianPath 一致
28. `test_follow_add_end_to_end` — 粘贴 `https://space.bilibili.com/1567748478` → 真实添加 → UI 出现新卡片 → `POST /api/follows` 返回 200
29. `test_follow_add_invalid_mid_error_modal` — 粘贴随机文本 → modal 显示 `该 UP主不存在或账号已注销`
30. `test_follow_add_backfill_50_videos_pending` — 添加成功后该 UP 主视频数=50 且 `decision_status='pending'`
31. `test_dashboard_tab_persists_after_reload` — 切到 `follow-failed` → F5 → 仍在 `follow-failed`
32. `test_health_status_badge_recomputes_after_scan` — 模拟 `follow.updated` SSE → 徽章颜色从 warning → healthy
33. `test_summarize_button_real_sidecar_pipeline` — 点 idle 按钮 → 真实 sidecar 处理一条短 B 站视频 → SSE `done` 后变绿色「查看总结」（要求真实字幕 + 总结可获取，CI 跳过）

---

## 7. 通知与提醒（Q11 + Q22）

