import type { Hotspot } from '../types'
import { apiFetch } from './client'

export const HOTSPOT_PAGE_LIMIT = 20

export interface HotspotListPayload {
  data: Hotspot[]
  meta: { total: number; page: number; limit: number }
}

export async function fetchHotspots(params: Record<string, string> = {}): Promise<HotspotListPayload> {
  const qs = new URLSearchParams(params)
  return apiFetch<HotspotListPayload>(`/hotspots?${qs}`)
}

export async function fetchHotspot(hotspotId: string): Promise<{ data: Hotspot }> {
  return apiFetch<{ data: Hotspot }>(`/hotspots/${hotspotId}`)
}

export async function fetchRelatedHotspots(hotspotId: string): Promise<{ data: Hotspot[] }> {
  return apiFetch<{ data: Hotspot[] }>(`/hotspots/${hotspotId}/related`)
}

export async function archiveHotspot(hotspotId: string): Promise<{ data: { source_note_path: string; summary_note_path: string } }> {
  return apiFetch<{ data: { source_note_path: string; summary_note_path: string } }>(
    `/hotspots/${hotspotId}/archive`,
    { method: 'POST' },
  )
}
