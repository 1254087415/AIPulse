/**
 * followedUp API client — typed wrapper around the REST endpoints for the
 * v0.3 follow-ups feature.
 *
 * The shape mirrors the Pydantic schema described in spec §3.1 — the backend
 * returns the full record on create / update so callers can refresh their
 * caches without a follow-up GET.
 */

import { apiFetch } from '../lib/apiFetch'

export type FollowedUpPlatform = 'bilibili' | 'wechat_mp' | 'douyin' | 'xiaohongshu'

export type FollowedUpStatus = 'active' | 'paused' | 'auth_failed'

export type FollowedUpHealth = 'healthy' | 'warning' | 'error'

export type FollowedUpCollectorStrategy = 'uapi' | 'html'

export interface FollowedUp {
  id: string
  platform: FollowedUpPlatform
  uid: string
  display_name: string
  profile_url: string
  collector_strategy: FollowedUpCollectorStrategy
  last_cursor_id: string | null
  fetch_interval_minutes: number
  is_active: boolean
  status: FollowedUpStatus
  health: FollowedUpHealth
  last_checked_at: string | null
  last_error: string | null
  failed_at: string | null
  created_at: string
  updated_at: string
  deleted_at: string | null
  config?: Record<string, unknown>
}

export interface FollowedUpCreate {
  platform: FollowedUpPlatform
  uid: string
  collector_strategy?: FollowedUpCollectorStrategy
  fetch_interval_minutes?: number
  display_name?: string
  profile_url?: string
  config?: Record<string, unknown>
}

export interface FollowedUpUpdate {
  collector_strategy?: FollowedUpCollectorStrategy
  fetch_interval_minutes?: number
  is_active?: boolean
  display_name?: string
  profile_url?: string
  config?: Record<string, unknown>
}

export interface FollowedUpValidation {
  valid: boolean
  display_name?: string
  avatar_url?: string | null
  message?: string
}

export interface FollowedUpListResponse {
  items: FollowedUp[]
  total: number
}

export interface FollowedUpSyncResponse {
  queued: boolean
  scan_id: string
}

export interface FollowedUpListOptions {
  includeDeleted?: boolean
}

function buildUrl(path: string, query?: Record<string, string>): string {
  if (!query) return path
  const params = new URLSearchParams(query)
  return `${path}?${params.toString()}`
}

export async function listFollowed(
  options: FollowedUpListOptions = {},
): Promise<FollowedUp[]> {
  const query: Record<string, string> = {}
  if (options.includeDeleted) {
    query.include_deleted = 'true'
  }
  const hasQuery = Object.keys(query).length > 0
  const url = buildUrl('/api/followed-up', hasQuery ? query : undefined)
  const response = await apiFetch<FollowedUpListResponse>(url, {
    method: 'GET',
    ...(hasQuery ? { query } : {}),
  })
  return response.items
}

export async function createFollowed(payload: FollowedUpCreate): Promise<FollowedUp> {
  return apiFetch<FollowedUp>('/api/followed-up', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function getFollowed(id: string): Promise<FollowedUp> {
  return apiFetch<FollowedUp>(`/api/followed-up/${encodeURIComponent(id)}`, {
    method: 'GET',
  })
}

export async function updateFollowed(id: string, payload: FollowedUpUpdate): Promise<FollowedUp> {
  return apiFetch<FollowedUp>(`/api/followed-up/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export async function deleteFollowed(id: string): Promise<void> {
  await apiFetch<{ ok: boolean }>(`/api/followed-up/${encodeURIComponent(id)}`, {
    method: 'DELETE',
  })
}

export async function validateFollowed(payload: FollowedUpCreate): Promise<FollowedUpValidation> {
  return apiFetch<FollowedUpValidation>('/api/followed-up/validate', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function syncFollowed(id: string): Promise<FollowedUpSyncResponse> {
  return apiFetch<FollowedUpSyncResponse>(
    `/api/followed-up/${encodeURIComponent(id)}/sync`,
    { method: 'POST' },
  )
}