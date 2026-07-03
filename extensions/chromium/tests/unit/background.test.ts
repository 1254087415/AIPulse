import { describe, expect, it, vi, beforeEach, afterEach, type Mock } from 'vitest';
import { cleanTrackingParams } from '../../src/utils';
import type { FoundLink, SubmitResult } from '../../src/types';

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

interface MockChrome {
  runtime: {
    onMessage: MockEvent;
    onInstalled: MockEvent;
    connectNative: Mock<(name: string) => chrome.runtime.Port>;
  };
  contextMenus: {
    create: Mock<(options: unknown) => void>;
    removeAll: Mock<(callback?: () => void) => void>;
    onClicked: MockEvent;
  };
}

describe('background helpers', () => {
  it('cleans url before submit', () => {
    const url = 'https://www.bilibili.com/video/BV1xx411c7mD?utm_source=share';
    expect(cleanTrackingParams(url)).toBe('https://www.bilibili.com/video/BV1xx411c7mD');
  });
});

describe('background message handlers', () => {
  let mockChrome: MockChrome;
  let backgroundModule: typeof import('../../src/background');

  beforeEach(async () => {
    vi.resetModules();
    vi.stubGlobal('fetch', vi.fn());

    mockChrome = {
      runtime: {
        onMessage: createMockEvent(),
        onInstalled: createMockEvent(),
        connectNative: vi.fn((name: string) => {
          void name;
          return createMockPort();
        }),
      },
      contextMenus: {
        create: vi.fn(),
        removeAll: vi.fn((callback?: () => void) => callback && callback()),
        onClicked: createMockEvent(),
      },
    };

    vi.stubGlobal('chrome', mockChrome as unknown as typeof chrome);

    backgroundModule = await import('../../src/background');
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('registers chrome runtime and context menu listeners on load', () => {
    expect(mockChrome.runtime.onMessage.addListener).toHaveBeenCalled();
    expect(mockChrome.runtime.onInstalled.addListener).toHaveBeenCalled();
    expect(mockChrome.contextMenus.onClicked.addListener).toHaveBeenCalled();
  });

  it('dedupes and caches FOUND_LINKS', () => {
    const links: FoundLink[] = [
      { url: 'https://example.com/video/1?utm_source=share', platform: 'test' },
      { url: 'https://example.com/video/1', platform: 'test' },
      { url: 'https://example.com/video/2', platform: 'test' },
    ];

    const sendResponse = vi.fn();
    mockChrome.runtime.onMessage.dispatch({ type: 'FOUND_LINKS', links }, {}, sendResponse);

    expect(sendResponse).toHaveBeenCalledWith({ ok: true, count: 2 });
    expect(backgroundModule.foundLinksCache).toHaveLength(2);
  });

  it('returns cached links on GET_FOUND_LINKS', () => {
    const cached: FoundLink[] = [{ url: 'https://example.com/cached', platform: 'test' }];
    mockChrome.runtime.onMessage.dispatch({ type: 'FOUND_LINKS', links: cached }, {}, vi.fn());

    const sendResponse = vi.fn();
    mockChrome.runtime.onMessage.dispatch({ type: 'GET_FOUND_LINKS' }, {}, sendResponse);

    expect(sendResponse).toHaveBeenCalledWith({ links: cached });
  });

  it('uses native messaging result when available', async () => {
    const nativeResult: SubmitResult = { task_id: 'native-1', url: 'https://example.com' };
    const port = createMockPort();
    mockChrome.runtime.connectNative.mockReturnValue(port);

    const resultPromise = backgroundModule.submitUrl('https://example.com', 'archive');
    (port.onMessage as unknown as MockEvent).dispatch({ result: nativeResult });

    const result = await resultPromise;
    expect(result).toEqual(nativeResult);
    expect(fetch).not.toHaveBeenCalled();
  });

  it('falls back from native messaging to HTTP on disconnect', async () => {
    const httpResult: SubmitResult = { task_id: 'http-1', url: 'https://example.com' };
    const port = createMockPort();
    mockChrome.runtime.connectNative.mockReturnValue(port);

    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      status: 200,
      statusText: 'OK',
      json: async () => httpResult,
    } as Response);

    const resultPromise = backgroundModule.submitUrl('https://example.com', 'archive');
    (port.onDisconnect as unknown as MockEvent).dispatch();

    const result = await resultPromise;
    expect(mockChrome.runtime.connectNative).toHaveBeenCalledWith('com.aipulse.native_host');
    expect(fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/api/videos/extract',
      expect.objectContaining({
        method: 'POST',
        body: expect.stringContaining('https://example.com'),
      })
    );
    expect(result).toEqual(httpResult);
  });

  it('creates context menus after removing existing ones on install', () => {
    mockChrome.runtime.onInstalled.dispatch();
    expect(mockChrome.contextMenus.removeAll).toHaveBeenCalled();
    expect(mockChrome.contextMenus.create).toHaveBeenCalledTimes(2);
  });
});
