import type { FoundLink } from '../types';
import { extractMatches } from './_helpers';

const DOUYIN_SHORT_LINK_PATTERN = /https?:\/\/v\.douyin\.com\/[\w]+/i;

const DOUYIN_PATTERNS = [
  {
    pattern: DOUYIN_SHORT_LINK_PATTERN,
    platform: 'douyin' as const,
  },
  {
    pattern: /https?:\/\/(?:www\.)?douyin\.com\/video\/(\d+)/i,
    platform: 'douyin' as const,
    transform: (match: RegExpMatchArray) => `https://www.douyin.com/video/${match[1]}`,
  },
  {
    pattern: /https?:\/\/(?:www\.)?douyin\.com\/note\/(\d+)/i,
    platform: 'douyin' as const,
    transform: (match: RegExpMatchArray) => `https://www.douyin.com/note/${match[1]}`,
  },
];

function normalizeUrl(value: string, baseUrl: string): string {
  if (!value) return '';
  if (value.startsWith('//')) {
    return `https:${value}`;
  }
  if (value.startsWith('/')) {
    try {
      return new URL(value, baseUrl).toString();
    } catch {
      return value;
    }
  }
  return value;
}

export function extractDouyinLinks(document: Document, url: string): FoundLink[] {
  const candidates = new Set<string>();
  candidates.add(url);

  // Douyin desktop uses <div href="//www.douyin.com/video/<id>"> cards on the homepage.
  for (const element of document.querySelectorAll('[href]')) {
    const raw = element.getAttribute('href') || '';
    const normalized = normalizeUrl(raw, url);
    if (normalized) candidates.add(normalized);
  }

  // Some cards expose the aweme id directly.
  for (const element of document.querySelectorAll('[data-aweme-id]')) {
    const awemeId = element.getAttribute('data-aweme-id');
    if (awemeId) {
      candidates.add(`https://www.douyin.com/video/${awemeId}`);
    }
  }

  for (const script of document.querySelectorAll('script')) {
    const text = script.textContent || '';
    const shareMatch = text.match(DOUYIN_SHORT_LINK_PATTERN);
    if (shareMatch) {
      candidates.add(shareMatch[0]);
    }
  }

  return extractMatches(candidates, DOUYIN_PATTERNS, document.title);
}
