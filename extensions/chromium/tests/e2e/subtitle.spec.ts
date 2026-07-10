import { chromium, expect, test } from '@playwright/test';
import http from 'http';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const EXTENSION_PATH = path.resolve(__dirname, '../../dist');
const MOCK_PORT = 3456;
const REAL_BILIBILI_URL = 'https://www.bilibili.com/video/BV1JNMV6dEp2/';

test.describe('AIPulse Clipper subtitle recognition on real Bilibili page', () => {
  let server: http.Server;
  let lastSubmission: {
    url: string;
    source: string;
    mode: string;
    subtitle_text?: string;
    subtitle_language?: string;
  } | null = null;

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
              subtitle_text: parsed.subtitle_text,
              subtitle_language: parsed.subtitle_language,
            };
            res.writeHead(200, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ task_id: 'e2e-subtitle-123', url: parsed.url }));
          } catch {
            res.writeHead(400);
            res.end('bad request');
          }
        });
        return;
      }

      res.writeHead(404);
      res.end('not found');
    });

    await new Promise<void>((resolve) => server.listen(MOCK_PORT, resolve));
  });

  test.afterAll(async () => {
    server.closeAllConnections();
    await new Promise<void>((resolve) => server.close(() => resolve()));
  });

  test('recognizes and loads real subtitles from Bilibili', async () => {
    const userDataDir = path.join(__dirname, '../.tmp/user-data-subtitle');

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
    await warmupPage.waitForTimeout(1000);
    const serviceWorkers = context.serviceWorkers();
    expect(serviceWorkers.length, 'extension service worker should be registered').toBeGreaterThan(0);
    const serviceWorker = serviceWorkers[0];
    const extId = serviceWorker.url().split('/')[2];
    expect(extId).toBeTruthy();

    // Redirect extension HTTP submissions to the local mock server.
    await serviceWorker.evaluate(
      (port) =>
        new Promise<void>((resolve) => {
          chrome.storage.local.set({ httpBaseUrl: `http://localhost:${port}` }, () => resolve());
        }),
      MOCK_PORT
    );

    await warmupPage.close();

    const page = await context.newPage();
    await page.goto(REAL_BILIBILI_URL, { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('networkidle');

    // Wait for the extension to recognize the Bilibili link.
    await expect
      .poll(async () => serviceWorker.evaluate(() => chrome.action.getBadgeText({})), {
        timeout: 20000,
      })
      .not.toBe('');

    // Verify the extension stored found links with real subtitle metadata.
    const foundLinks = await serviceWorker.evaluate(() =>
      new Promise<
        {
          url: string;
          platform: string;
          metadata?: {
            subtitleOptions: { lan: string; lanDoc: string; subtitleUrl: string }[];
            subtitleEntries: { from: number; to: number; content: string }[];
          };
        }[]
      >((resolve) => {
        chrome.storage.local.get('foundLinks', (result) => {
          resolve((result?.foundLinks as any) || []);
        });
      })
    );

    expect(foundLinks.length).toBeGreaterThan(0);
    const bilibiliLink = foundLinks.find((link) => link.platform === 'bilibili');
    expect(bilibiliLink, 'should recognize a Bilibili link').toBeTruthy();
    expect(bilibiliLink!.url).toContain('bilibili.com/video/BV1JNMV6dEp2');
    expect(
      bilibiliLink!.metadata?.subtitleOptions.length,
      'should detect at least one subtitle option'
    ).toBeGreaterThan(0);

    const firstOption = bilibiliLink!.metadata!.subtitleOptions[0];
    expect(firstOption.lan).toBeTruthy();
    expect(firstOption.lanDoc).toBeTruthy();
    expect(firstOption.subtitleUrl).toMatch(/^https?:\/\//);

    // Load the actual subtitle entries through the extension.
    const subtitleResult = await serviceWorker.evaluate(
      (url) =>
        new Promise<{
          ok: boolean;
          entries?: { from: number; to: number; content: string }[];
          formatted?: string;
          error?: string;
        }>((resolve) => {
          chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
            const tabId = tabs[0]?.id;
            if (!tabId) {
              resolve({ ok: false, error: 'no active tab' });
              return;
            }
            chrome.tabs.sendMessage(tabId, { type: 'FETCH_SUBTITLE', subtitleUrl: url }, (response) => {
              if (chrome.runtime.lastError) {
                resolve({ ok: false, error: chrome.runtime.lastError.message });
                return;
              }
              resolve((response as any) || { ok: false, error: 'no response' });
            });
          });
        }),
      firstOption.subtitleUrl
    );

    expect(subtitleResult.ok, `subtitle fetch failed: ${subtitleResult.error} (url: ${firstOption.subtitleUrl})`).toBe(true);
    expect(subtitleResult.entries?.length, 'should load real subtitle entries').toBeGreaterThan(0);

    const firstEntry = subtitleResult.entries![0];
    expect(typeof firstEntry.from).toBe('number');
    expect(typeof firstEntry.to).toBe('number');
    expect(typeof firstEntry.content).toBe('string');
    expect(firstEntry.content.length).toBeGreaterThan(0);

    // Submit the link with the loaded subtitle text through the E2E page bridge.
    lastSubmission = null;
    await page.evaluate(
      (args) => {
        window.dispatchEvent(
          new CustomEvent('AIPULSE_SUBMIT_URL', {
            detail: {
              url: args.url,
              mode: 'archive',
              subtitle_text: args.subtitleText,
              subtitle_language: args.subtitleLanguage,
            },
          })
        );
      },
      {
        url: REAL_BILIBILI_URL,
        subtitleText: subtitleResult.formatted,
        subtitleLanguage: firstOption.lan,
      }
    );

    await expect.poll(() => lastSubmission, { timeout: 10000 }).not.toBeNull();
    expect(lastSubmission!.url).toContain('bilibili.com/video/BV1JNMV6dEp2');
    expect(lastSubmission!.source).toBe('browser_extension');
    expect(lastSubmission!.mode).toBe('archive');
    expect(lastSubmission!.subtitle_language).toBe(firstOption.lan);
    expect(lastSubmission!.subtitle_text).toContain(firstEntry.content);

    // Open the popup directly and inject the real Bilibili tab so the UI renders the auto-loaded subtitle preview.
    const bilibiliTabId = await serviceWorker.evaluate(() =>
      new Promise<number | undefined>((resolve) => {
        chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
          resolve(tabs[0]?.id);
        });
      })
    );
    expect(bilibiliTabId).toBeTruthy();

    const popupPage = await context.newPage();
    await popupPage.goto(`chrome-extension://${extId}/popup.html`);

    await popupPage.evaluate(
      (args) => {
        (window as any).__TEST_TAB_ID__ = args.tabId;
        (window as any).__TEST_TAB_URL__ = args.url;
        (chrome.tabs as any).query = (queryInfo: any, callback?: any) => {
          const result = [{ id: args.tabId, url: args.url, active: true, windowId: 1 }];
          if (callback) callback(result);
          return Promise.resolve(result);
        };
        const refreshBtn = document.querySelector('button[title="刷新"]') as HTMLButtonElement | null;
        refreshBtn?.click();
      },
      { tabId: bilibiliTabId, url: REAL_BILIBILI_URL }
    );

    const preview = popupPage.locator('.subtitle-preview');
    await expect(preview).toBeVisible({ timeout: 15000 });
    const previewText = await preview.inputValue();
    expect(previewText.length).toBeGreaterThan(0);
    expect(previewText).toContain(firstEntry.content);

    await popupPage.screenshot({
      path: path.join(__dirname, './fixtures/subtitle-popup-real-bilibili.png'),
    });

    await popupPage.close();
    await page.close();
    await context.close();
  });
});
