<script setup lang="ts">
/**
 * DashboardHotspotPanel — placeholder for the v0.3 hotspot dashboard.
 *
 * Phase 1 only ships the surrounding chrome; the actual hotspot content
 * lands in a later phase. The placeholder exists so the dashboard tab
 * routing has a concrete component to mount and to give the designer a
 * canvas for the eventual layout.
 */
</script>

<template>
  <section class="dashboard-hotspot-panel" data-testid="panel-hotspot">
    <h2>AI 热点</h2>
    <p class="dashboard-hotspot-panel__hint">
      热点面板将在后续 Phase 渲染。当前页面展示顶部 tab 框架。
    </p>
  </section>
</template>

<style scoped>
.dashboard-hotspot-panel {
  padding: 24px;
  background: var(--surface-elevated);
  border: 1px dashed var(--border-subtle);
  border-radius: var(--radius-md);
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.dashboard-hotspot-panel h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
}

.dashboard-hotspot-panel__hint {
  margin: 0;
  font-size: 13px;
  color: var(--text-secondary);
}
</style>