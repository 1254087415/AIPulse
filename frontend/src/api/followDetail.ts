/**
 * Followed-up detail API client (spec §6.12, Q20).
 *
 * Two distinct endpoints power the FollowDetailView:
 *
 *   GET /api/followed-up/{key}/detail
 *     → FollowedUpDetail  (header / meta / collections[] / avatar / enabled)
 *
 *   GET /api/followed-up/{key}/videos?offset=&limit=&collection_id=
 *     → { items: FollowedUpVideo[], nextOffset: number | null }
 *
 * Both endpoints accept either the row's database UUID or — when the canonical
 * call 404s — the platform uid via the `/by-uid/bilibili/{uid}/...` alias. The
 * helper hides the fallback so the UI does not need to know which key it has.
 */

import { apiFetch, ApiError } from '../lib/apiFetch'

export type FollowedUpHealth = 'healthy' | 'warning' | 'error'
export type FollowedUpStrategy = 'uapi' | 'html'

export interface FollowedUpCollectionVideo {
  bvid: string
  title: string
  status: string
  hotspot_id: string
  collection_id?: string | null
  published_at?: string | null
}

export interface FollowedUpCollection {
  id: string
  title: string
  description: string | null
  video_count: number
  videos: FollowedUpCollectionVideo[]
}

export interface FollowedUpDetail {
  id: string
  /** Display name (a.k.a. display_name on the row) */
  name: string
  /** Platform uid (B站 mid etc.) */
  mid: string
  /** Canonical profile URL */
  url: string
  /** Resolved avatar URL (empty string when unavailable) */
  avatar: string
  health: FollowedUpHealth
  enabled: boolean
  strategy: FollowedUpStrategy
  interval_minutes: number
  last_checked_at: string | null
  last_error: string | null
  collections: FollowedUpCollection[]
  orphan_videos: FollowedUpCollectionVideo[]
}

export interface FollowedUpVideo {
  bvid: string
  title: string
  collection_id: string | null
  status: string
  published_at: string | null
  hotspot_id: string
}

export interface FollowedUpVideoList {
  items: FollowedUpVideo[]
  nextOffset: number | null
}

const DEFAULT_PLATFORM = 'bilibili'

/** Canonical + uid-alias fallback for the legacy /overview payload.
 *
 * The new detail endpoint at /detail supersedes this; older views (and the
 * existing follow-detail-api R2#2 tests) still use /overview, so we keep
 * the helper for backward compatibility. Round 8+ should migrate the
 * remaining callers to /detail and remove this shim.
 */
export interface FollowedUpOverview {
  id: string
  platform: string
  uid: string
  display_name: string
  profile_url: string
  health: {
    health: 'healthy' | 'warning' | 'error'
    last_checked_at: string | null
    last_error: string | null
    failed_at: string | null
    is_active: boolean
    fetch_interval_minutes: number
    status: 'active' | 'paused' | 'auth_failed'
  }
  config: Record<string, unknown>
  recent_jobs: Array<{
    id: string
    video_id: string
    status: string
    title: string | null
    created_at: string | null
    completed_at: string | null
    error: string | null
    note_path: string | null
  }>
  recent_learning_events: Array<{
    id: string
    title: string | null
    scheduled_at: string | null
    learning_status: string
    summary_note_path: string | null
    platform: string
  }>
  recent_collections: Array<{
    id: string
    title: string
    platform_collection_id: string
    description: string | null
    video_count: number
    created_at: string
  }>
}

export async function fetchOverview(key: string): Promise<FollowedUpOverview> {
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

/** Canonical + uid-alias fallback for /detail. */
export async function fetchDetail(key: string): Promise<FollowedUpDetail> {
  try {
    const response = await apiFetch<{ success: boolean; data: FollowedUpDetail }>(
      `/api/followed-up/${encodeURIComponent(key)}/detail`,
    )
    return response.data
  } catch (error: unknown) {
    if (!(error instanceof ApiError) || error.status !== 404) {
      throw error
    }
  }
  const alias = await apiFetch<{ success: boolean; data: FollowedUpDetail }>(
    `/api/followed-up/by-uid/${encodeURIComponent(DEFAULT_PLATFORM)}/${encodeURIComponent(key)}/detail`,
  )
  return alias.data
}

/** Canonical + uid-alias fallback for /videos pagination. */
export async function listVideos(
  key: string,
  opts: { offset: number; limit: number; collection_id?: string | null } = {
    offset: 0,
    limit: 20,
  },
): Promise<FollowedUpVideoList> {
  const query: Record<string, string> = {
    offset: String(opts.offset),
    limit: String(opts.limit),
  }
  if (opts.collection_id !== undefined && opts.collection_id !== null) {
    query.collection_id = opts.collection_id
  }
  const callCanonical = () =>
    apiFetch<{ success: boolean; data: FollowedUpVideoList }>(
      `/api/followed-up/${encodeURIComponent(key)}/videos`,
      { query },
    )
  try {
    const response = await callCanonical()
    return response.data
  } catch (error: unknown) {
    if (!(error instanceof ApiError) || error.status !== 404) {
      throw error
    }
  }
  const alias = await apiFetch<{ success: boolean; data: FollowedUpVideoList }>(
    `/api/followed-up/by-uid/${encodeURIComponent(DEFAULT_PLATFORM)}/${encodeURIComponent(key)}/videos`,
    { query },
  )
  return alias.data
}
