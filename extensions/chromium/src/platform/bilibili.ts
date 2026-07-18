import type { FoundLink, SubtitleOption } from '../types';
import { dedupeLinks } from '../utils';
import { extractBilibiliSubtitleOptions, fetchBilibiliSubtitleOptions } from './bilibili-subtitles';
import { extractMatches } from './_helpers';

const BILIBILI_PATTERN = /https?:\/\/(?:www\.)?bilibili\.com\/video\/(BV1[A-Za-z0-9]{8,})/i;
const B23_SHORT_PATTERN = /https?:\/\/(?:www\.)?b23\.tv\/[A-Za-z0-9_-]+(?=\?|$)/i;

function extractBvid(url: string): string | undefined {
  const match = url.match(BILIBILI_PATTERN);
  if (match) return match[1];
  try {
    const param = new URL(url).searchParams.get('bvid');
    return param && /^BV1[A-Za-z0-9]{8,}$/.test(param) ? param : undefined;
  } catch {
    return undefined;
  }
}

function isBilibiliNonVideoPage(url: string): boolean {
  try {
    const parsed = new URL(url);
    const isBilibiliHost =
      parsed.hostname === 'bilibili.com' || parsed.hostname.endsWith('.bilibili.com');
    if (!isBilibiliHost) return false;
    if (parsed.pathname.startsWith('/video/')) return false;
    if (extractBvid(url)) return false;
    return true;
  } catch {
    return false;
  }
}

const PAGE_ID_TIMEOUT_MS = 3000;

function extractBilibiliVideoIdsFromPage(): Promise<{ aid?: number; cid?: number }> {
  return new Promise((resolve) => {
    const eventName = 'AIPULSE_BILIBILI_VIDEO_IDS';
    let cleanedUp = false;

    const cleanup = (script: HTMLScriptElement, handler: (event: Event) => void) => {
      if (cleanedUp) return;
      cleanedUp = true;
      window.removeEventListener(eventName, handler);
      script.remove();
    };

    const handler = (event: Event) => {
      const detail = (event as CustomEvent).detail as string | undefined;
      cleanup(script, handler);
      if (!detail) {
        resolve({});
        return;
      }
      try {
        const parsed = JSON.parse(detail) as { aid?: number; cid?: number };
        resolve(parsed);
      } catch {
        resolve({});
      }
    };

    const script = document.createElement('script');
    script.textContent = `
      (function() {
        try {
          const state = window.__INITIAL_STATE__;
          window.dispatchEvent(new CustomEvent('${eventName}', {
            detail: JSON.stringify({
              aid: state?.aid || undefined,
              cid: state?.videoData?.cid || undefined
            })
          }));
        } catch (e) {
          window.dispatchEvent(new CustomEvent('${eventName}', { detail: '{}' }));
        }
      })();
    `;

    window.addEventListener(eventName, handler);
    document.documentElement.appendChild(script);

    window.setTimeout(() => {
      cleanup(script, handler);
      resolve({});
    }, PAGE_ID_TIMEOUT_MS);
  });
}

async function fetchApiSubtitleOptions(bvid: string, cid?: number, aid?: number): Promise<SubtitleOption[]> {
  try {
    return await fetchBilibiliSubtitleOptions(bvid, cid, aid);
  } catch (error) {
    // eslint-disable-next-line no-console
    console.error('AIPulse: failed to fetch Bilibili subtitle options', error);
    return [];
  }
}

export async function extractBilibiliLinks(document: Document, url: string): Promise<FoundLink[]> {
  if (isBilibiliNonVideoPage(url)) {
    return [];
  }

  const candidates = new Set<string>();

  const canonical = document.querySelector('link[rel="canonical"]');
  if (canonical) {
    candidates.add(canonical.getAttribute('href') || '');
  }

  // On list pages (/list/watchlater etc.) the current video only exists as a
  // bvid query param; synthesize its canonical URL so it ranks before anchors.
  const bvid = extractBvid(url);
  if (bvid && !BILIBILI_PATTERN.test(url)) {
    candidates.add(`https://www.bilibili.com/video/${bvid}`);
  }

  candidates.add(url);

  for (const anchor of document.querySelectorAll('a[href]')) {
    candidates.add(anchor.getAttribute('href') || '');
  }

  const pageIds = bvid ? await extractBilibiliVideoIdsFromPage() : {};
  const apiSubtitleOptions = bvid
    ? await fetchApiSubtitleOptions(bvid, pageIds.cid, pageIds.aid)
    : [];
  const inlineSubtitleOptions =
    apiSubtitleOptions.length === 0 ? extractBilibiliSubtitleOptions(document) : [];

  const subtitleOptions =
    apiSubtitleOptions.length > 0 ? apiSubtitleOptions : inlineSubtitleOptions;

  const rawLinks = extractMatches(
    candidates,
    [
      {
        pattern: BILIBILI_PATTERN,
        platform: 'bilibili',
        transform: (match) => `https://www.bilibili.com/video/${match[1]}`,
      },
      {
        pattern: B23_SHORT_PATTERN,
        platform: 'bilibili',
      },
    ],
    document.title
  );

  const links = dedupeLinks(rawLinks);

  return links.map((link) => ({
    ...link,
    metadata: {
      platform: 'bilibili',
      url: link.url,
      title: link.title || document.title,
      subtitleOptions,
      subtitleEntries: [],
      selectedSubtitleLan: subtitleOptions[0]?.lan || '',
    },
  }));
}
