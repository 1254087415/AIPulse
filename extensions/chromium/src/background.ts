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

interface TabLinksEntry {
  url?: string;
  links: FoundLink[];
}

function parseTabEntry(raw: unknown): TabLinksEntry | undefined {
  if (Array.isArray(raw)) return { links: raw as FoundLink[] };
  if (raw && typeof raw === 'object' && Array.isArray((raw as TabLinksEntry).links)) {
    return raw as TabLinksEntry;
  }
  return undefined;
}

async function loadFoundLinksByTab(): Promise<Record<string, TabLinksEntry>> {
  const storage = getStorage();
  if (!storage) return {};
  return new Promise((resolve) => {
    storage.get(FOUND_LINKS_BY_TAB_KEY, (result) => {
      const map = result?.[FOUND_LINKS_BY_TAB_KEY];
      resolve(map && typeof map === 'object' ? (map as Record<string, TabLinksEntry>) : {});
    });
  });
}

async function saveFoundLinksForTab(tabId: number, links: FoundLink[], url?: string): Promise<void> {
  const storage = getStorage();
  if (!storage) return;
  const map = await loadFoundLinksByTab();
  const updated = { ...map, [String(tabId)]: { url, links } };
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
  const entry = parseTabEntry(map[String(tabId)]);
  // No flat-key fallback: returning another tab's links would make the popup
  // show stale content when the user switches tabs. The popup triggers a
  // RESCAN instead when this returns empty.
  return entry ? entry.links : [];
}

function isSamePageUrl(a: string, b: string): boolean {
  try {
    const urlA = new URL(a);
    const urlB = new URL(b);
    return urlA.origin === urlB.origin && urlA.pathname === urlB.pathname;
  } catch {
    return false;
  }
}

async function saveFoundLinks(links: FoundLink[]): Promise<void> {
  const storage = getStorage();
  if (!storage) return;
  return new Promise((resolve) => {
    storage.set({ [FOUND_LINKS_KEY]: links }, () => resolve());
  });
}

const SUPPORTED_HOSTS = [
  'bilibili.com',
  'b23.tv',
  'douyin.com',
  'xiaohongshu.com',
  'xhslink.com',
  'mp.weixin.qq.com',
  'youtube.com',
  'youtu.be',
  'localhost',
];

const ALLOWED_FETCH_HOSTS = [
  'api.bilibili.com',
  'hdslb.com',
  'aisubtitle.hdslb.com',
  'www.bilibili.com',
  'bilibili.com',
  'localhost',
];

function isAllowedFetchHost(url: string): boolean {
  try {
    const host = new URL(url).hostname;
    return ALLOWED_FETCH_HOSTS.some(
      (allowed) => host === allowed || host.endsWith(`.${allowed}`)
    );
  } catch {
    return false;
  }
}

function isSupportedPage(url: string): boolean {
  try {
    const host = new URL(url).hostname.replace(/^www\./, '');
    return SUPPORTED_HOSTS.some((supported) => host === supported || host.endsWith(`.${supported}`));
  } catch {
    return false;
  }
}

async function setBadgeCount(count: number, tabId?: number): Promise<void> {
  if (typeof chrome === 'undefined' || !chrome.action) return;
  const text = count > 0 ? String(count) : '';
  await chrome.action.setBadgeText(tabId !== undefined ? { text, tabId } : { text });
  await chrome.action.setBadgeBackgroundColor({ color: '#1677ff' });
}

async function reportBadge(links: FoundLink[], tabId?: number): Promise<void> {
  // Global badge keeps "last reporter" semantics for backward compatibility
  // (E2E tests read getBadgeText({})); per-tab badge gives each tab its own count.
  await setBadgeCount(links.length);
  if (tabId !== undefined) {
    await setBadgeCount(links.length, tabId);
  }
}

async function notify(title: string, message: string): Promise<void> {
  if (typeof chrome === 'undefined' || !chrome.notifications) return;
  try {
    await chrome.notifications.create({
      type: 'basic',
      iconUrl: 'icon.png',
      title,
      message,
    });
  } catch {
    // Notification creation can fail when the OS notification center is
    // unavailable; the submission itself has already completed.
  }
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
          await saveFoundLinksForTab(tabId, deduped, sender.tab?.url);
        }
        await reportBadge(deduped, tabId);
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
    if (!isAllowedFetchHost(message.url)) {
      sendResponse({ ok: false, error: 'host not allowed' });
      return false;
    }
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
  if (info.menuItemId !== 'archive-current-page' && info.menuItemId !== 'archive-link') {
    return;
  }
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
  // The tab navigated somewhere new. Clear its per-tab links and badge so a stale
  // count never lingers. On unsupported hosts no content script runs to re-report,
  // so clear the global badge as well; supported pages re-report within ~1s.
  if (!changeInfo.url) return;
  const navigatedUrl = changeInfo.url;
  void (async () => {
    const map = await loadFoundLinksByTab();
    const entry = parseTabEntry(map[String(tabId)]);
    // Same-document URL tweaks (history.replaceState query/hash changes, e.g.
    // Bilibili's ?t= playback-position updates) are not navigations — the content
    // script does not re-run, so the stored links are still valid. Keep them.
    if (entry?.url && isSamePageUrl(entry.url, navigatedUrl)) return;

    await removeFoundLinksForTab(tabId);
    await setBadgeCount(0, tabId);
    if (!isSupportedPage(navigatedUrl)) {
      // No content script will run on the new page to re-report, so the global
      // badge would otherwise keep showing the previous tab's count forever.
      await setBadgeCount(0);
    }
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
