import type { SubmitPayload, SubmitResult } from './types';

const DEFAULT_HTTP_BASE = 'http://127.0.0.1:8000';
const HTTP_TIMEOUT_MS = 10000;

export async function submitViaHttp(payload: SubmitPayload, baseUrl?: string): Promise<SubmitResult> {
  const url = `${baseUrl || DEFAULT_HTTP_BASE}/api/videos/extract`;
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), HTTP_TIMEOUT_MS);

  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal: controller.signal,
    });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    return response.json() as Promise<SubmitResult>;
  } finally {
    clearTimeout(timeoutId);
  }
}
