import { chromium, expect, test } from '@playwright/test';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { startRealBackend, type RealBackend } from './helpers/real-backend';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const EXTENSION_PATH = path.resolve(__dirname, '../../dist');
const FIXTURES_DIR = path.resolve(__dirname, './fixtures');
const BACKEND_PORT = 3456;

test.describe('AIPulse Clipper E2E', () => {
  let backend: RealBackend;

  test.beforeAll(async () => {
    // Real Python sidecar + HTTP bridge. Fixture pages are served by the
    // fallback handler; submissions go to the real sidecar's submit_url.
    backend = await startRealBackend(BACKEND_PORT, (req, res) => {
      const url = new URL(req.url ?? '/', `http://localhost:${BACKEND_PORT}`);
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
  });

  test.afterAll(async () => {
    await backend.close();
  });

  test('detects links on each platform fixture and submits to the real sidecar', async () => {
    test.setTimeout(480_000);
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

    // Point HTTP fallback at the real backend bridge.
    await serviceWorker.evaluate(
      (port) =>
        new Promise<void>((resolve) => {
          chrome.storage.local.set(
            { httpBaseUrl: `http://localhost:${port}` },
            () => resolve()
          );
        }),
      BACKEND_PORT
    );

    await warmupPage.close();

    // Order matters: the real sidecar's pipeline blocks its JSON-RPC loop while
    // a download runs, so subsequent submissions stall until the previous
    // pipeline finishes. Cases with URLs whose pipelines fail fast (stale ids,
    // 404s) go first; the real, downloadable Bilibili video goes last so its
    // long-running download blocks nothing.
    const cases = [
      { page: 'wechat.html', expectedUrl: 'https://mp.weixin.qq.com/s/abcdef' },
      { page: 'xiaohongshu.html', expectedUrl: 'https://www.xiaohongshu.com/discovery/item/647b0af200000000130034f9' },
      { page: 'douyin.html', expectedUrl: 'https://www.douyin.com/video/1234567890' },
      { page: 'bilibili.html', expectedUrl: 'https://www.bilibili.com/video/BV1xx411c7mD' },
    ];

    for (const { page: fixture, expectedUrl } of cases) {
      const countBefore = backend.getSubmissionCount();
      console.log(`[case] ${fixture} start, countBefore=${countBefore}`);
      await serviceWorker.evaluate(() => chrome.action.setBadgeText({ text: '' }));
      const page = await context.newPage();
      page.on('console', (msg) => console.log(`[case] PAGE CONSOLE: ${msg.text()}`));
      page.on('pageerror', (err) => console.log(`[case] PAGE ERROR: ${err.message}`));
      await page.goto(`http://localhost:${BACKEND_PORT}/${fixture}`);
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
      console.log(`[case] ${fixture} dispatched submit for ${expectedUrl}`);

      // Wait for THIS submission to reach the real sidecar. The sidecar may be
      // busy with the previous case's pipeline (see ordering note above).
      await expect
        .poll(() => backend.getSubmissionCount(), { timeout: 90_000 })
        .toBe(countBefore + 1);
      const taskId = backend.getSubmittedTaskId();
      expect(taskId, 'real sidecar should assign a task id').toMatch(/^[a-f0-9]{12}$/);

      const submitBody = backend.getLastSubmitBody();
      expect(submitBody).not.toBeNull();
      expect(submitBody!.url).toBe(expectedUrl);
      expect(submitBody!.source).toBe('browser_extension');
      expect(submitBody!.mode).toBe('archive');

      const status = await backend.client.request('get_task_status', {
        task_id: taskId,
      });
      expect(status.error, `get_task_status failed: ${JSON.stringify(status.error)}`).toBeUndefined();

      await page.close();
    }

    await context.close();
  });
});
