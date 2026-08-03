/**
 * 截图捕获（仅一次）
 *
 * 真实页面访问 + 扩展 popup 截图存到 tests/e2e/__screenshots__/，便于
 * 人工 review（spec step 6 要求）。截图不参与断言。
 */
import { chromium, expect, test } from '@playwright/test';
import fs from 'fs';
import http, { type Server } from 'http';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const EXTENSION_PATH = path.resolve(__dirname, '../../dist');
const SCREENSHOT_DIR = path.resolve(__dirname, './__screenshots__');
// Must be 3456 — the e2e manifest only whitelists localhost:3456 in
// content_scripts.matches (see vite.config.ts transformManifest).
const FIXTURE_PORT = 3456;
const FIXTURES_DIR = path.resolve(__dirname, './fixtures');

test.describe('AIPulse Clipper screenshots', () => {
  let server: Server;
  let userDataDir: string;

  test.beforeAll(async () => {
    fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
    fs.mkdirSync((userDataDir = path.join(__dirname, '../.tmp/user-data-screenshots')), {
      recursive: true,
    });

    // Serve a real bilibili fixture over HTTP so the content script's
    // content_scripts.matches (which includes localhost) actually fires.
    // The fixture's canonical URL is a real bilibili.com BV link, so the
    // extension will recognize it and the popup can render.
    server = http.createServer((req, res) => {
      const url = new URL(req.url ?? '/', `http://localhost:${FIXTURE_PORT}`);
      const filePath = path.resolve(
        FIXTURES_DIR,
        url.pathname === '/' ? 'bilibili.html' : url.pathname.replace(/^\//, '')
      );
      if (!filePath.startsWith(path.resolve(FIXTURES_DIR))) {
        res.writeHead(403);
        res.end('forbidden');
        return;
      }
      fs.readFile(filePath, (err, data) => {
        if (err) {
          res.writeHead(404);
          res.end('not found');
          return;
        }
        res.writeHead(200, { 'Content-Type': 'text/html' });
        res.end(data);
      });
    });
    await new Promise<void>((resolve) => server.listen(FIXTURE_PORT, resolve));
  });

  test.afterAll(async () => {
    server.closeAllConnections();
    await new Promise<void>((resolve) => server.close(() => resolve()));
  });

  test('capture: extension popup on a bilibili fixture + real douyin + real bilibili', async () => {
    test.setTimeout(60_000);

    const context = await chromium.launchPersistentContext(userDataDir, {
      headless: false,
      args: [
        '--headless=new',
        `--disable-extensions-except=${EXTENSION_PATH}`,
        `--load-extension=${EXTENSION_PATH}`,
        '--disable-blink-features=AutomationControlled',
      ],
      userAgent:
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 ' +
        '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
      viewport: { width: 1280, height: 720 },
    });
    const warmup = await context.newPage();
    await warmup.goto('about:blank');
    await expect.poll(() => context.serviceWorkers().length).toBeGreaterThan(0);
    await warmup.waitForTimeout(1000);
    const serviceWorker = context.serviceWorkers()[0];
    const extId = serviceWorker.url().split('/')[2];
    await warmup.close();

    // Page 1: bilibili fixture (recognized → popup can render)
    const biliPage = await context.newPage();
    await biliPage.goto(`http://localhost:${FIXTURE_PORT}/bilibili.html`);
    await biliPage.waitForLoadState('networkidle');
    await expect
      .poll(() => serviceWorker.evaluate(() => chrome.action.getBadgeText({})), { timeout: 10_000 })
      .not.toBe('');

    const popupPage = await context.newPage();
    await popupPage.goto(`chrome-extension://${extId}/popup.html`);
    await popupPage.evaluate(
      (args) => {
        (window as unknown as { __TEST_TAB_ID__: number }).__TEST_TAB_ID__ = args.tabId;
        (window as unknown as { __TEST_TAB_URL__: string }).__TEST_TAB_URL__ = args.url;
        (chrome.tabs as unknown as { query: (q: unknown, cb?: (r: unknown) => void) => unknown }).query = (
          _q: unknown,
          callback?: (r: unknown) => void
        ) => {
          const result = [{ id: args.tabId, url: args.url, active: true, windowId: 1 }];
          if (callback) callback(result);
          return Promise.resolve(result);
        };
        const refresh = document.querySelector('button[title="刷新"]') as HTMLButtonElement | null;
        refresh?.click();
      },
      { tabId: 1, url: 'https://www.bilibili.com/video/BV1xx411c7mD' }
    );
    await popupPage.waitForTimeout(1500);
    await popupPage.screenshot({
      path: path.join(SCREENSHOT_DIR, 'popup-bilibili-fixture.png'),
      fullPage: true,
    });
    await popupPage.close();

    // Page 2: real douyin jingxuan
    const douyinPage = await context.newPage();
    await douyinPage.route('**/*bytegoofy.com/**', (route) => route.abort());
    await douyinPage.goto('https://www.douyin.com/jingxuan', {
      waitUntil: 'domcontentloaded',
      timeout: 30_000,
    });
    await douyinPage.waitForTimeout(3000);
    await douyinPage.mouse.wheel(0, 800).catch(() => {});
    await douyinPage.waitForTimeout(1500);
    await douyinPage.screenshot({
      path: path.join(SCREENSHOT_DIR, 'douyin-jingxuan-real.png'),
      fullPage: false,
    });
    await douyinPage.close();

    // Page 3: real bilibili homepage
    const realBiliPage = await context.newPage();
    await realBiliPage.goto('https://www.bilibili.com/', {
      waitUntil: 'domcontentloaded',
      timeout: 30_000,
    });
    await realBiliPage.waitForTimeout(3000);
    await realBiliPage.screenshot({
      path: path.join(SCREENSHOT_DIR, 'bilibili-homepage-real.png'),
      fullPage: false,
    });
    await realBiliPage.close();

    await biliPage.close();
    await context.close();
  });
});
