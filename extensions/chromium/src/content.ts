import { extractAllLinks } from './platform/registry';
import { dedupeLinks } from './utils';

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
  } catch {
    // Silently ignore extraction failures in production.
  }
}

scanAndReport();

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
