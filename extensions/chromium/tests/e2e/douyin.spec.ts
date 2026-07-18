import { chromium, expect, test } from '@playwright/test';
import path from 'path';
import { fileURLToPath } from 'url';
import { startRealBackend, type RealBackend } from './helpers/real-backend';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const EXTENSION_PATH = path.resolve(__dirname, '../../dist');
const BACKEND_PORT = 3457;
const REAL_DOUYIN_HOME_URL = 'https://www.douyin.com/';

test.describe('AIPulse Clipper Douyin recognition on real pages', () => {
  let backend: RealBackend;

  test.beforeAll(async () => {
    // Real Python sidecar + HTTP bridge. No mock backend: submissions are
    // forwarded to aipulse.desktop.sidecar's real submit_url and the returned
    // task_id comes from the real task store.
    backend = await startRealBackend(BACKEND_PORT);
  });

  test.afterAll(async () => {
    await backend.close();
  });

  test('recognizes video links from the real Douyin homepage and submits to the real sidecar', async () => {
    test.setTimeout(90_000);
    const userDataDir = path.join(__dirname, '../.tmp/user-data-douyin');

    const context = await chromium.launchPersistentContext(userDataDir, {
      // This is the documented Playwright recipe for testing MV3 extensions in
      // headless Chromium. headless:false tells Playwright NOT to inject its own
      // (legacy) --headless flag, which cannot host extension service workers;
      // the explicit --headless=new arg then selects the new headless engine,
      // which CAN run MV3 service workers and renders Douyin's SPA feed.
      // Setting headless:true here causes Playwright to inject a competing
      // headless flag and the extension service worker never registers.
      headless: false,
      args: [
        '--headless=new',
        `--disable-extensions-except=${EXTENSION_PATH}`,
        `--load-extension=${EXTENSION_PATH}`,
        '--disable-blink-features=AutomationControlled',
      ],
      userAgent:
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
      viewport: { width: 1280, height: 720 },
    });

    const warmupPage = await context.newPage();
    await warmupPage.goto('about:blank');
    await expect.poll(() => context.serviceWorkers().length).toBeGreaterThan(0);
    await warmupPage.waitForTimeout(1000);
    const serviceWorkers = context.serviceWorkers();
    expect(serviceWorkers.length, 'extension service worker should be registered').toBeGreaterThan(0);
    const serviceWorker = serviceWorkers[0];
    const extId = serviceWorker.url().split('/')[2];
    expect(extId).toBeTruthy();

    await serviceWorker.evaluate(
      (port) =>
        new Promise<void>((resolve) => {
          chrome.storage.local.set({ httpBaseUrl: `http://localhost:${port}` }, () => resolve());
        }),
      BACKEND_PORT
    );

    await warmupPage.close();

    const page = await context.newPage();
    // networkidle never fires on Douyin (continuous telemetry/video requests), so
    // use domcontentloaded and then wait for a concrete feed anchor instead.
    await page.goto(REAL_DOUYIN_HOME_URL, { waitUntil: 'domcontentloaded', timeout: 30000 });

    // The homepage redirects to /jingxuan and the feed is a lazy-loaded SPA.
    // Wait for whichever card anchor the current layout exposes, then scroll to
    // trigger lazy loading so the extractor sees real cards.
    await Promise.race([
      page.waitForSelector('[data-aweme-id]', { timeout: 20000 }),
      page.waitForSelector('[href*="/video/"]', { timeout: 20000 }),
      page.waitForSelector('[data-e2e-vid]', { timeout: 20000 }),
    ]).catch(() => {
      // If neither anchor appears in time we still attempt extraction below and
      // let the foundLinks poll produce a clear failure with diagnostics.
    });
    for (let i = 0; i < 4; i++) {
      await page.mouse.wheel(0, 900).catch(() => {});
      await page.waitForTimeout(400);
    }

    const pageTitle = await page.title();
    const videoCardCount = await page.locator('[href*="/video/"]').count();
    const awemeIdCount = await page.locator('[data-aweme-id]').count();
    console.log(
      `Douyin page title: ${pageTitle}, url: ${page.url()}, ` +
        `video hrefs: ${videoCardCount}, aweme ids: ${awemeIdCount}`
    );

    // Wait for the extension to recognize a Douyin link.
    let foundLinks: { url: string; platform: string }[] = [];
    try {
      await expect
        .poll(
          async () => {
            const links = await serviceWorker.evaluate(() =>
              new Promise<{ url: string; platform: string }[]>((resolve) => {
                chrome.storage.local.get('foundLinks', (result) => {
                  resolve((result?.foundLinks as any) || []);
                });
              })
            );
            foundLinks = links;
            return links.filter((link) => link.platform === 'douyin').length;
          },
          { timeout: 20000 }
        )
        .toBeGreaterThan(0);
    } catch (err) {
      console.log('Found links at timeout:', JSON.stringify(foundLinks));
      throw err;
    }
    const badgeText = await serviceWorker.evaluate(() => chrome.action.getBadgeText({}));
    console.log(`Extension badge: ${badgeText}`);

    const douyinLinks = foundLinks.filter((link) => link.platform === 'douyin');
    expect(douyinLinks.length, 'should recognize at least one Douyin link on the homepage').toBeGreaterThan(0);

    // Submit the first recognized link through the E2E bridge, all the way to
    // the real sidecar.
    const firstLink = douyinLinks[0];
    await page.evaluate(
      (url) => {
        window.dispatchEvent(
          new CustomEvent('AIPULSE_SUBMIT_URL', {
            detail: { url, mode: 'archive' },
          })
        );
      },
      firstLink.url
    );

    // The real sidecar assigns task ids (12 hex chars, see aipulse task store).
    await expect
      .poll(() => backend.getSubmittedTaskId(), { timeout: 20000 })
      .toMatch(/^[a-f0-9]{12}$/);

    const submitBody = backend.getLastSubmitBody();
    expect(submitBody).not.toBeNull();
    expect(submitBody!.url).toBe(firstLink.url);
    expect(submitBody!.source).toBe('browser_extension');
    expect(submitBody!.mode).toBe('archive');

    // The task must exist in the real sidecar's task store (front-back
    // integration), regardless of how the async download pipeline fares
    // against Douyin's login wall.
    const status = await backend.client.request('get_task_status', {
      task_id: backend.getSubmittedTaskId(),
    });
    expect(status.error, `get_task_status failed: ${JSON.stringify(status.error)}`).toBeUndefined();
    expect(status.result?.status, 'task should have a valid status in the real store').toBeTruthy();

    await page.close();
    await context.close();
  });
});
