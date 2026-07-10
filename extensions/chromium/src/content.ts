import { fetchSubtitleEntries, formatSubtitleEntries } from './platform/bilibili-subtitles';
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
    fetchSubtitleEntries(String(message.subtitleUrl))
      .then((entries) =>
        sendResponse({
          ok: true,
          entries,
          formatted: formatSubtitleEntries(entries),
        })
      )
      .catch((error: unknown) =>
        sendResponse({
          ok: false,
          error: error instanceof Error ? error.message : String(error),
        })
      );
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

let lastUrl = window.location.href;
let debounceTimer: number | null = null;
const observer = new MutationObserver(() => {
  if (window.location.href !== lastUrl) {
    lastUrl = window.location.href;
    if (debounceTimer) {
      window.clearTimeout(debounceTimer);
    }
    debounceTimer = window.setTimeout(() => {
      scanAndReport().catch((error: unknown) => {
        // eslint-disable-next-line no-console
        console.error('AIPulse: scan on navigation failed', error);
      });
    }, 500);
  }
});
observer.observe(document.body, { childList: true, subtree: true });
