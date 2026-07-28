import type {
  FollowedUp,
  FollowedUpCreate,
  FollowedUpHealthSnapshot,
  FollowedUpOverview,
  FollowedUpUpdate,
} from '../types'
import { apiFetch } from './client'

interface FollowedUpEnvelope {
  data: FollowedUp
}

interface FollowedUpListEnvelope {
  data: FollowedUp[]
}

interface FollowedUpOverviewEnvelope {
  data: FollowedUpOverview
}

interface FollowedUpHealthEnvelope {
  data: FollowedUpHealthSnapshot
}

interface DeleteResultEnvelope {
  data: { success: boolean }
}

interface SyncResultEnvelope {
  data: { followed_up_id: string; status: string; message?: string; new_videos?: number }
}

export async function listFollowedUps(): Promise<FollowedUp[]> {
  const res = await apiFetch<FollowedUpListEnvelope>('/followed-up')
  return res.data
}

export async function getFollowedUp(id: string): Promise<FollowedUp> {
  const res = await apiFetch<FollowedUpEnvelope>(`/followed-up/${id}`)
  return res.data
}

export async function createFollowedUp(payload: FollowedUpCreate): Promise<FollowedUp> {
  const res = await apiFetch<FollowedUpEnvelope>('/followed-up', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return res.data
}

export async function updateFollowedUp(
  id: string,
  payload: FollowedUpUpdate,
): Promise<FollowedUp> {
  const res = await apiFetch<FollowedUpEnvelope>(`/followed-up/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return res.data
}

export async function deleteFollowedUp(id: string): Promise<{ success: boolean }> {
  const res = await apiFetch<DeleteResultEnvelope>(`/followed-up/${id}`, {
    method: 'DELETE',
  })
  return res.data
}

export async function syncFollowedUp(
  id: string,
): Promise<SyncResultEnvelope['data']> {
  const res = await apiFetch<SyncResultEnvelope>(`/followed-up/${id}/sync`, {
    method: 'POST',
  })
  return res.data
}

export async function getFollowedUpHealth(id: string): Promise<FollowedUpHealthSnapshot> {
  const res = await apiFetch<FollowedUpHealthEnvelope>(`/followed-up/${id}/health`)
  return res.data
}

export async function getFollowedUpOverview(id: string): Promise<FollowedUpOverview> {
  const res = await apiFetch<FollowedUpOverviewEnvelope>(`/followed-up/${id}/overview`)
  return res.data
}