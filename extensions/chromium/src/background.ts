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

chrome.runtime.onMessage.addListener((message: BackgroundMessage, _sender, sendResponse) => {
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
      .catch((err) => sendResponse({ ok: false, error: err.message }));
    return true;
  }

  return false;
});

chrome.runtime.onInstalled.addListener(() => {
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

chrome.contextMenus.onClicked.addListener((info) => {
  const url = info.linkUrl || info.pageUrl;
  if (url) {
    submitUrl(url, 'archive').catch(console.error);
  }
});

async function submitUrl(url: string, mode: SubmitMode): Promise<SubmitResult> {
  const cleaned = cleanTrackingParams(url);
  const payload: SubmitPayload = {
    url: cleaned,
    source: 'browser_extension',
    mode,
  };

  try {
    return await submitViaNativeMessaging(payload);
  } catch (nativeErr) {
    console.warn('Native messaging failed, falling back to HTTP', nativeErr);
    return submitViaHttp(payload);
  }
}

export { submitUrl, foundLinksCache };
