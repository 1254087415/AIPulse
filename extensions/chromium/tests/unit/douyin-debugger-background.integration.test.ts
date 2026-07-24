/**
 * Integration tests for DOUYIN_DEBUGGER_HOVER via background.handleMessage.
 *
 * These tests use the REAL dispatchTrustedHover (not mocked) and real
 * chrome.debugger.* mocks (as Promises), verifying:
 *  - The internal DebuggerApi adapter correctly converts tabId (string→number)
 *  - chrome.debugger.attach is called with {tabId:123},'1.3'
 *  - chrome.debugger.sendCommand is called with {tabId:123},'Input.dispatchMouseEvent',
 *    {type:'mouseMoved',x:10,y:20,button:'none',clickCount:0}
 *  - chrome.debugger.detach is called with {tabId:123}
 *  - sendResponse is called with the correct async result
 *  - attach conflict (another debugger) returns fallback:true
 *
 * This file has NO vi.mock of douyin-debugger — it loads the real module.
 */

import { describe, expect, it, vi, beforeEach, afterEach, type Mock } from 'vitest';

// ---------------------------------------------------------------------------
// Helper types
// ---------------------------------------------------------------------------

type Listener = (...args: unknown[]) => unknown;

function createMockEvent() {
  const listeners: Listener[] = [];
  return {
    addListener: vi.fn((listener: Listener) => listeners.push(listener)),
    removeListener: vi.fn((listener: Listener) => {
      const idx = listeners.indexOf(listener);
      if (idx >= 0) listeners.splice(idx, 1);
    }),
    dispatch: (...args: unknown[]) => listeners.forEach((listener) => listener(...args)),
    listeners,
  };
}

type MockEvent = ReturnType<typeof createMockEvent>;

function createMockPort(): chrome.runtime.Port {
  return {
    name: '',
    disconnect: vi.fn(),
    postMessage: vi.fn(),
    onMessage: createMockEvent() as unknown as chrome.runtime.PortMessageEvent,
    onDisconnect: createMockEvent() as unknown as chrome.runtime.PortDisconnectEvent,
  } as unknown as chrome.runtime.Port;
}

interface DebuggerCalls {
  attach: Array<[chrome.debugger.Debuggee, string]>;
  sendCommand: Array<[chrome.debugger.Debuggee, string, Record<string, unknown> | undefined]>;
  detach: Array<[chrome.debugger.Debuggee]>;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('DOUYIN_DEBUGGER_HOVER with real dispatchTrustedHover and chrome.debugger mocks', () => {
  let debuggerMock: {
    mock: {
      attach: Mock<(target: chrome.debugger.Debuggee, version: string) => Promise<void>>;
      sendCommand: Mock<(target: chrome.debugger.Debuggee, method: string, params?: Record<string, unknown>) => Promise<unknown>>;
      detach: Mock<(target: chrome.debugger.Debuggee) => Promise<void>>;
    };
    calls: DebuggerCalls;
  };
  let mockChrome: {
    runtime: {
      onMessage: MockEvent;
      onInstalled: MockEvent;
      connectNative: Mock<(name: string) => chrome.runtime.Port>;
    };
    storage: {
      local: {
        get: Mock<(keys: string, callback: (result: Record<string, unknown>) => void) => void>;
        set: Mock<(items: Record<string, unknown>, callback?: () => void) => void>;
      };
    };
    contextMenus: {
      create: Mock<(options: unknown) => void>;
      removeAll: Mock<(callback?: () => void) => void>;
      onClicked: MockEvent;
    };
    tabs: {
      onRemoved: MockEvent;
      onUpdated: MockEvent;
    };
    notifications: {
      create: Mock<(options: unknown) => Promise<string>>;
    };
    debugger: {
      attach: Mock<(target: chrome.debugger.Debuggee, version: string) => Promise<void>>;
      detach: Mock<(target: chrome.debugger.Debuggee) => Promise<void>>;
      sendCommand: Mock<(target: chrome.debugger.Debuggee, method: string, params?: Record<string, unknown>) => Promise<unknown>>;
      onEvent: MockEvent;
    };
  };
  let backgroundModule: typeof import('../../src/background');

  function createDebuggerMock(): typeof debuggerMock {
    const calls: DebuggerCalls = { attach: [], sendCommand: [], detach: [] };
    return {
      mock: {
        attach: vi.fn(async (target: chrome.debugger.Debuggee, version: string) => {
          calls.attach.push([target, version]);
        }),
        sendCommand: vi.fn(async (target: chrome.debugger.Debuggee, method: string, params?: Record<string, unknown>) => {
          calls.sendCommand.push([target, method, params]);
        }),
        detach: vi.fn(async (target: chrome.debugger.Debuggee) => {
          calls.detach.push([target]);
        }),
      },
      calls,
    };
  }

  beforeEach(async () => {
    vi.resetModules();
    vi.stubGlobal('fetch', vi.fn());
    // No fake timers — dispatchTrustedHover uses real setTimeout for wait() delays
    // and Promise.race against captureAttempt (real async). Fake timers break
    // Promise.race when one side uses real async.

    const sessionStore: Record<string, unknown> = {};

    debuggerMock = createDebuggerMock();

    mockChrome = {
      runtime: {
        onMessage: createMockEvent(),
        onInstalled: createMockEvent(),
        connectNative: vi.fn((name: string) => {
          void name;
          return createMockPort();
        }),
      },
      storage: {
        local: {
          get: vi.fn((keys: string, callback: (result: Record<string, unknown>) => void) => {
            callback({ [keys]: sessionStore[keys] });
          }),
          set: vi.fn((items: Record<string, unknown>, callback?: () => void) => {
            Object.assign(sessionStore, items);
            if (callback) callback();
          }),
        },
      },
      contextMenus: {
        create: vi.fn(),
        removeAll: vi.fn((callback?: () => void) => callback && callback()),
        onClicked: createMockEvent(),
      },
      tabs: {
        onRemoved: createMockEvent(),
        onUpdated: createMockEvent(),
      },
      notifications: {
        create: vi.fn(async () => 'notification-id'),
      },
      debugger: {
        attach: debuggerMock.mock.attach,
        detach: debuggerMock.mock.detach,
        sendCommand: debuggerMock.mock.sendCommand,
        onEvent: createMockEvent(),
      },
    };

    vi.stubGlobal('chrome', mockChrome as unknown as typeof chrome);

    // Load background.ts — its DOUYIN_DEBUGGER_HOVER handler will use the real
    // dispatchTrustedHover from douyin-debugger (not mocked here).
    backgroundModule = await import('../../src/background');
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    vi.resetModules();
  });

  it('calls real dispatchTrustedHover and chrome.debugger with numeric tabId on success', async () => {
    const sendResponse = vi.fn();
    const sender = {
      tab: { id: 123, url: 'https://www.douyin.com/video/1' },
    };

    const done = backgroundModule.handleMessage(
      { type: 'DOUYIN_DEBUGGER_HOVER', point: { x: 10, y: 20 } },
      sender as chrome.runtime.MessageSender,
      sendResponse
    );
    expect(done).toBe(true);

    // The async IIFE fires sendResponse in a separate microtask
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(sendResponse).toHaveBeenCalledWith({ ok: true, captured: true, fallback: false });

    // Verify chrome.debugger was called via the internal DebuggerApi adapter
    expect(debuggerMock.calls.attach).toHaveLength(1);
    expect(debuggerMock.calls.attach[0]).toEqual([{ tabId: 123 }, '1.3']);

    expect(debuggerMock.calls.sendCommand).toHaveLength(1);
    expect(debuggerMock.calls.sendCommand[0]).toEqual([
      { tabId: 123 },
      'Input.dispatchMouseEvent',
      { type: 'mouseMoved', x: 10, y: 20, button: 'none', clickCount: 0 },
    ]);

    expect(debuggerMock.calls.detach).toHaveLength(1);
    expect(debuggerMock.calls.detach[0]).toEqual([{ tabId: 123 }]);
  });

  it('returns fallback:true when chrome.debugger.attach rejects with conflict error', async () => {
    // Use mockImplementation (not mockRejectedValue) so the push side-effect still runs.
    // mockRejectedValue replaces the entire mock implementation — no side effect.
    debuggerMock.mock.attach.mockImplementation(
      async (target: chrome.debugger.Debuggee, version: string) => {
        debuggerMock.calls.attach.push([target, version]);
        throw new Error('another debugger is already attached');
      }
    );

    const sendResponse = vi.fn();
    const sender = {
      tab: { id: 456, url: 'https://www.douyin.com/video/2' },
    };

    backgroundModule.handleMessage(
      { type: 'DOUYIN_DEBUGGER_HOVER', point: { x: 30, y: 40 } },
      sender as chrome.runtime.MessageSender,
      sendResponse
    );

    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(sendResponse).toHaveBeenCalledWith({ ok: true, captured: false, fallback: true });

    // attach was called once then stopped (no sendCommand, no detach)
    expect(debuggerMock.calls.attach).toHaveLength(1);
    expect(debuggerMock.calls.attach[0]).toEqual([{ tabId: 456 }, '1.3']);
    expect(debuggerMock.calls.sendCommand).toHaveLength(0);
    expect(debuggerMock.calls.detach).toHaveLength(0);
  });

  it('sends correct Input.dispatchMouseEvent params for given point', async () => {
    const sendResponse = vi.fn();
    const sender = {
      tab: { id: 789, url: 'https://www.douyin.com/notice' },
    };

    backgroundModule.handleMessage(
      { type: 'DOUYIN_DEBUGGER_HOVER', point: { x: 77, y: 88 } },
      sender as chrome.runtime.MessageSender,
      sendResponse
    );

    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(sendResponse).toHaveBeenCalledWith({ ok: true, captured: true, fallback: false });

    const [, method, params] = debuggerMock.calls.sendCommand[0];
    expect(method).toBe('Input.dispatchMouseEvent');
    expect(params).toEqual({
      type: 'mouseMoved',
      x: 77,
      y: 88,
      button: 'none',
      clickCount: 0,
    });
  });

  it('detach is called after successful attach even when sendCommand fails and retries', async () => {
    // First sendCommand fails → command_error → immediate retry (no wait)
    // Use mockImplementation to preserve side effects while throwing
    debuggerMock.mock.sendCommand
      .mockImplementationOnce(
        async (target: chrome.debugger.Debuggee, method: string, params?: Record<string, unknown>) => {
          debuggerMock.calls.sendCommand.push([target, method, params]);
          throw new Error('protocol error');
        }
      )
      .mockImplementationOnce(
        async (target: chrome.debugger.Debuggee, method: string, params?: Record<string, unknown>) => {
          debuggerMock.calls.sendCommand.push([target, method, params]);
        }
      );

    const sendResponse = vi.fn();
    const sender = {
      tab: { id: 111, url: 'https://www.douyin.com/video/3' },
    };

    backgroundModule.handleMessage(
      { type: 'DOUYIN_DEBUGGER_HOVER', point: { x: 5, y: 15 } },
      sender as chrome.runtime.MessageSender,
      sendResponse
    );

    // Two microtask flushes: first retry cycle completes, then second succeeds
    await new Promise((resolve) => setTimeout(resolve, 0));
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(sendResponse).toHaveBeenCalledWith({ ok: true, captured: true, fallback: false });

    // Two attach calls (first failed+detached, second succeeded)
    expect(debuggerMock.calls.attach).toHaveLength(2);
    expect(debuggerMock.calls.attach[0]).toEqual([{ tabId: 111 }, '1.3']);
    expect(debuggerMock.calls.attach[1]).toEqual([{ tabId: 111 }, '1.3']);

    // Two sendCommand calls
    expect(debuggerMock.calls.sendCommand).toHaveLength(2);

    // Two detach calls (once after each attach)
    expect(debuggerMock.calls.detach).toHaveLength(2);
    expect(debuggerMock.calls.detach[0]).toEqual([{ tabId: 111 }]);
    expect(debuggerMock.calls.detach[1]).toEqual([{ tabId: 111 }]);
  });

  it('rejects concurrent request for same tab with debugger busy', async () => {
    // Make dispatchTrustedHover hang indefinitely to simulate a long-running request
    debuggerMock.mock.attach.mockImplementation(
      async (target: chrome.debugger.Debuggee, version: string) => {
        debuggerMock.calls.attach.push([target, version]);
        // Never resolve - simulates a long-running debugger session
        await new Promise(() => {});
      }
    );

    const sendResponse1 = vi.fn();
    const sendResponse2 = vi.fn();
    const sender = {
      tab: { id: 999, url: 'https://www.douyin.com/video/concurrent' },
    };

    backgroundModule.handleMessage(
      { type: 'DOUYIN_DEBUGGER_HOVER', point: { x: 10, y: 20 } },
      sender as chrome.runtime.MessageSender,
      sendResponse1
    );

    // Wait for the first request to register in the throttle map
    await new Promise((resolve) => setTimeout(resolve, 0));

    // Second concurrent request for SAME tab should be immediately rejected
    backgroundModule.handleMessage(
      { type: 'DOUYIN_DEBUGGER_HOVER', point: { x: 30, y: 40 } },
      sender as chrome.runtime.MessageSender,
      sendResponse2
    );

    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(sendResponse2).toHaveBeenCalledWith({ ok: false, fallback: true, error: 'debugger busy' });
    // First request should not have received a response yet
    expect(sendResponse1).not.toHaveBeenCalled();
    // Only the first request should have called attach
    expect(debuggerMock.calls.attach).toHaveLength(1);
    expect(debuggerMock.calls.attach[0]).toEqual([{ tabId: 999 }, '1.3']);
  });

  it('allows concurrent requests for different tabs', async () => {
    const sendResponse1 = vi.fn();
    const sendResponse2 = vi.fn();

    backgroundModule.handleMessage(
      { type: 'DOUYIN_DEBUGGER_HOVER', point: { x: 10, y: 20 } },
      { tab: { id: 100, url: 'https://www.douyin.com/video/tab100' } } as chrome.runtime.MessageSender,
      sendResponse1
    );

    backgroundModule.handleMessage(
      { type: 'DOUYIN_DEBUGGER_HOVER', point: { x: 30, y: 40 } },
      { tab: { id: 200, url: 'https://www.douyin.com/video/tab200' } } as chrome.runtime.MessageSender,
      sendResponse2
    );

    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(sendResponse1).toHaveBeenCalledWith({ ok: true, captured: true, fallback: false });
    expect(sendResponse2).toHaveBeenCalledWith({ ok: true, captured: true, fallback: false });
    expect(debuggerMock.calls.attach).toHaveLength(2);
    expect(debuggerMock.calls.attach[0]).toEqual([{ tabId: 100 }, '1.3']);
    expect(debuggerMock.calls.attach[1]).toEqual([{ tabId: 200 }, '1.3']);
  });

  it('allows new request for same tab after previous completes (lock released)', async () => {
    const sendResponse1 = vi.fn();
    const sendResponse2 = vi.fn();
    const sender = {
      tab: { id: 333, url: 'https://www.douyin.com/video/locktest' },
    };

    // First request succeeds
    backgroundModule.handleMessage(
      { type: 'DOUYIN_DEBUGGER_HOVER', point: { x: 10, y: 20 } },
      sender as chrome.runtime.MessageSender,
      sendResponse1
    );

    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(sendResponse1).toHaveBeenCalledWith({ ok: true, captured: true, fallback: false });
    expect(debuggerMock.calls.attach).toHaveLength(1);
    expect(debuggerMock.calls.detach).toHaveLength(1);

    // Second request for the same tab should now succeed (lock was released)
    backgroundModule.handleMessage(
      { type: 'DOUYIN_DEBUGGER_HOVER', point: { x: 30, y: 40 } },
      sender as chrome.runtime.MessageSender,
      sendResponse2
    );

    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(sendResponse2).toHaveBeenCalledWith({ ok: true, captured: true, fallback: false });
    expect(debuggerMock.calls.attach).toHaveLength(2);
    expect(debuggerMock.calls.detach).toHaveLength(2);
  });
});
