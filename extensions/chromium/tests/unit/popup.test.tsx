/**
 * popup.test.tsx — Real React integration test for Popup
 *
 * Tests the consent-gated auto-fetch flow:
 *   1. Without consent → popup renders the explanation card and does NOT
 *      send FETCH_DOUYIN_SHARE_URL.
 *   2. With consent → popup sends FETCH_DOUYIN_SHARE_URL exactly once and
 *      surfaces the shareUrl.
 *
 * No mocking of React internals; chrome.* APIs are stubbed instead.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';

// ---------------------------------------------------------------------------
// Mock react-dom/client so the top-level createRoot in popup.tsx is a no-op
// ---------------------------------------------------------------------------
vi.mock('react-dom/client', () => ({
  default: { createRoot: vi.fn(() => ({ render: vi.fn() })) },
}));

// ---------------------------------------------------------------------------
// Helper: build a callback-style chrome.storage.local shim matching MV3 API
// ---------------------------------------------------------------------------
function makeStorage(initial: Record<string, unknown> = {}) {
  const store: Record<string, unknown> = { ...initial };
  const get = vi.fn((key: string, cb: (result: Record<string, unknown>) => void) => {
    cb({ [key]: store[key] });
  });
  const set = vi.fn((items: Record<string, unknown>, cb: () => void) => {
    Object.assign(store, items);
    cb();
  });
  return { store, get, set };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('Popup — Douyin consent + auto-fetch integration', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.resetAllMocks();
    vi.unstubAllGlobals();
  });

  it('does NOT send FETCH_DOUYIN_SHARE_URL when consent is missing', async () => {
    const sendMessageMock = vi.fn();
    const storage = makeStorage();

    vi.stubGlobal('chrome', {
      tabs: {
        query: vi.fn().mockResolvedValue([
          { id: 1, url: 'https://www.douyin.com/video/1234567890' },
        ]),
        sendMessage: sendMessageMock,
      },
      runtime: {
        sendMessage: vi.fn().mockResolvedValueOnce({ links: [] }),
        getManifest: () => ({ version: '0.0.0' }),
        lastError: undefined,
      },
      storage: { local: storage },
    });

    // RESCAN returns the Douyin video link
    sendMessageMock.mockResolvedValueOnce({
      ok: true,
      links: [
        {
          url: 'https://www.douyin.com/video/1234567890',
          platform: 'douyin',
          title: 'Test Video',
        },
      ],
    });

    const { Popup } = await import('../../src/popup');
    render(<Popup />);

    // Consent card with the explanation should appear
    expect(
      await screen.findByText(/启用抖音分享短链自动捕获/, {}, { timeout: 3000 })
    ).toBeInTheDocument();

    // Give the effect a chance to mis-fire; then assert no fetch was sent
    await new Promise((r) => setTimeout(r, 50));
    const fetchCalls = sendMessageMock.mock.calls.filter(
      ([, msg]) => (msg as { type?: string }).type === 'FETCH_DOUYIN_SHARE_URL'
    );
    expect(fetchCalls).toHaveLength(0);
  });

  it('sends FETCH_DOUYIN_SHARE_URL exactly once when consent is granted', async () => {
    const sendMessageMock = vi.fn();
    const storage = makeStorage({ douyinDebuggerAccepted: true });

    vi.stubGlobal('chrome', {
      tabs: {
        query: vi.fn().mockResolvedValue([
          { id: 1, url: 'https://www.douyin.com/video/1234567890' },
        ]),
        sendMessage: sendMessageMock,
      },
      runtime: {
        sendMessage: vi.fn().mockResolvedValueOnce({ links: [] }),
        getManifest: () => ({ version: '0.0.0' }),
        lastError: undefined,
      },
      storage: { local: storage },
    });

    // 1st sendMessage call → RESCAN returns the Douyin video link
    sendMessageMock.mockResolvedValueOnce({
      ok: true,
      links: [
        {
          url: 'https://www.douyin.com/video/1234567890',
          platform: 'douyin',
          title: 'Test Video',
        },
      ],
    });
    // 2nd sendMessage call → FETCH_DOUYIN_SHARE_URL response
    sendMessageMock.mockResolvedValueOnce({
      ok: true,
      shareUrl: 'https://v.douyin.com/AbCdEf/',
    });

    const { Popup } = await import('../../src/popup');
    render(<Popup />);

    // Wait for FETCH_DOUYIN_SHARE_URL to be sent
    await waitFor(
      () => {
        expect(sendMessageMock).toHaveBeenCalledWith(
          1,
          expect.objectContaining({
            type: 'FETCH_DOUYIN_SHARE_URL',
            videoId: '1234567890',
          })
        );
      },
      { timeout: 3000 }
    );

    // Assert: exactly one FETCH_DOUYIN_SHARE_URL call — catches double-fire regression
    const fetchCalls = sendMessageMock.mock.calls.filter(
      ([, msg]) => (msg as { type?: string }).type === 'FETCH_DOUYIN_SHARE_URL'
    );
    expect(fetchCalls).toHaveLength(1);
  });

  it('displays the resolved share short URL after FETCH_DOUYIN_SHARE_URL resolves', async () => {
    const sendMessageMock = vi.fn();
    const storage = makeStorage({ douyinDebuggerAccepted: true });

    vi.stubGlobal('chrome', {
      tabs: {
        query: vi.fn().mockResolvedValue([
          { id: 2, url: 'https://www.douyin.com/video/9876543210' },
        ]),
        sendMessage: sendMessageMock,
      },
      runtime: {
        sendMessage: vi.fn().mockResolvedValueOnce({ links: [] }),
        getManifest: () => ({ version: '0.1.0' }),
        lastError: undefined,
      },
      storage: { local: storage },
    });

    sendMessageMock.mockResolvedValueOnce({
      ok: true,
      links: [
        {
          url: 'https://www.douyin.com/video/9876543210',
          platform: 'douyin',
          title: 'Another Video',
        },
      ],
    });
    sendMessageMock.mockResolvedValueOnce({
      ok: true,
      shareUrl: 'https://v.douyin.com/XyZu/short',
    });

    const { Popup } = await import('../../src/popup');
    render(<Popup />);

    await waitFor(
      () => {
        const urlValue = screen.queryByText('https://v.douyin.com/XyZu/short');
        expect(urlValue).toBeInTheDocument();
      },
      { timeout: 3000 }
    );
  });
});

describe('Popup — inline copy URL button', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.resetAllMocks();
    vi.unstubAllGlobals();
  });

  function stubChromeWithLink() {
    const sendMessageMock = vi.fn();
    const storage = makeStorage();
    const link = {
      url: 'https://www.bilibili.com/video/BV1xx411c7mD',
      platform: 'bilibili',
      title: 'B站视频',
    };

    vi.stubGlobal('chrome', {
      tabs: {
        query: vi.fn().mockResolvedValue([{ id: 3, url: link.url }]),
        sendMessage: sendMessageMock,
      },
      runtime: {
        sendMessage: vi.fn().mockResolvedValueOnce({ links: [] }),
        getManifest: () => ({ version: '0.1.5' }),
        lastError: undefined,
      },
      storage: { local: storage },
    });
    sendMessageMock.mockResolvedValueOnce({ ok: true, links: [link] });
    return link;
  }

  it('renders the copy button inline in the link field, not in .actions', async () => {
    stubChromeWithLink();
    const { Popup } = await import('../../src/popup');
    const { container } = render(<Popup />);

    const copyBtn = await screen.findByRole('button', { name: '复制链接' }, { timeout: 3000 });
    expect(copyBtn).toHaveClass('copy-url-btn');
    // 位于链接行内
    expect(copyBtn.closest('.url-row')).not.toBeNull();
    // .actions 区不再有「复制链接」大按钮
    const actions = container.querySelector('.actions');
    expect(actions?.textContent ?? '').not.toContain('复制链接');
  });

  it('copies the displayed URL and shows confirmation status on click', async () => {
    const link = stubChromeWithLink();
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText },
      configurable: true,
    });

    const { Popup } = await import('../../src/popup');
    render(<Popup />);

    const copyBtn = await screen.findByRole('button', { name: '复制链接' }, { timeout: 3000 });
    fireEvent.click(copyBtn);

    await waitFor(() => {
      expect(writeText).toHaveBeenCalledWith(link.url);
      expect(screen.getByText('链接已复制')).toBeInTheDocument();
    });
  });
});