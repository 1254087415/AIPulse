<script setup lang="ts">
/**
 * SidebarNav — presentational navigation list used by `Sidebar`.
 *
 * Pure component: it accepts an `items` array and an `activeKey`, renders the
 * list, and emits `navigate` when an item is clicked. The container decides
 * how to react (router push, manual scroll, etc.).
 */
import { computed } from 'vue'

export interface SidebarNavItem {
  key: string
  label: string
  to: string
  /** Optional glyph displayed above the label when expanded. */
  icon?: string
}

interface Props {
  items: SidebarNavItem[]
  activeKey: string
  collapsed?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  collapsed: false,
})

const emit = defineEmits<{
  (e: 'navigate', to: string): void
}>()

const isActive = (item: SidebarNavItem): boolean => item.key === props.activeKey

const activeIndex = computed(() =>
  props.items.findIndex((item) => item.key === props.activeKey),
)

const onClick = (item: SidebarNavItem, event: MouseEvent): void => {
  // Allow modifier-click to open in new tab — only intercept plain clicks.
  if (event.metaKey || event.ctrlKey || event.shiftKey) return
  event.preventDefault()
  emit('navigate', item.to)
}
</script>

<template>
  <nav class="app-sidebar__nav" role="navigation" aria-label="主导航">
    <ul class="app-sidebar__list">
      <li
        v-for="item in items"
        :key="item.key"
        class="app-sidebar__item-wrap"
        :class="{ 'is-active': isActive(item) }"
      >
        <a
          :href="item.to"
          :class="['app-sidebar__item', { 'app-sidebar__item--active': isActive(item) }]"
          :aria-current="isActive(item) ? 'page' : undefined"
          @click="onClick(item, $event)"
        >
          <span v-if="item.icon" class="app-sidebar__icon" aria-hidden="true">
            {{ item.icon }}
          </span>
          <span v-if="!collapsed" class="app-sidebar__label">{{ item.label }}</span>
        </a>
      </li>
    </ul>
  </nav>
</template>

<style scoped>
.app-sidebar__nav {
  position: relative;
  flex: 1;
  overflow-y: auto;
}

.app-sidebar__list {
  list-style: none;
  padding: 0 8px;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: var(--sidebar-item-gap);
}

.app-sidebar__item-wrap {
  position: relative;
}

.app-sidebar__item {
  display: flex;
  align-items: center;
  gap: 10px;
  height: var(--sidebar-item-height);
  padding: var(--sidebar-item-padding-y) var(--sidebar-item-padding-x);
  border-radius: var(--sidebar-item-radius);
  color: var(--text-secondary);
  font-size: var(--sidebar-text-size);
  font-weight: var(--sidebar-text-weight);
  text-decoration: none;
  /* spec §6.8 + 09 §8.4 L1489: active-state swap must be instant;
     only :hover adds the 150ms ease-out transition. */
  transition: none;
  position: relative;
  border-left: 3px solid transparent;
}

.app-sidebar__item:hover {
  background: var(--sidebar-hover-bg);
  color: var(--text-primary);
  transition: background-color var(--sidebar-transition);
}

.app-sidebar__item:focus-visible {
  outline: none;
  box-shadow: inset 0 0 0 2px rgba(var(--signal-rgb), 0.30);
}

.app-sidebar__item--active {
  color: var(--sidebar-active-text-color);
  background: var(--sidebar-active-bg);
  font-weight: 500;
  border-left: 3px solid var(--sidebar-active-bar-color);
}

.app-sidebar__icon {
  width: 18px;
  text-align: center;
  flex-shrink: 0;
}

.app-sidebar__label {
  flex: 1;
  line-height: 1;
}
</style>