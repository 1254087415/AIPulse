import { fetchSubtitleEntries, formatSubtitleEntries } from './platform/bilibili-subtitles';
import { extractActiveFeedVideoId } from './platform/douyin';
import {
  extractDouyinVideoId,
  getCapturedShareUrl,
  installShareCapture,
  requestShareUrlCapture,
  findActiveSlideShareHoverPoint,
} from './platform/douyin-share';
import { DOUYIN_DEBUGGER_CONSENT_KEY } from './popup-debugger';
import { extractAllLinks } from './platform/registry';
import type { SubmitMode, SubtitleEntry } from './types';
import { cleanTrackingParams, dedupeLinks } from './utils';

// ---------------------------------------------------------------------------
// Safe wrapper for chrome.runtime.sendMessage.
// Handles:
// - Synchronous throw when extension context is invalidated
// - chrome.runtime.lastError in callback
// - Never forms an unhandled rejection
// ---------------------------------------------------------------------------
function safeSendMessage(message: unknown): Promise<{ ok?: boolean; captured?: boolean; fallback?: boolean; error?: string } | undefined> {
  return new Promise((resolve) => {
    try {
      chrome.runtime.sendMessage(message, (response) => {
        // Suppress lastError — it indicates the extension context was
        // invalidated, which is expected during navigation/restart.
        void chrome.runtime.lastError;
        resolve(response as { ok?: boolean; captured?: boolean; fallback?: boolean; error?: string } | undefined);
      });
    } catch {
      // Synchronous throw: extension context invalidated.
      resolve(undefined);
    }
  });
}

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

// ---------------------------------------------------------------------------
// Helper: wait for the main-world interceptor to capture a short link URL.
// Polls capturedShareUrls (populated by the douyin-share main-world interceptor)
// until the URL for the given videoId appears, or the timeout expires.
// ---------------------------------------------------------------------------

/**
 * Reads the user's consent for chrome.debugger-based hover from
 * chrome.storage.local. Returns true only when the user has explicitly
 * accepted the debugger attach banner. Returns false in any other case
 * (no value, invalid value, chrome unavailable, storage error) so that
 * the safe long-link fallback always wins.
 */
async function readDouyinDebuggerConsent(): Promise<boolean> {
  if (typeof chrome === 'undefined' || !chrome.storage?.local) return false;
  return new Promise((resolve) => {
    try {
      chrome.storage.local.get(DOUYIN_DEBUGGER_CONSENT_KEY, (result) => {
        void chrome.runtime.lastError;
        resolve(result?.[DOUYIN_DEBUGGER_CONSENT_KEY] === true);
      });
    } catch {
      resolve(false);
    }
  });
}

function waitForCapturedShareUrl(videoId: string, timeoutMs: number): Promise<string | undefined> {
  const pollInterval = 100;
  return new Promise((resolve) => {
    const deadline = Date.now() + timeoutMs;
    const check = (): void => {
      const url = getCapturedShareUrl(videoId);
      if (url) {
        resolve(url);
        return;
      }
      if (Date.now() >= deadline) {
        resolve(undefined);
        return;
      }
      setTimeout(check, pollInterval);
    };
    check();
  });
}

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
        const videoId = String(message.videoId);

        // Step 1: Check if we already have a captured short link for this video.
        const cached = getCapturedShareUrl(videoId);
        if (cached) {
          sendResponse({ ok: true, shareUrl: cached });
          return;
        }

        // Step 2: Find the share button hover point on the current page.
        const point = findActiveSlideShareHoverPoint(document);

        // Step 2.5: Honor user consent. chrome.debugger.attach triggers a
        // browser-level "Debugger is attached" banner — until the user has
        // explicitly accepted the explanation prompt, skip the debugger path
        // entirely and rely on the long-link fallback.
        const consentGranted = await readDouyinDebuggerConsent();

        if (point && consentGranted) {
          // Step 3a: Ask the background service worker to dispatch a trusted hover
          // via chrome.debugger (MV3 service worker cannot use debugger directly).
          try {
            const debuggerResponse = await safeSendMessage({
              type: 'DOUYIN_DEBUGGER_HOVER',
              point,
            });

            if (debuggerResponse?.ok && !debuggerResponse?.fallback) {
              // Step 4a: Debugger succeeded — wait up to 5000 ms for the main-world
              // interceptor to populate capturedShareUrls.
              const captured = await waitForCapturedShareUrl(videoId, 5000);
              if (captured) {
                sendResponse({ ok: true, shareUrl: captured });
                return;
              }
              // Timeout: fall through to Step 3b
            }
            // debuggerResponse.fallback === true or ok === false: fall through to Step 3b
          } catch {
            // Runtime error (extension context invalidated, etc.): fall through to Step 3b
          }
        }

        // Step 3b: Fallback — use the existing copy-link synthesis flow.
        const shareUrl = await requestShareUrlCapture(document, videoId);
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
