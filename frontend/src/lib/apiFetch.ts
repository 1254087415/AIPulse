/**
 * apiFetch — typed `fetch` wrapper for the AIPulse REST API.
 *
 * Responsibilities:
 *  1. Append `Authorization: Bearer <token>` when a token is configured.
 *  2. Default `Content-Type` to `application/json` for non-GET requests.
 *  3. Resolve to the parsed JSON body on 2xx responses.
 *  4. Reject with a typed `ApiError` (status + body) on non-2xx responses.
 *
 * The base URL is intentionally relative so the Tauri webview resolves the
 * request against the embedded FastAPI sidecar. In local development the
 * Vite dev server proxies `/api/*` to `http://127.0.0.1:<port>`.
 */

import { getApiToken } from './settings-store'

export interface ApiFetchOptions extends Omit<RequestInit, 'headers'> {
  headers?: HeadersInit
  /** Skip the Authorization header even when a token is configured. */
  skipAuth?: boolean
  /** Query string parameters appended to the URL before sending. */
  query?: Record<string, string>
}

export class ApiError extends Error {
  readonly status: number
  readonly body: unknown

  constructor(status: number, body: unknown, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.body = body
  }
}

function buildHeaders(
  token: string,
  skipAuth: boolean,
  providedHeaders: HeadersInit | undefined,
  method: string,
): Headers {
  const headers = new Headers(providedHeaders ?? {})

  if (!skipAuth && token) {
    headers.set('Authorization', `Bearer ${token}`)
  }

  // Default Content-Type for requests that carry a body.
  if (method !== 'GET' && method !== 'HEAD' && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }

  return headers
}

async function parseBody(response: Response): Promise<unknown> {
  const contentType = response.headers.get('Content-Type') ?? ''
  if (contentType.includes('application/json')) {
    try {
      return await response.json()
    } catch {
      return null
    }
  }
  try {
    return await response.text()
  } catch {
    return null
  }
}

/**
 * Resolve a possibly-relative URL against the current document location.
 * Browser + Tauri webview already resolve `/api/...` against the embedded
 * sidecar, but jsdom's `fetch` requires an absolute URL.
 */
function resolveUrl(input: string): string {
  if (/^https?:\/\//i.test(input)) return input
  if (typeof window !== 'undefined' && window.location?.origin) {
    return new URL(input, window.location.origin).toString()
  }
  return input
}

function appendQuery(input: string, query: Record<string, string> | undefined): string {
  if (!query) return input
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== null) {
      params.append(key, value)
    }
  }
  const qs = params.toString()
  if (!qs) return input
  return input.includes('?') ? `${input}&${qs}` : `${input}?${qs}`
}

export async function apiFetch<T = unknown>(
  input: string,
  options: ApiFetchOptions = {},
): Promise<T> {
  const { headers, skipAuth = false, method = 'GET', query, ...rest } = options
  const token = skipAuth ? '' : getApiToken()
  const finalHeaders = buildHeaders(token, skipAuth, headers, String(method).toUpperCase())
  const finalUrl = appendQuery(input, query)

  const response = await fetch(resolveUrl(finalUrl), {
    ...rest,
    method,
    headers: finalHeaders,
  })

  const body = await parseBody(response)

  if (!response.ok) {
    throw new ApiError(
      response.status,
      body,
      `API request failed with ${response.status} ${response.statusText}`,
    )
  }

  return body as T
}