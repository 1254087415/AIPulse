<script setup lang="ts">
/**
 * FollowDetailView — placeholder for the UP主 detail page.
 *
 * The full implementation lands in Phase 2 (per the spec §6.12 design).
 * For Phase 1 we only need the route to resolve so deep links don't 404.
 */
import { useRoute } from 'vue-router'
import { computed } from 'vue'

const route = useRoute()
const uid = computed<string>(() => String(route.params.uid ?? ''))
</script>

<template>
  <section class="follow-detail-placeholder">
    <h2>UP 主详情</h2>
    <p>UID: <code>{{ uid }}</code></p>
    <p>该页面将在 Phase 2 完整实现。</p>
  </section>
</template>

<style scoped>
.follow-detail-placeholder {
  padding: 24px;
  background: var(--surface-elevated);
  border: 1px dashed var(--border-subtle);
  border-radius: var(--radius-md);
  color: var(--text-secondary);
}
</style>