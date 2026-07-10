import type { FoundLink } from '../types';
import { extractMatches } from './_helpers';

const XHS_PATTERNS = [
  {
    pattern: /https?:\/\/(?:www\.)?xiaohongshu\.com\/explore\/[\w]+/i,
    platform: 'xiaohongshu' as const,
  },
  {
    pattern: /https?:\/\/(?:www\.)?xiaohongshu\.com\/discovery\/item\/[\w]+/i,
    platform: 'xiaohongshu' as const,
  },
  {
    pattern: /https?:\/\/xhslink\.com\/[\w]+/i,
    platform: 'xiaohongshu' as const,
  },
];

export function extractXiaohongshuLinks(document: Document, url: string): FoundLink[] {
  const candidates = new Set<string>();
  candidates.add(url);

  for (const anchor of document.querySelectorAll('a[href]')) {
    candidates.add(anchor.getAttribute('href') || '');
  }

  return extractMatches(candidates, XHS_PATTERNS, document.title);
}
