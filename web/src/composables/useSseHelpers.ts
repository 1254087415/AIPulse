import { type Ref } from 'vue'
import { API_BASE } from '../api/client'

export type SseStatus = 'connecting' | 'open' | 'closed' | 'error'

export interface EventHandlerConfig {
  type: string
  invalidate: Array<{ queryKey: unknown[]; exact?: boolean }>
}

const SSE_EVENT_HANDLERS: EventHandlerConfig[] = [
  {
    type: 'hotspot.new',
    invalidate: [{ queryKey: ['hotspots'], exact: false }],
  },
  {
    type: 'hotspot.updated',
    invalidate: [
      { queryKey: ['hotspots'], exact: false },
      { queryKey: ['hotspot'], exact: false },
    ],
  },
  {
    type: 'digest.ready',
    invalidate: [
      { queryKey: ['digests'], exact: false },
      { queryKey: ['digest', 'latest'], exact: false },
    ],
  },
  {
    type: 'sync.completed',
    invalidate: [
      { queryKey: ['sources'], exact: false },
      { queryKey: ['jobs'], exact: false },
    ],
  },
]

const INITIAL_RECONNECT_DELAY_MS = 1000
const MAX_RECONNECT_DELAY_MS = 30000

export interface UseSseControllerOptions {
  path: string
  status: Ref<SseStatus>
  invalidateQueries: (options: { queryKey: unknown[]; exact?: boolean }) => void
}

export interface UseSseController {
  start: () => void
  stop: () => void
}

export function createUseSseController(options: UseSseControllerOptions): UseSseController {
  const { path, status, invalidateQueries } = options

  let eventSource: EventSource | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let isActive = false
  let reconnectDelay = INITIAL_RECONNECT_DELAY_MS
  const eventHandlers = new Map<string, () => void>()

  const clearReconnectTimer = () => {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
  }

  const getEventHandler = (type: string): (() => void) => {
    let handler = eventHandlers.get(type)
    if (!handler) {
      handler = () => {
        const config = SSE_EVENT_HANDLERS.find((item) => item.type === type)
        if (!config) return

        for (const invalidateOptions of config.invalidate) {
          invalidateQueries(invalidateOptions)
        }
      }
      eventHandlers.set(type, handler)
    }
    return handler
  }

  const handleOpen = () => {
    status.value = 'open'
    reconnectDelay = INITIAL_RECONNECT_DELAY_MS
  }

  const handleError = () => {
    if (!isActive || !eventSource) return

    if (eventSource.readyState === EventSource.OPEN) {
      return
    }

    status.value = 'error'

    eventSource.close()
    clearReconnectTimer()

    reconnectTimer = setTimeout(() => {
      reconnectDelay = Math.min(reconnectDelay * 2, MAX_RECONNECT_DELAY_MS)
      connect()
    }, reconnectDelay)
  }

  const detachListeners = (source: EventSource) => {
    source.removeEventListener('open', handleOpen)
    source.removeEventListener('error', handleError)

    for (const { type } of SSE_EVENT_HANDLERS) {
      source.removeEventListener(type, getEventHandler(type))
    }
  }

  const connect = () => {
    if (!isActive) return

    clearReconnectTimer()

    if (eventSource) {
      detachListeners(eventSource)
      eventSource.close()
    }

    status.value = 'connecting'

    eventSource = new EventSource(`${API_BASE}${path}`)
    eventSource.addEventListener('open', handleOpen)
    eventSource.addEventListener('error', handleError)

    for (const { type } of SSE_EVENT_HANDLERS) {
      eventSource.addEventListener(type, getEventHandler(type))
    }
  }

  const start = () => {
    isActive = true
    connect()
  }

  const stop = () => {
    isActive = false
    clearReconnectTimer()

    if (eventSource) {
      detachListeners(eventSource)
      eventSource.close()
      eventSource = null
    }

    status.value = 'closed'
  }

  return { start, stop }
}
