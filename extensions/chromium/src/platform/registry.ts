import type { FoundLink } from '../types';
import { extractBilibiliLinks } from './bilibili';
import { extractDouyinLinks } from './douyin';
import { extractXiaohongshuLinks } from './xiaohongshu';
import { extractWechatLinks } from './wechat';

export interface PlatformExtractor {
  name: string;
  extract: (document: Document, url: string) => FoundLink[];
}

export const PLATFORM_EXTRACTORS: PlatformExtractor[] = [
  { name: 'bilibili', extract: extractBilibiliLinks },
  { name: 'douyin', extract: extractDouyinLinks },
  { name: 'xiaohongshu', extract: extractXiaohongshuLinks },
  { name: 'wechat', extract: extractWechatLinks },
];

export function extractAllLinks(document: Document, url: string): FoundLink[] {
  const links: FoundLink[] = [];
  for (const extractor of PLATFORM_EXTRACTORS) {
    links.push(...extractor.extract(document, url));
  }
  return links;
}
