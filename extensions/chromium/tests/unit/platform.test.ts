import { describe, expect, it, vi, beforeEach } from 'vitest';
import { extractBilibiliLinks } from '../../src/platform/bilibili';
import { setSubtitleRetryDelayMs } from '../../src/platform/bilibili-subtitles';
import { extractDouyinLinks } from '../../src/platform/douyin';
import { extractXiaohongshuLinks } from '../../src/platform/xiaohongshu';
import { extractWechatLinks } from '../../src/platform/wechat';

function makeDoc(html: string): Document {
  const parser = new DOMParser();
  return parser.parseFromString(html, 'text/html');
}

beforeEach(() => {
  setSubtitleRetryDelayMs(0);
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
});

describe('extractDouyinLinks', () => {
  it('extracts video id from current url', () => {
    const doc = makeDoc('<html></html>');
    const links = extractDouyinLinks(doc, 'https://www.douyin.com/video/1234567890');
    expect(links).toHaveLength(1);
    expect(links[0].url).toBe('https://www.douyin.com/video/1234567890');
    expect(links[0].platform).toBe('douyin');
  });

  it('extracts video id from anchor href', () => {
    const doc = makeDoc(
      '<html><body><a href="https://www.douyin.com/video/0987654321">Link</a></body></html>'
    );
    const links = extractDouyinLinks(doc, 'https://example.com');
    expect(links).toHaveLength(1);
    expect(links[0].url).toBe('https://www.douyin.com/video/0987654321');
  });

  it('extracts short link from script tag', () => {
    const doc = makeDoc(
      '<html><head><script>window.__INITIAL_STATE__ = {"shareUrl":"https://v.douyin.com/xxxxx"}</script></head></html>'
    );
    const links = extractDouyinLinks(doc, 'https://example.com');
    expect(links).toHaveLength(1);
    expect(links[0].url).toBe('https://v.douyin.com/xxxxx');
    expect(links[0].platform).toBe('douyin');
  });

  it('extracts video id from protocol-relative href on non-anchor element', () => {
    const doc = makeDoc(
      '<html><body><div href="//www.douyin.com/video/7639590279997132072">Video</div></body></html>'
    );
    const links = extractDouyinLinks(doc, 'https://www.douyin.com/?recommend=1');
    expect(links).toHaveLength(1);
    expect(links[0].url).toBe('https://www.douyin.com/video/7639590279997132072');
    expect(links[0].platform).toBe('douyin');
  });

  it('extracts video id from data-aweme-id attribute', () => {
    const doc = makeDoc(
      '<html><body><div data-aweme-id="7642239614674423291">Video</div></body></html>'
    );
    const links = extractDouyinLinks(doc, 'https://www.douyin.com/?recommend=1');
    expect(links).toHaveLength(1);
    expect(links[0].url).toBe('https://www.douyin.com/video/7642239614674423291');
    expect(links[0].platform).toBe('douyin');
  });

  it('normalizes long urls without www subdomain', () => {
    const doc = makeDoc('<html></html>');
    const links = extractDouyinLinks(doc, 'https://douyin.com/video/1111111111');
    expect(links).toHaveLength(1);
    expect(links[0].url).toBe('https://www.douyin.com/video/1111111111');
  });

  it('extracts article/note id from current url', () => {
    const doc = makeDoc('<html></html>');
    const links = extractDouyinLinks(doc, 'https://www.douyin.com/note/1234567890');
    expect(links).toHaveLength(1);
    expect(links[0].url).toBe('https://www.douyin.com/note/1234567890');
    expect(links[0].platform).toBe('douyin');
  });

  it('returns no links when nothing matches', () => {
    const doc = makeDoc('<html></html>');
    const links = extractDouyinLinks(doc, 'https://example.com');
    expect(links).toHaveLength(0);
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
});
