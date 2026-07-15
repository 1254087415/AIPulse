import type { DailyDigest } from '../types'
import { apiFetch } from './client'

export async function fetchDigests(limit = 30): Promise<{ data: DailyDigest[] }> {
  return apiFetch<{ data: DailyDigest[] }>(`/digests?limit=${limit}`)
}

export async function fetchLatestDigest(): Promise<{ data: DailyDigest }> {
  return apiFetch<{ data: DailyDigest }>('/digests/latest')
}

export async function generateDigest(): Promise<{ data: DailyDigest }> {
  return apiFetch<{ data: DailyDigest }>('/digests/generate', { method: 'POST' })
}
