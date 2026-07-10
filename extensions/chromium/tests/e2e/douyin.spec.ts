import { chromium, expect, test } from '@playwright/test';
import http from 'http';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const EXTENSION_PATH = path.resolve(__dirname, '../../dist');
const MOCK_PORT = 3457;
const REAL_DOUYIN_HOME_URL = 'https://www.douyin.com/';

test.describe('AIPulse Clipper Douyin recognition on real pages', () => {
  let server: http.Server;
  let lastSubmission: {
    url: string;
    source: string;
    mode: string;
  } | null = null;

  test.beforeAll(async () => {
    server = http.createServer((req, res) => {
      const url = new URL(req.url ?? '/', `http://localhost:${MOCK_PORT}`);

      // The extension service worker fetches this mock cross-origin (port 3457 is
      // not in the extension's host_permissions). A POST with Content-Type:
      // application/json triggers a CORS preflight; we must answer it or Chromium
      // blocks the real request and the submission never arrives. A real AIPulse
      // backend would send the same headers.
      if (req.method === 'OPTIONS') {
        res.writeHead(204, {
          'Access-Control-Allow-Origin': '*',
          'Access-Control-Allow-Methods': 'POST, OPTIONS',
          'Access-Control-Allow-Headers': 'Content-Type',
          'Access-Control-Max-Age': '600',
        });
        res.end();
        return;
      }

      if (url.pathname === '/api/videos/extract' && req.method === 'POST') {
        let body = '';
        req.on('data', (chunk) => {
          body += chunk;
        });
        req.on('end', () => {
          try {
            const parsed = JSON.parse(body);
            lastSubmission = {
              url: parsed.url,
              source: parsed.source,
              mode: parsed.mode,
            };
            res.writeHead(200, {
              'Content-Type': 'application/json',
              'Access-Control-Allow-Origin': '*',
            });
            res.end(JSON.stringify({ task_id: 'e2e-douyin-123', url: parsed.url }));
          } catch {
            res.writeHead(400, { 'Access-Control-Allow-Origin': '*' });
            res.end('bad request');
          }
        });
        return;
      }

      res.writeHead(404, { 'Access-Control-Allow-Origin': '*' });
      res.end('not found');
    });

    await new Promise<void>((resolve) => server.listen(MOCK_PORT, resolve));
  });

  test.afterAll(async () => {
    server.closeAllConnections();
    await new Promise<void>((resolve) => server.close(() => resolve()));
  });

  test('recognizes video links from the real Douyin homepage', async () => {
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
      MOCK_PORT
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

    // Submit the first recognized link through the E2E bridge.
    lastSubmission = null;
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

    await expect.poll(() => lastSubmission, { timeout: 20000 }).not.toBeNull();
    expect(lastSubmission!.url).toBe(firstLink.url);
    expect(lastSubmission!.source).toBe('browser_extension');
    expect(lastSubmission!.mode).toBe('archive');

    await page.close();
    await context.close();
  });
});
