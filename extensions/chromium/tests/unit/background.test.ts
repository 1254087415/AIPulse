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
  tabs: {
    onRemoved: MockEvent;
    onUpdated: MockEvent;
  };
  notifications: {
    create: Mock<(options: unknown) => Promise<string>>;
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
      tabs: {
        onRemoved: createMockEvent(),
        onUpdated: createMockEvent(),
      },
      notifications: {
        create: vi.fn(async () => 'notification-id'),
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

  it('stores FOUND_LINKS per tab and serves them by tabId', async () => {
    const linksTab1: FoundLink[] = [{ url: 'https://example.com/tab1', platform: 'test' }];
    const linksTab2: FoundLink[] = [{ url: 'https://example.com/tab2', platform: 'test' }];

    const response1 = vi.fn();
    mockChrome.runtime.onMessage.dispatch(
      { type: 'FOUND_LINKS', links: linksTab1 },
      { tab: { id: 1 } },
      response1
    );
    await vi.waitFor(() => expect(response1).toHaveBeenCalled());

    const response2 = vi.fn();
    mockChrome.runtime.onMessage.dispatch(
      { type: 'FOUND_LINKS', links: linksTab2 },
      { tab: { id: 2 } },
      response2
    );
    await vi.waitFor(() => expect(response2).toHaveBeenCalled());

    const getTab1 = vi.fn();
    mockChrome.runtime.onMessage.dispatch({ type: 'GET_FOUND_LINKS', tabId: 1 }, {}, getTab1);
    await vi.waitFor(() => expect(getTab1).toHaveBeenCalled());
    expect(getTab1).toHaveBeenCalledWith({ links: linksTab1 });

    const getTab2 = vi.fn();
    mockChrome.runtime.onMessage.dispatch({ type: 'GET_FOUND_LINKS', tabId: 2 }, {}, getTab2);
    await vi.waitFor(() => expect(getTab2).toHaveBeenCalled());
    expect(getTab2).toHaveBeenCalledWith({ links: linksTab2 });
  });

  it('clears per-tab links when the tab navigates', async () => {
    const links: FoundLink[] = [{ url: 'https://example.com/tab1', platform: 'test' }];
    const response = vi.fn();
    mockChrome.runtime.onMessage.dispatch(
      { type: 'FOUND_LINKS', links },
      { tab: { id: 1 } },
      response
    );
    await vi.waitFor(() => expect(response).toHaveBeenCalled());

    mockChrome.tabs.onUpdated.dispatch(1, { url: 'https://other.example/' });
    // Let the fire-and-forget clear settle before querying.
    await new Promise((resolve) => setTimeout(resolve, 0));

    const getTab1 = vi.fn();
    mockChrome.runtime.onMessage.dispatch({ type: 'GET_FOUND_LINKS', tabId: 1 }, {}, getTab1);
    await vi.waitFor(() => expect(getTab1).toHaveBeenCalled());
    expect(getTab1).toHaveBeenCalledWith({ links: [] });
  });

  it('keeps per-tab links on same-page query changes', async () => {
    const links: FoundLink[] = [{ url: 'https://example.com/video/1', platform: 'test' }];
    const response = vi.fn();
    mockChrome.runtime.onMessage.dispatch(
      { type: 'FOUND_LINKS', links },
      { tab: { id: 1, url: 'https://example.com/video/1' } },
      response
    );
    await vi.waitFor(() => expect(response).toHaveBeenCalled());

    // Bilibili-style playback-position update: same path, different query.
    mockChrome.tabs.onUpdated.dispatch(1, { url: 'https://example.com/video/1?t=123' });

    const getTab1 = vi.fn();
    mockChrome.runtime.onMessage.dispatch({ type: 'GET_FOUND_LINKS', tabId: 1 }, {}, getTab1);
    await vi.waitFor(() => expect(getTab1).toHaveBeenCalled());
    expect(getTab1).toHaveBeenCalledWith({ links });
  });

  it('removes per-tab links when the tab is closed', async () => {
    const links: FoundLink[] = [{ url: 'https://example.com/tab1', platform: 'test' }];
    const response = vi.fn();
    mockChrome.runtime.onMessage.dispatch(
      { type: 'FOUND_LINKS', links },
      { tab: { id: 1 } },
      response
    );
    await vi.waitFor(() => expect(response).toHaveBeenCalled());

    mockChrome.tabs.onRemoved.dispatch(1);
    // Let the fire-and-forget clear settle before querying.
    await new Promise((resolve) => setTimeout(resolve, 0));

    const getTab1 = vi.fn();
    mockChrome.runtime.onMessage.dispatch({ type: 'GET_FOUND_LINKS', tabId: 1 }, {}, getTab1);
    await vi.waitFor(() => expect(getTab1).toHaveBeenCalled());
    expect(getTab1).toHaveBeenCalledWith({ links: [] });
  });

  it('fetches AI subtitle files without credentials', async () => {
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ body: [] }),
    } as Response);

    const sendResponse = vi.fn();
    mockChrome.runtime.onMessage.dispatch(
      { type: 'FETCH_JSON', url: 'https://aisubtitle.hdslb.com/bfs/ai_subtitle/sub.json' },
      {},
      sendResponse
    );

    await vi.waitFor(() => expect(sendResponse).toHaveBeenCalled());
    expect(sendResponse).toHaveBeenCalledWith({ ok: true, data: { body: [] } });
    expect(fetch).toHaveBeenCalledWith(
      'https://aisubtitle.hdslb.com/bfs/ai_subtitle/sub.json',
      expect.objectContaining({ credentials: 'omit' })
    );
  });

  it('notifies the user after a context menu archive succeeds', async () => {
    const port = createMockPort();
    mockChrome.runtime.connectNative.mockReturnValue(port);
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      status: 200,
      statusText: 'OK',
      json: async () => ({ task_id: 'ctx-1', url: 'https://example.com' }),
    } as Response);

    mockChrome.contextMenus.onClicked.dispatch({
      menuItemId: 'archive-current-page',
      pageUrl: 'https://example.com',
    } as chrome.contextMenus.OnClickData);
    (port.onDisconnect as unknown as MockEvent).dispatch();

    await vi.waitFor(() => expect(mockChrome.notifications.create).toHaveBeenCalled());
    expect(mockChrome.notifications.create).toHaveBeenCalledWith(
      expect.objectContaining({
        type: 'basic',
        iconUrl: 'icon.png',
        title: 'AIPulse',
        message: '已归档到 AIPulse',
      })
    );
  });

  it('notifies the user when a context menu archive fails', async () => {
    const port = createMockPort();
    mockChrome.runtime.connectNative.mockReturnValue(port);
    vi.mocked(fetch).mockRejectedValue(new Error('connection refused'));

    mockChrome.contextMenus.onClicked.dispatch({
      menuItemId: 'archive-current-page',
      pageUrl: 'https://example.com',
    } as chrome.contextMenus.OnClickData);
    (port.onDisconnect as unknown as MockEvent).dispatch();

    await vi.waitFor(() => expect(mockChrome.notifications.create).toHaveBeenCalled());
    expect(mockChrome.notifications.create).toHaveBeenCalledWith(
      expect.objectContaining({
        title: 'AIPulse',
        message: expect.stringContaining('归档失败'),
      })
    );
  });

  it('returns global cached links when GET_FOUND_LINKS has no tabId', async () => {
    const links: FoundLink[] = [{ url: 'https://example.com/global', platform: 'test' }];
    const setResponse = vi.fn();
    mockChrome.runtime.onMessage.dispatch(
      { type: 'FOUND_LINKS', links },
      { tab: { id: 5 } },
      setResponse
    );
    await vi.waitFor(() => expect(setResponse).toHaveBeenCalled());

    const sendResponse = vi.fn();
    mockChrome.runtime.onMessage.dispatch({ type: 'GET_FOUND_LINKS' }, {}, sendResponse);
    await vi.waitFor(() => expect(sendResponse).toHaveBeenCalled());
    expect(sendResponse).toHaveBeenCalledWith({ links });
  });

  it('stores FOUND_LINKS globally when sender has no tab info', async () => {
    const links: FoundLink[] = [{ url: 'https://example.com/no-tab', platform: 'test' }];
    const setResponse = vi.fn();
    mockChrome.runtime.onMessage.dispatch({ type: 'FOUND_LINKS', links }, {}, setResponse);
    await vi.waitFor(() => expect(setResponse).toHaveBeenCalled());

    const sendResponse = vi.fn();
    mockChrome.runtime.onMessage.dispatch({ type: 'GET_FOUND_LINKS' }, {}, sendResponse);
    await vi.waitFor(() => expect(sendResponse).toHaveBeenCalled());
    expect(sendResponse).toHaveBeenCalledWith({ links });
  });

  it('rejects SUBMIT_URL with an invalid URL', async () => {
    const sendResponse = vi.fn();
    mockChrome.runtime.onMessage.dispatch(
      { type: 'SUBMIT_URL', url: 'not-a-url', mode: 'archive' },
      {},
      sendResponse
    );
    await vi.waitFor(() => expect(sendResponse).toHaveBeenCalled());
    expect(sendResponse).toHaveBeenCalledWith({ ok: false, error: 'invalid message' });
  });

  it('omits title and tags when they have invalid types in SUBMIT_URL', async () => {
    const port = createMockPort();
    mockChrome.runtime.connectNative.mockReturnValue(port);
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      status: 200,
      statusText: 'OK',
      json: async () => ({ task_id: 'http-types', url: 'https://example.com' }),
    } as Response);

    const sendResponse = vi.fn();
    mockChrome.runtime.onMessage.dispatch(
      {
        type: 'SUBMIT_URL',
        url: 'https://example.com',
        mode: 'archive',
        title: true,
        tags: ['ok', ''],
      },
      {},
      sendResponse
    );

    (port.onDisconnect as unknown as MockEvent).dispatch();
    await vi.waitFor(() => expect(sendResponse).toHaveBeenCalled());

    expect(sendResponse).toHaveBeenCalledWith({ ok: true, result: expect.any(Object) });
    const body = JSON.parse(vi.mocked(fetch).mock.calls[0][1]?.body as string);
    expect(body.title).toBeUndefined();
    expect(body.tags).toBeUndefined();
  });

  it('falls back to HTTP when native messaging host is unavailable', async () => {
    mockChrome.runtime.connectNative.mockImplementation(() => {
      throw new Error('host not found');
    });
    const httpResult: SubmitResult = {
      task_id: 'http-native-fail',
      url: 'https://example.com',
    };
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      status: 200,
      statusText: 'OK',
      json: async () => httpResult,
    } as Response);

    const sendResponse = vi.fn();
    mockChrome.runtime.onMessage.dispatch(
      { type: 'SUBMIT_URL', url: 'https://example.com', mode: 'archive' },
      {},
      sendResponse
    );

    await vi.waitFor(() => expect(sendResponse).toHaveBeenCalled());
    expect(sendResponse).toHaveBeenCalledWith({ ok: true, result: httpResult });
    expect(fetch).toHaveBeenCalled();
  });

  it('rejects FETCH_JSON for non-whitelisted domains', async () => {
    const sendResponse = vi.fn();
    mockChrome.runtime.onMessage.dispatch(
      { type: 'FETCH_JSON', url: 'https://example.com/data.json' },
      {},
      sendResponse
    );
    await vi.waitFor(() => expect(sendResponse).toHaveBeenCalled());
    expect(sendResponse).toHaveBeenCalledWith({ ok: false, error: 'host not allowed' });
  });

  it('ignores unknown context menu item ids', async () => {
    mockChrome.contextMenus.onClicked.dispatch({
      menuItemId: 'unknown',
      pageUrl: 'https://example.com',
    } as chrome.contextMenus.OnClickData);
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(mockChrome.runtime.connectNative).not.toHaveBeenCalled();
    expect(mockChrome.notifications.create).not.toHaveBeenCalled();
  });

  it('does not throw when notification creation fails', async () => {
    const port = createMockPort();
    mockChrome.runtime.connectNative.mockReturnValue(port);
    mockChrome.notifications.create.mockRejectedValue(new Error('notification failed'));

    mockChrome.contextMenus.onClicked.dispatch({
      menuItemId: 'archive-current-page',
      pageUrl: 'https://example.com',
    } as chrome.contextMenus.OnClickData);
    (port.onMessage as unknown as MockEvent).dispatch({
      result: { task_id: 'native-ctx', url: 'https://example.com' },
    });

    await vi.waitFor(() => expect(mockChrome.notifications.create).toHaveBeenCalled());
    expect(mockChrome.notifications.create).toHaveBeenCalledWith(
      expect.objectContaining({
        title: 'AIPulse',
        message: '已归档到 AIPulse',
      })
    );
  });

  it('does nothing when tabs.onUpdated fires without a url change', async () => {
    const links: FoundLink[] = [{ url: 'https://example.com/tab1', platform: 'test' }];
    const response = vi.fn();
    mockChrome.runtime.onMessage.dispatch(
      { type: 'FOUND_LINKS', links },
      { tab: { id: 1 } },
      response
    );
    await vi.waitFor(() => expect(response).toHaveBeenCalled());

    mockChrome.tabs.onUpdated.dispatch(1, { status: 'complete' });
    await new Promise((resolve) => setTimeout(resolve, 0));

    const getTab1 = vi.fn();
    mockChrome.runtime.onMessage.dispatch({ type: 'GET_FOUND_LINKS', tabId: 1 }, {}, getTab1);
    await vi.waitFor(() => expect(getTab1).toHaveBeenCalled());
    expect(getTab1).toHaveBeenCalledWith({ links });
  });

  it('does nothing when tabs.onRemoved fires for a tab without stored links', async () => {
    mockChrome.tabs.onRemoved.dispatch(999);
    await new Promise((resolve) => setTimeout(resolve, 0));

    const getTab999 = vi.fn();
    mockChrome.runtime.onMessage.dispatch({ type: 'GET_FOUND_LINKS', tabId: 999 }, {}, getTab999);
    await vi.waitFor(() => expect(getTab999).toHaveBeenCalled());
    expect(getTab999).toHaveBeenCalledWith({ links: [] });
  });
});
