import type { FoundLink } from '../types';
import { extractBilibiliLinks } from './bilibili';
import { extractDouyinLinks } from './douyin';
import { extractXiaohongshuLinks } from './xiaohongshu';
import { extractWechatLinks } from './wechat';

export interface PlatformExtractor {
  name: string;
  extract: (document: Document, url: string) => FoundLink[] | Promise<FoundLink[]>;
}

export const PLATFORM_EXTRACTORS: PlatformExtractor[] = [
  { name: 'bilibili', extract: extractBilibiliLinks },
  { name: 'douyin', extract: extractDouyinLinks },
  { name: 'xiaohongshu', extract: extractXiaohongshuLinks },
  { name: 'wechat', extract: extractWechatLinks },
];

export async function extractAllLinks(document: Document, url: string): Promise<FoundLink[]> {
  const links: FoundLink[] = [];
  for (const extractor of PLATFORM_EXTRACTORS) {
    const result = extractor.extract(document, url);
    links.push(...(await result));
  }
  return links;
}
