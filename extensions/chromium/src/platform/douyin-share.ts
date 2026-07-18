const CAPTURE_EVENT_NAME = 'AIPULSE_DOUYIN_SHARE_CAPTURED';
const capturedShareUrls = new Map<string, string>();
let captureInstalled = false;

export function extractDouyinVideoId(url: string): string | undefined {
  const match = url.match(/douyin\.com\/(?:video|note)\/(\d+)/);
  return match ? match[1] : undefined;
}

export function clearCapturedShareUrls(): void {
  capturedShareUrls.clear();
}

export function setCapturedShareUrl(videoId: string, shareUrl: string): void {
  capturedShareUrls.set(videoId, shareUrl);
}

export function getCapturedShareUrl(videoId: string): string | undefined {
  return capturedShareUrls.get(videoId);
}

export function installShareCapture(_document: Document): void {
  if (captureInstalled) return;
  captureInstalled = true;

  // The actual fetch/XHR interceptor runs in a MAIN-world content script
  // (src/platform/douyin-share-main.ts) to avoid CSP blocking inline scripts.
  // Here we just listen for the postMessage it sends (CustomEvents do not cross
  // the isolated/main world boundary).
  window.addEventListener('message', (event) => {
    if (event.data?.type !== CAPTURE_EVENT_NAME) return;
    const detail = event.data as { videoId?: string; shareUrl?: string } | undefined;
    if (detail?.videoId && detail.shareUrl) {
      capturedShareUrls.set(detail.videoId, detail.shareUrl);
    }
  });
}

function findActiveSlideShareButton(document: Document): Element | null {
  // The active slide may be the element that contains [data-e2e="feed-active-video"]
  // or any slide container with data-e2e-vid.
  const activeMarker = document.querySelector('[data-e2e="feed-active-video"]');
  const slide = activeMarker
    ? activeMarker.closest('[data-e2e-vid]') || activeMarker.parentElement
    : document.querySelector('[data-e2e-vid]');

  // Try several heuristics for the share button. Douyin uses SVG icons, so we
  // look for common text/aria labels and class name patterns.
  const selectors = [
    '[data-e2e="share-button"]',
    'button[aria-label*="分享"]',
    'div[aria-label*="分享"]',
    'svg[class*="share"]',
    'div[class*="share"]',
    'button[class*="share"]',
    // Real page share buttons often use data-e2e="share" or an SVG with title.
    '[data-e2e="share"]',
    'button[data-e2e="share-button" i]',
    'div[data-e2e="share-button" i]',
  ];

  // Search inside the active slide first, then fall back to the whole document
  // (e.g. detail/lightbox view where the action bar is outside the slide).
  const searchRoots: (Element | Document)[] = slide ? [slide] : [];
  searchRoots.push(document);

  for (const root of searchRoots) {
    for (const selector of selectors) {
      const btn = root.querySelector(selector);
      if (btn) return btn;
    }
  }

  // Fallback: the right-side action bar usually has 3-5 icons; the share icon
  // is often the last or second-to-last. Pick the last clickable element.
  const actions = (slide || document).querySelectorAll(
    'button, div[role="button"], a'
  );
  if (actions.length > 0) return actions[actions.length - 1];
  return null;
}

export async function requestShareUrlCapture(
  document: Document,
  videoId: string
): Promise<string | undefined> {
  const existing = capturedShareUrls.get(videoId);
  if (existing) return existing;

  const btn = findActiveSlideShareButton(document);
  if (!btn) return undefined;

  btn.dispatchEvent(new MouseEvent('mouseenter', { bubbles: true, cancelable: true }));
  btn.dispatchEvent(new MouseEvent('mouseover', { bubbles: true, cancelable: true }));

  // Wait for Douyin's own JS to fire the web_shorten request and for our
  // interceptor to capture the response.
  const wait = (ms: number) => new Promise<void>((resolve) => window.setTimeout(resolve, ms));
  for (let i = 0; i < 15; i++) {
    await wait(100);
    const captured = capturedShareUrls.get(videoId);
    if (captured) return captured;
  }
  return undefined;
}
