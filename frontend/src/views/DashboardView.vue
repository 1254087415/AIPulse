<script setup lang="ts">
/**
 * DashboardView — top-level tab container for the v0.3 dashboard.
 *
 * Renders a 5-tab nav (AI 热点 / 关注列表 / 处理记录 / 即将学习 / 失败) above
 * an active panel. Tab state is mirrored into the `?tab=` query so the
 * active tab survives a reload.
 *
 * Phase 1 only fills the "关注列表" panel; the rest are placeholders that
 * land in Phase 2+ alongside the hotspot content.
 */
import { computed, defineAsyncComponent } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import DashboardHotspotPanel from './panels/DashboardHotspotPanel.vue'
import FollowListPanel from '../components/follow-list-panel/FollowListPanel.vue'

const FollowRecordsPanel = defineAsyncComponent(
  () => import('./panels/FollowRecordsPanel.vue'),
)
const FollowUpcomingPanel = defineAsyncComponent(
  () => import('./panels/FollowUpcomingPanel.vue'),
)
const FollowFailedPanel = defineAsyncComponent(
  () => import('./panels/FollowFailedPanel.vue'),
)

interface TabDef {
  key: string
  label: string
  panel: unknown
}

const TAB_DEFS: TabDef[] = [
  { key: 'hotspot', label: 'AI 热点', panel: DashboardHotspotPanel },
  { key: 'follow-list', label: '关注列表', panel: FollowListPanel },
  { key: 'follow-records', label: '处理记录', panel: FollowRecordsPanel },
  { key: 'follow-upcoming', label: '即将学习', panel: FollowUpcomingPanel },
  { key: 'follow-failed', label: '失败', panel: FollowFailedPanel },
]

const VALID_KEYS = TAB_DEFS.map((tab) => tab.key)
const DEFAULT_TAB = 'hotspot'

const route = useRoute()
const router = useRouter()

const currentKey = computed<string>(() => {
  const tab = route.query.tab
  if (typeof tab === 'string' && VALID_KEYS.includes(tab)) return tab
  return DEFAULT_TAB
})

const currentPanel = computed(() =>
  TAB_DEFS.find((tab) => tab.key === currentKey.value)?.panel,
)

const setTab = (key: string): void => {
  void router.replace({ query: { ...route.query, tab: key } })
}
</script>

<template>
  <section class="dashboard-view" data-testid="dashboard-view">
    <nav
      class="dashboard-tabs"
      role="tablist"
      aria-label="Dashboard tabs"
    >
      <button
        v-for="tab in TAB_DEFS"
        :key="tab.key"
        type="button"
        role="tab"
        class="dashboard-tab"
        :class="{ 'dashboard-tab--active': currentKey === tab.key }"
        :aria-selected="currentKey === tab.key"
        :data-testid="`dashboard-tab-${tab.key}`"
        @click="setTab(tab.key)"
      >
        {{ tab.label }}
      </button>
    </nav>

    <section class="dashboard-panel" role="tabpanel">
      <component :is="currentPanel" />
    </section>
  </section>
</template>

<style scoped>
.dashboard-view {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  background: var(--sidebar-main-bg);
}

.dashboard-tabs {
  display: flex;
  align-items: stretch;
  gap: 0;
  padding: 0 16px;
  border-bottom: 1px solid var(--border-subtle);
  background: var(--sidebar-main-bg);
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
  transition: color 150ms ease;
  font-family: var(--font-body);
}

.dashboard-tab:hover {
  color: var(--text-primary);
}

.dashboard-tab:focus-visible {
  outline: none;
  box-shadow: inset 0 0 0 2px color-mix(in srgb, var(--sidebar-active-bar-color) 25%, transparent);
}

.dashboard-tab--active {
  color: var(--tab-active-text-color);
  font-weight: 600;
}

.dashboard-tab--active::after {
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
  overflow-y: auto;
}
</style>