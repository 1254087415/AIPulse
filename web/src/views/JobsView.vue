<script setup lang="ts">
import { ref } from 'vue'
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import { fetchJobs, runJob, pauseJob, resumeJob, fetchLogs } from '../api/scheduler'
import JobList from '../components/scheduler/JobList.vue'

const queryClient = useQueryClient()
const { data: jobs, isLoading, error } = useQuery({ queryKey: ['jobs'], queryFn: fetchJobs })
const { data: logs } = useQuery({ queryKey: ['scheduler', 'logs'], queryFn: () => fetchLogs(20) })
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

const pause = useMutation({
  mutationFn: pauseJob,
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ['jobs'] }),
})

const resume = useMutation({
  mutationFn: resumeJob,
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ['jobs'] }),
})

function handleRun(jobId: string) {
  run.mutate(jobId)
}

function handlePause(jobId: string) {
  pause.mutate(jobId)
}

function handleResume(jobId: string) {
  resume.mutate(jobId)
}
</script>

<template>
  <div class="page">
    <header class="page-header">
      <div class="page-title">
        <h1>定时任务</h1>
        <p class="subtitle">同步与摘要的调度状态</p>
      </div>
    </header>

    <div v-if="isLoading" class="state state-loading" role="status" aria-live="polite">
      正在同步信号…
    </div>

    <div v-else-if="error" class="state state-error" role="alert" aria-live="polite">
      任务接口异常：{{ (error as Error).message }}。请检查后端服务是否运行。
    </div>

    <JobList
      v-else-if="!error"
      :jobs="jobs?.data ?? []"
      :running="running"
      :logs="logs?.data ?? []"
      @run="handleRun"
      @pause="handlePause"
      @resume="handleResume"
    />
  </div>
</template>
