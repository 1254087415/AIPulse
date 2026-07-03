import type { SubmitPayload, SubmitResult } from './types';

const NATIVE_HOST_NAME = 'com.aipulse.native_host';

interface NativeError {
  message?: unknown;
}

interface NativeResponse {
  error?: NativeError;
  result?: unknown;
}

function isNativeResponse(value: unknown): value is NativeResponse {
  return value !== null && typeof value === 'object';
}

function getNativeErrorMessage(response: NativeResponse): string | undefined {
  if (response.error && typeof response.error === 'object' && 'message' in response.error) {
    const message = response.error.message;
    return typeof message === 'string' ? message : String(message);
  }
  return undefined;
}

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

    const messageListener = (response: unknown) => {
      resolved = true;
      port.onMessage.removeListener(messageListener);
      port.onDisconnect.removeListener(disconnectListener);

      if (!isNativeResponse(response)) {
        reject(new Error('Invalid native messaging response'));
        port.disconnect();
        return;
      }

      const errorMessage = getNativeErrorMessage(response);
      if (errorMessage) {
        reject(new Error(errorMessage));
      } else {
        resolve(response.result as SubmitResult);
      }
      port.disconnect();
    };

    const disconnectListener = () => {
      port.onMessage.removeListener(messageListener);
      port.onDisconnect.removeListener(disconnectListener);
      if (!resolved) {
        reject(new Error('Native messaging disconnected'));
      }
    };

    port.onMessage.addListener(messageListener);
    port.onDisconnect.addListener(disconnectListener);

    port.postMessage(request);
  });
}
