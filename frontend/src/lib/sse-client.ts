/**
 * sse-client — typed wrapper around `EventSource` for the AIPulse backend.
 *
 * The backend serves SSE on `/api/summary/events/{job_id}` using the
 * `sse_starlette` convention: each event carries an `event:` name and a
 * JSON-serialised `data:` payload. Vitest injects a `MockEventSource` on
 * `globalThis` so the production path can be unit-tested without a network.
 */

export interface SseHandler<TPayload = unknown> {
  /** SSE event name to listen for (matches the `event:` field server-side). */
  event: string
  /** Receives the JSON-decoded payload. */
  handler: (payload: TPayload) => void
}

interface MinimalEventSource {
  addEventListener(name: string, cb: (ev: { data: string }) => void): void
  removeEventListener(name: string, cb: (ev: { data: string }) => void): void
  close(): void
}

/**
 * Open an SSE subscription to `url` and wire the given handlers to the
 * matching `event:` names.
 *
 * Returns a teardown `() => void` that callers invoke on `onBeforeUnmount`
 * to release the underlying `EventSource` and its listeners.
 *
 * If the current environment does not provide an `EventSource` constructor
 * (jsdom, node test runner, server-side render) the function returns a
 * noop teardown. Components can still mount; the UI falls back to the
 * follower's HTTP polling path or a manual refresh.
 */
export function subscribeSse<TPayload = unknown>(
  url: string,
  handlers: SseHandler<TPayload>[],
): () => void {
  const EventSourceCtor = (globalThis as unknown as { EventSource?: typeof MinimalEventSource })
    .EventSource
  if (!EventSourceCtor) {
    // jsdom / server-side render — UI falls back to manual refresh or polling
    return () => {
      /* noop */
    }
  }
  const source = new EventSourceCtor(url)
  const listeners: Array<{
    name: string
    cb: (ev: { data: string }) => void
  }> = []

  for (const h of handlers) {
    const cb = (ev: { data: string }) => {
      try {
        h.handler(JSON.parse(ev.data) as TPayload)
      } catch {
        // Non-JSON payloads are ignored on purpose; the typed handler wins.
      }
    }
    source.addEventListener(h.event, cb)
    listeners.push({ name: h.event, cb })
  }

  return function teardown() {
    for (const { name, cb } of listeners) {
      try {
        source.removeEventListener(name, cb)
      } catch {
        /* noop */
      }
    }
    try {
      source.close()
    } catch {
      /* noop */
    }
  }
}
