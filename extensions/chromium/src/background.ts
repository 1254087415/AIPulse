import { submitViaHttp } from './http';
import { submitViaNativeMessaging } from './native';
import type { FoundLink, SubmitMode, SubmitPayload, SubmitResult } from './types';
import { cleanTrackingParams, dedupeLinks } from './utils';

const ALLOWED_MODES: SubmitMode[] = ['archive', 'knowledge_check'];

interface BackgroundMessage {
  type: 'FOUND_LINKS' | 'SUBMIT_URL' | 'GET_FOUND_LINKS';
  links?: FoundLink[];
  url?: unknown;
  mode?: unknown;
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

let foundLinksCache: FoundLink[] = [];

export function handleMessage(
  message: BackgroundMessage,
  _sender: chrome.runtime.MessageSender,
  sendResponse: (response: unknown) => void
): boolean {
  if (message.type === 'FOUND_LINKS' && message.links) {
    foundLinksCache = dedupeLinks(message.links);
    if (typeof chrome !== 'undefined' && chrome.action) {
      const count = foundLinksCache.length;
      chrome.action.setBadgeText({ text: count > 0 ? String(count) : '' });
      chrome.action.setBadgeBackgroundColor({ color: '#1677ff' });
    }
    sendResponse({ ok: true, count: foundLinksCache.length });
    return false;
  }

  if (message.type === 'GET_FOUND_LINKS') {
    sendResponse({ links: foundLinksCache });
    return false;
  }

  if (message.type === 'SUBMIT_URL' && isValidUrl(message.url) && isValidMode(message.mode)) {
    submitUrl(message.url, message.mode)
      .then((result) => sendResponse({ ok: true, result }))
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

async function submitUrl(url: string, mode: SubmitMode): Promise<SubmitResult> {
  const cleaned = cleanTrackingParams(url);
  const payload: SubmitPayload = {
    url: cleaned,
    source: 'browser_extension',
    mode,
  };

  try {
    return await submitViaNativeMessaging(payload);
  } catch {
    return submitViaHttp(payload);
  }
}

export { submitUrl, foundLinksCache };

if (typeof chrome !== 'undefined') {
  chrome.runtime.onMessage.addListener(handleMessage);
  chrome.runtime.onInstalled.addListener(setupContextMenus);
  chrome.contextMenus.onClicked.addListener(handleContextMenuClick);
}
