<script setup lang="ts">
import { ref } from 'vue'
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import { fetchJobs, runJob } from '../api/scheduler'
import JobList from '../components/scheduler/JobList.vue'

const queryClient = useQueryClient()
const { data, isLoading } = useQuery({ queryKey: ['jobs'], queryFn: fetchJobs })
const running = ref<Record<string, boolean>>({})

const run = useMutation({
  mutationFn: async (jobId: string) => {
    running.value = { ...running.value, [jobId]: true }
    try {
      return await runJob(jobId)
    } finally {
      running.value = { ...running.value, [jobId]: false }
    }
  },
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ['jobs'] }),
})

function handleRun(jobId: string) {
  run.mutate(jobId)
}
</script>

<template>
  <main>
    <h1>定时任务</h1>
    <p v-if="isLoading">加载中...</p>
    <JobList
      v-else
      :jobs="data?.data ?? []"
      :running="running"
      @run="handleRun"
    />
  </main>
</template>
