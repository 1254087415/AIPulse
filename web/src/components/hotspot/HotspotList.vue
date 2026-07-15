<script setup lang="ts">
import type { Hotspot } from '../../types'
import HotspotCard from './HotspotCard.vue'

const props = defineProps<{ hotspots: Hotspot[]; loading?: boolean }>()
</script>

<template>
  <section aria-label="热点列表" class="list">
    <p v-if="props.loading" class="state state-loading" role="status" aria-live="polite">正在同步信号…</p>
    <HotspotCard
      v-for="(hotspot, index) in props.hotspots"
      :key="hotspot.id"
      :hotspot="hotspot"
      :style="{ animationDelay: `${index * 40}ms` }"
      class="card-enter"
    />
  </section>
</template>

<style scoped>
.list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.card-enter {
  opacity: 0;
  transform: translateY(8px);
  animation: cardIn 0.35s ease forwards;
}

@media (prefers-reduced-motion: reduce) {
  .card-enter {
    opacity: 1;
    transform: none;
    animation: none;
  }
}

@keyframes cardIn {
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
