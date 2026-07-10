import { chromium, expect, test } from '@playwright/test';
import fs from 'fs';
import http from 'http';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const EXTENSION_PATH = path.resolve(__dirname, '../../dist');
const FIXTURES_DIR = path.resolve(__dirname, './fixtures');
const MOCK_PORT = 3456;

test.describe('AIPulse Clipper E2E', () => {
  let server: http.Server;
  let lastSubmission: { url: string; source: string; mode: string } | null = null;

  test.beforeAll(async () => {
    server = http.createServer((req, res) => {
      const url = new URL(req.url ?? '/', `http://localhost:${MOCK_PORT}`);

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
            res.writeHead(200, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ task_id: 'e2e-task-123', url: parsed.url }));
          } catch {
            res.writeHead(400);
            res.end('bad request');
          }
        });
        return;
      }

      const filePath = path.resolve(
        FIXTURES_DIR,
        url.pathname === '/' ? 'bilibili.html' : url.pathname.replace(/^\//, '')
      );
      if (!filePath.startsWith(path.resolve(FIXTURES_DIR))) {
        res.writeHead(403);
        res.end('forbidden');
        return;
      }
      const ext = path.extname(filePath);
      const contentType = ext === '.html' ? 'text/html' : 'application/octet-stream';
      fs.readFile(filePath, (err, data) => {
        if (err) {
          res.writeHead(404);
          res.end('not found');
          return;
        }
        res.writeHead(200, { 'Content-Type': contentType });
        res.end(data);
      });
    });

    await new Promise<void>((resolve) => server.listen(MOCK_PORT, resolve));
  });

  test.afterAll(async () => {
    server.closeAllConnections();
    await new Promise<void>((resolve) => server.close(() => resolve()));
  });

  test('detects links on each platform fixture and submits via HTTP fallback', async () => {
    const userDataDir = path.join(__dirname, '../.tmp/user-data');
    fs.mkdirSync(userDataDir, { recursive: true });

    const context = await chromium.launchPersistentContext(userDataDir, {
      headless: false,
      args: [
        '--headless=new',
        `--disable-extensions-except=${EXTENSION_PATH}`,
        `--load-extension=${EXTENSION_PATH}`,
      ],
    });

    const warmupPage = await context.newPage();
    await warmupPage.goto('about:blank');
    await expect.poll(() => context.serviceWorkers().length).toBeGreaterThan(0);
    // Give the MV3 service worker a moment to fully initialize before the
    // content script starts sending FOUND_LINKS messages.
    await warmupPage.waitForTimeout(1000);
    const serviceWorkers = context.serviceWorkers();
    expect(serviceWorkers.length, 'extension service worker should be registered').toBeGreaterThan(0);
    const serviceWorker = serviceWorkers[0];
    const extId = serviceWorker.url().split('/')[2];
    expect(extId).toBeTruthy();

    // Point HTTP fallback at the mock server.
    await serviceWorker.evaluate(
      (port) =>
        new Promise<void>((resolve) => {
          chrome.storage.local.set(
            { httpBaseUrl: `http://localhost:${port}` },
            () => resolve()
          );
        }),
      MOCK_PORT
    );

    await warmupPage.close();

    const cases = [
      { page: 'bilibili.html', expectedUrl: 'https://www.bilibili.com/video/BV1xx411c7mD' },
      { page: 'douyin.html', expectedUrl: 'https://www.douyin.com/video/1234567890' },
      { page: 'xiaohongshu.html', expectedUrl: 'https://www.xiaohongshu.com/discovery/item/647b0af200000000130034f9' },
      { page: 'wechat.html', expectedUrl: 'https://mp.weixin.qq.com/s/abcdef' },
    ];

    for (const { page: fixture, expectedUrl } of cases) {
      lastSubmission = null;
      await serviceWorker.evaluate(() => chrome.action.setBadgeText({ text: '' }));
      const page = await context.newPage();
      await page.goto(`http://localhost:${MOCK_PORT}/${fixture}`);
      await page.waitForLoadState('networkidle');

      await expect
        .poll(async () => serviceWorker.evaluate(() => chrome.action.getBadgeText({})))
        .not.toBe('');

      await page.evaluate(
        (args) => {
          window.dispatchEvent(
            new CustomEvent('AIPULSE_SUBMIT_URL', {
              detail: { url: args.expectedUrl, mode: 'archive' },
            })
          );
        },
        { expectedUrl }
      );

      await expect.poll(() => lastSubmission).not.toBeNull();
      const submission = lastSubmission!;
      expect(submission.url).toBe(expectedUrl);
      expect(submission.source).toBe('browser_extension');
      expect(submission.mode).toBe('archive');

      await page.close();
    }

    await context.close();
  });
});
