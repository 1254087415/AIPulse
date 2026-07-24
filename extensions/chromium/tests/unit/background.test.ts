import { describe, expect, it, vi, beforeEach, afterEach, type Mock } from 'vitest';
import { cleanTrackingParams } from '../../src/utils';
import type { FoundLink, SubmitResult } from '../../src/types';
import type { DebuggerHoverResult } from '../../src/platform/douyin-debugger';

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
  debugger: {
    attach: Mock<(target: chrome.debugger.Debuggee, version: string) => Promise<void>>;
    detach: Mock<(target: chrome.debugger.Debuggee) => Promise<void>>;
    sendCommand: Mock<(target: chrome.debugger.Debuggee, method: string, params?: Record<string, unknown>) => Promise<unknown>>;
    onEvent: MockEvent;
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
      debugger: {
        attach: vi.fn(),
        detach: vi.fn(),
        sendCommand: vi.fn(),
        onEvent: createMockEvent(),
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

// Module-level mock so vi.mock hoisting can reference it.
// vi.hoisted() keeps dispatchTrustedHoverMock synchronized with vi.mock's
// factory across vi.resetModules() calls.
const { mockFn: dispatchTrustedHoverMock } = vi.hoisted(() => {
  const fn = vi.fn();
  return { mockFn: fn };
});

vi.mock('../../src/platform/douyin-debugger', () => ({
  dispatchTrustedHover: dispatchTrustedHoverMock,
}));

describe('DOUYIN_DEBUGGER_HOVER message handler', () => {
  let mockChrome: MockChrome;
  let backgroundModule: typeof import('../../src/background');

  beforeEach(async () => {
    vi.resetModules();
    vi.stubGlobal('fetch', vi.fn());

    const sessionStore: Record<string, unknown> = {};

    dispatchTrustedHoverMock.mockReset();

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
        attach: vi.fn(),
        detach: vi.fn(),
        sendCommand: vi.fn(),
        onEvent: createMockEvent(),
      },
    };

    // Stub chrome BEFORE importing background so the module registers its
    // listener on the mock's onMessage (not the real chrome) and subsequent
    // dispatch() calls reach the registered listener.
    vi.stubGlobal('chrome', mockChrome as unknown as typeof chrome);

    backgroundModule = await import('../../src/background');

    // Clear per-tab throttle map between tests to prevent cross-test pollution
    Object.keys(backgroundModule.DEBUGGER_TAB_THROTTLE_MAP).forEach((k) => delete backgroundModule.DEBUGGER_TAB_THROTTLE_MAP[k]);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    vi.resetModules();
  });

  it('calls dispatchTrustedHover with correct api for valid douyin.com https request (no tabId in message)', async () => {
    const sendResponse = vi.fn();
    const sender = {
      tab: { id: 123, url: 'https://www.douyin.com/notice' },
    };

    dispatchTrustedHoverMock.mockResolvedValue({ captured: true, fallback: false });

    // Message does NOT include tabId field - content script cannot know its own tabId
    mockChrome.runtime.onMessage.dispatch(
      { type: 'DOUYIN_DEBUGGER_HOVER', point: { x: 100, y: 200 } },
      sender,
      sendResponse
    );

    // Yield to the event loop so the async handler runs before we assert
    await new Promise((resolve) => setTimeout(resolve, 0));

    await vi.waitFor(() => expect(dispatchTrustedHoverMock).toHaveBeenCalled());

    // Verify dispatchTrustedHover was called with sender.tab.id (not any message.tabId)
    expect(dispatchTrustedHoverMock).toHaveBeenCalledWith(
      '123',
      { x: 100, y: 200 },
      expect.any(Object)
    );

    expect(sendResponse).toHaveBeenCalledWith({ ok: true, captured: true, fallback: false });
  });

  it('ignores malicious tabId field and uses sender.tab.id as target', async () => {
    const sendResponse = vi.fn();
    const sender = {
      tab: { id: 123, url: 'https://www.douyin.com/notice' },
    };

    dispatchTrustedHoverMock.mockResolvedValue({ captured: true, fallback: false });

    // Attacker tries to trick background into targeting tab 999, but we ignore message.tabId
    mockChrome.runtime.onMessage.dispatch(
      { type: 'DOUYIN_DEBUGGER_HOVER', tabId: 999, point: { x: 100, y: 200 } },
      sender,
      sendResponse
    );

    // Yield to the event loop so the async handler runs before we assert
    await new Promise((resolve) => setTimeout(resolve, 0));

    await vi.waitFor(() => expect(dispatchTrustedHoverMock).toHaveBeenCalled());

    // Must use sender.tab.id (123), NOT the malicious message.tabId (999)
    expect(dispatchTrustedHoverMock).toHaveBeenCalledWith(
      '123',
      { x: 100, y: 200 },
      expect.any(Object)
    );

    expect(sendResponse).toHaveBeenCalledWith({ ok: true, captured: true, fallback: false });
  });

  it('returns error when sender.tab is missing', async () => {
    const sendResponse = vi.fn();
    const sender = {};

    mockChrome.runtime.onMessage.dispatch(
      { type: 'DOUYIN_DEBUGGER_HOVER', point: { x: 100, y: 200 } },
      sender,
      sendResponse
    );

    await vi.waitFor(() => expect(sendResponse).toHaveBeenCalled());
    expect(sendResponse).toHaveBeenCalledWith({ ok: false, fallback: false, error: 'invalid sender' });
    expect(dispatchTrustedHoverMock).not.toHaveBeenCalled();
  });

  it('returns error when sender.tab.id is not a number', async () => {
    const sendResponse = vi.fn();
    const sender = {
      tab: { id: '123', url: 'https://www.douyin.com/notice' },
    };

    mockChrome.runtime.onMessage.dispatch(
      { type: 'DOUYIN_DEBUGGER_HOVER', point: { x: 100, y: 200 } },
      sender,
      sendResponse
    );

    await vi.waitFor(() => expect(sendResponse).toHaveBeenCalled());
    expect(sendResponse).toHaveBeenCalledWith({ ok: false, fallback: false, error: 'invalid sender' });
  });

  it('returns error when sender.tab.url is not www.douyin.com', async () => {
    const sendResponse = vi.fn();
    const sender = {
      tab: { id: 123, url: 'https://www.bilibili.com/video/123' },
    };

    mockChrome.runtime.onMessage.dispatch(
      { type: 'DOUYIN_DEBUGGER_HOVER', point: { x: 100, y: 200 } },
      sender,
      sendResponse
    );

    await vi.waitFor(() => expect(sendResponse).toHaveBeenCalled());
    expect(sendResponse).toHaveBeenCalledWith({ ok: false, fallback: false, error: 'invalid url' });
  });

  it('returns error when sender.tab.url hostname has wrong www prefix', async () => {
    const sendResponse = vi.fn();
    const sender = {
      tab: { id: 123, url: 'https://douyin.com/notice' },
    };

    mockChrome.runtime.onMessage.dispatch(
      { type: 'DOUYIN_DEBUGGER_HOVER', point: { x: 100, y: 200 } },
      sender,
      sendResponse
    );

    await vi.waitFor(() => expect(sendResponse).toHaveBeenCalled());
    expect(sendResponse).toHaveBeenCalledWith({ ok: false, fallback: false, error: 'invalid url' });
  });

  it('returns error when sender.tab.url is not https', async () => {
    const sendResponse = vi.fn();
    const sender = {
      tab: { id: 123, url: 'http://www.douyin.com/notice' },
    };

    mockChrome.runtime.onMessage.dispatch(
      { type: 'DOUYIN_DEBUGGER_HOVER', point: { x: 100, y: 200 } },
      sender,
      sendResponse
    );

    await vi.waitFor(() => expect(sendResponse).toHaveBeenCalled());
    expect(sendResponse).toHaveBeenCalledWith({ ok: false, fallback: false, error: 'invalid url' });
  });

  it('returns error when point.x is not finite', async () => {
    const sendResponse = vi.fn();
    const sender = {
      tab: { id: 123, url: 'https://www.douyin.com/notice' },
    };

    mockChrome.runtime.onMessage.dispatch(
      { type: 'DOUYIN_DEBUGGER_HOVER', point: { x: NaN, y: 200 } },
      sender,
      sendResponse
    );

    await vi.waitFor(() => expect(sendResponse).toHaveBeenCalled());
    expect(sendResponse).toHaveBeenCalledWith({ ok: false, fallback: false, error: 'invalid point' });
  });

  it('returns error when point.y is negative', async () => {
    const sendResponse = vi.fn();
    const sender = {
      tab: { id: 123, url: 'https://www.douyin.com/notice' },
    };

    mockChrome.runtime.onMessage.dispatch(
      { type: 'DOUYIN_DEBUGGER_HOVER', point: { x: 100, y: -5 } },
      sender,
      sendResponse
    );

    await vi.waitFor(() => expect(sendResponse).toHaveBeenCalled());
    expect(sendResponse).toHaveBeenCalledWith({ ok: false, fallback: false, error: 'invalid point' });
  });

  it('returns error when point has negative x and y', async () => {
    const sendResponse = vi.fn();
    const sender = {
      tab: { id: 123, url: 'https://www.douyin.com/notice' },
    };

    mockChrome.runtime.onMessage.dispatch(
      { type: 'DOUYIN_DEBUGGER_HOVER', point: { x: -1, y: -2 } },
      sender,
      sendResponse
    );

    await vi.waitFor(() => expect(sendResponse).toHaveBeenCalled());
    expect(sendResponse).toHaveBeenCalledWith({ ok: false, fallback: false, error: 'invalid point' });
  });

  it('returns fallback:true when dispatchTrustedHover returns fallback:true', async () => {
    const sendResponse = vi.fn();
    const sender = {
      tab: { id: 123, url: 'https://www.douyin.com/notice' },
    };

    dispatchTrustedHoverMock.mockResolvedValue({ captured: false, fallback: true });

    mockChrome.runtime.onMessage.dispatch(
      { type: 'DOUYIN_DEBUGGER_HOVER', point: { x: 100, y: 200 } },
      sender,
      sendResponse
    );

    await vi.waitFor(() => expect(sendResponse).toHaveBeenCalled());
    expect(sendResponse).toHaveBeenCalledWith({ ok: true, captured: false, fallback: true });
  });

  it('returns captured:false fallback:false when dispatchTrustedHover returns captured:false fallback:false', async () => {
    const sendResponse = vi.fn();
    const sender = {
      tab: { id: 123, url: 'https://www.douyin.com/notice' },
    };

    dispatchTrustedHoverMock.mockResolvedValue({ captured: false, fallback: false });

    mockChrome.runtime.onMessage.dispatch(
      { type: 'DOUYIN_DEBUGGER_HOVER', point: { x: 100, y: 200 } },
      sender,
      sendResponse
    );

    await vi.waitFor(() => expect(sendResponse).toHaveBeenCalled());
    expect(sendResponse).toHaveBeenCalledWith({ ok: true, captured: false, fallback: false });
  });

  it('returns error when dispatchTrustedHover throws', async () => {
    const sendResponse = vi.fn();
    const sender = {
      tab: { id: 123, url: 'https://www.douyin.com/notice' },
    };

    dispatchTrustedHoverMock.mockRejectedValue(new Error('debugger connection failed'));

    mockChrome.runtime.onMessage.dispatch(
      { type: 'DOUYIN_DEBUGGER_HOVER', point: { x: 100, y: 200 } },
      sender,
      sendResponse
    );

    await vi.waitFor(() => expect(sendResponse).toHaveBeenCalled());
    // Error message should not leak the exception object details
    expect(sendResponse).toHaveBeenCalledWith({ ok: false, fallback: false, error: 'debugger error' });
  });

  it('rejects concurrent DOUYIN_DEBUGGER_HOVER for same tab (per-tab throttle)', async () => {
    const sendResponse1 = vi.fn();
    const sendResponse2 = vi.fn();
    const sender = {
      tab: { id: 123, url: 'https://www.douyin.com/notice' },
    };

    // First request starts and is still pending (dispatchTrustedHover not yet resolved)
    dispatchTrustedHoverMock.mockImplementation(async () => {
      // Simulate a long-running operation by never resolving
      return new Promise(() => {});
    });

    mockChrome.runtime.onMessage.dispatch(
      { type: 'DOUYIN_DEBUGGER_HOVER', point: { x: 100, y: 200 } },
      sender,
      sendResponse1
    );

    await vi.waitFor(() => expect(dispatchTrustedHoverMock).toHaveBeenCalledTimes(1));

    // Second concurrent request for the SAME tab should be rejected immediately
    mockChrome.runtime.onMessage.dispatch(
      { type: 'DOUYIN_DEBUGGER_HOVER', point: { x: 150, y: 250 } },
      sender,
      sendResponse2
    );

    await vi.waitFor(() => expect(sendResponse2).toHaveBeenCalled());
    expect(sendResponse2).toHaveBeenCalledWith({ ok: false, fallback: true, error: 'debugger busy' });

    // First request should still be pending (no response yet)
    expect(sendResponse1).not.toHaveBeenCalled();
  });

  it('allows concurrent DOUYIN_DEBUGGER_HOVER for different tabs (no throttle cross-tab)', async () => {
    const sendResponse1 = vi.fn();
    const sendResponse2 = vi.fn();
    const senderTab123 = {
      tab: { id: 123, url: 'https://www.douyin.com/notice' },
    };
    const senderTab456 = {
      tab: { id: 456, url: 'https://www.douyin.com/notice' },
    };

    dispatchTrustedHoverMock.mockResolvedValue({ captured: true, fallback: false });

    // Two requests for DIFFERENT tabs should both proceed
    mockChrome.runtime.onMessage.dispatch(
      { type: 'DOUYIN_DEBUGGER_HOVER', point: { x: 100, y: 200 } },
      senderTab123,
      sendResponse1
    );

    mockChrome.runtime.onMessage.dispatch(
      { type: 'DOUYIN_DEBUGGER_HOVER', point: { x: 150, y: 250 } },
      senderTab456,
      sendResponse2
    );

    await vi.waitFor(() => expect(dispatchTrustedHoverMock).toHaveBeenCalledTimes(2));
    expect(dispatchTrustedHoverMock).toHaveBeenNthCalledWith(
      1,
      '123',
      { x: 100, y: 200 },
      expect.any(Object)
    );
    expect(dispatchTrustedHoverMock).toHaveBeenNthCalledWith(
      2,
      '456',
      { x: 150, y: 250 },
      expect.any(Object)
    );
  });

  it('allows new request for same tab after previous completes (lock released in finally)', async () => {
    const sendResponse1 = vi.fn();
    const sendResponse2 = vi.fn();
    const sender = {
      tab: { id: 123, url: 'https://www.douyin.com/notice' },
    };

    // First request resolves immediately
    dispatchTrustedHoverMock.mockResolvedValue({ captured: true, fallback: false });

    mockChrome.runtime.onMessage.dispatch(
      { type: 'DOUYIN_DEBUGGER_HOVER', point: { x: 100, y: 200 } },
      sender,
      sendResponse1
    );

    await vi.waitFor(() => expect(sendResponse1).toHaveBeenCalledWith({ ok: true, captured: true, fallback: false }));

    // Second request for the SAME tab should now succeed (lock was released)
    mockChrome.runtime.onMessage.dispatch(
      { type: 'DOUYIN_DEBUGGER_HOVER', point: { x: 150, y: 250 } },
      sender,
      sendResponse2
    );

    await vi.waitFor(() => expect(sendResponse2).toHaveBeenCalledWith({ ok: true, captured: true, fallback: false }));
    expect(dispatchTrustedHoverMock).toHaveBeenCalledTimes(2);
  });
});

/**
 * Integration-style tests for DOUYIN_DEBUGGER_HOVER that exercise the real
 * dispatchTrustedHover path with real chrome.debugger.* mocks.
 *
 * These verify the DebuggerApi adapter inside handleMessage correctly:
 *  - converts sender.tab.id (string) to chrome.debugger tabId (number)
 *  - calls attach({tabId:123},'1.3')
 *  - calls sendCommand({tabId:123},'Input.dispatchMouseEvent',{type:'mouseMoved',x:10,y:20,...})
 *  - calls detach({tabId:123})
 *  - returns fallback:true when chrome.debugger.attach rejects with a conflict error
 */
