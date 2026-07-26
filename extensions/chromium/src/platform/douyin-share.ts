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

function getActiveSlide(document: Document): Element | null {
  const activeMarker = document.querySelector('[data-e2e="feed-active-video"]');
  if (activeMarker) {
    return activeMarker.closest('[data-e2e-vid]') || activeMarker.parentElement;
  }
  return document.querySelector('[data-e2e-vid]');
}

function isShareIconCandidate(element: Element): boolean {
  // Douyin Jingxuan uses icon-only action bars. The share icon is typically
  // the last SVG in the bottom action row of the active slide.
  const tag = element.tagName.toLowerCase();
  if (tag !== 'svg' && tag !== 'div' && tag !== 'button') return false;

  // Prefer SVGs or their immediate wrapper divs.
  if (tag === 'svg') return true;
  return element.querySelector('svg') !== null;
}

export function findActiveSlideShareButton(document: Document): Element | null {
  const slide = getActiveSlide(document);

  // Try several heuristics for the share button. Douyin uses SVG icons, so we
  // look for common text/aria labels and class name patterns.
  const selectors = [
    '[data-e2e="video-player-share"]',
    '[data-e2e="share-button"]',
    '[data-e2e="share"]',
    'button[aria-label*="分享"]',
    'div[aria-label*="分享"]',
    'svg[class*="share"]',
    'div[class*="share"]',
    'button[class*="share"]',
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

  // Jingxuan recommend feed (douyin.com/?recommend=1): the active slide has a
  // bottom action bar with 4 icon-only buttons (like, comment, star, share).
  // They have no aria-label/data-e2e, so we identify the share icon by position.
  if (slide) {
    const slideRect = slide.getBoundingClientRect();

    // Collect candidate action icons in the lower half of the active slide.
    const candidates = Array.from(slide.querySelectorAll('svg, div, button')).filter((el) => {
      if (!isShareIconCandidate(el)) return false;
      const rect = el.getBoundingClientRect();
      const cy = rect.top + rect.height / 2;
      return cy > slideRect.top + slideRect.height * 0.65;
    });

    if (candidates.length >= 3) {
      // The share icon is the rightmost main action icon.
      const rightmost = candidates.reduce((prev, cur) => {
        const prevRect = prev.getBoundingClientRect();
        const curRect = cur.getBoundingClientRect();
        return curRect.left > prevRect.left ? cur : prev;
      });
      return rightmost.parentElement?.tagName.toLowerCase() === 'div' ? rightmost.parentElement : rightmost;
    }

    // Fallback: pick the last SVG in the lower half of the slide.
    const svgs = Array.from(slide.querySelectorAll('svg')).filter((svg) => {
      const rect = svg.getBoundingClientRect();
      const cy = rect.top + rect.height / 2;
      return cy > slideRect.top + slideRect.height * 0.65;
    });
    if (svgs.length > 0) {
      const last = svgs[svgs.length - 1];
      return last.parentElement || last;
    }
  }

  // Last resort: the right-side action bar usually has 3-5 icons; the share icon
  // is often the last or second-to-last. Pick the last clickable element.
  const actions = (slide || document).querySelectorAll('button, div[role="button"], a');
  if (actions.length > 0) return actions[actions.length - 1];
  return null;
}

import type { HoverPoint } from './douyin-debugger';

export type { HoverPoint } from './douyin-debugger';

function getHoverTarget(element: Element): Element {
  // Native hover listeners are often attached to the icon wrapper rather than
  // the outer data-e2e container. Prefer the SVG or its immediate parent.
  const svg = element.querySelector('svg');
  if (svg) return svg.parentElement || svg;
  return element;
}

export function findActiveSlideShareHoverPoint(document: Document): HoverPoint | undefined {
  const btn = findActiveSlideShareButton(document);
  if (!btn) return undefined;

  btn.scrollIntoView({ block: 'nearest', inline: 'nearest' });

  const hoverTarget = getHoverTarget(btn);
  const rect = hoverTarget.getBoundingClientRect();
  const x = rect.left + rect.width / 2;
  const y = rect.top + rect.height / 2;

  // Validate center is finite and non-negative.
  if (!Number.isFinite(x) || !Number.isFinite(y)) return undefined;
  if (x < 0 || y < 0) return undefined;

  // Validate element has positive dimensions.
  if (rect.width <= 0 || rect.height <= 0) return undefined;

  // Validate center is within viewport.
  if (x >= window.innerWidth || y >= window.innerHeight) return undefined;

  return { x, y };
}

function dispatchHoverEvents(target: Element): void {
  const hoverTarget = getHoverTarget(target);
  const rect = hoverTarget.getBoundingClientRect();
  const x = rect.left + rect.width / 2;
  const y = rect.top + rect.height / 2;

  // Simulate a mouse moving into the icon. React/TikTok event systems rely on
  // relatedTarget to decide whether this is a genuine enter, so we provide a
  // target outside the element's subtree.
  const relatedTarget = document.body;
  const base = { bubbles: true, cancelable: true };

  const moveOpts = { ...base, clientX: x, clientY: y, relatedTarget };
  hoverTarget.dispatchEvent(new MouseEvent('mousemove', moveOpts));

  const enterOpts = { ...base, relatedTarget };
  try {
    hoverTarget.dispatchEvent(new PointerEvent('pointerover', enterOpts));
    hoverTarget.dispatchEvent(new PointerEvent('pointerenter', enterOpts));
  } catch {
    // Ignore environments without PointerEvent.
  }
  hoverTarget.dispatchEvent(new MouseEvent('mouseover', enterOpts));
  hoverTarget.dispatchEvent(new MouseEvent('mouseenter', enterOpts));
}

function findCopyLinkButton(document: Document): HTMLButtonElement | null {
  return (
    (document.querySelector('[data-e2e="copy-link"]') as HTMLButtonElement | null) ||
    Array.from(document.querySelectorAll('button')).find((b) =>
      b.textContent?.trim().includes('复制链接')
    ) ||
    null
  );
}

async function waitForCondition(
  condition: () => boolean,
  timeoutMs: number,
  intervalMs = 100
): Promise<boolean> {
  const wait = (ms: number) => new Promise<void>((resolve) => window.setTimeout(resolve, ms));
  const iterations = Math.ceil(timeoutMs / intervalMs);
  for (let i = 0; i < iterations; i++) {
    if (condition()) return true;
    await wait(intervalMs);
  }
  return false;
}

// Retry configuration for share URL capture.
const BASE_RETRY_DELAY_MS = 200;
const MAX_RETRY_ATTEMPTS = 3;

export async function requestShareUrlCapture(
  document: Document,
  videoId: string
): Promise<string | undefined> {
  const existing = capturedShareUrls.get(videoId);
  if (existing) return existing;

  const btn = findActiveSlideShareButton(document);
  if (!btn) return undefined;

  // Ensure the button is in the viewport so events are not suppressed.
  btn.scrollIntoView({ block: 'nearest', inline: 'nearest' });

  const wait = (ms: number) => new Promise<void>((resolve) => window.setTimeout(resolve, ms));

  // Retry loop with exponential backoff.
  // Each attempt: attach → dispatch hover → poll → check → detach
  for (let attempt = 0; attempt < MAX_RETRY_ATTEMPTS; attempt++) {
    // attach: prepare for capture attempt
    const attemptStart = Date.now();

    try {
      // Douyin detail pages call web_shorten when the share button is hovered.
      dispatchHoverEvents(btn);

      // Poll for capture with fixed interval (not exponential - that's the per-attempt poll)
      const captured = await pollForCapture(videoId, 30, 100);
      if (captured) return captured;

      // Fallback: click the share button.
      dispatchHoverEvents(btn);
      btn.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));

      const capturedAfterClick = await pollForCapture(videoId, 20, 100);
      if (capturedAfterClick) return capturedAfterClick;

      // If nothing was captured, the click probably opened a share dialog.
      const dialogAppeared = await waitForCondition(
        () => findCopyLinkButton(document) !== null,
        3000
      );
      if (dialogAppeared) {
        const copyBtn = findCopyLinkButton(document)!;
        copyBtn.scrollIntoView({ block: 'nearest', inline: 'nearest' });
        window.setTimeout(() => {
          copyBtn.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
        }, 0);

        const capturedFromDialog = await pollForCapture(videoId, 50, 100);
        if (capturedFromDialog) return capturedFromDialog;
      }
    } finally {
      // detach: cleanup after each attempt (always runs, even on failure)
      // Currently no-op but the structure allows for proper cleanup.
    }

    // If this wasn't the last attempt, wait with exponential backoff before retry.
    if (attempt < MAX_RETRY_ATTEMPTS - 1) {
      const backoffDelay = BASE_RETRY_DELAY_MS * Math.pow(2, attempt);
      await wait(backoffDelay);
    }
  }

  return undefined;
}

async function pollForCapture(
  videoId: string,
  maxIterations: number,
  intervalMs: number
): Promise<string | undefined> {
  const wait = (ms: number) => new Promise<void>((resolve) => window.setTimeout(resolve, ms));
  for (let i = 0; i < maxIterations; i++) {
    await wait(intervalMs);
    const captured = capturedShareUrls.get(videoId);
    if (captured) return captured;
  }
  return undefined;
}
