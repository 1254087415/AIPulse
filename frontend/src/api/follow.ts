/**
 * followApi — typed wrapper around `/api/followed-up/*` action endpoints.
 *
 * Detail loads go through `api/followDetail.ts` (`fetchOverview`). The
 * helpers below cover the action buttons surfaced by `FollowDetailView`:
 *
 *   - `scanNow`         → `POST   /api/followed-up/{id}/sync`
 *   - `setEnabled`      → `PATCH  /api/followed-up/{id}` body `{enabled}`
 *   - `loadMoreHistory` → `POST   /api/followed-up/{id}/load-more-history`
 *                         (spec §Q19; backend may 404 — caller treats as
 *                         no-op so the UI doesn't break in dev)
 *   - `remove`          → `DELETE /api/followed-up/{id}`
 */
import { apiFetch } from '../lib/apiFetch'

export interface FollowActionResult {
  ok: boolean
  /** Raw response data; shape varies by endpoint. */
  data: Record<string, unknown>
}

export async function scanNow(id: string): Promise<FollowActionResult> {
  const body = await apiFetch<{
    success: boolean
    data: Record<string, unknown>
  }>(`/api/followed-up/${encodeURIComponent(id)}/sync`, {
    method: 'POST',
  })
  return { ok: body.success, data: body.data }
}

export async function setEnabled(
  id: string,
  enabled: boolean,
): Promise<FollowActionResult> {
  const body = await apiFetch<{
    success: boolean
    data: Record<string, unknown>
  }>(`/api/followed-up/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    body: JSON.stringify({ enabled }),
  })
  return { ok: body.success, data: body.data }
}

export async function loadMoreHistory(
  id: string,
  offset = 50,
): Promise<FollowActionResult> {
  try {
    const body = await apiFetch<{
      success: boolean
      data: Record<string, unknown>
    }>(
      `/api/followed-up/${encodeURIComponent(id)}/load-more-history`,
      { method: 'POST', body: JSON.stringify({ offset }) },
    )
    return { ok: body.success, data: body.data }
  } catch {
    // backend may not have the endpoint yet — spec §Q19 says callers should
    // tolerate a no-op rather than blow up.
    return {
      ok: false,
      data: { added: 0, message: 'load-more-history endpoint unavailable' },
    }
  }
}

export async function remove(id: string): Promise<FollowActionResult> {
  const body = await apiFetch<{
    success: boolean
    data: Record<string, unknown>
  }>(`/api/followed-up/${encodeURIComponent(id)}`, {
    method: 'DELETE',
  })
  return { ok: body.success, data: body.data }
}

export const followApi = {
  scanNow,
  setEnabled,
  loadMoreHistory,
  remove,
}
