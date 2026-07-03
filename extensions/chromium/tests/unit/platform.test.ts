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
  it('extracts BV id from canonical link', () => {
    const doc = makeDoc(
      '<html><head><link rel="canonical" href="https://www.bilibili.com/video/BV1xx411c7mD"></head></html>'
    );
    const links = extractBilibiliLinks(doc, 'https://www.bilibili.com/video/BV1xx411c7mD');
    expect(links).toHaveLength(1);
    expect(links[0].url).toBe('https://www.bilibili.com/video/BV1xx411c7mD');
    expect(links[0].platform).toBe('bilibili');
  });
});

describe('extractDouyinLinks', () => {
  it('extracts video id from current url', () => {
    const doc = makeDoc('<html></html>');
    const links = extractDouyinLinks(doc, 'https://www.douyin.com/video/1234567890');
    expect(links).toHaveLength(1);
    expect(links[0].url).toBe('https://www.douyin.com/video/1234567890');
  });
});

describe('extractXiaohongshuLinks', () => {
  it('extracts explore link', () => {
    const doc = makeDoc('<html></html>');
    const links = extractXiaohongshuLinks(doc, 'https://www.xiaohongshu.com/explore/abc123');
    expect(links).toHaveLength(1);
    expect(links[0].platform).toBe('xiaohongshu');
  });
});

describe('extractWechatLinks', () => {
  it('extracts wechat article link', () => {
    const doc = makeDoc('<html></html>');
    const links = extractWechatLinks(doc, 'https://mp.weixin.qq.com/s/abcdef');
    expect(links).toHaveLength(1);
    expect(links[0].platform).toBe('wechat');
  });
});
