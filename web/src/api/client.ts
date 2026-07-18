export const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api'
export const API_TOKEN = import.meta.env.VITE_API_TOKEN || ''

export class ApiError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

const REQUEST_TIMEOUT_MS = 10000
const DEFAULT_ERROR_MESSAGE = '请求失败，请稍后重试'

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS)

  const headers: Record<string, string> = {}
  if (API_TOKEN) {
    headers['X-AIPulse-Token'] = API_TOKEN
  }
  if (init?.headers) {
    const initHeaders = init.headers as Record<string, string>
    for (const key of Object.keys(initHeaders)) {
      headers[key] = initHeaders[key]
    }
  }

  try {
    const response = await fetch(`${API_BASE}${path}`, { ...init, headers, signal: controller.signal })
    if (!response.ok) {
      throw new ApiError(DEFAULT_ERROR_MESSAGE, response.status)
    }
    const body = await response.json()
    if (body && typeof body === 'object' && 'success' in body && body.success === false) {
      throw new ApiError(body.error || DEFAULT_ERROR_MESSAGE, response.status)
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
