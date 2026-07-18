import type { FoundLink } from '../types';
import { extractMatches } from './_helpers';

const WECHAT_PATTERN = /https?:\/\/mp\.weixin\.qq\.com\/s\/[\w\-=]+(?=\?|$)/i;

export function extractWechatLinks(document: Document, url: string): FoundLink[] {
  const candidates = new Set<string>();
  candidates.add(url);

  for (const anchor of document.querySelectorAll('a[href]')) {
    candidates.add(anchor.getAttribute('href') || '');
  }

  return extractMatches(
    candidates,
    [{ pattern: WECHAT_PATTERN, platform: 'wechat' }],
    document.title
  );
}
