<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()

interface Tab {
  label: string
  path: string
}

const tabs: Tab[] = [
  { label: '输入', path: '/input' },
  { label: '任务', path: '/tasks' },
  { label: '设置', path: '/settings' },
]

const activePath = computed(() => route.path)
</script>

<template>
  <header class="app-header">
    <div class="brand">
      <img src="/src/assets/hero.png" alt="AIPulse" class="logo" />
      <span class="brand-name">AIPulse</span>
    </div>
    <nav class="tabs">
      <router-link
        v-for="tab in tabs"
        :key="tab.path"
        :to="tab.path"
        class="tab"
        :class="{ active: activePath === tab.path }"
      >
        {{ tab.label }}
      </router-link>
    </nav>
  </header>
</template>

<style scoped>
.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 44px;
  padding: 0 16px;
  background: var(--surface-bg);
  border-bottom: 1px solid var(--border-subtle);
  -webkit-app-region: drag;
  user-select: none;
}

.brand {
  display: flex;
  align-items: center;
  gap: 8px;
  -webkit-app-region: no-drag;
}

.logo {
  width: 20px;
  height: 20px;
  filter: grayscale(100%) brightness(1.6);
}

.brand-name {
  font-family: var(--font-display);
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--text-primary);
}

.tabs {
  display: flex;
  align-items: center;
  gap: 4px;
  -webkit-app-region: no-drag;
}

.tab {
  position: relative;
  padding: 8px 12px;
  font-family: var(--font-body);
  font-size: var(--text-sm);
  color: var(--text-secondary);
  text-decoration: none;
  border-radius: var(--radius-sm);
  transition: color 150ms ease, background-color 150ms ease;
}

.tab:hover {
  color: var(--text-primary);
  background-color: var(--surface-elevated-hover);
}

.tab.active {
  color: var(--accent-coral);
}

.tab.active::after {
  content: '';
  position: absolute;
  bottom: 2px;
  left: 12px;
  right: 12px;
  height: 2px;
  background-color: var(--accent-coral);
  border-radius: 1px;
  box-shadow: 0 0 8px var(--accent-coral-glow);
}
</style>
