<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import AppHeader from './components/AppHeader.vue'
import Sidebar from './components/sidebar/Sidebar.vue'

const route = useRoute()

// The new v0.3 dashboard uses a two-column layout (sidebar + content).
// Legacy input / settings / tasks windows keep the old header layout.
const usesNewShell = computed<boolean>(() => {
  const path = route.path
  return path === '/dashboard' || path.startsWith('/dashboard/')
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
