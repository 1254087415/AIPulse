/**
 * Hotspot API client for dashboard records and actions.
 */

import { apiFetch } from '../lib/apiFetch'

export interface HotspotRecord {
  id: string
  title: string
  url: string
  summary: string | null
  source_type: string
  content_id: string | null
  up_name: string | null
  heat_score: number
  importance: string
  category: string | null
  status: string
  decision_status: string
  notified: boolean
  obsidian_source_path: string | null
  obsidian_summary_path: string | null
  learning_event_id: string | null
  created_at: string | null
  published_at: string | null
}

interface HotspotListResponse {
  success: boolean
  data: HotspotRecord[]
  meta: { total: number; page: number; limit: number }
}

interface HotspotActionResponse {
  success: boolean
  data: Record<string, unknown>
}

export interface ListHotspotsOptions {
  decisionStatus?: string
  limit?: number
  page?: number
  sort?: string
  order?: string
}

export async function listHotspots(
  options: ListHotspotsOptions = {},
): Promise<HotspotRecord[]> {
  const query: Record<string, string> = {
    page: String(options.page ?? 1),
    limit: String(options.limit ?? 20),
  }
  if (options.decisionStatus) query.decision_status = options.decisionStatus
  if (options.sort) query.sort = options.sort
  if (options.order) query.order = options.order
  const response = await apiFetch<HotspotListResponse>('/api/hotspots', {
    method: 'GET',
    query,
  })
  return response.data
}

export async function updateHotspotDecision(
  hotspotId: string,
  decisionStatus: string,
): Promise<HotspotRecord> {
  const response = await apiFetch<{ success: boolean; data: HotspotRecord }>(
    `/api/hotspots/${encodeURIComponent(hotspotId)}`,
    {
      method: 'PATCH',
      body: JSON.stringify({ decision_status: decisionStatus }),
    },
  )
  return response.data
}

export async function archiveHotspot(hotspotId: string): Promise<HotspotActionResponse['data']> {
  const response = await apiFetch<HotspotActionResponse>(
    `/api/hotspots/${encodeURIComponent(hotspotId)}/archive`,
    { method: 'POST' },
  )
  return response.data
}

export async function notifyHotspot(hotspotId: string): Promise<HotspotActionResponse['data']> {
  const response = await apiFetch<HotspotActionResponse>(
    `/api/hotspots/${encodeURIComponent(hotspotId)}/notify`,
    { method: 'POST' },
  )
  return response.data
}

export async function retryHotspot(hotspotId: string): Promise<HotspotActionResponse['data']> {
  const response = await apiFetch<HotspotActionResponse>(
    `/api/agent/retry/${encodeURIComponent(hotspotId)}`,
    { method: 'POST' },
  )
  return response.data
}
