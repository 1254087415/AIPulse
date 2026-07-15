export const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api'

export class ApiError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

const REQUEST_TIMEOUT_MS = 10000

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS)

  try {
    const response = await fetch(`${API_BASE}${path}`, { ...init, signal: controller.signal })
    if (!response.ok) {
      throw new ApiError(`API request failed: ${response.statusText}`, response.status)
    }
    const body = await response.json()
    if (body && typeof body === 'object' && 'success' in body && body.success === false) {
      throw new ApiError(body.error || 'API error', response.status)
    }
    return body as T
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') {
      throw new Error('请求超时，请检查后端服务')
    }
    throw error
  } finally {
    clearTimeout(timeoutId)
  }
}
