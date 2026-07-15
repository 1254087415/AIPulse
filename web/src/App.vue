<script setup lang="ts">
import { RouterLink, RouterView } from 'vue-router'
import PulseLine from './components/PulseLine.vue'

const links = [
  { to: '/dashboard', label: 'AI 热点' },
  { to: '/keywords', label: '关键词' },
  { to: '/sources', label: '来源' },
  { to: '/jobs', label: '定时任务' },
  { to: '/digests', label: '摘要' },
]
</script>

<template>
  <div class="app">
    <a class="skip-link" href="#main-content">跳到主内容</a>
    <header class="top-bar">
      <div class="brand">
        <span class="wordmark">AIPulse</span>
        <PulseLine class="pulse" />
        <span class="status">信号正常</span>
      </div>
      <nav aria-label="Main navigation" class="nav">
        <RouterLink
          v-for="link in links"
          :key="link.to"
          :to="link.to"
          class="nav-link"
          active-class="nav-link-active"
        >
          {{ link.label }}
        </RouterLink>
      </nav>
    </header>
    <main id="main-content">
      <RouterView />
    </main>
  </div>
</template>

<style scoped>
.app {
  min-height: 100vh;
}

.top-bar {
  position: sticky;
  top: 0;
  z-index: 10;
  background: rgba(252, 250, 248, 0.94);
  border-bottom: 1px solid var(--mist);
  backdrop-filter: blur(4px);
  padding: 14px 20px 0;
}

.brand {
  display: flex;
  align-items: center;
  gap: 14px;
  max-width: 880px;
  margin: 0 auto;
}

.wordmark {
  font-family: var(--font-display);
  font-size: 20px;
  font-weight: 700;
  letter-spacing: -0.03em;
  color: var(--ink);
}

.status {
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--signal);
  margin-left: 4px;
}

.pulse {
  flex-shrink: 0;
}

.nav {
  display: flex;
  gap: 4px;
  max-width: 880px;
  margin: 12px auto 0;
  overflow-x: auto;
}

.nav-link {
  font-family: var(--font-display);
  font-size: 14px;
  font-weight: 500;
  color: var(--slate);
  padding: 8px 12px 10px;
  border-bottom: 2px solid transparent;
  white-space: nowrap;
  transition: color 0.15s ease;
}

.nav-link:hover {
  color: var(--ink);
}

.nav-link-active {
  color: var(--signal);
  border-bottom-color: var(--signal);
}

main {
  padding-top: 8px;
}

@media (max-width: 640px) {
  .top-bar {
    padding: 12px 14px 0;
  }

  .brand {
    flex-wrap: wrap;
    gap: 8px 12px;
  }

  .status {
    margin-left: auto;
  }

  .pulse {
    order: 3;
    width: 100%;
  }

  .nav {
    margin-top: 10px;
  }
}
</style>
