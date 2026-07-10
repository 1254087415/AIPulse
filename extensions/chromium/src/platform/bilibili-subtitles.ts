import type { SubtitleEntry, SubtitleOption } from '../types';

interface BilibiliSubtitleItem {
  id: number;
  id_str?: string;
  lan: string;
  lan_doc: string;
  subtitle_url: string;
  type?: number;
  ai_type?: number;
  ai_status?: number;
}

interface BilibiliSubtitleBodyItem {
  from: number;
  to: number;
  content: string;
}

interface BilibiliViewResponse {
  data?: {
    aid?: number;
    cid?: number;
  };
}

interface BilibiliPlayerResponse {
  data?: {
    subtitle?: {
      subtitles?: BilibiliSubtitleItem[];
    };
  };
}

function extractJsonObject(text: string, start: number): string | undefined {
  let i = start;
  while (i < text.length && /\s/.test(text[i])) {
    i += 1;
  }
  if (text[i] !== '{') return undefined;

  let depth = 0;
  let inString = false;
  let escape = false;
  for (; i < text.length; i += 1) {
    const ch = text[i];
    if (inString) {
      if (escape) {
        escape = false;
      } else if (ch === '\\') {
        escape = true;
      } else if (ch === '"') {
        inString = false;
      }
      continue;
    }

    if (ch === '"') {
      inString = true;
    } else if (ch === '{') {
      depth += 1;
    } else if (ch === '}') {
      depth -= 1;
      if (depth === 0) {
        return text.slice(start, i + 1);
      }
    }
  }
  return undefined;
}

function extractInitialState(document: Document): unknown {
  for (const script of document.querySelectorAll('script')) {
    const text = script.textContent || '';
    const match = text.match(/window\.__INITIAL_STATE__\s*=\s*/);
    if (!match) continue;

    const json = extractJsonObject(text, match.index! + match[0].length);
    if (!json) continue;

    try {
      return JSON.parse(json);
    } catch {
      return undefined;
    }
  }
  return undefined;
}

function getSubtitleList(initialState: unknown): BilibiliSubtitleItem[] {
  if (typeof initialState !== 'object' || initialState === null) return [];
  const state = initialState as Record<string, unknown>;
  const videoData = state.videoData as Record<string, unknown> | undefined;
  if (!videoData) return [];
  const subtitle = videoData.subtitle as Record<string, unknown> | undefined;
  if (!subtitle) return [];
  const list = subtitle.list as BilibiliSubtitleItem[] | undefined;
  return list || [];
}

function resolveSubtitleUrl(item: BilibiliSubtitleItem): string {
  if (item.subtitle_url) {
    // Bilibili serves AI subtitle urls as protocol-relative ("//aisubtitle.hdslb.com/...")
    // or plain http. Normalize to https so the value is directly fetchable, passes the
    // scheme check in fetchSubtitleEntries(), and matches the extension's host_permissions.
    if (item.subtitle_url.startsWith('//')) {
      return `https:${item.subtitle_url}`;
    }
    if (item.subtitle_url.startsWith('http://')) {
      return item.subtitle_url.replace(/^http:/, 'https:');
    }
    return item.subtitle_url;
  }
  if (item.id_str) {
    return `https://aisubtitle.hdslb.com/bfs/ai_subtitle/prod/${encodeURIComponent(item.id_str)}.json`;
  }
  return '';
}

function mapSubtitleOptions(list: BilibiliSubtitleItem[]): SubtitleOption[] {
  return list.map((item) => ({
    id: item.id_str || String(item.id),
    lan: item.lan,
    lanDoc: item.lan_doc,
    subtitleUrl: resolveSubtitleUrl(item),
  }));
}

export function extractBilibiliSubtitleOptions(document: Document): SubtitleOption[] {
  const initialState = extractInitialState(document);
  const list = getSubtitleList(initialState);
  return mapSubtitleOptions(list);
}

const PAGE_SCRIPT_TIMEOUT_MS = 3000;

export function extractBilibiliSubtitleOptionsFromPage(): Promise<SubtitleOption[]> {
  return new Promise((resolve) => {
    const eventName = 'AIPULSE_BILIBILI_SUBTITLES';
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
        resolve([]);
        return;
      }
      try {
        const list = JSON.parse(detail) as BilibiliSubtitleItem[];
        resolve(mapSubtitleOptions(list));
      } catch {
        resolve([]);
      }
    };

    const script = document.createElement('script');
    script.textContent = `
      (function() {
        try {
          const state = window.__INITIAL_STATE__;
          const list = state?.videoData?.subtitle?.list || [];
          window.dispatchEvent(new CustomEvent('${eventName}', {
            detail: JSON.stringify(list)
          }));
        } catch (e) {
          window.dispatchEvent(new CustomEvent('${eventName}', { detail: '[]' }));
        }
      })();
    `;

    window.addEventListener(eventName, handler);
    document.documentElement.appendChild(script);

    window.setTimeout(() => {
      cleanup(script, handler);
      resolve([]);
    }, PAGE_SCRIPT_TIMEOUT_MS);
  });
}

function isExtensionRuntime(): boolean {
  return (
    typeof chrome !== 'undefined' &&
    typeof chrome.runtime !== 'undefined' &&
    typeof chrome.runtime.sendMessage === 'function'
  );
}

async function fetchJsonThroughRuntime(url: string): Promise<unknown> {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage({ type: 'FETCH_JSON', url }, (response: { ok: boolean; data?: unknown; error?: string } | undefined) => {
      if (chrome.runtime.lastError) {
        reject(new Error(chrome.runtime.lastError.message));
        return;
      }
      if (!response?.ok) {
        reject(new Error(response?.error || 'Background fetch failed'));
        return;
      }
      resolve(response.data);
    });
  });
}

async function fetchJsonDirect(url: string): Promise<unknown> {
  const isBiliRequest = /(?:api\.bilibili\.com|hdslb\.com)/.test(url);
  // AI subtitle files on hdslb.com return Access-Control-Allow-Origin: *, which
  // Chromium rejects when credentials mode is 'include'. Use 'omit' for those.
  const isSubtitleFile = /aisubtitle\.hdslb\.com/.test(url);
  const response = await fetch(url, {
    credentials: isSubtitleFile ? 'omit' : 'include',
    cache: 'no-store',
    ...(isBiliRequest
      ? {
          headers: {
            Accept: 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Cache-Control': 'no-cache',
            Pragma: 'no-cache',
          },
          referrer: 'https://www.bilibili.com/',
          referrerPolicy: 'strict-origin-when-cross-origin',
        }
      : {}),
  });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return response.json();
}

async function fetchJson(url: string): Promise<unknown> {
  // Prefer direct fetch first; it carries the page's cookies and referrer which
  // Bilibili often requires. Fall back to the background runtime fetch only when
  // direct fetch is blocked (e.g. by CSP in a content script context).
  try {
    return await fetchJsonDirect(url);
  } catch (directError) {
    if (isExtensionRuntime()) {
      return fetchJsonThroughRuntime(url);
    }
    throw directError;
  }
}

async function fetchCidAndAid(bvid: string): Promise<{ cid: number; aid?: number } | undefined> {
  const data = (await fetchJson(
    `https://api.bilibili.com/x/web-interface/view?bvid=${encodeURIComponent(bvid)}`
  )) as BilibiliViewResponse;
  const cid = data?.data?.cid;
  const aid = data?.data?.aid;
  if (!cid) return undefined;
  return { cid, aid };
}

async function fetchSubtitlesFromWbiPlayer(
  bvid: string,
  cid: number,
  aid: number
): Promise<SubtitleOption[]> {
  const url =
    'https://api.bilibili.com/x/player/wbi/v2' +
    `?aid=${encodeURIComponent(String(aid))}` +
    `&cid=${encodeURIComponent(String(cid))}` +
    `&bvid=${encodeURIComponent(bvid)}`;
  const data = (await fetchJson(url)) as BilibiliPlayerResponse;
  const list = data?.data?.subtitle?.subtitles || [];
  return mapSubtitleOptions(list);
}

async function fetchSubtitlesFromPlayer(bvid: string, cid: number, aid?: number): Promise<SubtitleOption[]> {
  const params = new URLSearchParams();
  params.set('cid', String(cid));
  params.set('bvid', bvid);
  if (aid) params.set('aid', String(aid));
  const url = `https://api.bilibili.com/x/player/v2?${params.toString()}`;
  const data = (await fetchJson(url)) as BilibiliPlayerResponse;
  const list = data?.data?.subtitle?.subtitles || [];
  return mapSubtitleOptions(list);
}

// x/v2/dm/view exposes subtitle metadata without requiring login cookies,
// making it more reliable than player/v2 in extension contexts.
async function fetchSubtitlesFromDmView(cid: number): Promise<SubtitleOption[]> {
  const url = `https://api.bilibili.com/x/v2/dm/view?oid=${encodeURIComponent(String(cid))}&type=1`;
  const data = (await fetchJson(url)) as BilibiliPlayerResponse;
  const list = data?.data?.subtitle?.subtitles || [];
  return mapSubtitleOptions(list);
}

function filterValidSubtitleOptions(options: SubtitleOption[]): SubtitleOption[] {
  return options.filter((option) => option.subtitleUrl);
}

let subtitleRetryDelayMs = 8000;

// Exposed for tests so they can run without waiting for the real retry delay.
export function setSubtitleRetryDelayMs(ms: number): void {
  subtitleRetryDelayMs = ms;
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

async function tryFetchSubtitleOptions(
  bvid: string,
  cid: number,
  aid?: number
): Promise<SubtitleOption[]> {
  // Prefer the cookie-less dm/view endpoint; it is more reliable in extension contexts.
  try {
    const dmViewOptions = await fetchSubtitlesFromDmView(cid);
    const validDmView = filterValidSubtitleOptions(dmViewOptions);
    if (validDmView.length > 0) return validDmView;
  } catch (error) {
    // eslint-disable-next-line no-console
    console.error('AIPulse: dm/view subtitle request failed', error);
  }

  try {
    if (aid) {
      const wbiOptions = await fetchSubtitlesFromWbiPlayer(bvid, cid, aid);
      const validWbi = filterValidSubtitleOptions(wbiOptions);
      if (validWbi.length > 0) return validWbi;
    }
  } catch (error) {
    // eslint-disable-next-line no-console
    console.error('AIPulse: WBI player subtitle request failed', error);
  }

  try {
    const playerOptions = await fetchSubtitlesFromPlayer(bvid, cid, aid);
    return filterValidSubtitleOptions(playerOptions);
  } catch (error) {
    // eslint-disable-next-line no-console
    console.error('AIPulse: player subtitle request failed', error);
    return [];
  }
}

export async function fetchBilibiliSubtitleOptions(
  bvid: string,
  cid?: number,
  aid?: number
): Promise<SubtitleOption[]> {
  let resolvedCid = cid;
  let resolvedAid = aid;
  if (!resolvedCid) {
    const ids = await fetchCidAndAid(bvid);
    if (!ids) return [];
    resolvedCid = ids.cid;
    resolvedAid = ids.aid;
  }

  const firstAttempt = await tryFetchSubtitleOptions(bvid, resolvedCid, resolvedAid);
  if (firstAttempt.length > 0) return firstAttempt;

  // Bilibili sometimes delays exposing AI subtitle data until the player has initialized.
  // Wait and retry once before giving up.
  await delay(subtitleRetryDelayMs);
  return tryFetchSubtitleOptions(bvid, resolvedCid, resolvedAid);
}

function formatTimestamp(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  const ms = Math.floor((seconds % 1) * 1000);
  return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}.${String(ms).padStart(3, '0')}`;
}

export function formatSubtitleEntries(entries: SubtitleEntry[]): string {
  return entries.map((entry) => `${formatTimestamp(entry.from)} ${entry.content}`).join('\n');
}

export async function fetchSubtitleEntries(subtitleUrl: string): Promise<SubtitleEntry[]> {
  if (!subtitleUrl.startsWith('http://') && !subtitleUrl.startsWith('https://')) {
    throw new Error('Invalid subtitle URL scheme');
  }
  const data = (await fetchJson(subtitleUrl)) as { body?: BilibiliSubtitleBodyItem[] };
  const body = data.body || [];
  return body.map((item) => ({
    from: item.from,
    to: item.to,
    content: item.content.trim(),
  }));
}
