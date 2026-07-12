import { submitViaHttp } from './http';
import { submitViaNativeMessaging } from './native';
import type { FoundLink, SubmitMode, SubmitPayload, SubmitResult } from './types';
import { cleanTrackingParams, dedupeLinks } from './utils';

const ALLOWED_MODES: SubmitMode[] = ['archive', 'knowledge_check'];
// Flat array of the most recently reporting tab. Kept for backward compatibility:
// E2E tests and older popup builds read this key directly from chrome.storage.
const FOUND_LINKS_KEY = 'foundLinks';
// Per-tab map: { [tabId]: FoundLink[] }. Authoritative source for popup lookups.
const FOUND_LINKS_BY_TAB_KEY = 'foundLinksByTab';

interface BackgroundMessage {
  type: 'FOUND_LINKS' | 'SUBMIT_URL' | 'GET_FOUND_LINKS' | 'FETCH_JSON';
  links?: FoundLink[];
  tabId?: unknown;
  url?: unknown;
  title?: unknown;
  mode?: unknown;
  tags?: unknown;
  subtitle_text?: unknown;
  subtitle_language?: unknown;
}

function isValidSubtitleText(value: unknown): value is string {
  return typeof value === 'string';
}

function isValidSubtitleLanguage(value: unknown): value is string {
  return typeof value === 'string';
}

function isValidTitle(value: unknown): value is string {
  return typeof value === 'string';
}

function isValidTags(value: unknown): value is string[] {
  if (!Array.isArray(value)) return false;
  return value.every((item) => typeof item === 'string' && item.length > 0);
}

function isValidUrl(value: unknown): value is string {
  if (typeof value !== 'string') return false;
  try {
    const parsed = new URL(value);
    return parsed.protocol === 'http:' || parsed.protocol === 'https:';
  } catch {
    return false;
  }
}

function isValidMode(value: unknown): value is SubmitMode {
  return typeof value === 'string' && (ALLOWED_MODES as string[]).includes(value);
}

function errorMessage(err: unknown): string {
  if (err instanceof Error) return err.message;
  return String(err);
}

function isBiliRequest(url: string): boolean {
  return /(?:api\.bilibili\.com|hdslb\.com)/.test(url);
}

async function fetchJsonThroughBackground(url: string): Promise<unknown> {
  const headers = new Headers();
  if (isBiliRequest(url)) {
    headers.set('Accept', 'application/json, text/plain, */*');
    headers.set('Accept-Language', 'zh-CN,zh;q=0.9,en;q=0.8');
    headers.set('Cache-Control', 'no-cache');
    headers.set('Pragma', 'no-cache');
  }

  // AI subtitle files on aisubtitle.hdslb.com return Access-Control-Allow-Origin: *,
  // which Chromium rejects when credentials mode is 'include'.
  const isSubtitleFile = /aisubtitle\.hdslb\.com/.test(url);

  const options: RequestInit = {
    method: 'GET',
    credentials: isSubtitleFile ? 'omit' : 'include',
    cache: 'no-store',
    headers,
  };
  if (isBiliRequest(url)) {
    options.referrer = 'https://www.bilibili.com/';
    options.referrerPolicy = 'strict-origin-when-cross-origin';
  }

  const response = await fetch(url, options);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return response.json();
}

function getStorage(): chrome.storage.LocalStorageArea | undefined {
  return typeof chrome !== 'undefined' ? chrome.storage?.local : undefined;
}

async function loadFoundLinks(): Promise<FoundLink[]> {
  const storage = getStorage();
  if (!storage) return [];
  return new Promise((resolve) => {
    storage.get(FOUND_LINKS_KEY, (result) => {
      const links = result?.[FOUND_LINKS_KEY];
      resolve(Array.isArray(links) ? links : []);
    });
  });
}

async function loadFoundLinksByTab(): Promise<Record<string, FoundLink[]>> {
  const storage = getStorage();
  if (!storage) return {};
  return new Promise((resolve) => {
    storage.get(FOUND_LINKS_BY_TAB_KEY, (result) => {
      const map = result?.[FOUND_LINKS_BY_TAB_KEY];
      resolve(map && typeof map === 'object' ? (map as Record<string, FoundLink[]>) : {});
    });
  });
}

async function saveFoundLinksForTab(tabId: number, links: FoundLink[]): Promise<void> {
  const storage = getStorage();
  if (!storage) return;
  const map = await loadFoundLinksByTab();
  const updated = { ...map, [String(tabId)]: links };
  return new Promise((resolve) => {
    storage.set({ [FOUND_LINKS_BY_TAB_KEY]: updated }, () => resolve());
  });
}

async function removeFoundLinksForTab(tabId: number): Promise<void> {
  const storage = getStorage();
  if (!storage) return;
  const map = await loadFoundLinksByTab();
  if (!(String(tabId) in map)) return;
  const updated = { ...map };
  delete updated[String(tabId)];
  return new Promise((resolve) => {
    storage.set({ [FOUND_LINKS_BY_TAB_KEY]: updated }, () => resolve());
  });
}

async function loadFoundLinksForTab(tabId: number): Promise<FoundLink[]> {
  const map = await loadFoundLinksByTab();
  const links = map[String(tabId)];
  if (Array.isArray(links)) return links;
  return loadFoundLinks();
}

async function saveFoundLinks(links: FoundLink[]): Promise<void> {
  const storage = getStorage();
  if (!storage) return;
  return new Promise((resolve) => {
    storage.set({ [FOUND_LINKS_KEY]: links }, () => resolve());
  });
}

async function updateBadge(links: FoundLink[], tabId?: number): Promise<void> {
  if (typeof chrome === 'undefined' || !chrome.action) return;
  const count = links.length;
  const details: chrome.action.BadgeTextDetails = { text: count > 0 ? String(count) : '' };
  if (tabId !== undefined) details.tabId = tabId;
  await chrome.action.setBadgeText(details);
  await chrome.action.setBadgeBackgroundColor({ color: '#1677ff' });
}

async function notify(title: string, message: string): Promise<void> {
  if (typeof chrome === 'undefined' || !chrome.notifications) return;
  await chrome.notifications.create({
    type: 'basic',
    iconUrl: 'icon.png',
    title,
    message,
  });
}

function senderTabId(sender: chrome.runtime.MessageSender): number | undefined {
  return typeof sender.tab?.id === 'number' ? sender.tab.id : undefined;
}

export function handleMessage(
  message: BackgroundMessage,
  sender: chrome.runtime.MessageSender,
  sendResponse: (response: unknown) => void
): boolean {
  if (message.type === 'FOUND_LINKS' && message.links) {
    void (async () => {
      try {
        const deduped = dedupeLinks(message.links!);
        const tabId = senderTabId(sender);
        await saveFoundLinks(deduped);
        if (tabId !== undefined) {
          await saveFoundLinksForTab(tabId, deduped);
        }
        await updateBadge(deduped, tabId);
        sendResponse({ ok: true, count: deduped.length });
      } catch (err: unknown) {
        sendResponse({ ok: false, error: errorMessage(err) });
      }
    })();
    return true;
  }

  if (message.type === 'GET_FOUND_LINKS') {
    void (async () => {
      try {
        const tabId = typeof message.tabId === 'number' ? message.tabId : undefined;
        const links = tabId !== undefined ? await loadFoundLinksForTab(tabId) : await loadFoundLinks();
        sendResponse({ links });
      } catch (err: unknown) {
        sendResponse({ links: [], error: errorMessage(err) });
      }
    })();
    return true;
  }

  if (message.type === 'SUBMIT_URL' && isValidUrl(message.url) && isValidMode(message.mode)) {
    const url = message.url;
    const mode = message.mode;
    void (async () => {
      try {
        const result = await submitUrl(
          url,
          mode,
          isValidTitle(message.title) ? message.title : undefined,
          isValidTags(message.tags) ? message.tags : undefined,
          isValidSubtitleText(message.subtitle_text) ? message.subtitle_text : undefined,
          isValidSubtitleLanguage(message.subtitle_language) ? message.subtitle_language : undefined
        );
        sendResponse({ ok: true, result });
      } catch (err: unknown) {
        sendResponse({ ok: false, error: errorMessage(err) });
      }
    })();
    return true;
  }

  if (message.type === 'FETCH_JSON' && isValidUrl(message.url)) {
    const url = message.url;
    void (async () => {
      try {
        const data = await fetchJsonThroughBackground(url);
        sendResponse({ ok: true, data });
      } catch (err: unknown) {
        sendResponse({ ok: false, error: errorMessage(err) });
      }
    })();
    return true;
  }

  sendResponse({ ok: false, error: 'invalid message' });
  return false;
}

export function setupContextMenus(): void {
  chrome.contextMenus.removeAll(() => {
    chrome.contextMenus.create({
      id: 'archive-current-page',
      title: '归档当前页面到 AIPulse',
      contexts: ['page'],
    });
    chrome.contextMenus.create({
      id: 'archive-link',
      title: '归档此链接到 AIPulse',
      contexts: ['link'],
    });
  });
}

export async function handleContextMenuClick(info: chrome.contextMenus.OnClickData): Promise<void> {
  const url = info.linkUrl || info.pageUrl;
  if (!isValidUrl(url)) return;
  try {
    await submitUrl(url, 'archive');
    await notify('AIPulse', '已归档到 AIPulse');
  } catch (err: unknown) {
    await notify('AIPulse', `归档失败: ${errorMessage(err)}`);
  }
}

async function submitUrl(
  url: string,
  mode: SubmitMode,
  title?: string,
  tags?: string[],
  subtitleText?: string,
  subtitleLanguage?: string
): Promise<SubmitResult> {
  const cleaned = cleanTrackingParams(url);
  const payload: SubmitPayload = {
    url: cleaned,
    source: 'browser_extension',
    mode,
    title,
    tags,
    subtitle_text: subtitleText,
    subtitle_language: subtitleLanguage,
  };

  try {
    return await submitViaNativeMessaging(payload);
  } catch {
    return submitViaHttp(payload);
  }
}

export { submitUrl };

function handleTabRemoved(tabId: number): void {
  void removeFoundLinksForTab(tabId);
}

function handleTabUpdated(tabId: number, changeInfo: chrome.tabs.TabChangeInfo): void {
  // The tab navigated somewhere new. Clear its links and badge immediately so a
  // stale count never lingers on unsupported pages (where no content script runs
  // to report an empty result). Supported pages re-report within ~1s.
  if (!changeInfo.url) return;
  void (async () => {
    await removeFoundLinksForTab(tabId);
    await updateBadge([], tabId);
  })();
}

if (typeof chrome !== 'undefined') {
  chrome.runtime.onMessage.addListener(handleMessage);
  chrome.runtime.onInstalled.addListener(setupContextMenus);
  chrome.contextMenus.onClicked.addListener((info) => {
    void handleContextMenuClick(info);
  });
  if (chrome.tabs?.onRemoved) {
    chrome.tabs.onRemoved.addListener(handleTabRemoved);
  }
  if (chrome.tabs?.onUpdated) {
    chrome.tabs.onUpdated.addListener(handleTabUpdated);
  }
}
