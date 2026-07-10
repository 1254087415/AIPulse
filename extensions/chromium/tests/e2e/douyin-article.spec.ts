import { chromium, expect, test } from '@playwright/test';
import http from 'http';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const EXTENSION_PATH = path.resolve(__dirname, '../../dist');
const MOCK_PORT = 3457;

// Real Douyin note/article URL. Douyin note ids are 19-digit numbers; this one
// follows the public /note/<id> pattern served by douyin.com's real web app.
// Popular creator note URLs rotate quickly (notes get deleted/privated), so
// pinning a specific live note would make the test flaky. The extension's
// Douyin adapter recognizes the link purely from the page URL pattern
// (see src/platform/douyin.ts and the "extracts article/note id from current
// url" unit test), so a real-pattern URL is sufficient: the content script
// runs on douyin.com (matched by manifest `https://www.douyin.com/*`) and adds
// window.location.href itself as a candidate, which the /note/<id> pattern
// matches even when the specific note returns Douyin's SPA shell / 404.
const DOUYIN_NOTE_URL = 'https://www.douyin.com/note/7380173298765432109';

interface FoundLink {
  url: string;
  platform: string;
  title?: string;
  contentPreview?: string;
}

test.describe('AIPulse Douyin article/note E2E', () => {
  let server: http.Server;
  let lastSubmission: { url: string; source: string; mode: string } | null = null;

  test.beforeAll(async () => {
    server = http.createServer((req, res) => {
      const url = new URL(req.url ?? '/', `http://localhost:${MOCK_PORT}`);

      // The extension service worker fetches this mock cross-origin (port 3457 is
      // not in the extension's host_permissions, which only allow 3456). A POST
      // with Content-Type: application/json triggers a CORS preflight; we must
      // answer it or Chromium blocks the real request and the submission never
      // arrives. A real AIPulse backend would send the same headers.
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
            res.end(JSON.stringify({ task_id: 'e2e-douyin-note-123', url: parsed.url }));
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

  test('recognizes a Douyin note URL and submits it via HTTP fallback', async () => {
    const userDataDir = path.join(__dirname, '../.tmp/user-data-douyin-article');

    const context = await chromium.launchPersistentContext(userDataDir, {
      // Documented Playwright recipe for MV3 extensions in headless Chromium:
      // headless:false stops Playwright injecting its own legacy --headless flag
      // (which cannot host service workers); the explicit --headless=new selects
      // the new headless engine which CAN run MV3 service workers.
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
          chrome.storage.local.set({ httpBaseUrl: `http://localhost:${port}` }, () => resolve());
        }),
      MOCK_PORT
    );

    await warmupPage.close();

    lastSubmission = null;
    // The persistent user-data dir reuses chrome.storage.local across runs, so a
    // foundLinks value written by a previous run would otherwise be read back by
    // the storage poll and short-circuit it with a stale URL. Clear it (and the
    // badge) so the poll only observes links reported during THIS navigation.
    await serviceWorker.evaluate(
      () =>
        new Promise<void>((resolve) => {
          chrome.storage.local.set({ foundLinks: [] }, () => resolve());
        })
    );
    await serviceWorker.evaluate(() => chrome.action.setBadgeText({ text: '' }));

    const page = await context.newPage();
    page.on('console', (msg) => console.log('PAGE CONSOLE:', msg.text()));
    page.on('pageerror', (err) => console.log('PAGE ERROR:', err.message));

    // Douyin's note page pulls in ByteDance's anti-bot security SDK from
    // lf-security(-backup).bytegoofy.com as a parser-blocking script. In headless
    // Chromium that script never finishes loading (it hangs phoning home), so the
    // document never reaches DOMContentLoaded/document_idle and the MV3 content
    // script (run_at: document_idle) never fires — foundLinks would stay empty.
    // Aborting only that third-party SDK lets the real note page finish loading;
    // we are not mocking page content, just refusing to load its anti-bot script.
    await page.route('**/*bytegoofy.com/**', (route) => route.abort());

    // networkidle never fires on Douyin (continuous telemetry requests), so use
    // domcontentloaded, which now resolves once the anti-bot script is aborted.
    // The content script runs at document_idle and reports the page URL as a
    // candidate, which the /note/<id> adapter pattern matches.
    await page.goto(DOUYIN_NOTE_URL, { waitUntil: 'domcontentloaded', timeout: 30000 });

    // Poll the persisted storage rather than the GET_FOUND_LINKS runtime message:
    // the MV3 service worker is volatile and its in-memory foundLinksCache can be
    // empty after a recycle, whereas chrome.storage.local is durable.
    let foundLinks: FoundLink[] = [];
    try {
      await expect
        .poll(
          async () => {
            const links = await serviceWorker.evaluate(
              () =>
                new Promise<FoundLink[]>((resolve) => {
                  chrome.storage.local.get('foundLinks', (result) => {
                    resolve((result?.foundLinks as FoundLink[]) || []);
                  });
                })
            );
            foundLinks = links;
            return links.filter(
              (link) => link.platform === 'douyin' && /\/note\/\d+/.test(link.url)
            ).length;
          },
          { timeout: 20000 }
        )
        .toBeGreaterThan(0);
    } catch (err) {
      console.log('Page URL at timeout:', page.url());
      console.log('Found links at timeout:', JSON.stringify(foundLinks));
      throw err;
    }

    console.log('Page URL:', page.url());
    console.log('Found links:', JSON.stringify(foundLinks));

    const noteLinks = foundLinks.filter(
      (link) => link.platform === 'douyin' && /\/note\/\d+/.test(link.url)
    );
    expect(noteLinks.length, 'foundLinks should contain a Douyin note link').toBeGreaterThan(0);
    expect(
      noteLinks.map((link) => link.url),
      'the recognized note link should be the page URL we navigated to'
    ).toContain(DOUYIN_NOTE_URL);

    // Trigger a submission through the E2E bridge.
    await page.evaluate((url) => {
      window.dispatchEvent(
        new CustomEvent('AIPULSE_SUBMIT_URL', {
          detail: { url, mode: 'archive' },
        })
      );
    }, DOUYIN_NOTE_URL);

    await expect.poll(() => lastSubmission, { timeout: 20000 }).not.toBeNull();
    const submission = lastSubmission!;
    expect(submission.url).toBe(DOUYIN_NOTE_URL);
    expect(submission.source).toBe('browser_extension');
    expect(submission.mode).toBe('archive');

    await page.close();
    await context.close();
  });
});
