import type { FoundLink } from '../types';

const DOUYIN_VIDEO_PATTERN = /https?:\/\/www\.douyin\.com\/video\/(\d+)/i;

export function extractDouyinLinks(document: Document, url: string): FoundLink[] {
  const links: FoundLink[] = [];
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

  for (const candidate of candidates) {
    const match = candidate.match(DOUYIN_VIDEO_PATTERN);
    if (match) {
      links.push({
        url: `https://www.douyin.com/video/${match[1]}`,
        platform: 'douyin',
        title: document.title || undefined,
      });
    }
  }

  return links;
}
