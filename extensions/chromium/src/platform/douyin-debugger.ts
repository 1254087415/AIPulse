/**
 * MV3 service worker debugger hover dispatcher.
 *
 * Uses chrome.debugger to dispatch trusted Input.dispatchMouseEvent events
 * at a given screen coordinate and waits for a capture result via the
 * provided captureAttempt callback.
 *
 * Architecture:
 *  - DebuggerApi is a pure Promise-based abstraction over chrome.debugger.
 *  - dispatchTrustedHover orchestrates attach → sendCommand → captureAttempt
 *    with configurable retry semantics.
 */

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** A point on the page / screen that the debugger will hover. */
export interface HoverPoint {
  x: number;
  y: number;
}

/** Return shape of dispatchTrustedHover. */
export interface DebuggerHoverResult {
  captured: boolean;
  fallback: boolean;
}

/** Pure Promise API wrapping chrome.debugger. */
export interface DebuggerApi {
  attach(target: DebuggerTarget, version: string): Promise<void>;
  sendCommand(
    target: DebuggerTarget,
    method: string,
    params?: Record<string, unknown>
  ): Promise<unknown>;
  detach(target: DebuggerTarget): Promise<void>;
}

export interface DebuggerTarget {
  tabId: string;
}

/** Options for dispatchTrustedHover. */
export interface DispatchOptions {
  /** Injectable debugger API (for testing). */
  api: DebuggerApi;
  /**
   * Called after Input.dispatchMouseEvent is sent.
   * Receives the remaining timeout window in ms.
   * Resolves with { captured: true } on success, rejects on timeout/failure.
   */
  captureAttempt(remainingMs: number): Promise<{ captured: boolean }>;
  /** Called between retry attempts with the delay in ms (retryDelaysMs). */
  wait(delayMs: number): Promise<void>;
  /** Timeout for each capture attempt in ms. Default: 5000. */
  timeoutMs?: number;
  /** Maximum number of attach+hover+wait cycles. Default: 3. */
  maxAttempts?: number;
  /**
   * Delays between retry attempts (ms).
   * Default: [1000, 2000].
   */
  retryDelaysMs?: number[];
}

// ---------------------------------------------------------------------------
// Coordinate validation
// ---------------------------------------------------------------------------

function isValidPoint(point: HoverPoint): boolean {
  return (
    Number.isFinite(point.x) &&
    Number.isFinite(point.y) &&
    point.x >= 0 &&
    point.y >= 0
  );
}

// ---------------------------------------------------------------------------
// Debugger conflict detection
// ---------------------------------------------------------------------------

/**
 * Returns true if the error message indicates a debugger conflict
 * (another debugger is already attached to the target).
 * Matching is case-insensitive.
 */
function isDebuggerConflict(error: unknown): boolean {
  if (!(error instanceof Error)) return false;
  const msg = error.message.toLowerCase();
  return (
    msg.includes('another debugger') ||
    msg.includes('already attached') ||
    msg.includes('target is already being debugged')
  );
}

// ---------------------------------------------------------------------------
// Native timer with cancel support
// ---------------------------------------------------------------------------

/**
 * Creates a promise that resolves after `ms` milliseconds.
 * The returned `cancel` function clears the underlying timer when called.
 */
function createCancellableTimeout(
  ms: number
): { promise: Promise<void>; cancel: () => void } {
  let timerId: ReturnType<typeof setTimeout> | null = null;
  let cancelled = false;

  const promise = new Promise<void>((resolve) => {
    timerId = setTimeout(() => {
      // Only resolve if not cancelled
      if (!cancelled) {
        resolve();
      }
    }, ms);
  });

  const cancel = (): void => {
    cancelled = true;
    if (timerId !== null) {
      clearTimeout(timerId);
    }
  };

  return { promise, cancel };
}

// ---------------------------------------------------------------------------
// Main export
// ---------------------------------------------------------------------------

/**
 * Dispatch a trusted hover event at the given point using chrome.debugger.
 *
 * Retry policy:
 *  - command_error (sendCommand rejection) → immediate retry (no wait call).
 *  - capture_error (captureAttempt rejection) → wait then retry.
 *  - timeout (captureAttempt exceeds timeoutMs) → wait then retry.
 *  - attach conflict ("another debugger attached", etc.) → fallback=true, stop.
 *  - success → stop, return { captured: true, fallback: false }.
 *
 * After every successful attach, detach is always called.
 */
export async function dispatchTrustedHover(
  tabId: string,
  point: HoverPoint,
  options: DispatchOptions
): Promise<DebuggerHoverResult> {
  const {
    api,
    captureAttempt,
    wait,
    timeoutMs = 5000,
    maxAttempts = 3,
    retryDelaysMs = [1000, 2000],
  } = options;

  const target: DebuggerTarget = { tabId };

  // ---- Coordinate guard ----------------------------------------------------
  if (!isValidPoint(point)) {
    return { captured: false, fallback: true };
  }

  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    // ---- Attach -------------------------------------------------------------
    try {
      await api.attach(target, '1.3');
    } catch (attachError) {
      // Only treat as debugger conflict (fallback) if the error message matches.
      // Other attach errors (network, tab not found, etc.) should retry immediately.
      if (isDebuggerConflict(attachError)) {
        // Debugger conflict → do not retry, do not detach
        return { captured: false, fallback: true };
      }
      // Other attach errors: retry immediately without calling wait
      // (no successful attach, so no detach needed either)
      continue;
    }

    // ---- Send hover command -------------------------------------------------
    let commandError = false;
    try {
      await api.sendCommand(target, 'Input.dispatchMouseEvent', {
        type: 'mouseMoved',
        x: point.x,
        y: point.y,
        button: 'none',
        clickCount: 0,
      });
    } catch {
      commandError = true;
    }

    if (commandError) {
      // All sendCommand errors are command_error → immediate retry (no captureAttempt, no wait)
      try {
        await api.detach(target);
      } catch {
        // ignore
      }
      continue;
    }

    // ---- Wait for capture (race cancellable timeout vs captureAttempt) -------
    // Native setTimeout is used for the timeout race so it works in real time
    // in both test and production environments.
    // `wait` is ONLY used for retryDelaysMs, keeping the two concerns separate.
    let captureResult: { captured: boolean } | null = null;
    let timedOut = false;
    let captureError = false;

    const timer = createCancellableTimeout(timeoutMs);

    try {
      const raceResult = await Promise.race([
        timer.promise.then(() => ({ type: 'timeout' as const })),
        captureAttempt(timeoutMs).then(
          (r) => ({ type: 'capture' as const, result: r }),
          (e) => ({ type: 'error' as const, error: e })
        ),
      ]);

      // Cancel the timeout timer now that we've resolved
      timer.cancel();

      if (raceResult.type === 'timeout') {
        timedOut = true;
      } else if (raceResult.type === 'error') {
        // captureAttempt rejected - this is a capture_error, not a timeout
        captureError = true;
      } else {
        captureResult = raceResult.result;
      }
    } catch {
      // This catch handles unexpected errors from Promise.race itself
      timer.cancel();
      captureError = true;
    }

    // ---- Detach (always) ----------------------------------------------------
    // Detach errors do not overwrite the main result - we track success/failure
    // separately and return based on captureResult, timedOut, captureError.
    let detachError: unknown;
    try {
      await api.detach(target);
      detachError = null;
    } catch (e) {
      detachError = e;
    }

    // ---- Evaluate result ----------------------------------------------------
    if (captureResult != null && captureResult.captured) {
      // Success
      return { captured: true, fallback: false };
    }

    // Failure (timeout, capture_error, or captured=false) → retry if attempts remain
    if (attempt < maxAttempts - 1) {
      await wait(retryDelaysMs[attempt] ?? 1000);
    }
    // loop continues
  }

  // All attempts exhausted
  return { captured: false, fallback: false };
}
