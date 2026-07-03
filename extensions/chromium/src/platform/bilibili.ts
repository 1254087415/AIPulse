import type { FoundLink } from '../types';
import { extractMatches } from './_helpers';

const BILIBILI_PATTERN = /https?:\/\/(?:www\.)?bilibili\.com\/video\/(BV1[A-Za-z0-9]{8})/i;

export function extractBilibiliLinks(document: Document, url: string): FoundLink[] {
  const candidates = new Set<string>();

  const canonical = document.querySelector('link[rel="canonical"]');
  if (canonical) {
    candidates.add(canonical.getAttribute('href') || '');
  }
  candidates.add(url);

  for (const anchor of document.querySelectorAll('a[href]')) {
    candidates.add(anchor.getAttribute('href') || '');
  }

  return extractMatches(
    candidates,
    [
      {
        pattern: BILIBILI_PATTERN,
        platform: 'bilibili',
        transform: (match) => `https://www.bilibili.com/video/${match[1]}`,
      },
    ],
    document.title
  );
}
