class MockEventSource {
  url = ''
  listeners: Record<string, ((event: MessageEvent) => void)[]> = {}
  constructor(url: string) {
    this.url = url
  }
  addEventListener(event: string, handler: (event: MessageEvent) => void) {
    if (!this.listeners[event]) this.listeners[event] = []
    this.listeners[event].push(handler)
  }
  removeEventListener() {}
  close() {}
}

Object.defineProperty(globalThis, 'EventSource', {
  value: MockEventSource,
  writable: true,
})
