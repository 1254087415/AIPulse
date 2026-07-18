import type { Keyword } from '../types'
import { apiFetch } from './client'

export interface KeywordUpdatePayload {
  is_active?: boolean
  notify_on_match?: boolean
}

export async function fetchKeywords(): Promise<{ data: Keyword[] }> {
  return apiFetch<{ data: Keyword[] }>('/keywords')
}

export async function createKeyword(value: string): Promise<{ data: Keyword }> {
  return apiFetch<{ data: Keyword }>('/keywords', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ value }),
  })
}

export async function updateKeyword(
  keywordId: string,
  payload: KeywordUpdatePayload,
): Promise<{ data: Keyword }> {
  return apiFetch<{ data: Keyword }>(`/keywords/${keywordId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export async function deleteKeyword(keywordId: string): Promise<{ data: { id: string } }> {
  return apiFetch<{ data: { id: string } }>(`/keywords/${keywordId}`, {
    method: 'DELETE',
  })
}
