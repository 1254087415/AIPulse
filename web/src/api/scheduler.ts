import type { Job } from '../types'
import { apiFetch } from './client'

export interface SchedulerLog {
  id: string
  job_id: string
  job_name: string | null
  status: string
  started_at: string | null
  finished_at: string | null
  message: string | null
  exception: string | null
}

export async function fetchJobs(): Promise<{ data: Job[] }> {
  return apiFetch<{ data: Job[] }>('/scheduler/jobs')
}

export async function runJob(jobId: string): Promise<{ success: boolean }> {
  return apiFetch<{ success: boolean }>(`/scheduler/jobs/${jobId}/run`, { method: 'POST' })
}

export async function pauseJob(jobId: string): Promise<{ success: boolean }> {
  return apiFetch<{ success: boolean }>(`/scheduler/jobs/${jobId}/pause`, { method: 'POST' })
}

export async function resumeJob(jobId: string): Promise<{ success: boolean }> {
  return apiFetch<{ success: boolean }>(`/scheduler/jobs/${jobId}/resume`, { method: 'POST' })
}

export async function fetchLogs(limit = 50): Promise<{ data: SchedulerLog[] }> {
  return apiFetch<{ data: SchedulerLog[] }>(`/scheduler/logs?limit=${limit}`)
}
