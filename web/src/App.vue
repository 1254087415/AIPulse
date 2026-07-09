<script setup lang="ts">
import { RouterLink, RouterView } from 'vue-router'
</script>

<template>
  <div class="app">
    <header>
      <nav aria-label="Main navigation">
        <RouterLink to="/dashboard">AI 热点</RouterLink>
        <RouterLink to="/keywords">关键词</RouterLink>
        <RouterLink to="/sources">来源</RouterLink>
        <RouterLink to="/jobs">定时任务</RouterLink>
        <RouterLink to="/digests">摘要</RouterLink>
      </nav>
    </header>
    <main>
      <RouterView />
    </main>
  </div>
</template>

<style scoped>
.app {
  max-width: 1200px;
  margin: 0 auto;
  padding: 1rem;
}
header {
  margin-bottom: 1.5rem;
  border-bottom: 1px solid #e5e7eb;
  padding-bottom: 1rem;
}
nav {
  display: flex;
  gap: 1rem;
}
nav a {
  color: #374151;
  text-decoration: none;
  font-weight: 500;
}
nav a.router-link-active {
  color: #2563eb;
}
</style>
