<script setup lang="ts">
/**
 * Sidebar — 200px fixed navigation rail for the dashboard.
 *
 * Layout responsibilities (spec §6.9):
 *  - Render the six top-level sections: AI 热点 / 来源 / 关键词 / 定时任务
 *    / 摘要 / 系统
 *  - Highlight the active item via the route
 *  - Offer a collapse toggle that shrinks the rail to an icon-only column
 *
 * The component is intentionally presentational: it routes through vue-router
 * but accepts its own collapsed state via props/v-model so a layout shell can
 * persist the preference.
 */
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import SidebarNav, { type SidebarNavItem } from './SidebarNav.vue'

interface Props {
  /** Two-way binding for the collapsed state. */
  collapsed?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  collapsed: false,
})

const emit = defineEmits<{
  (e: 'update:collapsed', value: boolean): void
}>()

const route = useRoute()
const router = useRouter()

// Spec §6.9 — six-entry nav rail. Follow-up tabs (关注列表 / 处理记录 /
// 即将学习 / 失败) live inside DashboardView, not here.
const NAV_ITEMS: SidebarNavItem[] = [
  { key: 'hotspot', label: 'AI 热点', to: '/dashboard', icon: '◐' },
  { key: 'sources', label: '来源', to: '/sources', icon: '⚙' },
  { key: 'keywords', label: '关键词', to: '/keywords', icon: '✎' },
  { key: 'jobs', label: '定时任务', to: '/jobs', icon: '⏱' },
  { key: 'digests', label: '摘要', to: '/digests', icon: '✦' },
  { key: 'settings', label: '系统', to: '/settings', icon: '☰' },
]

const activeKey = computed<string>(() => {
  const path = route.path
  // Choose the most specific item whose `to` is a prefix of the path.
  const sorted = [...NAV_ITEMS].sort((a, b) => b.to.length - a.to.length)
  for (const item of sorted) {
    if (path === item.to || path.startsWith(`${item.to}/`)) {
      return item.key
    }
  }
  // Fallback: stay on the dashboard entry (which is the root landing).
  return 'hotspot'
})

// Local mirror of the collapsed prop so the toggle updates immediately even
// when the parent doesn't bind it via v-model (e.g. unit tests).
const collapsed = ref<boolean>(props.collapsed)
watch(
  () => props.collapsed,
  (next) => {
    collapsed.value = next
  },
)

const toggleCollapsed = (): void => {
  collapsed.value = !collapsed.value
  emit('update:collapsed', collapsed.value)
}

const onNavigate = (to: string): void => {
  void router.push(to)
}

const asideClass = computed(() => ({
  'app-sidebar': true,
  'app-sidebar--collapsed': collapsed.value,
}))
</script>

<template>
  <aside
    :class="asideClass"
    aria-label="主导航"
    :style="{
      width: collapsed ? 'var(--sidebar-width-collapsed)' : 'var(--sidebar-width)',
    }"
  >
    <header class="app-sidebar__brand">
      <span class="app-sidebar__brand-mark" aria-hidden="true">A</span>
      <span v-if="!collapsed" class="app-sidebar__brand-name">AIPulse</span>
    </header>

    <SidebarNav
      :items="NAV_ITEMS"
      :active-key="activeKey"
      :collapsed="collapsed"
      @navigate="onNavigate"
    />

    <button
      type="button"
      class="app-sidebar__toggle"
      :aria-label="collapsed ? '展开侧边栏' : '折叠侧边栏'"
      :aria-expanded="!collapsed"
      data-testid="sidebar-toggle"
      @click="toggleCollapsed"
    >
      <span aria-hidden="true">{{ collapsed ? '»' : '«' }}</span>
    </button>
  </aside>
</template>

<style scoped>
.app-sidebar {
  width: var(--sidebar-width);
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--sidebar-bg);
  border-right: 1px solid var(--border-subtle);
  padding: 12px 0 16px;
  transition: width var(--sidebar-transition);
  flex-shrink: 0;
}

.app-sidebar--collapsed {
  width: var(--sidebar-width-collapsed);
}

.app-sidebar__brand {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 16px 16px;
  margin: 0 8px 8px;
  border-bottom: 1px solid var(--border-subtle);
}

.app-sidebar__brand-mark {
  width: 24px;
  height: 24px;
  border-radius: 6px;
  background: var(--accent-coral);
  color: var(--surface-elevated);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-family: var(--font-display);
  font-weight: 700;
  font-size: 14px;
}

.app-sidebar__brand-name {
  font-family: var(--font-display);
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  letter-spacing: 0.02em;
}

.app-sidebar__toggle {
  align-self: flex-end;
  margin: 0 12px;
  padding: 4px 10px;
  background: transparent;
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
  font-size: 12px;
  cursor: pointer;
  transition:
    color var(--sidebar-transition),
    border-color var(--sidebar-transition);
}

.app-sidebar__toggle:hover {
  color: var(--text-primary);
  border-color: var(--text-secondary);
}

.app-sidebar--collapsed .app-sidebar__brand {
  justify-content: center;
  padding: 4px 0 16px;
}
</style>