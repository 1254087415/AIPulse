import type { Source } from '../types'
import { apiFetch } from './client'

export interface SourceUpdatePayload {
  config?: Record<string, unknown>
  default_weight?: number
  fetch_interval_minutes?: number
  is_active?: boolean
}

export async function fetchSources(): Promise<{ data: Source[] }> {
  return apiFetch<{ data: Source[] }>('/sources')
}

export async function updateSource(
  sourceId: string,
  payload: SourceUpdatePayload,
): Promise<{ data: Source }> {
  return apiFetch<{ data: Source }>(`/sources/${sourceId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export async function syncSource(sourceId: string): Promise<{ data: { job_id: string; source_id: string } }> {
  return apiFetch<{ data: { job_id: string; source_id: string } }>(`/sources/${sourceId}/sync`, {
    method: 'POST',
  })
}
