import type { Job } from '../types'
import { apiFetch } from './client'

export async function fetchJobs(): Promise<{ data: Job[] }> {
  return apiFetch<{ data: Job[] }>('/scheduler/jobs')
}

export async function runJob(jobId: string): Promise<{ success: boolean }> {
  return apiFetch<{ success: boolean }>(`/scheduler/jobs/${jobId}/run`, { method: 'POST' })
}
