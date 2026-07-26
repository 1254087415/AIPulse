import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  DOUYIN_DEBUGGER_CONSENT_KEY,
  getDouyinDebuggerConsent,
  setDouyinDebuggerConsent,
} from '../../src/popup-debugger';

interface StorageMock {
  store: Record<string, unknown>;
  get: ReturnType<typeof vi.fn>;
  set: ReturnType<typeof vi.fn>;
}

function installStorage(): StorageMock {
  const store: Record<string, unknown> = {};
  const get = vi.fn((key: string, cb: (result: Record<string, unknown>) => void) => {
    cb({ [key]: store[key] });
  });
  const set = vi.fn((items: Record<string, unknown>, cb: () => void) => {
    Object.assign(store, items);
    cb();
  });
  (globalThis as { chrome?: unknown }).chrome = {
    storage: { local: { get, set } },
    runtime: { lastError: undefined },
  };
  return { store, get, set };
}

function uninstallStorage(): void {
  delete (globalThis as { chrome?: unknown }).chrome;
}

beforeEach(() => installStorage());
afterEach(() => uninstallStorage());

describe('popup-debugger consent', () => {
  it('returns false when nothing has been stored', async () => {
    const result = await getDouyinDebuggerConsent();
    expect(result).toBe(false);
  });

  it('returns true after setDouyinDebuggerConsent(true)', async () => {
    await setDouyinDebuggerConsent(true);
    const result = await getDouyinDebuggerConsent();
    expect(result).toBe(true);
  });

  it('persists value under DOUYIN_DEBUGGER_CONSENT_KEY', async () => {
    await setDouyinDebuggerConsent(true);
    const result = await getDouyinDebuggerConsent();
    expect(result).toBe(true);
  });

  it('returns false for non-boolean stored values', async () => {
    // Custom storage that returns string 'true' instead of boolean true
    (globalThis as { chrome?: unknown }).chrome = {
      storage: {
        local: {
          get: (_key: string, cb: (result: Record<string, unknown>) => void) => {
            cb({ douyinDebuggerAccepted: 'true' });
          },
          set: vi.fn(),
        },
      },
      runtime: { lastError: undefined },
    };
    const result = await getDouyinDebuggerConsent();
    expect(result).toBe(false);
  });

  it('returns false for false stored value', async () => {
    await setDouyinDebuggerConsent(false);
    const result = await getDouyinDebuggerConsent();
    expect(result).toBe(false);
  });

  it('returns undefined when chrome is not available', async () => {
    uninstallStorage();
    const result = await getDouyinDebuggerConsent();
    expect(result).toBeUndefined();
  });

  it('setDouyinDebuggerConsent is a no-op when chrome is unavailable', async () => {
    uninstallStorage();
    await expect(setDouyinDebuggerConsent(true)).resolves.toBeUndefined();
  });

  it('uses the expected storage key constant', () => {
    expect(DOUYIN_DEBUGGER_CONSENT_KEY).toBe('douyinDebuggerAccepted');
  });
});