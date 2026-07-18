import { chromium, expect, test } from '@playwright/test';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import type { FoundLink } from '../../src/types';
import { startRealBackend, type RealBackend } from './helpers/real-backend';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const EXTENSION_PATH = path.resolve(__dirname, '../../dist');
const BACKEND_PORT = 3457;
const COOKIE_FILE = path.resolve(__dirname, '../.tmp/douyin-cookies.json');
const USER_DATA_DIR = path.resolve(__dirname, '../.tmp/user-data-douyin-share');

const DOUYIN_HOME_URL = 'https://www.douyin.com/';

test.describe('AIPulse Douyin share short-link capture on real pages', () => {
  let backend: RealBackend;

  test.beforeAll(async () => {
    backend = await startRealBackend(BACKEND_PORT);
  });

  test.afterAll(async () => {
    await backend.close();
  });

  test('attempts real v.douyin.com short-link extraction on a logged-in Douyin session', async () => {
    // This test drives the real Douyin page without mocking web_shorten. It
    // requires a logged-in Douyin session (saved by tests/e2e/helpers/login-douyin.mjs).
    // Douyin's web_shorten endpoint returns {"reason":"not allowed to shorten"}
    // for many sessions, so a real v.douyin.com URL is captured only when Douyin
    // allows it.
    test.setTimeout(120_000);

    if (!fs.existsSync(COOKIE_FILE)) {
      test.skip();
    }

    const context = await chromium.launchPersistentContext(USER_DATA_DIR, {
      headless: false,
      args: [
        `--disable-extensions-except=${EXTENSION_PATH}`,
        `--load-extension=${EXTENSION_PATH}`,
        '--disable-blink-features=AutomationControlled',
        '--window-size=1280,720',
      ],
      userAgent:
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
      viewport: { width: 1280, height: 720 },
    });

    const warmupPage = await context.newPage();
    await warmupPage.goto('about:blank');
    await expect.poll(() => context.serviceWorkers().length).toBeGreaterThan(0);
    const serviceWorkers = context.serviceWorkers();
    expect(serviceWorkers.length).toBeGreaterThan(0);
    const serviceWorker = serviceWorkers[0];

    await serviceWorker.evaluate(
      (port) =>
        new Promise<void>((resolve) => {
          chrome.storage.local.set({ httpBaseUrl: `http://localhost:${port}` }, () => resolve());
        }),
      BACKEND_PORT
    );
    await warmupPage.close();

    const page = await context.newPage();
    let lastWebShortenResponse: string | null = null;
    page.on('response', (res) => {
      const url = res.url();
      if (url.includes('web_shorten')) {
        void res.text().then((text) => {
          lastWebShortenResponse = text;
          console.log('WEB_SHORTEN RESPONSE:', text.slice(0, 300));
        });
      }
    });

    await page.route('**/*bytegoofy.com/**', (route) => route.abort());

    // Get a real video id from the logged-in feed.
    await page.goto(DOUYIN_HOME_URL, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await expect(page.locator('[href*="/video/"]').first()).toBeVisible({ timeout: 15000 });
    const cardHref = await page.locator('[href*="/video/"]').first().getAttribute('href');
    const detailUrl = cardHref?.startsWith('http') ? cardHref : `https:${cardHref}`;
    expect(detailUrl).toMatch(/\/video\/\d+/);

    // Open the real video detail page (not the feed modal).
    await page.goto(detailUrl, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForTimeout(3000);
    console.log('Detail page URL:', page.url());
    console.log('Detail page title:', await page.title());
    expect(page.url()).toMatch(/\/video\/\d+/);

    // Wait for the extension to report the Douyin link.
    let foundLinks: FoundLink[] = [];
    await expect
      .poll(
        async () => {
          const links = await serviceWorker.evaluate(
            () =>
              new Promise<FoundLink[]>((resolve) => {
                chrome.storage.local.get('foundLinks', (result) => resolve((result?.foundLinks as FoundLink[]) || []));
              })
          );
          foundLinks = links;
          return links.filter((link) => link.platform === 'douyin').length;
        },
        { timeout: 25000 }
      )
      .toBeGreaterThan(0);

    const targetLink = foundLinks.find((link) => link.platform === 'douyin');
    expect(targetLink).toBeDefined();
    const videoId = targetLink!.url.match(/\/video\/(\d+)/)?.[1];
    expect(videoId).toBeDefined();

    // Try to trigger the share button so Douyin's own JS calls web_shorten.
    const shareBtn = page.locator('text=分享, [data-e2e="share-button"], [data-e2e="share"]').first();
    if (await shareBtn.isVisible().catch(() => false)) {
      await shareBtn.click({ timeout: 5000 }).catch(() => {});
    }

    const tabs = await serviceWorker.evaluate(() =>
      new Promise<{ id?: number }[]>((resolve) => {
        chrome.tabs.query({ url: 'https://www.douyin.com/*' }, (found) => resolve(found));
      })
    );
    const tabId = tabs[0]?.id;
    expect(tabId).toBeDefined();

    await serviceWorker.evaluate(
      (args) =>
        new Promise<void>((resolve) => {
          chrome.tabs.sendMessage(
            args.tabId,
            { type: 'FETCH_DOUYIN_SHARE_URL', videoId: args.videoId },
            () => resolve()
          );
        }),
      { tabId: tabId!, videoId }
    );

    // Directly call web_shorten as a fallback probe; the interceptor will log it.
    await page.evaluate(async (id) => {
      const target = encodeURIComponent(`share/video/${id}`);
      try {
        await fetch(`https://www.douyin.com/aweme/v1/web/web_shorten/?target=${target}&type=1`, {
          credentials: 'include',
        });
      } catch {}
    }, videoId);

    await serviceWorker.evaluate(
      (args) =>
        new Promise<void>((resolve) => {
          chrome.tabs.sendMessage(args.tabId, { type: 'RESCAN' }, () => resolve());
        }),
      { tabId: tabId! }
    );

    const linksWithShare = await serviceWorker.evaluate(
      () =>
        new Promise<FoundLink[]>((resolve) => {
          chrome.storage.local.get('foundLinks', (result) => {
            const links = (result?.foundLinks as FoundLink[]) || [];
            resolve(
              links.filter(
                (link) =>
                  link.platform === 'douyin' &&
                  link.metadata?.shareUrl?.startsWith('https://v.douyin.com/')
              )
            );
          });
        })
    );

    if (linksWithShare.length === 0) {
      const reason = lastWebShortenResponse || 'no web_shorten response observed';
      throw new Error(
        `Douyin did not return a real v.douyin.com short link for video ${videoId}. ` +
          `Real API response: ${reason}. ` +
          `This is a Douyin server-side restriction, not a code bug.`
      );
    }

    const shareUrl = linksWithShare[0].metadata?.shareUrl;
    console.log('Captured real Douyin share short link:', shareUrl);
    expect(shareUrl).toMatch(/^https:\/\/v\.douyin\.com\//);

    await page.evaluate(
      (url) => {
        window.dispatchEvent(new CustomEvent('AIPULSE_SUBMIT_URL', { detail: { url, mode: 'archive' } }));
      },
      linksWithShare[0].url
    );

    await expect
      .poll(() => backend.getSubmittedTaskId(), { timeout: 20000 })
      .toMatch(/^[a-f0-9]{12}$/);

    const submitBody = backend.getLastSubmitBody();
    expect(submitBody).not.toBeNull();
    expect(submitBody!.url).toBe(linksWithShare[0].url);
    expect(submitBody!.source).toBe('browser_extension');
    expect(submitBody!.mode).toBe('archive');

    await page.close();
    await context.close();
  });
});
