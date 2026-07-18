import { chromium, expect, test } from '@playwright/test';
import path from 'path';
import { fileURLToPath } from 'url';
import { startRealBackend, type RealBackend } from './helpers/real-backend';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const EXTENSION_PATH = path.resolve(__dirname, '../../dist');
const BACKEND_PORT = 3457;

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

  test('recognizes a Douyin note URL and submits it to the real sidecar', async () => {
    test.setTimeout(90_000);
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

    // Point HTTP fallback at the real backend bridge.
    await serviceWorker.evaluate(
      (port) =>
        new Promise<void>((resolve) => {
          chrome.storage.local.set({ httpBaseUrl: `http://localhost:${port}` }, () => resolve());
        }),
      BACKEND_PORT
    );

    await warmupPage.close();

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

    // Trigger a submission through the E2E bridge, all the way to the real
    // sidecar.
    await page.evaluate((url) => {
      window.dispatchEvent(
        new CustomEvent('AIPULSE_SUBMIT_URL', {
          detail: { url, mode: 'archive' },
        })
      );
    }, DOUYIN_NOTE_URL);

    // The real sidecar assigns task ids (12 hex chars, see aipulse task store).
    await expect
      .poll(() => backend.getSubmittedTaskId(), { timeout: 20000 })
      .toMatch(/^[a-f0-9]{12}$/);

    const submitBody = backend.getLastSubmitBody();
    expect(submitBody).not.toBeNull();
    expect(submitBody!.url).toBe(DOUYIN_NOTE_URL);
    expect(submitBody!.source).toBe('browser_extension');
    expect(submitBody!.mode).toBe('archive');

    // The task must exist in the real sidecar's task store (front-back
    // integration), regardless of how the async pipeline fares.
    const status = await backend.client.request('get_task_status', {
      task_id: backend.getSubmittedTaskId(),
    });
    expect(status.error, `get_task_status failed: ${JSON.stringify(status.error)}`).toBeUndefined();
    expect(status.result?.status, 'task should have a valid status in the real store').toBeTruthy();

    await page.close();
    await context.close();
  });
});
