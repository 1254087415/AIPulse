import { submitViaHttp } from './http';
import { submitViaNativeMessaging } from './native';
import type { FoundLink, SubmitMode, SubmitPayload, SubmitResult } from './types';
import { cleanTrackingParams, dedupeLinks } from './utils';

const ALLOWED_MODES: SubmitMode[] = ['archive', 'knowledge_check'];
const FOUND_LINKS_KEY = 'foundLinks';

interface BackgroundMessage {
  type: 'FOUND_LINKS' | 'SUBMIT_URL' | 'GET_FOUND_LINKS' | 'FETCH_JSON';
  links?: FoundLink[];
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

  const options: RequestInit = {
    method: 'GET',
    credentials: 'include',
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

async function saveFoundLinks(links: FoundLink[]): Promise<void> {
  const storage = getStorage();
  if (!storage) return;
  return new Promise((resolve) => {
    storage.set({ [FOUND_LINKS_KEY]: links }, () => resolve());
  });
}

async function updateBadge(links: FoundLink[]): Promise<void> {
  if (typeof chrome === 'undefined' || !chrome.action) return;
  const count = links.length;
  chrome.action.setBadgeText({ text: count > 0 ? String(count) : '' });
  chrome.action.setBadgeBackgroundColor({ color: '#1677ff' });
}

export function handleMessage(
  message: BackgroundMessage,
  _sender: chrome.runtime.MessageSender,
  sendResponse: (response: unknown) => void
): boolean {
  if (message.type === 'FOUND_LINKS' && message.links) {
    const deduped = dedupeLinks(message.links);
    saveFoundLinks(deduped)
      .then(() => updateBadge(deduped))
      .then(() => sendResponse({ ok: true, count: deduped.length }))
      .catch((err: unknown) => sendResponse({ ok: false, error: errorMessage(err) }));
    return true;
  }

  if (message.type === 'GET_FOUND_LINKS') {
    loadFoundLinks()
      .then((links) => sendResponse({ links }))
      .catch((err: unknown) => sendResponse({ links: [], error: errorMessage(err) }));
    return true;
  }

  if (message.type === 'SUBMIT_URL' && isValidUrl(message.url) && isValidMode(message.mode)) {
    submitUrl(
      message.url,
      message.mode,
      isValidTitle(message.title) ? message.title : undefined,
      isValidTags(message.tags) ? message.tags : undefined,
      isValidSubtitleText(message.subtitle_text) ? message.subtitle_text : undefined,
      isValidSubtitleLanguage(message.subtitle_language) ? message.subtitle_language : undefined
    )
      .then((result) => sendResponse({ ok: true, result }))
      .catch((err: unknown) => sendResponse({ ok: false, error: errorMessage(err) }));
    return true;
  }

  if (message.type === 'FETCH_JSON' && isValidUrl(message.url)) {
    fetchJsonThroughBackground(message.url)
      .then((data) => sendResponse({ ok: true, data }))
      .catch((err: unknown) => sendResponse({ ok: false, error: errorMessage(err) }));
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

export function handleContextMenuClick(info: chrome.contextMenus.OnClickData): void {
  const url = info.linkUrl || info.pageUrl;
  if (isValidUrl(url)) {
    submitUrl(url, 'archive').catch((err: unknown) => {
      // eslint-disable-next-line no-console
      console.error('AIPulse: context-menu submit failed', err);
    });
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

if (typeof chrome !== 'undefined') {
  chrome.runtime.onMessage.addListener(handleMessage);
  chrome.runtime.onInstalled.addListener(setupContextMenus);
  chrome.contextMenus.onClicked.addListener(handleContextMenuClick);
}
