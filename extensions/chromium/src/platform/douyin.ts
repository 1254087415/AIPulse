import type { FoundLink, VideoMetadata } from '../types';
import { extractMatches } from './_helpers';
import { extractDouyinVideoId, getCapturedShareUrl } from './douyin-share';

const DOUYIN_SHORT_LINK_PATTERN = /https?:\/\/v\.douyin\.com\/[\w]+(?=\?|["'<>\)\s]|$)/i;
const DOUYIN_VIDEO_PATTERN = /https?:\/\/(?:www\.)?douyin\.com\/video\/(\d+)\/?(?:\?.*)?$/i;
const DOUYIN_NOTE_PATTERN = /https?:\/\/(?:www\.)?douyin\.com\/note\/(\d+)\/?(?:\?.*)?$/i;

const DOUYIN_PATTERNS = [
  {
    pattern: DOUYIN_SHORT_LINK_PATTERN,
    platform: 'douyin' as const,
  },
  {
    pattern: DOUYIN_VIDEO_PATTERN,
    platform: 'douyin' as const,
    transform: (match: RegExpMatchArray) => `https://www.douyin.com/video/${match[1]}`,
  },
  {
    pattern: DOUYIN_NOTE_PATTERN,
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

export function extractActiveFeedVideoId(document: Document): string | undefined {
  const active = document.querySelector('[data-e2e="feed-active-video"]');
  if (!active) return undefined;
  let el: Element | null = active;
  while (el) {
    const vid = el.getAttribute('data-e2e-vid');
    if (vid && /^\d+$/.test(vid)) return vid;
    el = el.parentElement;
  }
  return undefined;
}

// The logged-in recommend feed (douyin.com/?recommend=1) renders a fullscreen
// slide player without /video/ anchors. Its slides carry the aweme id in
// data-e2e-vid and in the sliderVideo `video_<id>` class.
function collectSlideVideoIds(document: Document): string[] {
  const ids: string[] = [];
  const seen = new Set<string>();
  const push = (vid: string | null) => {
    if (vid && /^\d+$/.test(vid) && !seen.has(vid)) {
      seen.add(vid);
      ids.push(vid);
    }
  };
  for (const element of document.querySelectorAll('[data-e2e-vid]')) {
    push(element.getAttribute('data-e2e-vid'));
  }
  for (const element of document.querySelectorAll('div[class*="video_"]')) {
    const match = element.className.match(/(?:^|\s)video_(\d+)/);
    if (match) push(match[1]);
  }
  return ids;
}

function extractItemId(url: string): { id: string; kind: 'video' | 'note' } | undefined {
  const video = url.match(DOUYIN_VIDEO_PATTERN);
  if (video) return { id: video[1], kind: 'video' };
  const note = url.match(DOUYIN_NOTE_PATTERN);
  if (note) return { id: note[1], kind: 'note' };
  return undefined;
}

function withMetadata(link: FoundLink, videoId: string, shareUrl?: string): FoundLink {
  const metadata: VideoMetadata = {
    platform: 'douyin',
    url: link.url,
    title: link.title || '',
    subtitleOptions: [],
    subtitleEntries: [],
    selectedSubtitleLan: '',
    ...(shareUrl ? { shareUrl } : {}),
  };
  return { ...link, metadata };
}

export async function extractDouyinLinks(document: Document, url: string): Promise<FoundLink[]> {
  // The slide feed DOM accumulates slides while scrolling. Only the currently
  // playing video matters — collecting every slide made the badge count grow
  // without bound (10 on load, 70+ after scrolling).
  const slideVids = collectSlideVideoIds(document);
  if (slideVids.length > 0) {
    const primaryId = extractActiveFeedVideoId(document) || slideVids[0];
    const link: FoundLink = {
      url: `https://www.douyin.com/video/${primaryId}`,
      platform: 'douyin',
      title: document.title || undefined,
    };
    const shareUrl = getCapturedShareUrl(primaryId);
    return [withMetadata(link, primaryId, shareUrl)];
  }

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

  const links = extractMatches(candidates, DOUYIN_PATTERNS, document.title);
  return links.map((link) => {
    const videoId = extractDouyinVideoId(link.url);
    const shareUrl = videoId ? getCapturedShareUrl(videoId) : undefined;
    return withMetadata(link, videoId || '', shareUrl);
  });
}
