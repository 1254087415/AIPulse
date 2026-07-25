import type { SettingsResponse, SettingsUpdate } from '../types'
import { apiFetch } from './client'

interface SettingsEnvelope {
  data: SettingsResponse
}

export async function fetchSettings(): Promise<SettingsResponse> {
  const res = await apiFetch<SettingsEnvelope>('/settings')
  return res.data
}

export async function updateSettings(payload: SettingsUpdate): Promise<SettingsResponse> {
  const res = await apiFetch<SettingsEnvelope>('/settings', {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return res.data
}