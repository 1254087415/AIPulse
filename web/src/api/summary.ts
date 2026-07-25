import type { SummaryEnqueueResult, SummaryEvent, SummaryJob } from '../types'
import { API_BASE, apiFetch } from './client'

interface SummaryEnvelope {
  data: SummaryJob
}

interface SummaryListEnvelope {
  data: SummaryJob[]
}

interface EnqueueEnvelope {
  data: SummaryEnqueueResult
}

export async function enqueueSummary(videoId: string): Promise<SummaryEnqueueResult> {
  const res = await apiFetch<EnqueueEnvelope>(`/summary/${encodeURIComponent(videoId)}`, {
    method: 'POST',
  })
  return res.data
}

export async function getSummaryJob(jobId: string): Promise<SummaryJob> {
  const res = await apiFetch<SummaryEnvelope>(`/summary/job/${jobId}`)
  return res.data
}

export async function listSummaryJobs(): Promise<SummaryJob[]> {
  const res = await apiFetch<SummaryListEnvelope>('/summary/jobs')
  return res.data
}

export interface SummaryEventHandlers {
  onEvent: (event: SummaryEvent) => void
  onError?: (error: unknown) => void
}

export interface SummaryEventHandle {
  close: () => void
}

export function subscribeSummaryEvents(
  jobId: string,
  handlers: SummaryEventHandlers,
): SummaryEventHandle {
  const url = `${API_BASE}/summary/events/${encodeURIComponent(jobId)}`
  const source = new EventSource(url)

  source.onmessage = (raw) => {
    try {
      const parsed = JSON.parse(raw.data) as SummaryEvent
      handlers.onEvent(parsed)
    } catch (error) {
      handlers.onError?.(error)
    }
  }

  source.onerror = (error) => {
    handlers.onError?.(error)
  }

  return {
    close: () => source.close(),
  }
}