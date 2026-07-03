import type { SubmitPayload, SubmitResult } from './types';

const NATIVE_HOST_NAME = 'com.aipulse.native_host';

export function submitViaNativeMessaging(payload: SubmitPayload): Promise<SubmitResult> {
  return new Promise((resolve, reject) => {
    let port: chrome.runtime.Port;
    try {
      port = chrome.runtime.connectNative(NATIVE_HOST_NAME);
    } catch (err) {
      reject(new Error('Native messaging host not available'));
      return;
    }

    const request = {
      jsonrpc: '2.0',
      id: 1,
      method: 'submit_url',
      params: payload,
    };

    let resolved = false;

    port.onMessage.addListener((response) => {
      resolved = true;
      if (response.error) {
        reject(new Error(response.error.message));
      } else {
        resolve(response.result as SubmitResult);
      }
      port.disconnect();
    });

    port.onDisconnect.addListener(() => {
      if (!resolved) {
        reject(new Error('Native messaging disconnected'));
      }
    });

    port.postMessage(request);
  });
}
