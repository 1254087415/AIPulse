import { apiFetch } from '../lib/apiFetch'

export type SummaryJobStatus = 'queued' | 'running' | 'completed' | 'partial' | 'failed' | 'timeout'

export interface SummaryJob {
  id: string
  video_id: string
  title: string | null
  up_name: string | null
  status: SummaryJobStatus | string
  error: string | null
  note_path: string | null
  created_at: string | null
  updated_at?: string | null
  hotspot_id?: string | null
}

export interface SummaryJobListOptions {
  limit?: number
  status?: string
}

interface SummaryJobListResponse {
  success: boolean
  data: SummaryJob[]
}

export async function listSummaryJobs(
  options: SummaryJobListOptions = {},
): Promise<SummaryJob[]> {
  const query: Record<string, string> = {
    limit: String(options.limit ?? 20),
  }
  if (options.status) query.status = options.status
  const response = await apiFetch<SummaryJobListResponse>('/api/summary/jobs', {
    method: 'GET',
    query,
  })
  return response.data
}

export interface Hotspot {
  id: string
  content_id?: string | null
  video_id?: string | null
  title?: string | null
  up_name?: string | null
  source?: string | null
  decision_status?: string | null
  created_at?: string | null
}

interface HotspotListResponse {
  success: boolean
  data: Hotspot[]
}

export async function listPendingHotspots(): Promise<Hotspot[]> {
  const response = await apiFetch<HotspotListResponse>('/api/hotspots', {
    method: 'GET',
    query: { decision_status: 'pending', page: '1', limit: '20' },
  })
  return response.data.filter((hotspot) => hotspot.decision_status === 'pending')
}
