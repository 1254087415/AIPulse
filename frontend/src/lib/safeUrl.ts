/**
 * safeHref — sanitize a backend-supplied URL before binding to `<a :href>`.
 *
 * Vue does not sanitize dynamic href values. A backend field that ever
 * contains `javascript:`, `data:text/html`, or `vbscript:` would be
 * executed when the link is clicked. We only allow `http:` and `https:`
 * schemes and return `null` for anything else so callers can render a
 * plain text fallback.
 */

const ALLOWED_SCHEMES = new Set(['http:', 'https:'])

export function safeHref(raw: string | null | undefined): string | null {
  if (!raw) return null
  const trimmed = raw.trim()
  if (!trimmed) return null
  try {
    const url = new URL(trimmed)
    if (!ALLOWED_SCHEMES.has(url.protocol)) return null
    return url.toString()
  } catch {
    return null
  }
}

export function isSafeHttpUrl(raw: string | null | undefined): boolean {
  return safeHref(raw) !== null
}