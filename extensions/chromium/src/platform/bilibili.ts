import type { FoundLink } from '../types';

const BILIBILI_PATTERN = /https?:\/\/www\.bilibili\.com\/video\/(BV[\w]+)/i;

export function extractBilibiliLinks(document: Document, url: string): FoundLink[] {
  const links: FoundLink[] = [];
  const candidates = new Set<string>();

  const canonical = document.querySelector('link[rel="canonical"]');
  if (canonical) {
    candidates.add(canonical.getAttribute('href') || '');
  }
  candidates.add(url);

  for (const anchor of document.querySelectorAll('a[href]')) {
    candidates.add(anchor.getAttribute('href') || '');
  }

  for (const candidate of candidates) {
    const match = candidate.match(BILIBILI_PATTERN);
    if (match) {
      links.push({
        url: `https://www.bilibili.com/video/${match[1]}`,
        platform: 'bilibili',
        title: document.title || undefined,
      });
    }
  }

  return links;
}
