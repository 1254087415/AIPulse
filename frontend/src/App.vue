<script setup lang="ts">
/**
 * App.vue — top-level shell selector (spec §6.14 / §8.1).
 *
 * Two layouts are supported:
 *   1. New v0.3 shell — Sidebar (left) + main content (right). Used by every
 *      v0.3 surface: dashboard, sources, keywords, jobs, digests, settings,
 *      followed-up detail, hotspot detail. Also used as the safe default for
 *      any future routes that haven't been enumerated yet.
 *   2. Legacy Tauri header — used by the two legacy Tauri-only windows
 *      (/input and /tasks). These rely on `@tauri-apps/api/core` and cannot
 *      render under the browser; they keep the old banner.
 */
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import AppHeader from './components/AppHeader.vue'
import Sidebar from './components/sidebar/Sidebar.vue'

const LEGACY_PATHS: readonly string[] = ['/input', '/tasks']

const route = useRoute()

const usesNewShell = computed<boolean>(() => {
  return !LEGACY_PATHS.includes(route.path)
})
</script>

<template>
  <div class="app-shell">
    <template v-if="usesNewShell">
      <div class="app-shell__new">
        <Sidebar />
        <main class="app-main app-main--dashboard">
          <router-view />
        </main>
      </div>
    </template>
    <template v-else>
      <AppHeader />
      <main class="app-main">
        <router-view />
      </main>
    </template>
  </div>
</template>

<style scoped>
.app-shell {
  display: flex;
  flex-direction: column;
  width: 100%;
  height: 100%;
  background: var(--surface-bg);
}

.app-shell__new {
  display: flex;
  flex-direction: row;
  width: 100%;
  height: 100%;
  min-height: 0;
}

.app-main {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.app-main--dashboard {
  display: flex;
  flex-direction: column;
  background: var(--sidebar-main-bg);
}
</style>
