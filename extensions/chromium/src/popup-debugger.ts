/**
 * Douyin auto-hover consent state.
 *
 * The first time a popup is opened on a Douyin page, the user is shown an
 * explanation that hovering the share button uses `chrome.debugger`, which
 * makes Chrome display a yellow "Debugger is attached" banner. After the
 * user confirms, the preference is persisted in `chrome.storage.local` so
 * that subsequent visits skip the prompt. Until the user confirms, content
 * scripts must continue to use the long-link fallback.
 */

export const DOUYIN_DEBUGGER_CONSENT_KEY = 'douyinDebuggerAccepted';

function getStorage(): chrome.storage.LocalStorageArea | undefined {
  if (typeof chrome === 'undefined') return undefined;
  return chrome.storage?.local;
}

export async function getDouyinDebuggerConsent(): Promise<boolean | undefined> {
  const storage = getStorage();
  if (!storage) return undefined;
  return new Promise((resolve) => {
    try {
      storage.get(DOUYIN_DEBUGGER_CONSENT_KEY, (result) => {
        void chrome.runtime.lastError;
        const raw = result?.[DOUYIN_DEBUGGER_CONSENT_KEY];
        resolve(raw === true);
      });
    } catch {
      resolve(undefined);
    }
  });
}

export async function setDouyinDebuggerConsent(accepted: boolean): Promise<void> {
  const storage = getStorage();
  if (!storage) return;
  await new Promise<void>((resolve) => {
    try {
      storage.set({ [DOUYIN_DEBUGGER_CONSENT_KEY]: accepted }, () => {
        void chrome.runtime.lastError;
        resolve();
      });
    } catch {
      resolve();
    }
  });
}