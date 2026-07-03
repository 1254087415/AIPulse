import { submitViaHttp } from './http';
import { submitViaNativeMessaging } from './native';
import type { FoundLink, SubmitMode, SubmitPayload, SubmitResult } from './types';
import { cleanTrackingParams, dedupeLinks } from './utils';

interface BackgroundMessage {
  type: 'FOUND_LINKS' | 'SUBMIT_URL' | 'GET_FOUND_LINKS';
  links?: FoundLink[];
  url?: string;
  mode?: SubmitMode;
}

let foundLinksCache: FoundLink[] = [];

function errorMessage(err: unknown): string {
  if (err instanceof Error) return err.message;
  return String(err);
}

export function handleMessage(
  message: BackgroundMessage,
  _sender: chrome.runtime.MessageSender,
  sendResponse: (response: unknown) => void
): boolean {
  if (message.type === 'FOUND_LINKS' && message.links) {
    foundLinksCache = dedupeLinks(message.links);
    sendResponse({ ok: true, count: foundLinksCache.length });
    return false;
  }

  if (message.type === 'GET_FOUND_LINKS') {
    sendResponse({ links: foundLinksCache });
    return false;
  }

  if (message.type === 'SUBMIT_URL' && message.url) {
    submitUrl(message.url, message.mode || 'archive')
      .then((result) => sendResponse({ ok: true, result }))
      .catch((err: unknown) => sendResponse({ ok: false, error: errorMessage(err) }));
    return true;
  }

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
  if (url) {
    submitUrl(url, 'archive').catch(() => {
      // Silently ignore context-menu submission errors in MVP.
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
