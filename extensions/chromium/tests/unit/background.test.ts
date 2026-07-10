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

    const sessionStore: Record<string, unknown> = {};

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

  it('dedupes and caches FOUND_LINKS', async () => {
    const links: FoundLink[] = [
      { url: 'https://example.com/video/1?utm_source=share', platform: 'test' },
      { url: 'https://example.com/video/1', platform: 'test' },
      { url: 'https://example.com/video/2', platform: 'test' },
    ];

    const sendResponse = vi.fn();
    mockChrome.runtime.onMessage.dispatch({ type: 'FOUND_LINKS', links }, {}, sendResponse);

    await vi.waitFor(() => expect(sendResponse).toHaveBeenCalled());
    expect(sendResponse).toHaveBeenCalledWith({ ok: true, count: 2 });

    const getResponse = vi.fn();
    mockChrome.runtime.onMessage.dispatch({ type: 'GET_FOUND_LINKS' }, {}, getResponse);
    await vi.waitFor(() => expect(getResponse).toHaveBeenCalled());
    expect(getResponse).toHaveBeenCalledWith({ links: expect.any(Array) });
    expect(getResponse.mock.calls[0][0].links).toHaveLength(2);
  });

  it('returns cached links on GET_FOUND_LINKS', async () => {
    const cached: FoundLink[] = [{ url: 'https://example.com/cached', platform: 'test' }];
    const setResponse = vi.fn();
    mockChrome.runtime.onMessage.dispatch({ type: 'FOUND_LINKS', links: cached }, {}, setResponse);
    await vi.waitFor(() => expect(setResponse).toHaveBeenCalled());

    const sendResponse = vi.fn();
    mockChrome.runtime.onMessage.dispatch({ type: 'GET_FOUND_LINKS' }, {}, sendResponse);

    await vi.waitFor(() => expect(sendResponse).toHaveBeenCalled());
    expect(sendResponse).toHaveBeenCalledWith({ links: cached });
  });

  it('forwards title and tags in SUBMIT_URL payload', async () => {
    const httpResult: SubmitResult = { task_id: 'http-2', url: 'https://example.com' };
    const port = createMockPort();
    mockChrome.runtime.connectNative.mockReturnValue(port);
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      status: 200,
      statusText: 'OK',
      json: async () => httpResult,
    } as Response);

    const sendResponse = vi.fn();
    mockChrome.runtime.onMessage.dispatch(
      {
        type: 'SUBMIT_URL',
        url: 'https://example.com',
        title: 'My Title',
        mode: 'archive',
        tags: ['foo', 'bar'],
      },
      {},
      sendResponse
    );

    (port.onDisconnect as unknown as MockEvent).dispatch();
    await vi.waitFor(() => expect(sendResponse).toHaveBeenCalled());

    expect(sendResponse).toHaveBeenCalledWith({ ok: true, result: httpResult });
    expect(fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/api/videos/extract',
      expect.objectContaining({
        method: 'POST',
        body: expect.stringContaining('"title":"My Title"'),
      })
    );
    const body = vi.mocked(fetch).mock.calls[0][1]?.body as string;
    expect(JSON.parse(body).tags).toEqual(['foo', 'bar']);
  });

  it('rejects invalid tags and title in SUBMIT_URL', async () => {
    const port = createMockPort();
    mockChrome.runtime.connectNative.mockReturnValue(port);
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      status: 200,
      statusText: 'OK',
      json: async () => ({ task_id: 'http-3', url: 'https://example.com' }),
    } as Response);
    const sendResponse = vi.fn();
    mockChrome.runtime.onMessage.dispatch(
      {
        type: 'SUBMIT_URL',
        url: 'https://example.com',
        title: 123,
        mode: 'archive',
        tags: ['foo', 123, 'bar'],
      },
      {},
      sendResponse
    );

    (port.onDisconnect as unknown as MockEvent).dispatch();
    await vi.waitFor(() => expect(sendResponse).toHaveBeenCalled());

    expect(sendResponse).toHaveBeenCalledWith({ ok: true, result: expect.any(Object) });
    const body = vi.mocked(fetch).mock.calls[0][1]?.body as string;
    const parsed = JSON.parse(body);
    expect(parsed.title).toBeUndefined();
    expect(parsed.tags).toBeUndefined();
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

  it('fetches Bilibili API through background with credentials and referrer', async () => {
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ code: 0, data: { subtitle: { subtitles: [{ id: 1, subtitle_url: '//aisubtitle.hdslb.com/sub.json' }] } } }),
    } as Response);

    const sendResponse = vi.fn();
    mockChrome.runtime.onMessage.dispatch(
      { type: 'FETCH_JSON', url: 'https://api.bilibili.com/x/player/v2?cid=1&bvid=BV1xx411c7m' },
      {},
      sendResponse
    );

    await vi.waitFor(() => expect(sendResponse).toHaveBeenCalled());
    expect(sendResponse).toHaveBeenCalledWith({
      ok: true,
      data: { code: 0, data: { subtitle: { subtitles: [{ id: 1, subtitle_url: '//aisubtitle.hdslb.com/sub.json' }] } } },
    });
    expect(fetch).toHaveBeenCalledWith(
      'https://api.bilibili.com/x/player/v2?cid=1&bvid=BV1xx411c7m',
      expect.objectContaining({
        method: 'GET',
        credentials: 'include',
        cache: 'no-store',
        referrer: 'https://www.bilibili.com/',
        referrerPolicy: 'strict-origin-when-cross-origin',
      })
    );
  });

  it('rejects FETCH_JSON with invalid url', async () => {
    const sendResponse = vi.fn();
    mockChrome.runtime.onMessage.dispatch({ type: 'FETCH_JSON', url: 'not-a-url' }, {}, sendResponse);
    await vi.waitFor(() => expect(sendResponse).toHaveBeenCalled());
    expect(sendResponse).toHaveBeenCalledWith({ ok: false, error: 'invalid message' });
  });

  it('creates context menus after removing existing ones on install', () => {
    mockChrome.runtime.onInstalled.dispatch();
    expect(mockChrome.contextMenus.removeAll).toHaveBeenCalled();
    expect(mockChrome.contextMenus.create).toHaveBeenCalledTimes(2);
  });
});
