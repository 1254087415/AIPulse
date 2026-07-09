import type { Hotspot } from '../types'
import { apiFetch } from './client'

export interface HotspotListPayload {
  data: Hotspot[]
  meta: { total: number; page: number; limit: number }
}

export async function fetchHotspots(params: Record<string, string> = {}): Promise<HotspotListPayload> {
  const qs = new URLSearchParams(params)
  return apiFetch<HotspotListPayload>(`/hotspots?${qs}`)
}
