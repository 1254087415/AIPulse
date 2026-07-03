import type { FoundLink } from '../types';

const XHS_PATTERNS = [
  /https?:\/\/www\.xiaohongshu\.com\/explore\/[\w]+/i,
  /https?:\/\/xhslink\.com\/[\w]+/i,
];

export function extractXiaohongshuLinks(document: Document, url: string): FoundLink[] {
  const links: FoundLink[] = [];
  const candidates = new Set<string>();
  candidates.add(url);

  for (const anchor of document.querySelectorAll('a[href]')) {
    candidates.add(anchor.getAttribute('href') || '');
  }

  for (const candidate of candidates) {
    for (const pattern of XHS_PATTERNS) {
      const match = candidate.match(pattern);
      if (match) {
        links.push({
          url: match[0],
          platform: 'xiaohongshu',
          title: document.title || undefined,
        });
        break;
      }
    }
  }

  return links;
}
