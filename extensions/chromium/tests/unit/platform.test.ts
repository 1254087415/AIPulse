import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { extractBilibiliLinks } from '../../src/platform/bilibili';
import { setSubtitleRetryDelayMs } from '../../src/platform/bilibili-subtitles';
import { extractDouyinLinks } from '../../src/platform/douyin';
import { clearCapturedShareUrls, setCapturedShareUrl } from '../../src/platform/douyin-share';
import { extractXiaohongshuLinks } from '../../src/platform/xiaohongshu';
import { extractWechatLinks } from '../../src/platform/wechat';

function makeDoc(html: string): Document {
  const parser = new DOMParser();
  return parser.parseFromString(html, 'text/html');
}

beforeEach(() => {
  setSubtitleRetryDelayMs(0);
  clearCapturedShareUrls();
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        data: {
          aid: 67890,
          cid: 12345,
          subtitle: { subtitles: [] },
        },
      }),
    })
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('extractBilibiliLinks', () => {
  it('extracts BV id from current url', async () => {
    const doc = makeDoc('<html></html>');
    const links = await extractBilibiliLinks(doc, 'https://www.bilibili.com/video/BV1xx411c7m');
    expect(links).toHaveLength(1);
    expect(links[0].url).toBe('https://www.bilibili.com/video/BV1xx411c7m');
    expect(links[0].platform).toBe('bilibili');
  });

  it('extracts BV id from anchor href', async () => {
    const doc = makeDoc(
      '<html><body><a href="https://www.bilibili.com/video/BV1yy411c7m">Link</a></body></html>'
    );
    const links = await extractBilibiliLinks(doc, 'https://example.com');
    expect(links).toHaveLength(1);
    expect(links[0].url).toBe('https://www.bilibili.com/video/BV1yy411c7m');
  });

  it('extracts BV id from canonical link', async () => {
    const doc = makeDoc(
      '<html><head><link rel="canonical" href="https://www.bilibili.com/video/BV1zz411c7m"></head></html>'
    );
    const links = await extractBilibiliLinks(doc, 'https://example.com');
    expect(links).toHaveLength(1);
    expect(links[0].url).toBe('https://www.bilibili.com/video/BV1zz411c7m');
  });

  it('extracts real 12-character BV id with tracking params', async () => {
    const doc = makeDoc('<html></html>');
    const url =
      'https://www.bilibili.com/video/BV1JRMb6qE5H/?spm_id_from=333.1365.list.card_archive.click&vd_source=b8dd888f48bd000885ca4528e68fb34e';
    const links = await extractBilibiliLinks(doc, url);
    expect(links).toHaveLength(1);
    expect(links[0].url).toBe('https://www.bilibili.com/video/BV1JRMb6qE5H');
    expect(links[0].platform).toBe('bilibili');
  });

  it('normalizes urls without www subdomain', async () => {
    const doc = makeDoc('<html></html>');
    const links = await extractBilibiliLinks(doc, 'https://bilibili.com/video/BV1aa411c7m');
    expect(links).toHaveLength(1);
    expect(links[0].url).toBe('https://www.bilibili.com/video/BV1aa411c7m');
  });

  it('extracts b23.tv short link from current url', async () => {
    const doc = makeDoc('<html></html>');
    const links = await extractBilibiliLinks(doc, 'https://b23.tv/abc123');
    expect(links).toHaveLength(1);
    expect(links[0].url).toBe('https://b23.tv/abc123');
    expect(links[0].platform).toBe('bilibili');
  });

  it('extracts b23.tv short link from anchor href', async () => {
    const doc = makeDoc(
      '<html><body><a href="https://b23.tv/xyz789">Link</a></body></html>'
    );
    const links = await extractBilibiliLinks(doc, 'https://example.com');
    expect(links).toHaveLength(1);
    expect(links[0].url).toBe('https://b23.tv/xyz789');
  });

  it('extracts b23.tv short link with hyphen and underscore', async () => {
    const doc = makeDoc('<html></html>');
    const links = await extractBilibiliLinks(doc, 'https://b23.tv/abc-123_xyz');
    expect(links).toHaveLength(1);
    expect(links[0].url).toBe('https://b23.tv/abc-123_xyz');
  });

  it('extracts www.b23.tv short link', async () => {
    const doc = makeDoc('<html></html>');
    const links = await extractBilibiliLinks(doc, 'https://www.b23.tv/abc123');
    expect(links).toHaveLength(1);
    expect(links[0].url).toBe('https://www.b23.tv/abc123');
  });

  it('rejects invalid BV ids', async () => {
    const doc = makeDoc('<html></html>');
    const links = await extractBilibiliLinks(doc, 'https://www.bilibili.com/video/BVtooshort');
    expect(links).toHaveLength(0);
  });

  it('returns no links when nothing matches', async () => {
    const doc = makeDoc('<html></html>');
    const links = await extractBilibiliLinks(doc, 'https://example.com');
    expect(links).toHaveLength(0);
  });

  it('skips extraction on bilibili non-video pages', async () => {
    const doc = makeDoc(
      '<html><body><a href="https://www.bilibili.com/video/BV1yy411c7m">Link</a></body></html>'
    );
    const homepage = await extractBilibiliLinks(doc, 'https://www.bilibili.com/');
    expect(homepage).toHaveLength(0);
    const channel = await extractBilibiliLinks(doc, 'https://www.bilibili.com/v/douga');
    expect(channel).toHaveLength(0);
    const space = await extractBilibiliLinks(doc, 'https://space.bilibili.com/12345');
    expect(space).toHaveLength(0);
  });

  it('extracts the playing video from the watchlater list page', async () => {
    const doc = makeDoc('<html></html>');
    const url =
      'https://www.bilibili.com/list/watchlater?spm_id_from=333.1007.view_later.pip&bvid=BV12kTp6tENs&oid=116854148370829';
    const links = await extractBilibiliLinks(doc, url);
    expect(links.length).toBeGreaterThan(0);
    expect(links[0].url).toBe('https://www.bilibili.com/video/BV12kTp6tENs');
    expect(links[0].platform).toBe('bilibili');
  });

  it('uses inline subtitle options when __INITIAL_STATE__ has them', async () => {
    const doc = makeDoc(`
      <html><head>
        <script>window.__INITIAL_STATE__ = {
          "videoData": {
            "subtitle": {
              "list": [
                { "id": 1, "lan": "zh-CN", "lan_doc": "中文", "subtitle_url": "https://example.com/sub.json" }
              ]
            }
          }
        };</script>
      </head></html>
    `);
    const links = await extractBilibiliLinks(doc, 'https://www.bilibili.com/video/BV1xx411c7m');
    expect(links[0].metadata?.subtitleOptions).toHaveLength(1);
    expect(links[0].metadata?.subtitleOptions[0].lan).toBe('zh-CN');
  });

  it('fetches subtitle options from Bilibili WBI player API', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn()
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            data: { aid: 67890, cid: 12345 },
          }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            data: {
              subtitle: {
                subtitles: [
                  { id: 1, lan: 'ai-zh', lan_doc: '中文 [AI]', subtitle_url: 'https://aisubtitle.hdslb.com/sub.json' },
                ],
              },
            },
          }),
        })
    );
    const doc = makeDoc('<html></html>');
    const links = await extractBilibiliLinks(doc, 'https://www.bilibili.com/video/BV1xx411c7m');
    expect(links[0].metadata?.subtitleOptions).toHaveLength(1);
    expect(links[0].metadata?.subtitleOptions[0].lan).toBe('ai-zh');
    expect(links[0].metadata?.subtitleOptions[0].subtitleUrl).toBe('https://aisubtitle.hdslb.com/sub.json');
  });

  // Real-world shape for BV1JNMV6dEp2 as observed in a logged-in browser:
  // - __INITIAL_STATE__ contains aid/cid and a subtitle list, but subtitle_url is empty.
  // - WBI player endpoint returns no usable subtitles without a valid WBI signature.
  // - The extension must fall back to player v2, which returns the real AI subtitle URL
  //   in protocol-relative form ("//aisubtitle.hdslb.com/...?auth_key=...").
  it('falls back to player v2 and normalizes protocol-relative AI subtitle url (BV1JNMV6dEp2 shape)', async () => {
    const doc = makeDoc(`
      <html><head>
        <script>window.__INITIAL_STATE__ = {
          "aid": 116884330584046,
          "videoData": {
            "cid": 39764823837,
            "subtitle": {
              "list": [
                {
                  "id": 2058255665230725000,
                  "id_str": "2058255665230725120",
                  "lan": "ai-zh",
                  "lan_doc": "中文",
                  "is_lock": false,
                  "subtitle_url": "",
                  "type": 1,
                  "ai_type": 0,
                  "ai_status": 2
                }
              ]
            }
          }
        };</script>
      </head></html>
    `);

    vi.stubGlobal(
      'fetch',
      vi.fn()
        // 1st call: view API provides cid/aid because the injected page script
        // does not run in jsdom.
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            data: { aid: 116884330584046, cid: 39764823837 },
          }),
        })
        // 2nd call: WBI player endpoint returns an empty subtitle list -> fallback.
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            data: { subtitle: { subtitles: [] } },
          }),
        })
        // 3rd call: player v2 endpoint returns the real protocol-relative AI subtitle URL.
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            data: {
              subtitle: {
                subtitles: [
                  {
                    id: 1533361809971807000,
                    id_str: '1533361809971806976',
                    lan: 'ai-zh',
                    lan_doc: '中文',
                    is_lock: false,
                    subtitle_url:
                      '//aisubtitle.hdslb.com/bfs/ai_subtitle/prod/16560705161614942327d7282051948946c32b42cd71d2e6aadf?auth_key=1783603114-83f248e6e8344facac8c7b21a21979e90-0-dfb68f584b4cee72027987184b2d7864',
                    type: 1,
                    ai_type: 0,
                    ai_status: 2,
                  },
                ],
              },
            },
          }),
        })
    );

    const links = await extractBilibiliLinks(
      doc,
      'https://www.bilibili.com/video/BV1JNMV6dEp2/?spm_id_from=333.1365.list.card_archive.click&vd_source=b8dd888f48bd000885ca4528e68fb34e'
    );

    expect(links).toHaveLength(1);
    expect(links[0].url).toBe('https://www.bilibili.com/video/BV1JNMV6dEp2');
    expect(links[0].metadata?.subtitleOptions).toHaveLength(1);
    expect(links[0].metadata?.subtitleOptions[0]).toEqual({
      id: '1533361809971806976',
      lan: 'ai-zh',
      lanDoc: '中文',
      subtitleUrl:
        'https://aisubtitle.hdslb.com/bfs/ai_subtitle/prod/16560705161614942327d7282051948946c32b42cd71d2e6aadf?auth_key=1783603114-83f248e6e8344facac8c7b21a21979e90-0-dfb68f584b4cee72027987184b2d7864',
    });
  });

  it('still extracts links when subtitle API rejects', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockRejectedValue(new Error('network error'))
    );
    const doc = makeDoc('<html></html>');
    const links = await extractBilibiliLinks(doc, 'https://www.bilibili.com/video/BV1xx411c7m');
    expect(links).toHaveLength(1);
    expect(links[0].metadata?.subtitleOptions).toHaveLength(0);
  });

  it('accepts lowercase BV ids and preserves the extracted id', async () => {
    const doc = makeDoc('<html></html>');
    const links = await extractBilibiliLinks(doc, 'https://www.bilibili.com/video/bv1xx411c7m');
    expect(links).toHaveLength(1);
    expect(links[0].platform).toBe('bilibili');
    expect(links[0].url).toContain('bv1xx411c7m');
  });

  it('rejects malformed b23.tv short links', async () => {
    const doc = makeDoc('<html></html>');
    expect(await extractBilibiliLinks(doc, 'https://b23.tv/')).toHaveLength(0);
    expect(await extractBilibiliLinks(doc, 'https://b23.tv/abc$def')).toHaveLength(0);
  });

  it('returns links with empty subtitle options when __INITIAL_STATE__ is missing or malformed', async () => {
    const emptyDoc = makeDoc('<html></html>');
    const emptyLinks = await extractBilibiliLinks(emptyDoc, 'https://www.bilibili.com/video/BV1xx411c7m');
    expect(emptyLinks).toHaveLength(1);
    expect(emptyLinks[0].metadata?.subtitleOptions).toHaveLength(0);

    const malformedDoc = makeDoc('<html><head><script>window.__INITIAL_STATE__ = "not-an-object";</script></head></html>');
    const malformedLinks = await extractBilibiliLinks(malformedDoc, 'https://www.bilibili.com/video/BV1xx411c7m');
    expect(malformedLinks).toHaveLength(1);
    expect(malformedLinks[0].metadata?.subtitleOptions).toHaveLength(0);
  });

  it('handles malformed __INITIAL_STATE__ script JSON', async () => {
    const doc = makeDoc('<html><head><script>window.__INITIAL_STATE__ = { invalid json };</script></head></html>');
    const links = await extractBilibiliLinks(doc, 'https://www.bilibili.com/video/BV1xx411c7m');
    expect(links).toHaveLength(1);
    expect(links[0].metadata?.subtitleOptions).toHaveLength(0);
  });

  it('deduplicates the same BV found in multiple candidates with different tracking params', async () => {
    const doc = makeDoc(
      '<html><head><link rel="canonical" href="https://www.bilibili.com/video/BV1xx411c7m"></head>' +
        '<body>' +
        '<a href="https://www.bilibili.com/video/BV1xx411c7m?utm_source=share">Link 1</a>' +
        '<a href="https://www.bilibili.com/video/BV1xx411c7m?spm_id_from=123">Link 2</a>' +
        '</body></html>'
    );
    const links = await extractBilibiliLinks(doc, 'https://www.bilibili.com/video/BV1xx411c7m&vd_source=x');
    expect(links).toHaveLength(1);
    expect(links[0].url).toBe('https://www.bilibili.com/video/BV1xx411c7m');
  });
});

describe('extractDouyinLinks', () => {
  it('extracts video id from current url', async () => {
    const doc = makeDoc('<html></html>');
    const links = await extractDouyinLinks(doc, 'https://www.douyin.com/video/1234567890');
    expect(links).toHaveLength(1);
    expect(links[0].url).toBe('https://www.douyin.com/video/1234567890');
    expect(links[0].platform).toBe('douyin');
  });

  it('extracts video id from anchor href', async () => {
    const doc = makeDoc(
      '<html><body><a href="https://www.douyin.com/video/0987654321">Link</a></body></html>'
    );
    const links = await extractDouyinLinks(doc, 'https://example.com');
    expect(links).toHaveLength(1);
    expect(links[0].url).toBe('https://www.douyin.com/video/0987654321');
  });

  it('extracts short link from script tag', async () => {
    const doc = makeDoc(
      '<html><head><script>window.__INITIAL_STATE__ = {"shareUrl":"https://v.douyin.com/xxxxx"}</script></head></html>'
    );
    const links = await extractDouyinLinks(doc, 'https://example.com');
    expect(links).toHaveLength(1);
    expect(links[0].url).toBe('https://v.douyin.com/xxxxx');
    expect(links[0].platform).toBe('douyin');
  });

  it('extracts video id from protocol-relative href on non-anchor element', async () => {
    const doc = makeDoc(
      '<html><body><div href="//www.douyin.com/video/7639590279997132072">Video</div></body></html>'
    );
    const links = await extractDouyinLinks(doc, 'https://www.douyin.com/?recommend=1');
    expect(links).toHaveLength(1);
    expect(links[0].url).toBe('https://www.douyin.com/video/7639590279997132072');
    expect(links[0].platform).toBe('douyin');
  });

  it('extracts video id from data-aweme-id attribute', async () => {
    const doc = makeDoc(
      '<html><body><div data-aweme-id="7642239614674423291">Video</div></body></html>'
    );
    const links = await extractDouyinLinks(doc, 'https://www.douyin.com/?recommend=1');
    expect(links).toHaveLength(1);
    expect(links[0].url).toBe('https://www.douyin.com/video/7642239614674423291');
    expect(links[0].platform).toBe('douyin');
  });

  it('normalizes long urls without www subdomain', async () => {
    const doc = makeDoc('<html></html>');
    const links = await extractDouyinLinks(doc, 'https://douyin.com/video/1111111111');
    expect(links).toHaveLength(1);
    expect(links[0].url).toBe('https://www.douyin.com/video/1111111111');
  });

  it('extracts article/note id from current url', async () => {
    const doc = makeDoc('<html></html>');
    const links = await extractDouyinLinks(doc, 'https://www.douyin.com/note/1234567890');
    expect(links).toHaveLength(1);
    expect(links[0].url).toBe('https://www.douyin.com/note/1234567890');
    expect(links[0].platform).toBe('douyin');
  });

  it('returns no links when nothing matches', async () => {
    const doc = makeDoc('<html></html>');
    const links = await extractDouyinLinks(doc, 'https://example.com');
    expect(links).toHaveLength(0);
  });

  it('extracts video id from data-e2e-vid on the recommend feed player', async () => {
    // Real DOM from the logged-in recommend feed (douyin.com/?recommend=1):
    // the fullscreen slide player marks videos with data-e2e-vid and carries no
    // /video/ anchors when the jingxuan grid is not rendered underneath.
    const doc = makeDoc(
      '<html><body><div data-e2e="feed-active-video"><video></video></div>' +
        '<div data-e2e-vid="7660477699462286642" class="sliderVideo video_7660477699462286642"></div></body></html>'
    );
    const links = await extractDouyinLinks(doc, 'https://www.douyin.com/?recommend=1');
    expect(links).toHaveLength(1);
    expect(links[0].url).toBe('https://www.douyin.com/video/7660477699462286642');
    expect(links[0].platform).toBe('douyin');
  });

  it('extracts video id from the sliderVideo video_<id> class', async () => {
    const doc = makeDoc(
      '<html><body><div class="NhEiLku8 video_7659421015035324922 sliderVideo"></div></body></html>'
    );
    const links = await extractDouyinLinks(doc, 'https://www.douyin.com/?recommend=1');
    expect(links).toHaveLength(1);
    expect(links[0].url).toBe('https://www.douyin.com/video/7659421015035324922');
  });

  it('puts the currently playing feed video first on the recommend feed', async () => {
    // Real DOM structure from the logged-in recommend feed: the active slide is
    // the data-e2e-vid container holding [data-e2e="feed-active-video"].
    const doc = makeDoc(
      '<html><body>' +
        '<div data-e2e-vid="1111111111111111111" class="sliderVideo video_1111111111111111111"><video></video></div>' +
        '<div data-e2e-vid="2222222222222222222" class="sliderVideo video_2222222222222222222">' +
        '<div data-e2e="feed-active-video"><video></video></div></div>' +
        '</body></html>'
    );
    const links = await extractDouyinLinks(doc, 'https://www.douyin.com/?recommend=1');
    expect(links.length).toBeGreaterThan(0);
    expect(links[0].url).toBe('https://www.douyin.com/video/2222222222222222222');
  });

  it('returns only the active video when the feed DOM accumulates many slides', async () => {
    // Regression: scrolling the recommend feed piles slides into the DOM, and
    // collecting every slide made the badge count grow without bound (10 on
    // load, 70+ after scrolling). Only the currently playing video matters.
    const doc = makeDoc(
      '<html><body>' +
        '<div data-e2e-vid="1111111111111111111" class="sliderVideo video_1111111111111111111"><video></video></div>' +
        '<div data-e2e-vid="2222222222222222222" class="sliderVideo video_2222222222222222222">' +
        '<div data-e2e="feed-active-video"><video></video></div></div>' +
        '<div data-e2e-vid="3333333333333333333" class="sliderVideo video_3333333333333333333"><video></video></div>' +
        '</body></html>'
    );
    const links = await extractDouyinLinks(doc, 'https://www.douyin.com/?recommend=1');
    expect(links).toHaveLength(1);
    expect(links[0].url).toBe('https://www.douyin.com/video/2222222222222222222');
  });

  it('falls back to the first slide when the active feed marker is missing', async () => {
    const doc = makeDoc(
      '<html><body>' +
        '<div data-e2e-vid="1111111111111111111" class="sliderVideo video_1111111111111111111"></div>' +
        '<div data-e2e-vid="2222222222222222222" class="sliderVideo video_2222222222222222222"></div>' +
        '</body></html>'
    );
    const links = await extractDouyinLinks(doc, 'https://www.douyin.com/?recommend=1');
    expect(links).toHaveLength(1);
    expect(links[0].url).toBe('https://www.douyin.com/video/1111111111111111111');
  });

  it('attaches the official share short link to the detail page video', async () => {
    setCapturedShareUrl('1234567890', 'https://v.douyin.com/AbCdEf/');
    const doc = makeDoc('<html></html>');
    const links = await extractDouyinLinks(doc, 'https://www.douyin.com/video/1234567890');
    expect(links[0].metadata?.shareUrl).toBe('https://v.douyin.com/AbCdEf/');
    expect(links[0].url).toBe('https://www.douyin.com/video/1234567890');
  });

  it('attaches the share short link to the active feed video', async () => {
    setCapturedShareUrl('2222222222222222222', 'https://v.douyin.com/FeedLink/');
    const doc = makeDoc(
      '<html><body>' +
        '<div data-e2e-vid="2222222222222222222" class="sliderVideo video_2222222222222222222">' +
        '<div data-e2e="feed-active-video"><video></video></div></div>' +
        '</body></html>'
    );
    const links = await extractDouyinLinks(doc, 'https://www.douyin.com/?recommend=1');
    expect(links[0].metadata?.shareUrl).toBe('https://v.douyin.com/FeedLink/');
  });

  it('omits shareUrl when no short link has been captured', async () => {
    const doc = makeDoc('<html></html>');
    const links = await extractDouyinLinks(doc, 'https://www.douyin.com/video/1234567890');
    expect(links[0].url).toBe('https://www.douyin.com/video/1234567890');
    expect(links[0].metadata?.shareUrl).toBeUndefined();
  });

  it('rejects non-numeric video ids', async () => {
    const doc = makeDoc('<html></html>');
    expect(await extractDouyinLinks(doc, 'https://www.douyin.com/video/abc')).toHaveLength(0);
    expect(await extractDouyinLinks(doc, 'https://www.douyin.com/video/123abc')).toHaveLength(0);
  });

  it('returns no links for an empty recommend feed', async () => {
    const doc = makeDoc('<html></html>');
    const links = await extractDouyinLinks(doc, 'https://www.douyin.com/?recommend=1');
    expect(links).toHaveLength(0);
  });

  it('does not attach a share url that belongs to a different video', async () => {
    setCapturedShareUrl('other-id', 'https://v.douyin.com/Other/');
    const doc = makeDoc('<html></html>');
    const links = await extractDouyinLinks(doc, 'https://www.douyin.com/video/1234567890');
    expect(links[0].metadata?.shareUrl).toBeUndefined();
  });

  it('rejects invalid note ids', async () => {
    const doc = makeDoc('<html></html>');
    expect(await extractDouyinLinks(doc, 'https://www.douyin.com/note/abc')).toHaveLength(0);
  });
});

describe('extractXiaohongshuLinks', () => {
  it('extracts explore link from current url', () => {
    const doc = makeDoc('<html></html>');
    const links = extractXiaohongshuLinks(doc, 'https://www.xiaohongshu.com/explore/abc123');
    expect(links).toHaveLength(1);
    expect(links[0].url).toBe('https://www.xiaohongshu.com/explore/abc123');
    expect(links[0].platform).toBe('xiaohongshu');
  });

  it('extracts explore link from anchor href', () => {
    const doc = makeDoc(
      '<html><body><a href="https://www.xiaohongshu.com/explore/def456">Link</a></body></html>'
    );
    const links = extractXiaohongshuLinks(doc, 'https://example.com');
    expect(links).toHaveLength(1);
    expect(links[0].url).toBe('https://www.xiaohongshu.com/explore/def456');
  });

  it('extracts xhslink short link', () => {
    const doc = makeDoc('<html></html>');
    const links = extractXiaohongshuLinks(doc, 'https://xhslink.com/xyz789');
    expect(links).toHaveLength(1);
    expect(links[0].url).toBe('https://xhslink.com/xyz789');
  });

  it('matches url without www subdomain', () => {
    const doc = makeDoc('<html></html>');
    const links = extractXiaohongshuLinks(doc, 'https://xiaohongshu.com/explore/ghi012');
    expect(links).toHaveLength(1);
    expect(links[0].url).toBe('https://xiaohongshu.com/explore/ghi012');
  });

  it('extracts discovery/item share link from current url', () => {
    const doc = makeDoc('<html></html>');
    const url =
      'https://www.xiaohongshu.com/discovery/item/647b0af200000000130034f9?source=webshare';
    const links = extractXiaohongshuLinks(doc, url);
    expect(links).toHaveLength(1);
    expect(links[0].url).toBe('https://www.xiaohongshu.com/discovery/item/647b0af200000000130034f9');
    expect(links[0].platform).toBe('xiaohongshu');
  });

  it('extracts discovery/item share link from anchor href', () => {
    const doc = makeDoc(
      '<html><body><a href="https://www.xiaohongshu.com/discovery/item/641f8f6000000000140273b6">Link</a></body></html>'
    );
    const links = extractXiaohongshuLinks(doc, 'https://example.com');
    expect(links).toHaveLength(1);
    expect(links[0].url).toBe(
      'https://www.xiaohongshu.com/discovery/item/641f8f6000000000140273b6'
    );
  });

  it('returns no links when nothing matches', () => {
    const doc = makeDoc('<html></html>');
    const links = extractXiaohongshuLinks(doc, 'https://example.com');
    expect(links).toHaveLength(0);
  });

  it('rejects malformed explore ids', () => {
    const doc = makeDoc('<html></html>');
    expect(extractXiaohongshuLinks(doc, 'https://www.xiaohongshu.com/explore/')).toHaveLength(0);
    expect(extractXiaohongshuLinks(doc, 'https://www.xiaohongshu.com/explore/abc!')).toHaveLength(0);
  });

  it('deduplicates the same explore link across url and anchors with query variants', () => {
    const doc = makeDoc(
      '<html><body><a href="https://www.xiaohongshu.com/explore/abc">Link</a></body></html>'
    );
    const links = extractXiaohongshuLinks(doc, 'https://www.xiaohongshu.com/explore/abc?source=webshare');
    expect(links).toHaveLength(1);
    expect(links[0].url).toBe('https://www.xiaohongshu.com/explore/abc');
  });

  it('strips query params from discovery/item anchors', () => {
    const doc = makeDoc(
      '<html><body><a href="https://www.xiaohongshu.com/discovery/item/641f8f6000000000140273b6?source=webshare">Link</a></body></html>'
    );
    const links = extractXiaohongshuLinks(doc, 'https://example.com');
    expect(links).toHaveLength(1);
    expect(links[0].url).toBe('https://www.xiaohongshu.com/discovery/item/641f8f6000000000140273b6');
  });
});

describe('extractWechatLinks', () => {
  it('extracts article link from current url', () => {
    const doc = makeDoc('<html></html>');
    const links = extractWechatLinks(doc, 'https://mp.weixin.qq.com/s/abcdef');
    expect(links).toHaveLength(1);
    expect(links[0].url).toBe('https://mp.weixin.qq.com/s/abcdef');
    expect(links[0].platform).toBe('wechat');
  });

  it('extracts article link from anchor href', () => {
    const doc = makeDoc(
      '<html><body><a href="https://mp.weixin.qq.com/s/xyz-123=">Link</a></body></html>'
    );
    const links = extractWechatLinks(doc, 'https://example.com');
    expect(links).toHaveLength(1);
    expect(links[0].url).toBe('https://mp.weixin.qq.com/s/xyz-123=');
  });

  it('returns no links when nothing matches', () => {
    const doc = makeDoc('<html></html>');
    const links = extractWechatLinks(doc, 'https://example.com');
    expect(links).toHaveLength(0);
  });

  it('extracts article link and strips query params', () => {
    const doc = makeDoc('<html></html>');
    const links = extractWechatLinks(doc, 'https://mp.weixin.qq.com/s/abcdef?foo=bar');
    expect(links).toHaveLength(1);
    expect(links[0].url).toBe('https://mp.weixin.qq.com/s/abcdef');
  });

  it('rejects invalid article paths', () => {
    const doc = makeDoc('<html></html>');
    expect(extractWechatLinks(doc, 'https://mp.weixin.qq.com/s/')).toHaveLength(0);
    expect(extractWechatLinks(doc, 'https://mp.weixin.qq.com/s/abc!')).toHaveLength(0);
  });
});
