import { fetchSubtitleEntries, formatSubtitleEntries } from './platform/bilibili-subtitles';
import { extractActiveFeedVideoId } from './platform/douyin';
import {
  extractDouyinVideoId,
  installShareCapture,
  requestShareUrlCapture,
} from './platform/douyin-share';
import { extractAllLinks } from './platform/registry';
import type { SubmitMode, SubtitleEntry } from './types';
import { cleanTrackingParams, dedupeLinks } from './utils';

async function scanAndReport() {
  try {
    const links = await extractAllLinks(document, window.location.href);
    const deduped = dedupeLinks(links);
    chrome.runtime.sendMessage({ type: 'FOUND_LINKS', links: deduped }, () => {
      if (chrome.runtime.lastError) {
        // Silent in production; extension not installed or context invalidated.
        return;
      }
    });
  } catch (error) {
    // eslint-disable-next-line no-console
    console.error('AIPulse: link extraction failed', error);
  }
}

scanAndReport();

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message.type === 'FETCH_SUBTITLE' && message.subtitleUrl) {
    void (async () => {
      try {
        const entries = await fetchSubtitleEntries(String(message.subtitleUrl));
        sendResponse({
          ok: true,
          entries,
          formatted: formatSubtitleEntries(entries),
        });
      } catch (error: unknown) {
        sendResponse({
          ok: false,
          error: error instanceof Error ? error.message : String(error),
        });
      }
    })();
    return true;
  }

  if (message.type === 'FETCH_DOUYIN_SHARE_URL' && message.videoId) {
    void (async () => {
      try {
        const shareUrl = await requestShareUrlCapture(document, String(message.videoId));
        sendResponse({ ok: !!shareUrl, shareUrl });
      } catch (error: unknown) {
        sendResponse({
          ok: false,
          shareUrl: undefined,
          error: error instanceof Error ? error.message : String(error),
        });
      }
    })();
    return true;
  }

  if (message.type === 'RESCAN') {
    void (async () => {
      try {
        const links = await extractAllLinks(document, window.location.href);
        const deduped = dedupeLinks(links);
        chrome.runtime.sendMessage({ type: 'FOUND_LINKS', links: deduped }, () => {
          void chrome.runtime.lastError;
        });
        sendResponse({ ok: true, links: deduped });
      } catch (error: unknown) {
        sendResponse({
          ok: false,
          links: [],
          error: error instanceof Error ? error.message : String(error),
        });
      }
    })();
    return true;
  }

  return false;
});

// Test bridge: pages can dispatch AIPULSE_SUBMIT_URL to trigger a submission.
// This block is compiled out of production builds (vite define __E2E__ = false).
if (__E2E__) {
  window.addEventListener('AIPULSE_SUBMIT_URL', (event) => {
    const detail = (event as CustomEvent).detail as
      | { url: string; mode?: SubmitMode; subtitle_text?: string; subtitle_language?: string }
      | undefined;
    if (!detail?.url) return;
    chrome.runtime.sendMessage(
      {
        type: 'SUBMIT_URL',
        url: cleanTrackingParams(detail.url),
        mode: detail.mode || 'archive',
        subtitle_text: detail.subtitle_text,
        subtitle_language: detail.subtitle_language,
      },
      () => {
        // Ignore response; the E2E test verifies the HTTP request on the server.
      }
    );
  });
}

// Douyin's share short-link endpoint is protected by anti-bot signatures.
// We install a main-world interceptor so that when the user (or we) hovers the
// share button, the generated short link is captured and surfaced in the popup.
if (window.location.href.includes('douyin.com')) {
  installShareCapture(document);
}

let lastUrl = window.location.href;
let lastActiveDouyinId = extractActiveFeedVideoId(document);
let debounceTimer: number | null = null;

function currentDouyinActiveId(): string | undefined {
  if (!window.location.href.includes('douyin.com')) return undefined;
  return extractActiveFeedVideoId(document);
}

function scheduleScan() {
  if (debounceTimer) {
    window.clearTimeout(debounceTimer);
  }
  debounceTimer = window.setTimeout(() => {
    scanAndReport().catch((error: unknown) => {
      // eslint-disable-next-line no-console
      console.error('AIPulse: scan failed', error);
    });
  }, 500);
}

const observer = new MutationObserver(() => {
  const urlChanged = window.location.href !== lastUrl;
  const activeDouyinId = currentDouyinActiveId();
  const activeChanged = activeDouyinId !== undefined && activeDouyinId !== lastActiveDouyinId;
  if (!urlChanged && !activeChanged) return;

  lastUrl = window.location.href;
  if (activeChanged) {
    lastActiveDouyinId = activeDouyinId;
  }
  scheduleScan();
});
observer.observe(document.body, { childList: true, subtree: true });
