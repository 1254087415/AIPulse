import { chromium, expect, test } from '@playwright/test';
import { spawn, type ChildProcessWithoutNullStreams } from 'child_process';
import fs from 'fs';
import http, { type Server } from 'http';
import os from 'os';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const EXTENSION_PATH = path.resolve(__dirname, '../../dist');
const ARTICLE_PORT = 3456;
const BRIDGE_PORT = ARTICLE_PORT; // Extension host_permissions only allow localhost:3456
const LLM_MOCK_PORT = 3458;
const PROJECT_ROOT = path.resolve(__dirname, '../../../..');
const PYTHON = path.resolve(PROJECT_ROOT, '.venv/bin/python');

const ARTICLE_HTML = `<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>Obsidian Archive E2E Test Article</title>
</head>
<body>
  <article>
    <h1>Obsidian Archive E2E Test Article</h1>
    <p>This is a stable article used to verify the AIPulse browser extension Obsidian archive flow.</p>
    <p>The Python sidecar extracts this text, asks the configured LLM for a summary, and writes source and summary notes into the Obsidian vault.</p>
    <p>Key topics: end-to-end testing, browser extensions, and Obsidian archiving.</p>
  </article>
</body>
</html>`;

interface SidecarResponse {
  jsonrpc: '2.0';
  id?: number;
  result?: Record<string, unknown>;
  error?: { code: number; message: string };
}

interface SidecarNotification {
  jsonrpc: '2.0';
  method: string;
  params: Record<string, unknown>;
}

class SidecarClient {
  private process: ChildProcessWithoutNullStreams;
  private pending = new Map<number, (value: SidecarResponse) => void>();
  private nextId = 1;
  private buffer = '';
  notifications: SidecarNotification[] = [];

  constructor(process: ChildProcessWithoutNullStreams) {
    this.process = process;
    process.stdout.on('data', (chunk: Buffer) => {
      this.buffer += chunk.toString('utf-8');
      let lineEnd: number;
      while ((lineEnd = this.buffer.indexOf('\n')) >= 0) {
        const line = this.buffer.slice(0, lineEnd).trim();
        this.buffer = this.buffer.slice(lineEnd + 1);
        if (line) this._handleLine(line);
      }
    });
  }

  private _handleLine(line: string): void {
    try {
      const parsed = JSON.parse(line) as SidecarResponse | SidecarNotification;
      if ('id' in parsed && parsed.id !== undefined) {
        const resolver = this.pending.get(parsed.id);
        if (resolver) {
          this.pending.delete(parsed.id);
          resolver(parsed);
        }
      } else if ('method' in parsed) {
        this.notifications.push(parsed as SidecarNotification);
      }
    } catch {
      // Ignore non-JSON lines (e.g. stray logs).
    }
  }

  request(method: string, params: Record<string, unknown> = {}): Promise<SidecarResponse> {
    const id = this.nextId++;
    const payload = { jsonrpc: '2.0', id, method, params };
    return new Promise((resolve, reject) => {
      if (!this.process.stdin) {
        reject(new Error('Sidecar stdin is not available'));
        return;
      }
      this.pending.set(id, resolve);
      this.process.stdin.write(JSON.stringify(payload) + '\n', (err) => {
        if (err) {
          this.pending.delete(id);
          reject(err);
        }
      });
    });
  }

  async close(): Promise<void> {
    if (this.process.stdin) {
      this.process.stdin.end();
    }
    await new Promise<void>((resolve) => {
      const timeout = setTimeout(() => {
        this.process.kill('SIGKILL');
        resolve();
      }, 5000);
      this.process.on('exit', () => {
        clearTimeout(timeout);
        resolve();
      });
      this.process.kill('SIGTERM');
    });
  }
}

function startHttpServer(
  handler: (req: http.IncomingMessage, res: http.ServerResponse) => void
): Promise<Server> {
  return new Promise((resolve, reject) => {
    const server = http.createServer(handler);
    server.listen(BRIDGE_PORT, () => resolve(server));
    server.on('error', reject);
  });
}

interface MarkdownNote {
  path: string;
  content: string;
}

function collectMarkdown(dir: string): MarkdownNote[] {
  const results: MarkdownNote[] = [];
  if (!fs.existsSync(dir)) return results;
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      results.push(...collectMarkdown(full));
    } else if (entry.name.endsWith('.md')) {
      results.push({ path: full, content: fs.readFileSync(full, 'utf-8') });
    }
  }
  return results;
}

function startLlmMockServer(): Promise<Server> {
  const summaryResponse = JSON.stringify({
    title: 'E2E Archived Article Summary',
    summary: 'This end-to-end test verifies that the AIPulse extension can submit a page to the Python sidecar, which archives the source and generated summary into an Obsidian vault.',
    key_points: [
      'The extension dispatches AIPULSE_SUBMIT_URL to the background service worker.',
      'The background worker falls back to HTTP and posts to /api/videos/extract.',
      'The sidecar receives the URL, runs the article pipeline, and writes Obsidian notes.',
    ],
    tags: ['e2e', 'obsidian', 'archive'],
  });

  const chatCompletion = JSON.stringify({
    id: 'chatcmpl-e2e',
    object: 'chat.completion',
    created: Math.floor(Date.now() / 1000),
    model: 'e2e-mock',
    choices: [
      {
        index: 0,
        message: { role: 'assistant', content: summaryResponse },
        finish_reason: 'stop',
      },
    ],
  });

  return new Promise((resolve, reject) => {
    const server = http.createServer((req, res) => {
      const url = new URL(req.url ?? '/', `http://localhost:${LLM_MOCK_PORT}`);
      if (req.method === 'POST' && url.pathname === '/chat/completions') {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(chatCompletion);
        return;
      }
      res.writeHead(404);
      res.end('not found');
    });
    server.listen(LLM_MOCK_PORT, () => resolve(server));
    server.on('error', reject);
  });
}

function startSidecarProcess(env: NodeJS.ProcessEnv): {
  process: ChildProcessWithoutNullStreams;
  client: SidecarClient;
} {
  const proc = spawn(PYTHON, ['-m', 'aipulse.desktop.sidecar'], {
    cwd: PROJECT_ROOT,
    env,
    stdio: ['pipe', 'pipe', 'pipe'],
  });
  const client = new SidecarClient(proc);
  return { process: proc, client };
}

test.describe('Obsidian archive E2E', () => {
  let articleServer: Server;
  let llmServer: Server;
  let sidecarProc: ChildProcessWithoutNullStreams;
  let sidecarClient: SidecarClient;
  let httpBridge: Server;
  let tempDir: string;
  let lastSubmitBody: Record<string, unknown> | null = null;
  let submittedTaskId: string | null = null;

  let sidecarStderr: string[] = [];

  test.beforeAll(async () => {
    tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'aipulse-e2e-'));
    const dataDir = path.join(tempDir, 'data');
    const vaultDir = path.join(tempDir, 'vault');
    fs.mkdirSync(dataDir, { recursive: true });
    fs.mkdirSync(vaultDir, { recursive: true });

    // 1. Mock LLM so the pipeline can generate a summary without a real API key.
    llmServer = await startLlmMockServer();

    // 2. Start the real Python sidecar against a temporary vault.
    const sidecarEnv = {
      ...process.env,
      DATA_DIR: dataDir,
      DOWNLOAD_DIR: path.join(dataDir, 'downloads'),
      DATABASE_URL: `sqlite+aiosqlite:///${path.join(dataDir, 'aipulse.db')}`,
      OBSIDIAN_VAULT_PATH: vaultDir,
      LLM_BASE_URL: `http://127.0.0.1:${LLM_MOCK_PORT}`,
      LLM_API_KEY: 'e2e-dummy-key',
      LLM_MODEL: 'e2e-mock',
      AUTO_CREATE_TABLES: 'true',
      all_proxy: '',
      http_proxy: '',
      https_proxy: '',
    };
    const { process: proc, client } = startSidecarProcess(sidecarEnv);
    sidecarProc = proc;
    sidecarClient = client;
    proc.stderr.on('data', (chunk: Buffer) => {
      sidecarStderr.push(chunk.toString('utf-8'));
    });

    // 3. HTTP bridge: extension can only talk to localhost:3456, so host both
    //    the article page and the /api/videos/extract endpoint on that port.
    httpBridge = await startHttpServer((req, res) => {
      const url = new URL(req.url ?? '/', `http://localhost:${BRIDGE_PORT}`);

      if (url.pathname === '/api/videos/extract' && req.method === 'POST') {
        let body = '';
        req.on('data', (chunk) => {
          body += chunk;
        });
        req.on('end', async () => {
          try {
            lastSubmitBody = JSON.parse(body) as Record<string, unknown>;
            const response = await sidecarClient.request('submit_url', lastSubmitBody);
            if (response.error) {
              res.writeHead(500, { 'Content-Type': 'application/json' });
              res.end(JSON.stringify({ error: response.error.message }));
              return;
            }
            submittedTaskId = (response.result?.task_id as string) ?? null;
            res.writeHead(200, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify(response.result));
          } catch (err) {
            res.writeHead(500, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ error: String(err) }));
          }
        });
        return;
      }

      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
      res.end(ARTICLE_HTML);
    });

    // 4. Article server shares the bridge port; this path is only used for clarity.
    articleServer = httpBridge;

    // Give the sidecar a moment to finish init_db and start reading stdin.
    await new Promise((resolve) => setTimeout(resolve, 800));
  });

  test.afterAll(async () => {
    await sidecarClient.close();
    articleServer?.closeAllConnections();
    await new Promise<void>((resolve) => articleServer?.close(() => resolve()));
    llmServer?.closeAllConnections();
    await new Promise<void>((resolve) => llmServer?.close(() => resolve()));
    fs.rmSync(tempDir, { recursive: true, force: true });
  });

  test(
    'archives a real article page through the sidecar and writes Obsidian notes',
    async () => {
      test.setTimeout(60_000);
      const userDataDir = path.join(__dirname, '../.tmp/user-data-obsidian');
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
      await warmupPage.waitForTimeout(1000);
      const serviceWorkers = context.serviceWorkers();
      expect(serviceWorkers.length, 'extension service worker should be registered').toBeGreaterThan(
        0
      );
      const serviceWorker = serviceWorkers[0];

      // Point the extension's HTTP fallback at our bridge (same port as the article page).
      await serviceWorker.evaluate(
        (port) =>
          new Promise<void>((resolve) => {
            chrome.storage.local.set({ httpBaseUrl: `http://localhost:${port}` }, () => resolve());
          }),
        BRIDGE_PORT
      );
      await warmupPage.close();

      const page = await context.newPage();
      const articleUrl = `http://localhost:${ARTICLE_PORT}/article`;
      await page.goto(articleUrl);
      await page.waitForLoadState('networkidle');
      // Wait for the content script to register the E2E bridge listener.
      await page.waitForTimeout(800);

      // Trigger the archive flow from the page.
      await page.evaluate(
        (url) => {
          window.dispatchEvent(
            new CustomEvent('AIPULSE_SUBMIT_URL', { detail: { url, mode: 'archive' } })
          );
        },
        articleUrl
      );

      // Wait for the bridge to receive the request and sidecar to return a task id.
      await expect
        .poll(() => submittedTaskId, { timeout: 15000 })
        .toMatch(/^[a-f0-9]{12}$/);

      expect(lastSubmitBody).not.toBeNull();
      expect(lastSubmitBody!.url).toBe(articleUrl);
      expect(lastSubmitBody!.mode).toBe('archive');
      expect(lastSubmitBody!.source).toBe('browser_extension');

      // Poll the sidecar until the pipeline finishes archiving.
      let completed = false;
      let taskResult: Record<string, unknown> | null = null;
      for (let i = 0; i < 40; i++) {
        const status = await sidecarClient.request('get_task_status', {
          task_id: submittedTaskId,
        });
        if (status.error) break;
        taskResult = status.result ?? null;
        const taskStatus = String(taskResult?.status ?? '');
        if (taskStatus === 'completed') {
          completed = true;
          break;
        }
        if (taskStatus === 'failed') {
          break;
        }
        await new Promise((resolve) => setTimeout(resolve, 500));
      }

      expect(completed, `pipeline should complete; last status=${JSON.stringify(taskResult)}`).toBe(
        true
      );

      // Diagnostic dump so we can see sidecar logs and vault contents on failure.
      const vaultDir = path.join(tempDir, 'vault');
      const archiveRoot = path.join(vaultDir, '工作学习', '已归档');
      const summaryRoot = path.join(vaultDir, '工作学习', 'AI', 'AI总结文档');
      const notes = collectMarkdown(vaultDir);
      test.info().attach('sidecar-stderr', {
        body: sidecarStderr.join(''),
        contentType: 'text/plain',
      });
      test.info().attach('vault-tree', {
        body: JSON.stringify({
          vaultExists: fs.existsSync(vaultDir),
          archiveRootExists: fs.existsSync(archiveRoot),
          summaryRootExists: fs.existsSync(summaryRoot),
          notePaths: notes.map((note) => path.relative(vaultDir, note.path)),
        }),
        contentType: 'application/json',
      });

      // The archiver writes source notes under 工作学习/已归档/<platform> and
      // summary notes under 工作学习/AI/AI总结文档. Discover the notes by content
      // rather than pinning the platform subdirectory: an extracted article has
      // no platform, so the source folder is "unknown".
      expect(fs.existsSync(archiveRoot), 'archive root should exist').toBe(true);
      expect(fs.existsSync(summaryRoot), 'summary root should exist').toBe(true);
      expect(notes.length, 'expected one source and one summary note').toBe(2);

      const sourceNote = notes.find(
        (note) => note.content.includes(articleUrl) && note.content.includes('## 转写')
      );
      const summaryNote = notes.find(
        (note) =>
          note.content.includes('E2E Archived Article Summary') && note.content.includes('## 要点')
      );

      expect(sourceNote, 'source note with url and transcript should exist').toBeTruthy();
      expect(summaryNote, 'summary note with title and key points should exist').toBeTruthy();
      expect(summaryNote!.content).toContain('## 摘要');

      await page.close();
      await context.close();
    }
  );
});
