import type { Keyword } from '../types'
import { apiFetch } from './client'

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
