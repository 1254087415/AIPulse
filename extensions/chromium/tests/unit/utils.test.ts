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

  it('returns url unchanged when no tracking params exist', () => {
    const url = 'https://example.com/page?foo=bar#section';
    expect(cleanTrackingParams(url)).toBe('https://example.com/page?foo=bar#section');
  });

  it('preserves hash fragment when stripping tracking params', () => {
    const url = 'https://example.com/page?utm_source=share#section';
    expect(cleanTrackingParams(url)).toBe('https://example.com/page#section');
  });

  it('removes multiple tracking params at once', () => {
    const url =
      'https://example.com/page?utm_source=email&spm_id_from=123&vd_source=abc&timestamp=999';
    expect(cleanTrackingParams(url)).toBe('https://example.com/page');
  });

  it('returns empty string for empty input', () => {
    expect(cleanTrackingParams('')).toBe('');
  });

  it('returns original value for non-url input', () => {
    expect(cleanTrackingParams('::not-a-url::')).toBe('::not-a-url::');
  });

  it('normalizes a url that only contained tracking params', () => {
    expect(cleanTrackingParams('https://example.com/?utm_source=share')).toBe('https://example.com/');
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

  it('returns empty array for empty input', () => {
    expect(dedupeLinks([])).toEqual([]);
  });

  it('returns a single link unchanged', () => {
    const link = { url: 'https://example.com/video', platform: 'bilibili', title: 'Title' };
    expect(dedupeLinks([link])).toEqual([{ ...link, url: 'https://example.com/video' }]);
  });

  it('preserves platform and metadata while deduplicating', () => {
    const metadata = {
      platform: 'bilibili',
      url: 'https://a.com',
      title: 'Title',
      subtitleOptions: [],
      subtitleEntries: [],
      selectedSubtitleLan: '',
    };
    const links = [
      { url: 'https://a.com?utm_source=1', platform: 'bilibili', metadata },
      { url: 'https://a.com?utm_source=2', platform: 'douyin' },
    ];
    const result = dedupeLinks(links);
    expect(result).toHaveLength(1);
    expect(result[0].platform).toBe('bilibili');
    expect(result[0].metadata).toBe(metadata);
  });

  it('keeps the first occurrence and discards later duplicates', () => {
    const first = { url: 'https://a.com?utm_source=1', platform: 'first' };
    const second = { url: 'https://a.com?utm_source=2', platform: 'second' };
    const result = dedupeLinks([first, second, { url: 'https://b.com', platform: 'third' }]);
    expect(result).toHaveLength(2);
    expect(result[0].platform).toBe('first');
    expect(result[1].platform).toBe('third');
  });
});
