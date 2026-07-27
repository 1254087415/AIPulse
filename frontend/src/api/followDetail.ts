/**
 * FollowedUp 详情页 API client — typed wrapper around `/api/followed-up/{id}/overview`.
 *
 * Spec §6.12 + backend route GET /api/followed-up/{followed_up_id}/overview.
 *
 * Phase 8 R2#2: The dashboard's URL may carry either the row's database
 * UUID (linked from the FollowCard on FollowListPanel) or the platform uid
 * (B站 mid) when callers hand-edit URLs in the address bar. We try the db-id
 * endpoint first and fall back to the uid alias when it 404s — both paths
 * serve the same payload, so the UI never has to branch.
 */

import { apiFetch, ApiError } from '../lib/apiFetch'

export interface FollowedUpHealth {
  health: 'healthy' | 'warning' | 'error'
  last_checked_at: string | null
  last_error: string | null
  failed_at: string | null
  is_active: boolean
  fetch_interval_minutes: number
  status: 'active' | 'paused' | 'auth_failed'
}

export interface RecentCollection {
  id: string
  title: string
  platform_collection_id: string
  description: string | null
  video_count: number
  created_at: string
}

export interface RecentJob {
  id: string
  video_id: string
  status: string
  title: string | null
  created_at: string | null
  completed_at: string | null
  error: string | null
  note_path: string | null
}

export interface RecentLearningEvent {
  id: string
  title: string | null
  scheduled_at: string | null
  learning_status: string
  summary_note_path: string | null
  platform: string
}

export interface FollowedUpOverview {
  id: string
  platform: string
  uid: string
  display_name: string
  profile_url: string
  health: FollowedUpHealth
  config: Record<string, unknown>
  recent_jobs: RecentJob[]
  recent_learning_events: RecentLearningEvent[]
  recent_collections: RecentCollection[]
}

/** Default platform for the v0.3 /by-uid alias lookup. */
const DEFAULT_PLATFORM = 'bilibili'

export async function fetchOverview(key: string): Promise<FollowedUpOverview> {
  // Try the db-id endpoint first — most internal callers (FollowCard) hand
  // us a UUID. If that returns 404, assume the key is a platform uid and
  // re-query via the alias route.
  try {
    const response = await apiFetch<{ success: boolean; data: FollowedUpOverview }>(
      `/api/followed-up/${encodeURIComponent(key)}/overview`,
    )
    return response.data
  } catch (error: unknown) {
    if (!(error instanceof ApiError) || error.status !== 404) {
      throw error
    }
  }

  const alias = await apiFetch<{ success: boolean; data: FollowedUpOverview }>(
    `/api/followed-up/by-uid/${encodeURIComponent(DEFAULT_PLATFORM)}/${encodeURIComponent(key)}/overview`,
  )
  return alias.data
}