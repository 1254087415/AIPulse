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

// Inline lucide-style SVG paths (24x24 viewBox, stroke-width 2, currentColor)
// 一套线宽/尺寸的图标，loop D 把 ◐/⚙/✎/⏱/✦/☰ 散装 unicode 替换为统一 icon set。
const ICONS: Readonly<Record<string, string>> = {
  hotspot: '<circle cx="12" cy="12" r="9"/><path d="M12 3v18M3 12h18"/>',
  sources: '<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v6c0 1.66 4.03 3 9 3s9-1.34 9-3V5"/><path d="M3 11v6c0 1.66 4.03 3 9 3s9-1.34 9-3v-6"/>',
  keywords: '<path d="M4 20l4-1 11-11a2.83 2.83 0 0 0-4-4L4 15v5z"/><path d="M14 5l4 4"/>',
  jobs: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  digests: '<path d="M4 4h12l4 4v12a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z"/><path d="M16 4v4h4"/><path d="M8 12h8M8 16h6"/>',
  settings: '<path d="M12 2l2 4 4-1-1 4 4 2-4 2 1 4-4-1-2 4-2-4-4 1 1-4-4-2 4-2-1-4 4 1z"/><circle cx="12" cy="12" r="3"/>',
}

const NAV_ITEMS: SidebarNavItem[] = [
  { key: 'hotspot', label: 'AI 热点', to: '/dashboard', icon: ICONS.hotspot },
  { key: 'sources', label: '来源', to: '/sources', icon: ICONS.sources },
  { key: 'keywords', label: '关键词', to: '/keywords', icon: ICONS.keywords },
  { key: 'jobs', label: '定时任务', to: '/jobs', icon: ICONS.jobs },
  { key: 'digests', label: '摘要', to: '/digests', icon: ICONS.digests },
  { key: 'settings', label: '系统', to: '/settings', icon: ICONS.settings },
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