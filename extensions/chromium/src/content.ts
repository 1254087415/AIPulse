import { extractAllLinks } from './platform/registry';
import { dedupeLinks } from './utils';

function scanAndReport() {
  const links = extractAllLinks(document, window.location.href);
  const deduped = dedupeLinks(links);
  chrome.runtime.sendMessage({ type: 'FOUND_LINKS', links: deduped }, () => {
    if (chrome.runtime.lastError) {
      // Silent in production; extension not installed or context invalidated.
      return;
    }
  });
}

scanAndReport();

let lastUrl = window.location.href;
const observer = new MutationObserver(() => {
  if (window.location.href !== lastUrl) {
    lastUrl = window.location.href;
    scanAndReport();
  }
});
observer.observe(document.body, { childList: true, subtree: true });
