import { extractAllLinks } from './platform/registry';
import type { SubmitMode } from './types';
import { cleanTrackingParams, dedupeLinks } from './utils';

function scanAndReport() {
  try {
    const links = extractAllLinks(document, window.location.href);
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

// Test bridge: pages can dispatch AIPULSE_SUBMIT_URL to trigger a submission.
// This block is compiled out of production builds (vite define __E2E__ = false).
if (__E2E__) {
  window.addEventListener('AIPULSE_SUBMIT_URL', (event) => {
    const detail = (event as CustomEvent).detail as { url: string; mode?: SubmitMode } | undefined;
    if (!detail?.url) return;
    chrome.runtime.sendMessage(
      {
        type: 'SUBMIT_URL',
        url: cleanTrackingParams(detail.url),
        mode: detail.mode || 'archive',
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
    debounceTimer = window.setTimeout(scanAndReport, 500);
  }
});
observer.observe(document.body, { childList: true, subtree: true });
