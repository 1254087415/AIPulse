import { describe, expect, it } from 'vitest';
import { cleanTrackingParams, dedupeLinks } from '../../src/utils';

describe('cleanTrackingParams', () => {
  it('strips known tracking parameters', () => {
    const url = 'https://www.bilibili.com/video/BV1xx411c7mD?utm_source=share&spm_id_from=123';
    expect(cleanTrackingParams(url)).toBe('https://www.bilibili.com/video/BV1xx411c7mD');
  });

  it('strips bilibili vd_source and trailing slash', () => {
    const url =
      'https://www.bilibili.com/video/BV1JRMb6qE5H/?spm_id_from=333.1365.list.card_archive.click&vd_source=b8dd888f48bd000885ca4528e68fb34e';
    expect(cleanTrackingParams(url)).toBe('https://www.bilibili.com/video/BV1JRMb6qE5H/');
  });

  it('returns original url when parse fails', () => {
    expect(cleanTrackingParams('not-a-url')).toBe('not-a-url');
  });
});

describe('dedupeLinks', () => {
  it('removes duplicate urls after cleaning', () => {
    const links = [
      { url: 'https://a.com?utm_source=1', platform: 'bilibili' },
      { url: 'https://a.com?utm_source=2', platform: 'bilibili' },
      { url: 'https://b.com', platform: 'douyin' },
    ];
    const result = dedupeLinks(links);
    expect(result).toHaveLength(2);
    expect(result[0].url).toBe('https://a.com/');
  });
});
