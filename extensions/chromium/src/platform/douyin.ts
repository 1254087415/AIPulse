import type { FoundLink } from '../types';
import { extractMatches } from './_helpers';

const DOUYIN_PATTERNS = [
  {
    pattern: /https?:\/\/v\.douyin\.com\/[\w]+/i,
    platform: 'douyin' as const,
  },
  {
    pattern: /https?:\/\/(?:www\.)?douyin\.com\/video\/(\d+)/i,
    platform: 'douyin' as const,
    transform: (match: RegExpMatchArray) => `https://www.douyin.com/video/${match[1]}`,
  },
];

export function extractDouyinLinks(document: Document, url: string): FoundLink[] {
  const candidates = new Set<string>();
  candidates.add(url);

  for (const anchor of document.querySelectorAll('a[href]')) {
    candidates.add(anchor.getAttribute('href') || '');
  }

  for (const script of document.querySelectorAll('script')) {
    const text = script.textContent || '';
    const shareMatch = text.match(/https?:\/\/v\.douyin\.com\/[\w]+/i);
    if (shareMatch) {
      candidates.add(shareMatch[0]);
    }
  }

  return extractMatches(candidates, DOUYIN_PATTERNS, document.title);
}
