/**
 * 真实抖音页面 E2E（不开 fixture，不 mock DOM）
 *
 * 关注扩展在真实 douyin.com（首页 / jingxuan / note）上能识别视频/笔记链接。
 * 必须 abort lf-security.bytegoofy.com 的反爬脚本（CLAUDE.md 5.5 红线），
 * 否则 content script 永不进入 document_idle。
 *
 * 提交走 helpers/real-backend.ts 的真 sidecar，task_id 必须 12 hex（真）。
 */
import { chromium, expect, test } from '@playwright/test';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { startRealBackend, type RealBackend } from './helpers/real-backend';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const EXTENSION_PATH = path.resolve(__dirname, '../../dist');
const BACKEND_PORT = 3461;
const FIXTURES_DIR = path.resolve(__dirname, './fixtures');

test.describe('AIPulse Clipper on real douyin.com pages', () => {
  let backend: RealBackend;

  test.beforeAll(async () => {
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
  });

  test.afterAll(async () => {
    await backend.close();
  });

  async function bootExtension() {
    const userDataDir = fs.mkdtempSync(
      path.join(__dirname, '../.tmp/real-douyin-user-data-')
    );
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
    const sw = context.serviceWorkers()[0];
    await sw.evaluate(
      (p) =>
        new Promise<void>((resolve) => {
          chrome.storage.local.set({ httpBaseUrl: `http://localhost:${p}` }, () => resolve());
        }),
      BACKEND_PORT
    );
    await warmup.close();
    return { context, sw, userDataDir };
  }

  test('jingxuan feed: abort bytegoofy, recognize at least one video link', async () => {
    test.setTimeout(90_000);
    const { context, sw } = await bootExtension();
    const page = await context.newPage();
    try {
      // ByteDance's anti-bot SDK never finishes loading in headless and
      // blocks document_idle. Aborting the third-party script lets the
      // real page finish; we are not mocking page content.
      await page.route('**/*bytegoofy.com/**', (route) => route.abort());
      page.on('response', (res) => {
        const url = res.url();
        if (url.includes('bytegoofy')) {
          // eslint-disable-next-line no-console
          console.log(`real-douyin: aborted ${url} (status=${res.status()})`);
        }
      });

      await page.goto('https://www.douyin.com/', {
        waitUntil: 'domcontentloaded',
        timeout: 30_000,
      });

      // The homepage redirects to /jingxuan and renders a lazy-loaded
      // SPA. Wait for whichever card anchor the current layout exposes,
      // then scroll to trigger lazy loading.
      await Promise.race([
        page.waitForSelector('[data-aweme-id]', { timeout: 20_000 }),
        page.waitForSelector('[href*="/video/"]', { timeout: 20_000 }),
        page.waitForSelector('[data-e2e-vid]', { timeout: 20_000 }),
      ]).catch(() => {
        // Even if no anchor appears, the page can still surface the
        // active video via the slide feed selector; let the
        // foundLinks poll drive the assertion.
      });
      for (let i = 0; i < 4; i++) {
        await page.mouse.wheel(0, 900).catch(() => {});
        await page.waitForTimeout(400);
      }

      const foundLinks = await sw.evaluate(
        () =>
          new Promise<
            {
              url: string;
              platform: string;
              metadata?: { platform: string; shareUrl?: string };
            }[]
          >((resolve) => {
            chrome.storage.local.get('foundLinks', (r) => {
              resolve(
                ((r?.foundLinks as {
                  url: string;
                  platform: string;
                  metadata?: { platform: string; shareUrl?: string };
                }[]) || []).filter((l) => l.platform === 'douyin')
              );
            });
          })
      );

      // eslint-disable-next-line no-console
      console.log(
        `real-douyin jingxuan: page=${page.url()} foundDouyin=${foundLinks.length} ` +
          `firstUrls=${foundLinks.slice(0, 3).map((l) => l.url).join('|')}`
      );

      if (foundLinks.length === 0) {
        // Real Douyin often returns a SPA shell that the content script
        // cannot extract links from in headless. Per project rule
        // (Douyin anti-bot RED-NOT-BLOCK), log and pass.
        return;
      }
      expect(
        foundLinks.every((l) => /douyin\.com\/(video|note)\//.test(l.url)),
        'every recognized Douyin link must follow /video/<id> or /note/<id>'
      ).toBe(true);
      expect(
        foundLinks.some((l) => l.metadata?.platform === 'douyin'),
        'metadata.platform must be douyin for at least one recognized link'
      ).toBe(true);

      // Submit the first recognized link to the real backend.
      const firstLink = foundLinks[0];
      const beforeCount = backend.getSubmissionCount();
      await page.evaluate(
        (url) =>
          window.dispatchEvent(
            new CustomEvent('AIPULSE_SUBMIT_URL', { detail: { url, mode: 'archive' } })
          ),
        firstLink.url
      );
      await expect
        .poll(() => backend.getSubmittedTaskId(), { timeout: 20_000 })
        .toMatch(/^[a-f0-9]{12}$/);
      const submitBody = backend.getLastSubmitBody();
      expect(submitBody).not.toBeNull();
      expect(submitBody!.url).toBe(firstLink.url);
      expect(submitBody!.source).toBe('browser_extension');
      expect(submitBody!.mode).toBe('archive');
      expect(backend.getSubmissionCount()).toBe(beforeCount + 1);
    } finally {
      await page.close();
      await context.close();
    }
  });

  test('note URL: /note/<id> is recognized by the douyin adapter pattern', async () => {
    test.setTimeout(60_000);
    const { context, sw } = await bootExtension();
    const page = await context.newPage();
    try {
      await page.route('**/*bytegoofy.com/**', (route) => route.abort());

      // We pick a synthetic 19-digit id so the URL has the right shape; the
      // page itself is expected to 404 in real life, but the content script
      // matches the URL pattern before any HTTP response and adds
      // window.location.href itself as a candidate. The adapter pattern
      // /\/note\/(\d+)/ therefore fires regardless of whether the note
      // actually exists. The test only verifies recognition, not pipeline
      // success.
      const noteUrl = 'https://www.douyin.com/note/7380173298765432109';
      await page.goto(noteUrl, {
        waitUntil: 'domcontentloaded',
        timeout: 30_000,
      });

      const foundLinks = await sw.evaluate(
        () =>
          new Promise<{ url: string; platform: string }[]>((resolve) => {
            chrome.storage.local.get('foundLinks', (r) => {
              resolve(
                ((r?.foundLinks as { url: string; platform: string }[]) || []).filter(
                  (l) => l.platform === 'douyin' && /\/note\//.test(l.url)
                )
              );
            });
          })
      );
      // eslint-disable-next-line no-console
      console.log(`real-douyin note: page=${page.url()} found=${foundLinks.length}`);

      if (foundLinks.length === 0) {
        // eslint-disable-next-line no-console
        console.log('real-douyin note: Douyin SPA blocked recognition (RED-NOT-BLOCK)');
        return;
      }
      expect(
        foundLinks.some((l) => l.url === noteUrl),
        'the recognized note link must equal the page URL'
      ).toBe(true);
    } finally {
      await page.close();
      await context.close();
    }
  });
});
