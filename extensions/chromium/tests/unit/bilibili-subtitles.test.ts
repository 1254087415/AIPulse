import { describe, expect, it, vi } from 'vitest';
import {
  extractBilibiliSubtitleOptions,
  extractBilibiliSubtitleOptionsFromPage,
  fetchBilibiliSubtitleOptions,
  fetchSubtitleEntries,
  formatSubtitleEntries,
} from '../../src/platform/bilibili-subtitles';

function makeDoc(html: string): Document {
  const parser = new DOMParser();
  return parser.parseFromString(html, 'text/html');
}

describe('extractBilibiliSubtitleOptions', () => {
  it('extracts subtitle options from __INITIAL_STATE__', () => {
    const doc = makeDoc(`
      <html>
        <head>
          <script>window.__INITIAL_STATE__ = {
            "videoData": {
              "subtitle": {
                "list": [
                  { "id": 1, "lan": "zh-CN", "lan_doc": "中文（自动生成）", "subtitle_url": "https://example.com/sub1.json" },
                  { "id": 2, "lan": "en-US", "lan_doc": "English", "subtitle_url": "https://example.com/sub2.json" }
                ]
              }
            }
          };</script>
        </head>
      </html>
    `);
    const options = extractBilibiliSubtitleOptions(doc);
    expect(options).toHaveLength(2);
    expect(options[0]).toEqual({
      id: '1',
      lan: 'zh-CN',
      lanDoc: '中文（自动生成）',
      subtitleUrl: 'https://example.com/sub1.json',
    });
  });

  it('returns empty array when no subtitle data', () => {
    const doc = makeDoc('<html></html>');
    const options = extractBilibiliSubtitleOptions(doc);
    expect(options).toHaveLength(0);
  });

  it('parses __INITIAL_STATE__ containing braces inside strings', () => {
    const doc = makeDoc(`
      <html>
        <head>
          <script>window.__INITIAL_STATE__ = {
            "videoData": {
              "title": "a}b",
              "subtitle": {
                "list": [
                  { "id": 1, "lan": "zh-CN", "lan_doc": "中文", "subtitle_url": "https://example.com/sub.json" }
                ]
              }
            }
          };</script>
        </head>
      </html>
    `);
    const options = extractBilibiliSubtitleOptions(doc);
    expect(options).toHaveLength(1);
    expect(options[0].lan).toBe('zh-CN');
  });

  it('constructs AI subtitle URL from id_str when subtitle_url is empty', () => {
    const doc = makeDoc(`
      <html><head>
        <script>window.__INITIAL_STATE__ = {
          "videoData": {
            "subtitle": {
              "list": [
                { "id": 4, "id_str": "2058255665230725120", "lan": "ai-zh", "lan_doc": "中文", "subtitle_url": "" }
              ]
            }
          }
        };</script>
      </head></html>
    `);
    const options = extractBilibiliSubtitleOptions(doc);
    expect(options).toHaveLength(1);
    expect(options[0].id).toBe('2058255665230725120');
    expect(options[0].subtitleUrl).toBe(
      'https://aisubtitle.hdslb.com/bfs/ai_subtitle/prod/2058255665230725120.json'
    );
  });

  // Real-world shape returned for BV1JNMV6dEp2 (AI-generated subtitles):
  // Bilibili serves AI subtitle URLs as protocol-relative ("//aisubtitle.hdslb.com/...").
  // Without normalization the downstream fetchSubtitleEntries() rejects them with
  // "Invalid subtitle URL scheme", so the option is unusable even when present.
  it('normalizes protocol-relative AI subtitle url to https (BV1JNMV6dEp2 shape)', () => {
    const doc = makeDoc(`
      <html><head>
        <script>window.__INITIAL_STATE__ = {
          "videoData": {
            "subtitle": {
              "list": [
                { "id": 2058255665230725120, "id_str": "2058255665230725120", "lan": "ai-zh", "lan_doc": "中文（自动生成）", "subtitle_url": "//aisubtitle.hdslb.com/bfs/ai_subtitle/prod/2058255665230725120.json" },
                { "id": 2058255665230725121, "id_str": "2058255665230725121", "lan": "ai-en", "lan_doc": "English", "subtitle_url": "//aisubtitle.hdslb.com/bfs/ai_subtitle/prod/2058255665230725121.json" }
              ]
            }
          }
        };</script>
      </head></html>
    `);
    const options = extractBilibiliSubtitleOptions(doc);
    expect(options).toHaveLength(2);
    expect(options[0].subtitleUrl).toBe(
      'https://aisubtitle.hdslb.com/bfs/ai_subtitle/prod/2058255665230725120.json'
    );
    expect(options[1].subtitleUrl).toBe(
      'https://aisubtitle.hdslb.com/bfs/ai_subtitle/prod/2058255665230725121.json'
    );
    // Every returned option must be directly fetchable.
    for (const option of options) {
      expect(option.subtitleUrl.startsWith('https://')).toBe(true);
    }
  });
});

describe('extractBilibiliSubtitleOptionsFromPage', () => {
  it('extracts subtitle options from page window.__INITIAL_STATE__', async () => {
    const doc = makeDoc('<html><head></head></html>');
    document.documentElement.innerHTML = doc.documentElement.innerHTML;

    const script = document.createElement('script');
    script.textContent = `
      window.__INITIAL_STATE__ = {
        videoData: {
          subtitle: {
            list: [
              { id: 3, lan: 'zh-CN', lan_doc: '中文（自动生成）', subtitle_url: 'https://example.com/page-sub.json' }
            ]
          }
        }
      };
    `;
    document.head.appendChild(script);

    const options = await extractBilibiliSubtitleOptionsFromPage();
    expect(options).toHaveLength(1);
    expect(options[0]).toEqual({
      id: '3',
      lan: 'zh-CN',
      lanDoc: '中文（自动生成）',
      subtitleUrl: 'https://example.com/page-sub.json',
    });
  });
});

describe('fetchBilibiliSubtitleOptions', () => {
  it('fetches subtitle options from Bilibili API', async () => {
    const originalFetch = globalThis.fetch;
    globalThis.fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ data: { cid: 12345 } }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          data: {
            subtitle: {
              subtitles: [
                { id: 1, lan: 'zh-CN', lan_doc: '中文', subtitle_url: 'https://example.com/sub.json' },
              ],
            },
          },
        }),
      }) as unknown as typeof fetch;

    const options = await fetchBilibiliSubtitleOptions('BV1xx411c7m');
    expect(options).toHaveLength(1);
    expect(options[0]).toEqual({
      id: '1',
      lan: 'zh-CN',
      lanDoc: '中文',
      subtitleUrl: 'https://example.com/sub.json',
    });

    globalThis.fetch = originalFetch;
  });

  it('uses provided cid without calling view API', async () => {
    const originalFetch = globalThis.fetch;
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        data: {
          subtitle: {
            subtitles: [{ id: 2, lan: 'en-US', lan_doc: 'English', subtitle_url: 'https://example.com/en.json' }],
          },
        },
      }),
    }) as unknown as typeof fetch;

    const options = await fetchBilibiliSubtitleOptions('BV1xx411c7m', 12345);
    expect(globalThis.fetch).toHaveBeenCalledTimes(1);
    expect(options[0].lan).toBe('en-US');

    globalThis.fetch = originalFetch;
  });

  it('retries once after delay when all endpoints return empty subtitles', async () => {
    vi.useFakeTimers();
    const originalFetch = globalThis.fetch;
    globalThis.fetch = vi
      .fn()
      // First attempt: dm/view, WBI, and player all return empty.
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ data: { subtitle: { subtitles: [] } } }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ data: { subtitle: { subtitles: [] } } }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ data: { subtitle: { subtitles: [] } } }),
      })
      // Retry: dm/view and WBI still empty, player returns subtitles.
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ data: { subtitle: { subtitles: [] } } }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ data: { subtitle: { subtitles: [] } } }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          data: {
            subtitle: {
              subtitles: [
                {
                  id: 3,
                  lan: 'ai-zh',
                  lan_doc: '中文',
                  subtitle_url: 'https://example.com/retried.json',
                },
              ],
            },
          },
        }),
      }) as unknown as typeof fetch;

    const promise = fetchBilibiliSubtitleOptions('BV1xx411c7m', 12345, 67890);
    await vi.advanceTimersByTimeAsync(8000);
    const options = await promise;

    expect(options).toHaveLength(1);
    expect(options[0].lan).toBe('ai-zh');
    expect(globalThis.fetch).toHaveBeenCalledTimes(6);

    vi.useRealTimers();
    globalThis.fetch = originalFetch;
  });

  it('returns empty array when view API fails', async () => {
    const originalFetch = globalThis.fetch;
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 503,
      json: async () => ({}),
    }) as unknown as typeof fetch;

    await expect(fetchBilibiliSubtitleOptions('BV1xx411c7m')).rejects.toThrow('HTTP 503');

    globalThis.fetch = originalFetch;
  });

  it('returns empty array when cid is missing', async () => {
    const originalFetch = globalThis.fetch;
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ data: {} }),
    }) as unknown as typeof fetch;

    const options = await fetchBilibiliSubtitleOptions('BV1xx411c7m');
    expect(options).toHaveLength(0);

    globalThis.fetch = originalFetch;
  });

  // End-to-end against the real ids for BV1JNMV6dEp2 (aid 116884330584046,
  // cid 39764823837). Bilibili's player API returns AI subtitle urls in
  // protocol-relative form; the option must be normalized so it is fetchable.
  it('normalizes protocol-relative subtitle url from player API (BV1JNMV6dEp2 ids)', async () => {
    const originalFetch = globalThis.fetch;
    globalThis.fetch = vi
      .fn()
      // First call: dm/view endpoint returns an empty subtitle list -> fallback.
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ data: { subtitle: { subtitles: [] } } }),
      })
      // Second call: WBI player endpoint returns an empty subtitle list -> fallback.
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ data: { subtitle: { subtitles: [] } } }),
      })
      // Third call: player v2 endpoint returns protocol-relative AI subtitle urls.
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          data: {
            subtitle: {
              subtitles: [
                {
                  id: 2058255665230725120,
                  id_str: '2058255665230725120',
                  lan: 'ai-zh',
                  lan_doc: '中文（自动生成）',
                  subtitle_url: '//aisubtitle.hdslb.com/bfs/ai_subtitle/prod/2058255665230725120.json',
                },
              ],
            },
          },
        }),
      }) as unknown as typeof fetch;

    const options = await fetchBilibiliSubtitleOptions('BV1JNMV6dEp2', 39764823837, 116884330584046);
    expect(options).toHaveLength(1);
    expect(options[0].subtitleUrl).toBe(
      'https://aisubtitle.hdslb.com/bfs/ai_subtitle/prod/2058255665230725120.json'
    );

    globalThis.fetch = originalFetch;
  });
});

describe('formatSubtitleEntries', () => {
  it('formats entries with timestamps', () => {
    const entries = [
      { from: 0, to: 3, content: 'Hello' },
      { from: 63.5, to: 66, content: 'World' },
    ];
    expect(formatSubtitleEntries(entries)).toBe('00:00.000 Hello\n01:03.500 World');
  });
});

describe('fetchSubtitleEntries', () => {
  it('fetches and parses subtitle json', async () => {
    const originalFetch = globalThis.fetch;
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        body: [
          { from: 0, to: 2, content: '  Hello  ' },
          { from: 2, to: 4, content: 'World' },
        ],
      }),
    }) as unknown as typeof fetch;

    const entries = await fetchSubtitleEntries('https://example.com/sub.json');
    expect(entries).toHaveLength(2);
    expect(entries[0].content).toBe('Hello');
    expect(entries[1].content).toBe('World');

    globalThis.fetch = originalFetch;
  });

  it('rejects invalid URL scheme', async () => {
    await expect(fetchSubtitleEntries('javascript:alert(1)')).rejects.toThrow('Invalid subtitle URL scheme');
  });

  it('fetches subtitle entries through background when chrome runtime is available', async () => {
    const sendMessage = vi.fn((_message, callback) => {
      callback({ ok: true, data: { body: [{ from: 0, to: 2, content: '  Hello  ' }] } });
    });
    vi.stubGlobal('chrome', { runtime: { sendMessage } });

    try {
      const entries = await fetchSubtitleEntries('https://aisubtitle.hdslb.com/sub.json');
      expect(entries).toHaveLength(1);
      expect(entries[0].content).toBe('Hello');
      expect(sendMessage).toHaveBeenCalledWith(
        { type: 'FETCH_JSON', url: 'https://aisubtitle.hdslb.com/sub.json' },
        expect.any(Function)
      );
    } finally {
      vi.unstubAllGlobals();
    }
  });

  it('throws when background fetch fails', async () => {
    const sendMessage = vi.fn((_message, callback) => {
      callback({ ok: false, error: 'Background fetch failed' });
    });
    vi.stubGlobal('chrome', { runtime: { sendMessage } });

    try {
      await expect(fetchSubtitleEntries('https://aisubtitle.hdslb.com/sub.json')).rejects.toThrow(
        'Background fetch failed'
      );
    } finally {
      vi.unstubAllGlobals();
    }
  });

  it('throws when subtitle response is not ok', async () => {
    const originalFetch = globalThis.fetch;
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
    }) as unknown as typeof fetch;

    await expect(fetchSubtitleEntries('https://example.com/sub.json')).rejects.toThrow('HTTP 404');

    globalThis.fetch = originalFetch;
  });
});
