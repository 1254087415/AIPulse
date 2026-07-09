<script setup lang="ts">
import type { Hotspot } from '../../types'
import HotspotCard from './HotspotCard.vue'

const props = defineProps<{ hotspots: Hotspot[]; loading: boolean }>()
</script>

<template>
  <section aria-label="Hotspot list">
    <p v-if="props.loading">加载中...</p>
    <div v-else-if="props.hotspots.length === 0">暂无热点</div>
    <div v-else class="list">
      <HotspotCard
        v-for="hotspot in props.hotspots"
        :key="hotspot.id"
        :hotspot="hotspot"
      />
    </div>
  </section>
</template>

<style scoped>
.list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}
</style>
