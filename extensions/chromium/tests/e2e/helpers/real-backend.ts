/**
 * 真实后端联调桥（禁止 mock 后端）
 *
 * 用户硬性要求：E2E 提交链路必须打真实 AIPulse 后端，不允许用假 HTTP server
 * 冒充后端返回伪造的 task_id。本模块启动真实的 Python sidecar
 * （aipulse.desktop.sidecar，stdio JSON-RPC），并提供一个 HTTP 桥：
 * 扩展的 HTTP fallback（POST /api/videos/extract）→ 桥 → 真实 sidecar
 * submit_url → 真实 task_id。桥只负责传输协议转换，所有后端逻辑（任务入库、
 * pipeline 调度）均由真实 sidecar 执行。
 */
import { spawn, type ChildProcessWithoutNullStreams } from 'child_process';
import fs from 'fs';
import http, { type Server } from 'http';
import os from 'os';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
export const PROJECT_ROOT = path.resolve(__dirname, '../../../../..');

/**
 * Resolve the Python interpreter used to launch the sidecar.
 * Prefer the project-local venv (`.venv/bin/python`) when it exists; otherwise
 * fall back to the active `python3` / `python` on PATH. The fallback is what
 * the test fleet actually uses in the AIStudio dev environment, where deps
 * live in /opt/anaconda3 and no per-project venv is created.
 */
function resolvePython(projectRoot: string): string {
  const venvPython = path.join(projectRoot, '.venv', 'bin', 'python');
  if (fs.existsSync(venvPython)) return venvPython;
  // Prefer `python3` (always present on macOS/Linux); fall back to `python`.
  for (const candidate of ['python3', 'python']) {
    const resolved = spawnSync(candidate, ['--version']);
    if (resolved.status === 0) return candidate;
  }
  return 'python3';
}

function spawnSync(cmd: string, args: string[]): { status: number | null } {
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    return require('child_process').spawnSync(cmd, args, { stdio: 'ignore' });
  } catch {
    return { status: null };
  }
}

export const PYTHON = resolvePython(PROJECT_ROOT);

/**
 * Resolve the aipulse package source root that should be added to PYTHONPATH
 * before invoking `python -m aipulse.desktop.sidecar`. The repo currently
 * ships the package under `src/aipulse`; older layouts used `src-python/aipulse`.
 * Pick whichever exists.
 */
function resolvePackageRoot(projectRoot: string): string {
  for (const candidate of ['src-python', 'src']) {
    const abs = path.join(projectRoot, candidate);
    if (fs.existsSync(path.join(abs, 'aipulse', 'desktop', 'sidecar.py'))) {
      return abs;
    }
  }
  // Last resort: assume `src`.
  return path.join(projectRoot, 'src');
}

export const PACKAGE_ROOT = resolvePackageRoot(PROJECT_ROOT);

interface SidecarResponse {
  jsonrpc: '2.0';
  id?: number;
  result?: Record<string, unknown>;
  error?: { code: number; message: string };
}

export class SidecarClient {
  private process: ChildProcessWithoutNullStreams;
  private pending = new Map<number, (value: SidecarResponse) => void>();
  private nextId = 1;
  private buffer = '';

  constructor(process: ChildProcessWithoutNullStreams) {
    this.process = process;
    process.stdout.on('data', (chunk: Buffer) => {
      this.buffer += chunk.toString('utf-8');
      let lineEnd: number;
      while ((lineEnd = this.buffer.indexOf('\n')) >= 0) {
        const line = this.buffer.slice(0, lineEnd).trim();
        this.buffer = this.buffer.slice(lineEnd + 1);
        if (line) this.handleLine(line);
      }
    });
  }

  private handleLine(line: string): void {
    try {
      const parsed = JSON.parse(line) as SidecarResponse;
      if (parsed.id !== undefined) {
        const resolver = this.pending.get(parsed.id);
        if (resolver) {
          this.pending.delete(parsed.id);
          resolver(parsed);
        }
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

export interface RealBackend {
  server: Server;
  client: SidecarClient;
  tempDir: string;
  stderr: string[];
  getLastSubmitBody: () => Record<string, unknown> | null;
  getSubmittedTaskId: () => string | null;
  getSubmissionCount: () => number;
  close: () => Promise<void>;
}

/**
 * 启动真实 sidecar + HTTP 桥。
 *
 * @param port 桥监听端口。扩展 host_permissions 仅含 localhost:3456；其他端口
 * 需要 CORS 响应头才能通过 Chromium 的跨域预检。
 * @param fallbackHandler 非 /api/videos/extract 请求的处理器（如托管测试
 * fixture 页面）；未提供时返回 404。
 */
export async function startRealBackend(
  port: number,
  fallbackHandler?: (req: http.IncomingMessage, res: http.ServerResponse) => void
): Promise<RealBackend> {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'aipulse-e2e-real-'));
  const dataDir = path.join(tempDir, 'data');
  fs.mkdirSync(dataDir, { recursive: true });

  const sidecarEnv = {
    ...process.env,
    DATA_DIR: dataDir,
    DOWNLOAD_DIR: path.join(dataDir, 'downloads'),
    DATABASE_URL: `sqlite+aiosqlite:///${path.join(dataDir, 'aipulse.db')}`,
    AUTO_CREATE_TABLES: 'true',
    all_proxy: '',
    http_proxy: '',
    https_proxy: '',
  };
  const proc = spawn(PYTHON, ['-m', 'aipulse.desktop.sidecar'], {
    cwd: PROJECT_ROOT,
    env: { ...sidecarEnv, PYTHONPATH: PACKAGE_ROOT },
    stdio: ['pipe', 'pipe', 'pipe'],
  });
  const client = new SidecarClient(proc);
  const stderr: string[] = [];
  proc.stderr.on('data', (chunk: Buffer) => {
    stderr.push(chunk.toString('utf-8'));
  });

  let lastSubmitBody: Record<string, unknown> | null = null;
  let submittedTaskId: string | null = null;
  let submissionCount = 0;

  const corsHeaders = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Access-Control-Max-Age': '600',
  };

  const server = http.createServer((req, res) => {
    const url = new URL(req.url ?? '/', `http://localhost:${port}`);

    if (req.method === 'OPTIONS') {
      res.writeHead(204, corsHeaders);
      res.end();
      return;
    }

    if (url.pathname === '/api/videos/extract' && req.method === 'POST') {
      let body = '';
      req.on('data', (chunk) => {
        body += chunk;
      });
      req.on('end', async () => {
        try {
          lastSubmitBody = JSON.parse(body) as Record<string, unknown>;
          const response = await client.request('submit_url', lastSubmitBody);
          if (response.error) {
            console.log(`[real-backend] submit_url error for ${lastSubmitBody.url}: ${response.error.message}`);
            res.writeHead(500, { 'Content-Type': 'application/json', ...corsHeaders });
            res.end(JSON.stringify({ error: response.error.message }));
            return;
          }
          submittedTaskId = (response.result?.task_id as string) ?? null;
          submissionCount += 1;
          console.log(`[real-backend] submitted ${lastSubmitBody.url} -> task ${submittedTaskId}`);
          res.writeHead(200, { 'Content-Type': 'application/json', ...corsHeaders });
          res.end(JSON.stringify(response.result));
        } catch (err) {
          res.writeHead(500, { 'Content-Type': 'application/json', ...corsHeaders });
          res.end(JSON.stringify({ error: String(err) }));
        }
      });
      return;
    }

    if (fallbackHandler) {
      fallbackHandler(req, res);
      return;
    }
    res.writeHead(404, corsHeaders);
    res.end('not found');
  });

  await new Promise<void>((resolve, reject) => {
    server.listen(port, () => resolve());
    server.on('error', reject);
  });

  // Give the sidecar a moment to finish init_db and start reading stdin.
  await new Promise((resolve) => setTimeout(resolve, 800));

  return {
    server,
    client,
    tempDir,
    stderr,
    getLastSubmitBody: () => lastSubmitBody,
    getSubmittedTaskId: () => submittedTaskId,
    getSubmissionCount: () => submissionCount,
    close: async () => {
      await client.close();
      server.closeAllConnections();
      await new Promise<void>((resolve) => server.close(() => resolve()));
      fs.rmSync(tempDir, { recursive: true, force: true });
    },
  };
}
