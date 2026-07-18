const CAPTURE_EVENT_NAME = 'AIPULSE_DOUYIN_SHARE_CAPTURED';

(function installDouyinShareCapture() {
  const w = window as unknown as Record<string, unknown>;
  if (w.__aipulse_douyin_capture_installed) return;
  w.__aipulse_douyin_capture_installed = true;

  function extractVideoId(target: string): string | null {
    const m = decodeURIComponent(target || '').match(/share\/(?:video|note)\/(\d+)/);
    return m ? m[1] : null;
  }

  function dispatch(videoId: string, shareUrl: string): void {
    // Use postMessage instead of CustomEvent so the isolated content script
    // can receive it. CustomEvents dispatched on window do not cross the
    // isolated/main world boundary in MV3 content scripts.
    window.postMessage(
      { type: CAPTURE_EVENT_NAME, videoId, shareUrl },
      location.origin
    );
  }

  function handleResponse(url: string, text: string): void {
    if (!url || !url.includes('/aweme/v1/web/web_shorten/')) return;
    try {
      const body = JSON.parse(text) as { code?: number; data?: unknown };
      if (
        body.code === 0 &&
        typeof body.data === 'string' &&
        body.data.startsWith('https://v.douyin.com/')
      ) {
        const u = new URL(url, location.href);
        const target = u.searchParams.get('target') || '';
        const videoId = extractVideoId(target);
        if (videoId) dispatch(videoId, body.data);
      }
    } catch {
      // Ignore malformed responses.
    }
  }

  function requestUrl(request: RequestInfo | URL): string {
    if (typeof request === 'string') return request;
    if (request instanceof URL) return request.href;
    return request.url;
  }

  const origFetch = window.fetch;
  window.fetch = async function (...args: Parameters<typeof fetch>) {
    const [request] = args;
    const url = requestUrl(request);
    const response = await origFetch.apply(this, args);
    if (url.includes('/aweme/v1/web/web_shorten/')) {
      response
        .clone()
        .text()
        .then((text) => handleResponse(url, text))
        .catch(() => {});
    }
    return response;
  };

  type OpenFn = (
    this: XMLHttpRequest,
    method: string,
    url: string | URL,
    async?: boolean,
    username?: string | null,
    password?: string | null
  ) => void;
  type SendFn = (this: XMLHttpRequest, body?: XMLHttpRequestBodyInit | Document | null) => void;

  const origOpen = XMLHttpRequest.prototype.open as OpenFn;
  const origSend = XMLHttpRequest.prototype.send as SendFn;
  let lastUrl = '';
  XMLHttpRequest.prototype.open = function (
    method: string,
    url: string | URL,
    async?: boolean,
    username?: string | null,
    password?: string | null
  ) {
    lastUrl = String(url);
    return origOpen.call(this, method, url, async, username, password);
  };
  XMLHttpRequest.prototype.send = function (body?: XMLHttpRequestBodyInit | Document | null) {
    const url = lastUrl;
    this.addEventListener('load', function () {
      if (url.includes('/aweme/v1/web/web_shorten/')) {
        handleResponse(url, (this as XMLHttpRequest).responseText);
      }
    });
    return origSend.call(this, body);
  };
})();
