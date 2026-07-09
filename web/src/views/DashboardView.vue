<script setup lang="ts">
import { ref } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { fetchHotspots } from '../api/hotspots'
import HotspotList from '../components/hotspot/HotspotList.vue'
import { useSse } from '../composables/useSse'

const page = ref(1)
const { data, isLoading, error } = useQuery({
  queryKey: ['hotspots', page],
  queryFn: () => fetchHotspots({ page: String(page.value), limit: '20' }),
})
useSse('/sse/hotspots')
</script>

<template>
  <main>
    <h1>AI 热点</h1>
    <p v-if="error" role="alert">加载失败：{{ (error as Error).message }}</p>
    <HotspotList :hotspots="data?.data ?? []" :loading="isLoading" />
  </main>
</template>
