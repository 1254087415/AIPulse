import type { SubmitPayload, SubmitResult } from './types';

const DEFAULT_HTTP_BASE = 'http://127.0.0.1:8000';
const HTTP_TIMEOUT_MS = 10000;
const STORAGE_KEY = 'httpBaseUrl';

function normalizeBaseUrl(raw: unknown): string {
  if (typeof raw !== 'string') {
    return DEFAULT_HTTP_BASE;
  }
  try {
    const parsed = new URL(raw);
    if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
      return DEFAULT_HTTP_BASE;
    }
    return parsed.origin;
  } catch {
    return DEFAULT_HTTP_BASE;
  }
}

async function resolveBaseUrl(override?: string): Promise<string> {
  if (override) {
    return normalizeBaseUrl(override);
  }

  if (typeof chrome === 'undefined' || !chrome.storage?.local) {
    return DEFAULT_HTTP_BASE;
  }

  try {
    const stored = await chrome.storage.local.get(STORAGE_KEY);
    return normalizeBaseUrl(stored[STORAGE_KEY]);
  } catch {
    return DEFAULT_HTTP_BASE;
  }
}

export async function submitViaHttp(payload: SubmitPayload, baseUrl?: string): Promise<SubmitResult> {
  const url = `${await resolveBaseUrl(baseUrl)}/api/videos/extract`;
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
