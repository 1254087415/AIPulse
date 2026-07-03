import { describe, expect, it } from 'vitest';
import { extractBilibiliLinks } from '../../src/platform/bilibili';
import { extractDouyinLinks } from '../../src/platform/douyin';
import { extractXiaohongshuLinks } from '../../src/platform/xiaohongshu';
import { extractWechatLinks } from '../../src/platform/wechat';

function makeDoc(html: string): Document {
  const parser = new DOMParser();
  return parser.parseFromString(html, 'text/html');
}

describe('extractBilibiliLinks', () => {
  it('extracts BV id from current url', () => {
    const doc = makeDoc('<html></html>');
    const links = extractBilibiliLinks(doc, 'https://www.bilibili.com/video/BV1xx411c7m');
    expect(links).toHaveLength(1);
    expect(links[0].url).toBe('https://www.bilibili.com/video/BV1xx411c7m');
    expect(links[0].platform).toBe('bilibili');
  });

  it('extracts BV id from anchor href', () => {
    const doc = makeDoc(
      '<html><body><a href="https://www.bilibili.com/video/BV1yy411c7m">Link</a></body></html>'
    );
    const links = extractBilibiliLinks(doc, 'https://example.com');
    expect(links).toHaveLength(1);
    expect(links[0].url).toBe('https://www.bilibili.com/video/BV1yy411c7m');
  });

  it('extracts BV id from canonical link', () => {
    const doc = makeDoc(
      '<html><head><link rel="canonical" href="https://www.bilibili.com/video/BV1zz411c7m"></head></html>'
    );
    const links = extractBilibiliLinks(doc, 'https://example.com');
    expect(links).toHaveLength(1);
    expect(links[0].url).toBe('https://www.bilibili.com/video/BV1zz411c7m');
  });

  it('normalizes urls without www subdomain', () => {
    const doc = makeDoc('<html></html>');
    const links = extractBilibiliLinks(doc, 'https://bilibili.com/video/BV1aa411c7m');
    expect(links).toHaveLength(1);
    expect(links[0].url).toBe('https://www.bilibili.com/video/BV1aa411c7m');
  });

  it('rejects invalid BV ids', () => {
    const doc = makeDoc('<html></html>');
    const links = extractBilibiliLinks(doc, 'https://www.bilibili.com/video/BVtooshort');
    expect(links).toHaveLength(0);
  });

  it('returns no links when nothing matches', () => {
    const doc = makeDoc('<html></html>');
    const links = extractBilibiliLinks(doc, 'https://example.com');
    expect(links).toHaveLength(0);
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

  it('normalizes long urls without www subdomain', () => {
    const doc = makeDoc('<html></html>');
    const links = extractDouyinLinks(doc, 'https://douyin.com/video/1111111111');
    expect(links).toHaveLength(1);
    expect(links[0].url).toBe('https://www.douyin.com/video/1111111111');
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
