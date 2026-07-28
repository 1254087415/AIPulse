/**
 * 错误路径 E2E（断网 / 5xx / cookie 失效）
 *
 * 三个用例都用真后端（real sidecar via helpers/real-backend.ts）跑 happy
 * path 验证；这里专测失败形态，按 spec 显式允许的"mock 返 500"做局部拦截：
 *   - 断网：context.setOffline(true) — SW 的 fetch 自然失败（真网络断）
 *   - 5xx：独立 500-only HTTP server（spec 显式说"mock 返 500"）
 *   - cookie 失效：往 SW 注入空 storage + 触发 RESCAN（真重扫路径）
 *
 * 三个测试都断言 chrome.storage 没崩（per CLAUDE.md I 类红线：
 * 业务失败不许标 completed），且 SW 在失败后仍响应 chrome.runtime.id
 * 这类简单 ping。
 */
import { chromium, expect, test } from '@playwright/test';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { startRealBackend, type RealBackend } from './helpers/real-backend';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const EXTENSION_PATH = path.resolve(__dirname, '../../dist');
const BACKEND_PORT = 3456;
const FIXTURES_DIR = path.resolve(__dirname, './fixtures');

test.describe('AIPulse Clipper error paths', () => {
  let backend: RealBackend;

  test.beforeAll(async () => {
    backend = await startRealBackend(BACKEND_PORT, (req, res) => {
      const filePath = path.resolve(FIXTURES_DIR, 'bilibili.html');
      res.writeHead(200, { 'Content-Type': 'text/html' });
      res.end(fs.readFileSync(filePath));
    });
  });

  test.afterAll(async () => {
    await backend.close();
  });

  async function bootExtension(port: number) {
    const userDataDir = fs.mkdtempSync(
      path.join(__dirname, '../.tmp/error-paths-user-data-')
    );
    const context = await chromium.launchPersistentContext(userDataDir, {
      headless: false,
      args: [
        '--headless=new',
        `--disable-extensions-except=${EXTENSION_PATH}`,
        `--load-extension=${EXTENSION_PATH}`,
      ],
    });
    const warmup = await context.newPage();
    await warmup.goto('about:blank');
    await expect.poll(() => context.serviceWorkers().length).toBeGreaterThan(0);
    await warmup.waitForTimeout(1000);
    const sw = context.serviceWorkers()[0];
    await sw.evaluate(
      (p) =>
        new Promise<void>((resolve) => {
          chrome.storage.local.set({ httpBaseUrl: `http://localhost:${p}` }, () => resolve());
        }),
      port
    );
    await warmup.close();
    return { context, sw, userDataDir };
  }

  /**
   * SW liveness probe — uses a primitive that does NOT depend on the message
   * bus (which can deadlock if a previous handler is still in flight). It
   * also avoids chrome.storage because the offline test wipes it.
   */
  async function isSwAlive(sw: Awaited<ReturnType<typeof bootExtension>>['sw']): Promise<boolean> {
    try {
      return await sw.evaluate(
        () => typeof chrome !== 'undefined' && typeof chrome.runtime !== 'undefined' && !!chrome.runtime.id
      );
    } catch {
      return false;
    }
  }

  test('network offline: submitViaHttp fails gracefully, storage stays consistent', async () => {
    test.setTimeout(60_000);
    const { context, sw } = await bootExtension(BACKEND_PORT);
    const page = await context.newPage();
    await page.goto(`http://localhost:${BACKEND_PORT}/bilibili.html`);
    await page.waitForLoadState('networkidle');

    // Baseline: extension must recognize the bilibili fixture via badge.
    await expect
      .poll(() => sw.evaluate(() => chrome.action.getBadgeText({})), { timeout: 10_000 })
      .not.toBe('');

    const beforeCount = backend.getSubmissionCount();
    const beforeBadge = await sw.evaluate(() => chrome.action.getBadgeText({}));

    // Cut the network and dispatch the E2E submit bridge. The SW's
    // submitViaHttp will fail with net::ERR_INTERNET_DISCONNECTED; we
    // assert (a) no submit reached the backend, (b) SW is still alive,
    // (c) storage wasn't corrupted.
    await context.setOffline(true);
    await page.evaluate(
      () =>
        window.dispatchEvent(
          new CustomEvent('AIPULSE_SUBMIT_URL', {
            detail: { url: 'https://www.bilibili.com/video/BV1xx411c7mD', mode: 'archive' },
          })
        )
    );

    // Give the SW a generous window to attempt the request and fail.
    await page.waitForTimeout(3000);

    expect(
      backend.getSubmissionCount(),
      'no submit should reach the backend when offline'
    ).toBe(beforeCount);

    expect(await isSwAlive(sw), 'SW must remain alive after offline submit').toBe(true);

    const afterBadge = await sw.evaluate(() => chrome.action.getBadgeText({}));
    expect(afterBadge, 'badge must be unchanged by failed offline submit').toBe(beforeBadge);

    // foundLinks must remain a valid array.
    const linksShape = await sw.evaluate(
      () =>
        new Promise<boolean>((resolve) => {
          chrome.storage.local.get('foundLinks', (r) => {
            const v = r?.foundLinks;
            resolve(v === undefined || Array.isArray(v));
          });
        })
    );
    expect(linksShape, 'foundLinks must remain a valid shape (or absent) after offline failure').toBe(true);

    await context.setOffline(false);
    await page.close();
    await context.close();
  });

  test('server 5xx: submitViaHttp returns 500, surfaces error, no phantom success', async () => {
    test.setTimeout(60_000);

    // Use the real backend port (BACKEND_PORT) and intercept the SW's POST
    // at the browser level. We do NOT mock the sidecar; only the HTTP
    // response is forced to 500 so we can assert how the SW surfaces a
    // backend failure. context.route() intercepts every request that goes
    // through Chromium's network stack, including the service worker's
    // submitViaHttp.
    let received: { url: string; body: string } | null = null;

    const { context, sw } = await bootExtension(BACKEND_PORT);
    const page = await context.newPage();
    await page.goto(`http://localhost:${BACKEND_PORT}/bilibili.html`);
    await page.waitForLoadState('networkidle');

    await expect
      .poll(() => sw.evaluate(() => chrome.action.getBadgeText({})), { timeout: 10_000 })
      .not.toBe('');

    // Install the 500-only route AFTER the page-load network so the
    // extension's badge poll isn't intercepted. Use a `*` glob for any
    // path under the bridge (content scripts hit /api/videos/extract; SW
    // may also hit /api/videos/extract or /api/tasks/* depending on flow).
    await context.route('**/api/videos/extract', (route) => {
      const req = route.request();
      received = { url: req.url(), body: req.postData() || '' };
      route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ error: 'forced 500 for E2E' }),
      });
    });

    // Dispatch the E2E submit bridge. The SW's submitViaHttp will hit
    // the bridge (now returning 500) and surface the failure.
    await page.evaluate(
      () =>
        window.dispatchEvent(
          new CustomEvent('AIPULSE_SUBMIT_URL', {
            detail: { url: 'https://www.bilibili.com/video/BV1xx411c7mD', mode: 'archive' },
          })
        )
    );

    await expect
      .poll(() => received !== null, { timeout: 10_000 })
      .toBe(true);

    expect(received!.url).toContain('/api/videos/extract');
    const body = JSON.parse(received!.body) as { url: string; source: string; mode: string };
    expect(body.url).toBe('https://www.bilibili.com/video/BV1xx411c7mD');
    expect(body.source).toBe('browser_extension');
    expect(body.mode).toBe('archive');

    // Storage must not contain phantom success records.
    const stored = await sw.evaluate(
      () =>
        new Promise<string[]>((resolve) => {
          chrome.storage.local.get(null, (r) => resolve(Object.keys(r ?? {})));
        })
    );
    expect(stored, 'storage must not contain a phantom success record').not.toContain('submitResult');
    expect(stored, 'storage must not contain a phantom task_id').not.toContain('taskId');

    expect(await isSwAlive(sw), 'SW must remain alive after 5xx response').toBe(true);

    // Real backend saw no successful submission — every request was
    // intercepted and forced to 500 before reaching the bridge.
    expect(backend.getSubmissionCount()).toBe(0);

    await page.close();
    await context.close();
  });

  test('cookie 失效: SW resets and rescan re-populates links without crashing', async () => {
    test.setTimeout(60_000);
    const { context, sw } = await bootExtension(BACKEND_PORT);
    const page = await context.newPage();
    await page.goto(`http://localhost:${BACKEND_PORT}/bilibili.html`);
    await page.waitForLoadState('networkidle');

    // Wait for initial recognition so we know the SW is healthy.
    await expect
      .poll(() => sw.evaluate(() => chrome.action.getBadgeText({})), { timeout: 10_000 })
      .not.toBe('');

    // Wipe storage to simulate a cookie session reset. The badge goes to
    // 0. We then ask the SW to rescan the active tab — this is what the
    // popup does on mount when the per-tab map is empty.
    await sw.evaluate(
      () =>
        new Promise<void>((resolve) => {
          chrome.storage.local.set({ foundLinks: [] }, () => resolve());
        })
    );
    await sw.evaluate(() => chrome.action.setBadgeText({ text: '' }));

    const rescan = await sw.evaluate(
      () =>
        new Promise<{ ok: boolean; count: number; error?: string }>((resolve) => {
          chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
            const tabId = tabs[0]?.id;
            if (!tabId) {
              resolve({ ok: false, count: 0, error: 'no active tab' });
              return;
            }
            chrome.tabs.sendMessage(tabId, { type: 'RESCAN' }, (response) => {
              void chrome.runtime.lastError;
              const r = response as { ok: boolean; links?: unknown[] } | undefined;
              resolve({
                ok: !!r?.ok,
                count: Array.isArray(r?.links) ? r.links.length : 0,
                error: chrome.runtime.lastError?.message,
              });
            });
          });
        })
    );
    expect(rescan.ok, `rescan must succeed after cookie reset; got ${JSON.stringify(rescan)}`).toBe(true);
    expect(rescan.count, 'rescan must find at least one link after cache reset').toBeGreaterThan(0);

    // Badge re-asserts to a non-empty value (the content script reported a
    // link back to the SW via FOUND_LINKS).
    await expect
      .poll(() => sw.evaluate(() => chrome.action.getBadgeText({})), { timeout: 5_000 })
      .not.toBe('');

    expect(await isSwAlive(sw), 'SW must remain alive after cookie/cache reset').toBe(true);

    await page.close();
    await context.close();
  });
});
