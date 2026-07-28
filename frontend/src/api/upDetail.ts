import { apiFetch } from '../lib/apiFetch'
import type { FollowedUp } from './followedUp'

export interface UpHotspot {
  id: string
  title: string
  url: string
  canonical_url: string
  summary: string | null
  source_type: string
  published_at: string | null
  created_at: string | null
  heat_score: number
}

export interface UpSyncHistory {
  id: string
  video_id: string
  title: string | null
  status: string
  error: string | null
  created_at: string | null
  started_at: string | null
  completed_at: string | null
}

export async function fetchUpDetail(uid: string): Promise<FollowedUp> {
  const response = await apiFetch<{ success: boolean; data: FollowedUp }>(
    `/api/followed-up/${encodeURIComponent(uid)}`,
  )
  return response.data
}

export async function fetchUpHotspots(uid: string): Promise<UpHotspot[]> {
  const response = await apiFetch<{ success: boolean; data: UpHotspot[] }>(
    `/api/followed-up/${encodeURIComponent(uid)}/hotspots`,
  )
  return response.data
}

export async function fetchUpSyncHistory(uid: string): Promise<UpSyncHistory[]> {
  const response = await apiFetch<{ success: boolean; data: UpSyncHistory[] }>(
    `/api/followed-up/${encodeURIComponent(uid)}/sync-history`,
  )
  return response.data
}
