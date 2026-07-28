/**
 * Settings store — read-only accessors for the AIPulse frontend configuration.
 *
 * Why a separate module: the production Tauri webview stores the API token
 * inside the same `settings` table the desktop app uses. For Phase 1 we keep
 * the access path tiny and dependency-free so tests can stub it via
 * `vi.mock('../../src/lib/settings-store', ...)`.
 *
 * Future: replace this stub with a real Pinia store that fetches settings from
 * the FastAPI backend through `invoke('get_settings')` on app startup.
 */

const API_TOKEN_STORAGE_KEY = 'aipulse.apiToken'
const ENV_API_TOKEN =
  import.meta.env.VITE_API_TOKEN || import.meta.env.AIPULSE_API_TOKEN || ''

/**
 * Returns the configured AIPulse API token, or an empty string when none is
 * configured (local dev mode where the backend skips auth).
 *
 * Reads from `localStorage` so the value survives reloads inside the Tauri
 * webview without needing a round-trip to the sidecar on every request.
 */
export function getApiToken(): string {
  if (typeof window === 'undefined') return ''
  try {
    const value = window.localStorage.getItem(API_TOKEN_STORAGE_KEY)
    return value ?? ENV_API_TOKEN
  } catch {
    return ENV_API_TOKEN
  }
}

/**
 * Persist the API token from the Settings panel.
 *
 * Side effect only; callers are expected to also propagate to the backend
 * via the existing `update_settings` Tauri command.
 */
export function setApiToken(token: string): void {
  if (typeof window === 'undefined') return
  try {
    if (token) {
      window.localStorage.setItem(API_TOKEN_STORAGE_KEY, token)
    } else {
      window.localStorage.removeItem(API_TOKEN_STORAGE_KEY)
    }
  } catch {
    // Ignore storage failures — auth will simply not be sent.
  }
}