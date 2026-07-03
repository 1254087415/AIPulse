import type { FoundLink } from '../types';

const WECHAT_PATTERN = /https?:\/\/mp\.weixin\.qq\.com\/s\/[\w\-=]+/i;

export function extractWechatLinks(document: Document, url: string): FoundLink[] {
  const links: FoundLink[] = [];
  const candidates = new Set<string>();
  candidates.add(url);

  for (const anchor of document.querySelectorAll('a[href]')) {
    candidates.add(anchor.getAttribute('href') || '');
  }

  for (const candidate of candidates) {
    const match = candidate.match(WECHAT_PATTERN);
    if (match) {
      links.push({
        url: match[0],
        platform: 'wechat',
        title: document.title || undefined,
      });
    }
  }

  return links;
}
