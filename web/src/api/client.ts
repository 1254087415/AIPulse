export const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api'

export class ApiError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init)
  if (!response.ok) {
    throw new ApiError(`API request failed: ${response.statusText}`, response.status)
  }
  const body = await response.json()
  if (body && typeof body === 'object' && 'success' in body && body.success === false) {
    throw new ApiError(body.error || 'API error', response.status)
  }
  return body as T
}
