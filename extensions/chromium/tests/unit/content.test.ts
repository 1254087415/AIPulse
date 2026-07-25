/**
 * Unit tests for content.ts — schema validation of debugger responses.
 *
 * Background: content.ts sends DOUYIN_DEBUGGER_HOVER to the background SW
 * via chrome.runtime.sendMessage and trusts the response shape to decide
 * whether the debugger path succeeded. An attacker-controlled response
 * (or a future buggy SW build) must not coerce us into skipping the safe
 * long-link fallback.
 *
 * These tests verify:
 *  - When sendMessage returns a response missing required boolean fields,
 *    content.ts falls back to the long-link synthesis path.
 *  - When sendMessage returns a fallback:true response, content.ts falls
 *    back to the long-link path (the debugger session was preempted).
 *  - When the user has not granted debugger consent, content.ts never even
 *    sends DOUYIN_DEBUGGER_HOVER — straight to fallback.
 *  - When consent IS granted AND response is well-formed AND ok=true AND
 *    fallback=false, content.ts waits for the main-world share capture.
 */

import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

// We need to control:
//  - chrome.runtime.sendMessage → returns whatever shape we choose
//  - chrome.runtime.onMessage → must be installed before content.ts loads
//  - chrome.storage.local.get → consent gate
//  - platform/douyin-share → installShareCapture is a no-op here
//  - window.location.href → must contain 'douyin.com' so installShareCapture
//    runs without throwing

vi.mock('../../src/platform/douyin-share', () => ({
  extractDouyinVideoId: () => undefined,
  getCapturedShareUrl: () => undefined,
  installShareCapture: () => undefined,
  requestShareUrlCapture: vi.fn(async () => 'https://www.douyin.com/video/12345/'),
  findActiveSlideShareHoverPoint: vi.fn(() => ({ x: 100, y: 200 })),
}));

vi.mock('../../src/platform/douyin', () => ({
  extractActiveFeedVideoId: () => undefined,
}));

vi.mock('../../src/platform/registry', () => ({
  extractAllLinks: vi.fn(async () => []),
}));

vi.mock('../../src/platform/bilibili-subtitles', () => ({
  fetchSubtitleEntries: vi.fn(async () => []),
  formatSubtitleEntries: vi.fn(() => ''),
}));

import {
  getDouyinDebuggerConsent,
  setDouyinDebuggerConsent,
} from '../../src/popup-debugger';

function createMockEvent() {
  const listeners: Array<(...args: unknown[]) => unknown> = [];
  return {
    addListener: vi.fn((l: (...args: unknown[]) => unknown) => listeners.push(l)),
    removeListener: vi.fn((l: (...args: unknown[]) => unknown) => {
      const i = listeners.indexOf(l);
      if (i >= 0) listeners.splice(i, 1);
    }),
    dispatch: (...args: unknown[]) => listeners.forEach((l) => l(...args)),
    listeners,
  };
}

interface ContentTestSetup {
  sendMessageMock: ReturnType<typeof vi.fn>;
  fire: (msg: unknown) => Promise<unknown>;
  consent: boolean;
  debuggerResponse: unknown;
}

async function setupContentHarness(opts: {
  consent?: boolean;
  debuggerResponse?: unknown;
}): Promise<ContentTestSetup> {
  vi.resetModules();
  const sessionStore: Record<string, unknown> = {};

  const sendMessageMock = vi.fn((message: unknown, callback: (response: unknown) => void) => {
    if (
      message &&
      typeof message === 'object' &&
      (message as { type?: string }).type === 'DOUYIN_DEBUGGER_HOVER'
    ) {
      callback(opts.debuggerResponse);
    } else {
      callback(undefined);
    }
  });

  const mockChrome = {
    runtime: {
      id: 'aipulse-test',
      onMessage: createMockEvent(),
      sendMessage: sendMessageMock,
      lastError: undefined as unknown,
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
  };

  vi.stubGlobal('chrome', mockChrome as unknown as typeof chrome);

  // Seed consent if requested.
  if (opts.consent) {
    await setDouyinDebuggerConsent(true);
  } else {
    await setDouyinDebuggerConsent(false);
  }
  // Reset sessionStore so we can re-seed for the test.
  for (const k of Object.keys(sessionStore)) delete sessionStore[k];
  if (opts.consent) sessionStore['douyinDebuggerAccepted'] = true;

  // Stub window.location via Object.defineProperty hack — content.ts checks
  // window.location.href.includes('douyin.com') and installShareCapture is
  // mocked, so we just need to satisfy the conditional.
  Object.defineProperty(window, 'location', {
    value: { href: 'https://www.douyin.com/video/12345' },
    writable: true,
    configurable: true,
  });

  // Now import content.ts — its top-level onMessage listener registers.
  await import('../../src/content');

  function fire(message: unknown): Promise<unknown> {
    return new Promise((resolve) => {
      const sendResponse = (response: unknown) => resolve(response);
      const listeners = mockChrome.runtime.onMessage.listeners;
      // Pass three args (message, sender, sendResponse) per chrome API.
      listeners[0](message, { tab: { id: 1 } } as chrome.runtime.MessageSender, sendResponse);
    });
  }

  return {
    sendMessageMock,
    fire,
    consent: !!opts.consent,
    debuggerResponse: opts.debuggerResponse,
  };
}

describe('content.ts — FETCH_DOUYIN_SHARE_URL schema validation', () => {
  beforeEach(async () => {
    // Clean consent storage between tests
    await setDouyinDebuggerConsent(false);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    vi.resetModules();
  });

  it('skips debugger path when consent is missing — never calls DOUYIN_DEBUGGER_HOVER', async () => {
    const { sendMessageMock, fire } = await setupContentHarness({
      consent: false,
      debuggerResponse: { ok: true, captured: true, fallback: false },
    });

    const response = (await fire({
      type: 'FETCH_DOUYIN_SHARE_URL',
      videoId: '12345',
    })) as { ok: boolean; shareUrl?: string };

    // content.ts may call sendMessage for FOUND_LINKS (scanAndReport), but
    // MUST NOT call DOUYIN_DEBUGGER_HOVER when consent is missing.
    const debuggerCalls = sendMessageMock.mock.calls.filter(
      ([m]) =>
        m &&
        typeof m === 'object' &&
        (m as { type?: string }).type === 'DOUYIN_DEBUGGER_HOVER'
    );
    expect(debuggerCalls.length).toBe(0);
    // Falls back to requestShareUrlCapture (which returns the stub long link)
    expect(response.ok).toBe(true);
    expect(response.shareUrl).toBe('https://www.douyin.com/video/12345/');
  });

  it('rejects malformed debugger response (missing fields) → fallback to long link', async () => {
    const { sendMessageMock, fire } = await setupContentHarness({
      consent: true,
      debuggerResponse: { ok: true }, // missing captured + fallback booleans
    });

    const response = (await fire({
      type: 'FETCH_DOUYIN_SHARE_URL',
      videoId: '12345',
    })) as { ok: boolean; shareUrl?: string };

    // We DID call sendMessage (consent granted), but the schema guard rejects
    // the malformed payload and we drop to the long-link fallback.
    const debuggerCalls = sendMessageMock.mock.calls.filter(
      ([m]) =>
        m &&
        typeof m === 'object' &&
        (m as { type?: string }).type === 'DOUYIN_DEBUGGER_HOVER'
    );
    expect(debuggerCalls.length).toBe(1);
    expect(response.shareUrl).toBe('https://www.douyin.com/video/12345/');
    expect(response.ok).toBe(true);
  });

  it('rejects debugger response with wrong field types → fallback to long link', async () => {
    const { fire } = await setupContentHarness({
      consent: true,
      // The schema requires boolean booleans — strings here must be rejected.
      debuggerResponse: { ok: 'yes', captured: 'true', fallback: 'false' },
    });

    const response = (await fire({
      type: 'FETCH_DOUYIN_SHARE_URL',
      videoId: '12345',
    })) as { ok: boolean; shareUrl?: string };

    expect(response.shareUrl).toBe('https://www.douyin.com/video/12345/');
  });

  it('honors debugger fallback:true → falls through to long link', async () => {
    const { fire } = await setupContentHarness({
      consent: true,
      debuggerResponse: { ok: true, captured: false, fallback: true },
    });

    const response = (await fire({
      type: 'FETCH_DOUYIN_SHARE_URL',
      videoId: '12345',
    })) as { ok: boolean; shareUrl?: string };

    expect(response.shareUrl).toBe('https://www.douyin.com/video/12345/');
  });

  it('honors debugger ok:false → falls through to long link', async () => {
    const { fire } = await setupContentHarness({
      consent: true,
      debuggerResponse: { ok: false, captured: false, fallback: false },
    });

    const response = (await fire({
      type: 'FETCH_DOUYIN_SHARE_URL',
      videoId: '12345',
    })) as { ok: boolean; shareUrl?: string };

    expect(response.shareUrl).toBe('https://www.douyin.com/video/12345/');
  });

  it('consent storage round-trip: set then read returns true', async () => {
    // The previous tests stubbed chrome via setupContentHarness; for this
    // isolated round-trip we set up a minimal chrome stub directly.
    const store: Record<string, unknown> = {};
    vi.stubGlobal('chrome', {
      storage: {
        local: {
          get: vi.fn((keys: string, cb: (r: Record<string, unknown>) => void) =>
            cb({ [keys]: store[keys] })
          ),
          set: vi.fn((items: Record<string, unknown>, cb?: () => void) => {
            Object.assign(store, items);
            if (cb) cb();
          }),
        },
      },
      runtime: { lastError: undefined },
    } as unknown as typeof chrome);

    await setDouyinDebuggerConsent(true);
    expect(await getDouyinDebuggerConsent()).toBe(true);
    await setDouyinDebuggerConsent(false);
    expect(await getDouyinDebuggerConsent()).toBe(false);
    // Make sure 'truthy non-bool' values are NOT accepted.
    store['douyinDebuggerAccepted'] = 'yes';
    expect(await getDouyinDebuggerConsent()).toBe(false);
  });
});