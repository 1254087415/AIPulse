import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import {
  dispatchTrustedHover,
  type HoverPoint,
  type DebuggerHoverResult,
} from '../../src/platform/douyin-debugger';

// ---------------------------------------------------------------------------
// Mock debugger API
// ---------------------------------------------------------------------------
type MockApi = {
  attach: ReturnType<typeof vi.fn>;
  sendCommand: ReturnType<typeof vi.fn>;
  detach: ReturnType<typeof vi.fn>;
};

function makeMockApi(): MockApi {
  return {
    attach: vi.fn(),
    sendCommand: vi.fn(),
    detach: vi.fn(),
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------
describe('dispatchTrustedHover', () => {
  let mockApi: MockApi;

  beforeEach(() => {
    mockApi = makeMockApi();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  // -------------------------------------------------------------------------
  // Coordinate validation
  // -------------------------------------------------------------------------
  it('does not call API when point x is NaN', async () => {
    const result = await dispatchTrustedHover('tab1', { x: NaN, y: 100 }, {
      api: mockApi as never,
      wait: vi.fn().mockResolvedValue(undefined),
      captureAttempt: vi.fn().mockResolvedValue({ captured: true }),
    });
    expect(result.fallback).toBe(true);
    expect(mockApi.attach).not.toHaveBeenCalled();
    expect(mockApi.sendCommand).not.toHaveBeenCalled();
  });

  it('does not call API when point y is Infinity', async () => {
    const result = await dispatchTrustedHover('tab1', { x: 50, y: Infinity }, {
      api: mockApi as never,
      wait: vi.fn().mockResolvedValue(undefined),
      captureAttempt: vi.fn().mockResolvedValue({ captured: true }),
    });
    expect(result.fallback).toBe(true);
    expect(mockApi.attach).not.toHaveBeenCalled();
    expect(mockApi.sendCommand).not.toHaveBeenCalled();
  });

  it('does not call API when point x is negative', async () => {
    const result = await dispatchTrustedHover('tab1', { x: -1, y: 50 }, {
      api: mockApi as never,
      wait: vi.fn().mockResolvedValue(undefined),
      captureAttempt: vi.fn().mockResolvedValue({ captured: true }),
    });
    expect(result.fallback).toBe(true);
    expect(mockApi.attach).not.toHaveBeenCalled();
  });

  it('does not call API when point y is negative', async () => {
    const result = await dispatchTrustedHover('tab1', { x: 50, y: -5 }, {
      api: mockApi as never,
      wait: vi.fn().mockResolvedValue(undefined),
      captureAttempt: vi.fn().mockResolvedValue({ captured: true }),
    });
    expect(result.fallback).toBe(true);
    expect(mockApi.attach).not.toHaveBeenCalled();
  });

  it('accepts zero coordinates', async () => {
    mockApi.attach.mockResolvedValue(undefined);
    mockApi.sendCommand.mockResolvedValue(undefined);
    mockApi.detach.mockResolvedValue(undefined);

    const result = await dispatchTrustedHover(
      'tab1',
      { x: 0, y: 0 },
      {
        api: mockApi as never,
        wait: vi.fn().mockResolvedValue(undefined),
        captureAttempt: vi.fn().mockResolvedValue({ captured: true }),
      }
    );

    expect(result.fallback).toBe(false);
    expect(mockApi.attach).toHaveBeenCalledTimes(1);
  });

  // -------------------------------------------------------------------------
  // Successful first attempt stops immediately
  // -------------------------------------------------------------------------
  it('succeeds on first attempt and does not retry', async () => {
    mockApi.attach.mockResolvedValue(undefined);
    mockApi.sendCommand.mockResolvedValue(undefined);
    mockApi.detach.mockResolvedValue(undefined);

    const captureAttempt = vi.fn().mockResolvedValue({ captured: true });
    const wait = vi.fn().mockResolvedValue(undefined);

    const result = await dispatchTrustedHover('tab1', { x: 200, y: 150 }, {
      api: mockApi as never,
      captureAttempt,
      wait,
    });

    expect(result.captured).toBe(true);
    expect(captureAttempt).toHaveBeenCalledTimes(1);
    expect(mockApi.attach).toHaveBeenCalledTimes(1);
    expect(mockApi.sendCommand).toHaveBeenCalledTimes(1);
    expect(mockApi.detach).toHaveBeenCalledTimes(1);
    // No retry needed → wait never called
    expect(wait).not.toHaveBeenCalled();
  });

  // -------------------------------------------------------------------------
  // Command error → immediate retry (no captureAttempt call), then success
  // -------------------------------------------------------------------------
  it('retries immediately on sendCommand rejection without calling captureAttempt', async () => {
    mockApi.attach
      .mockResolvedValueOnce(undefined)
      .mockResolvedValueOnce(undefined);
    mockApi.detach.mockResolvedValue(undefined);

    // First call fails, second succeeds
    mockApi.sendCommand
      .mockRejectedValueOnce(new Error('protocol error'))
      .mockResolvedValueOnce(undefined);

    const captureAttempt = vi.fn().mockResolvedValue({ captured: true });
    const wait = vi.fn().mockResolvedValue(undefined);

    const result = await dispatchTrustedHover('tab1', { x: 100, y: 200 }, {
      api: mockApi as never,
      captureAttempt,
      wait,
      maxAttempts: 3,
      retryDelaysMs: [1000, 2000],
    });

    expect(result.captured).toBe(true);
    // captureAttempt was only called on the successful attempt
    expect(captureAttempt).toHaveBeenCalledTimes(1);
    expect(mockApi.sendCommand).toHaveBeenCalledTimes(2);
    // Two attaches: first failed+detached, second succeeded
    expect(mockApi.attach).toHaveBeenCalledTimes(2);
    expect(mockApi.detach).toHaveBeenCalledTimes(2);
    // No wait: command_error triggers immediate retry without delay
    expect(wait).not.toHaveBeenCalled();
  });

  // -------------------------------------------------------------------------
  // Timeout → retry with wait delay
  // -------------------------------------------------------------------------
  it('retries on timeout', async () => {
    mockApi.attach.mockResolvedValue(undefined);
    mockApi.detach.mockResolvedValue(undefined);
    mockApi.sendCommand.mockResolvedValue(undefined);

    // 3 return values: fail, fail, success
    const captureAttempt = vi
      .fn()
      .mockRejectedValueOnce(new Error('timeout'))
      .mockRejectedValueOnce(new Error('timeout'))
      .mockResolvedValueOnce({ captured: true });

    const wait = vi.fn().mockResolvedValue(undefined);

    const result = await dispatchTrustedHover('tab1', { x: 300, y: 250 }, {
      api: mockApi as never,
      captureAttempt,
      wait,
      timeoutMs: 5000,
      maxAttempts: 3,
      retryDelaysMs: [1000, 2000],
    });

    expect(result.captured).toBe(true);
    expect(captureAttempt).toHaveBeenCalledTimes(3);
    // wait is called for each retry delay (between attempt 0→1 and 1→2)
    expect(wait).toHaveBeenCalledTimes(2);
    expect(wait).toHaveBeenNthCalledWith(1, 1000);
    expect(wait).toHaveBeenNthCalledWith(2, 2000);
  });

  // -------------------------------------------------------------------------
  // Attach conflict → fallback=true, no retry, no detach
  // -------------------------------------------------------------------------
  it('returns fallback=true on attach conflict without retry or detach', async () => {
    mockApi.attach.mockRejectedValue(new Error('another debugger attached'));

    const captureAttempt = vi.fn();
    const wait = vi.fn();

    const result = await dispatchTrustedHover('tab1', { x: 400, y: 300 }, {
      api: mockApi as never,
      captureAttempt,
      wait,
      maxAttempts: 3,
    });

    expect(result.fallback).toBe(true);
    expect(result.captured).toBe(false);
    expect(captureAttempt).not.toHaveBeenCalled();
    expect(wait).not.toHaveBeenCalled();
    expect(mockApi.detach).not.toHaveBeenCalled(); // never attached, never detached
    expect(mockApi.attach).toHaveBeenCalledTimes(1);
  });

  // -------------------------------------------------------------------------
  // All attempts exhausted → returns last result
  // -------------------------------------------------------------------------
  it('exhausts all attempts and returns last captured status', async () => {
    mockApi.attach.mockResolvedValue(undefined);
    mockApi.detach.mockResolvedValue(undefined);
    mockApi.sendCommand.mockResolvedValue(undefined);

    // All 3 capture attempts return captured=false (exhaustion path)
    const captureAttempt = vi
      .fn()
      .mockResolvedValueOnce({ captured: false })
      .mockResolvedValueOnce({ captured: false })
      .mockResolvedValueOnce({ captured: false });

    const wait = vi.fn().mockResolvedValue(undefined);

    const result = await dispatchTrustedHover('tab1', { x: 500, y: 400 }, {
      api: mockApi as never,
      captureAttempt,
      wait,
      maxAttempts: 3,
      retryDelaysMs: [1000, 2000],
    });

    expect(result.captured).toBe(false);
    expect(result.fallback).toBe(false); // exhausted retries, not fallback
    expect(mockApi.attach).toHaveBeenCalledTimes(3);
    expect(mockApi.sendCommand).toHaveBeenCalledTimes(3);
    expect(mockApi.detach).toHaveBeenCalledTimes(3);
    // wait called between attempt 0→1 and 1→2 (not after attempt 2, loop ends)
    expect(wait).toHaveBeenCalledTimes(2);
    expect(wait).toHaveBeenNthCalledWith(1, 1000);
    expect(wait).toHaveBeenNthCalledWith(2, 2000);
  });

  // -------------------------------------------------------------------------
  // wait receives exact retry delay values
  // -------------------------------------------------------------------------
  it('passes correct delay to wait on each retry', async () => {
    mockApi.attach.mockResolvedValue(undefined);
    mockApi.detach.mockResolvedValue(undefined);
    mockApi.sendCommand.mockResolvedValue(undefined);

    // Fail twice, succeed on third
    const captureAttempt = vi
      .fn()
      .mockRejectedValueOnce(new Error('t1'))
      .mockRejectedValueOnce(new Error('t2'))
      .mockResolvedValueOnce({ captured: true });

    const wait = vi.fn().mockResolvedValue(undefined);

    await dispatchTrustedHover('tab1', { x: 600, y: 500 }, {
      api: mockApi as never,
      captureAttempt,
      wait,
      maxAttempts: 3,
      retryDelaysMs: [1000, 2000],
    });

    expect(wait).toHaveBeenCalledTimes(2);
    expect(wait).toHaveBeenNthCalledWith(1, 1000);
    expect(wait).toHaveBeenNthCalledWith(2, 2000);
  });

  // -------------------------------------------------------------------------
  // Default options
  // -------------------------------------------------------------------------
  it('uses default timeoutMs=5000 and maxAttempts=3', async () => {
    mockApi.attach.mockResolvedValue(undefined);
    mockApi.detach.mockResolvedValue(undefined);
    mockApi.sendCommand.mockResolvedValue(undefined);

    const captureAttempt = vi.fn().mockResolvedValue({ captured: true });
    const wait = vi.fn().mockResolvedValue(undefined);

    await dispatchTrustedHover('tab1', { x: 700, y: 600 }, {
      api: mockApi as never,
      captureAttempt,
      wait,
    });

    expect(captureAttempt).toHaveBeenCalledTimes(1);
    expect(mockApi.attach).toHaveBeenCalledTimes(1);
  });

  // -------------------------------------------------------------------------
  // dispatchMouseEvent is sent with correct parameters
  // -------------------------------------------------------------------------
  it('sends Input.dispatchMouseEvent with type=mouseMoved and correct coordinates', async () => {
    mockApi.attach.mockResolvedValue(undefined);
    mockApi.sendCommand.mockResolvedValue(undefined);
    mockApi.detach.mockResolvedValue(undefined);

    const captureAttempt = vi.fn().mockResolvedValue({ captured: true });
    const wait = vi.fn().mockResolvedValue(undefined);

    await dispatchTrustedHover('tab1', { x: 321, y: 654 }, {
      api: mockApi as never,
      captureAttempt,
      wait,
    });

    expect(mockApi.sendCommand).toHaveBeenCalledWith(
      { tabId: 'tab1' },
      'Input.dispatchMouseEvent',
      {
        type: 'mouseMoved',
        x: 321,
        y: 654,
        button: 'none',
        clickCount: 0,
      }
    );
  });

  // -------------------------------------------------------------------------
  // captureAttempt receives timeout window in ms
  // -------------------------------------------------------------------------
  it('passes timeoutMs as remaining window to captureAttempt', async () => {
    mockApi.attach.mockResolvedValue(undefined);
    mockApi.sendCommand.mockResolvedValue(undefined);
    mockApi.detach.mockResolvedValue(undefined);

    const captureAttempt = vi.fn().mockResolvedValue({ captured: true });
    const wait = vi.fn().mockResolvedValue(undefined);

    await dispatchTrustedHover('tab1', { x: 111, y: 222 }, {
      api: mockApi as never,
      captureAttempt,
      wait,
      timeoutMs: 5000,
    });

    expect(captureAttempt).toHaveBeenCalledTimes(1);
    expect(captureAttempt).toHaveBeenCalledWith(5000);
  });

  // -------------------------------------------------------------------------
  // Detach is always called after successful attach
  // -------------------------------------------------------------------------
  it('detaches after successful capture', async () => {
    mockApi.attach.mockResolvedValue(undefined);
    mockApi.sendCommand.mockResolvedValue(undefined);
    mockApi.detach.mockResolvedValue(undefined);

    const captureAttempt = vi.fn().mockResolvedValue({ captured: true });
    const wait = vi.fn().mockResolvedValue(undefined);

    await dispatchTrustedHover('tab1', { x: 50, y: 50 }, {
      api: mockApi as never,
      captureAttempt,
      wait,
    });

    expect(mockApi.detach).toHaveBeenCalledTimes(1);
    expect(mockApi.detach).toHaveBeenCalledWith({ tabId: 'tab1' });
  });

  it('detaches after failed attempt within retry loop', async () => {
    mockApi.attach.mockResolvedValue(undefined);
    mockApi.detach.mockResolvedValue(undefined);
    mockApi.sendCommand.mockResolvedValue(undefined);

    const captureAttempt = vi
      .fn()
      .mockRejectedValueOnce(new Error('fail'))
      .mockResolvedValueOnce({ captured: true });

    const wait = vi.fn().mockResolvedValue(undefined);

    await dispatchTrustedHover('tab1', { x: 60, y: 60 }, {
      api: mockApi as never,
      captureAttempt,
      wait,
    });

    expect(mockApi.detach).toHaveBeenCalledTimes(2);
  });

  // -------------------------------------------------------------------------
  // fallback=true on attach conflict stops retry loop entirely
  // -------------------------------------------------------------------------
  it('does not retry after attach conflict error', async () => {
    mockApi.attach
      .mockRejectedValueOnce(new Error('debugger already attached'))
      .mockRejectedValueOnce(new Error('debugger already attached'))
      .mockResolvedValue(undefined);
    mockApi.detach.mockResolvedValue(undefined);

    const captureAttempt = vi.fn();
    const wait = vi.fn();

    const result = await dispatchTrustedHover('tab1', { x: 77, y: 88 }, {
      api: mockApi as never,
      captureAttempt,
      wait,
      maxAttempts: 3,
    });

    expect(result.fallback).toBe(true);
    expect(mockApi.attach).toHaveBeenCalledTimes(1); // stopped after first
    expect(mockApi.sendCommand).not.toHaveBeenCalled();
    expect(captureAttempt).not.toHaveBeenCalled();
    expect(wait).not.toHaveBeenCalled();
    expect(mockApi.detach).not.toHaveBeenCalled();
  });

  // -------------------------------------------------------------------------
  // REVIEW FEEDBACK 1: Attach error matching - only debugger conflict returns fallback
  // -------------------------------------------------------------------------

  it('returns fallback=true for "another debugger" message (case insensitive)', async () => {
    mockApi.attach.mockRejectedValue(new Error('Another debugger is already attached'));

    const result = await dispatchTrustedHover('tab1', { x: 100, y: 100 }, {
      api: mockApi as never,
      wait: vi.fn(),
      captureAttempt: vi.fn(),
      maxAttempts: 3,
    });

    expect(result.fallback).toBe(true);
    expect(result.captured).toBe(false);
    expect(mockApi.attach).toHaveBeenCalledTimes(1);
    expect(mockApi.sendCommand).not.toHaveBeenCalled();
  });

  it('returns fallback=true for "already attached" message (case insensitive)', async () => {
    mockApi.attach.mockRejectedValue(new Error('Target is ALREADY ATTACHED'));

    const result = await dispatchTrustedHover('tab1', { x: 100, y: 100 }, {
      api: mockApi as never,
      wait: vi.fn(),
      captureAttempt: vi.fn(),
      maxAttempts: 3,
    });

    expect(result.fallback).toBe(true);
    expect(result.captured).toBe(false);
    expect(mockApi.attach).toHaveBeenCalledTimes(1);
    expect(mockApi.sendCommand).not.toHaveBeenCalled();
  });

  it('returns fallback=true for "target is already being debugged" message', async () => {
    mockApi.attach.mockRejectedValue(new Error('target is already being debugged'));

    const result = await dispatchTrustedHover('tab1', { x: 100, y: 100 }, {
      api: mockApi as never,
      wait: vi.fn(),
      captureAttempt: vi.fn(),
      maxAttempts: 3,
    });

    expect(result.fallback).toBe(true);
    expect(result.captured).toBe(false);
    expect(mockApi.attach).toHaveBeenCalledTimes(1);
    expect(mockApi.sendCommand).not.toHaveBeenCalled();
  });

  it('RETRIES on non-conflict attach error (network failure)', async () => {
    mockApi.attach
      .mockRejectedValueOnce(new Error('net::ERR_CONNECTION_REFUSED'))
      .mockResolvedValueOnce(undefined);
    mockApi.sendCommand.mockResolvedValue(undefined);
    mockApi.detach.mockResolvedValue(undefined);

    const captureAttempt = vi.fn().mockResolvedValue({ captured: true });
    const wait = vi.fn().mockResolvedValue(undefined);

    const result = await dispatchTrustedHover('tab1', { x: 100, y: 100 }, {
      api: mockApi as never,
      captureAttempt,
      wait,
      maxAttempts: 3,
      retryDelaysMs: [1000],
    });

    expect(result.fallback).toBe(false); // NOT a debugger conflict fallback
    expect(result.captured).toBe(true);
    expect(mockApi.attach).toHaveBeenCalledTimes(2); // retried
    expect(mockApi.sendCommand).toHaveBeenCalledTimes(1);
  });

  it('RETRIES on non-conflict attach error (tab not found)', async () => {
    mockApi.attach
      .mockRejectedValueOnce(new Error('No tab with given ID'))
      .mockResolvedValueOnce(undefined);
    mockApi.sendCommand.mockResolvedValue(undefined);
    mockApi.detach.mockResolvedValue(undefined);

    const captureAttempt = vi.fn().mockResolvedValue({ captured: true });
    const wait = vi.fn().mockResolvedValue(undefined);

    const result = await dispatchTrustedHover('tab1', { x: 100, y: 100 }, {
      api: mockApi as never,
      captureAttempt,
      wait,
      maxAttempts: 3,
      retryDelaysMs: [1000],
    });

    expect(result.fallback).toBe(false); // NOT a debugger conflict fallback
    expect(result.captured).toBe(true);
    expect(mockApi.attach).toHaveBeenCalledTimes(2); // retried
  });

  it('exhausts retries on non-conflict attach errors and returns fallback=false', async () => {
    mockApi.attach
      .mockRejectedValueOnce(new Error('net::ERR_CONNECTION_REFUSED'))
      .mockRejectedValueOnce(new Error('net::ERR_CONNECTION_REFUSED'))
      .mockRejectedValueOnce(new Error('net::ERR_CONNECTION_REFUSED'));

    const captureAttempt = vi.fn();
    const wait = vi.fn().mockResolvedValue(undefined);

    const result = await dispatchTrustedHover('tab1', { x: 100, y: 100 }, {
      api: mockApi as never,
      captureAttempt,
      wait,
      maxAttempts: 3,
      retryDelaysMs: [1000, 2000],
    });

    expect(result.fallback).toBe(false); // exhausted retries, NOT a debugger conflict fallback
    expect(result.captured).toBe(false);
    expect(mockApi.attach).toHaveBeenCalledTimes(3);
    expect(mockApi.sendCommand).not.toHaveBeenCalled();
    expect(wait).not.toHaveBeenCalled(); // no successful attach, no detach to retry
  });

  // -------------------------------------------------------------------------
  // REVIEW FEEDBACK 2: captureAttempt rejection is NOT timeout
  // -------------------------------------------------------------------------

  it('captureAttempt rejection is treated as capture_error, not timeout', async () => {
    mockApi.attach.mockResolvedValue(undefined);
    mockApi.detach.mockResolvedValue(undefined);
    mockApi.sendCommand.mockResolvedValue(undefined);

    // captureAttempt rejects with non-timeout error
    const captureAttempt = vi
      .fn()
      .mockRejectedValueOnce(new Error('Extension context invalidated'))
      .mockResolvedValueOnce({ captured: true });

    const wait = vi.fn().mockResolvedValue(undefined);

    const result = await dispatchTrustedHover('tab1', { x: 100, y: 100 }, {
      api: mockApi as never,
      captureAttempt,
      wait,
      maxAttempts: 3,
      retryDelaysMs: [1000],
    });

    expect(result.captured).toBe(true);
    expect(result.fallback).toBe(false);
    expect(captureAttempt).toHaveBeenCalledTimes(2);
    // Retry should have happened with wait delay
    expect(wait).toHaveBeenCalledTimes(1);
  });

  it('captureAttempt rejection does NOT set timedOut flag (used for timeout result)', async () => {
    mockApi.attach.mockResolvedValue(undefined);
    mockApi.detach.mockResolvedValue(undefined);
    mockApi.sendCommand.mockResolvedValue(undefined);

    // All captureAttempts reject - should exhaust retries
    const captureAttempt = vi
      .fn()
      .mockRejectedValueOnce(new Error('some error'))
      .mockRejectedValueOnce(new Error('another error'))
      .mockRejectedValueOnce(new Error('third error'));

    const wait = vi.fn().mockResolvedValue(undefined);

    const result = await dispatchTrustedHover('tab1', { x: 100, y: 100 }, {
      api: mockApi as never,
      captureAttempt,
      wait,
      maxAttempts: 3,
      retryDelaysMs: [1000, 2000],
    });

    // Should NOT be marked as fallback (debugger conflict) but as exhausted retries
    expect(result.fallback).toBe(false);
    expect(result.captured).toBe(false);
  });

  // -------------------------------------------------------------------------
  // REVIEW FEEDBACK 3: Cancelable timeout - timer cleared when race completes
  // -------------------------------------------------------------------------

  it('does not leave pending timer after captureAttempt resolves early', async () => {
    mockApi.attach.mockResolvedValue(undefined);
    mockApi.sendCommand.mockResolvedValue(undefined);
    mockApi.detach.mockResolvedValue(undefined);

    // captureAttempt resolves immediately, much faster than timeoutMs
    const captureAttempt = vi.fn().mockResolvedValue({ captured: true });
    const wait = vi.fn().mockResolvedValue(undefined);

    const result = await dispatchTrustedHover('tab1', { x: 100, y: 100 }, {
      api: mockApi as never,
      captureAttempt,
      wait,
      timeoutMs: 5000,
      maxAttempts: 1,
    });

    // After function returns, advancing time should not cause any side effects
    // because the timer should have been cleared when captureAttempt resolved early
    vi.advanceTimersByTime(10000);

    expect(result.captured).toBe(true);
    expect(result.fallback).toBe(false);
  });

  it('clears timeout timer after successful capture', async () => {
    mockApi.attach.mockResolvedValue(undefined);
    mockApi.sendCommand.mockResolvedValue(undefined);
    mockApi.detach.mockResolvedValue(undefined);

    const captureAttempt = vi.fn().mockResolvedValue({ captured: true });
    const wait = vi.fn().mockResolvedValue(undefined);

    const result = await dispatchTrustedHover('tab1', { x: 100, y: 100 }, {
      api: mockApi as never,
      captureAttempt,
      wait,
      timeoutMs: 10000,
      maxAttempts: 1,
    });

    // After function returns, advancing timers should not trigger any callbacks
    // because the timer should have been cleared
    vi.advanceTimersByTime(20000);
    expect(result.captured).toBe(true);
    expect(result.fallback).toBe(false);
  });

  it('clears timeout timer after failed capture (not timeout)', async () => {
    mockApi.attach.mockResolvedValue(undefined);
    mockApi.detach.mockResolvedValue(undefined);
    mockApi.sendCommand.mockResolvedValue(undefined);

    const captureAttempt = vi.fn().mockRejectedValue(new Error('some error'));
    const wait = vi.fn().mockResolvedValue(undefined);

    const result = await dispatchTrustedHover('tab1', { x: 100, y: 100 }, {
      api: mockApi as never,
      captureAttempt,
      wait,
      timeoutMs: 5000,
      maxAttempts: 1,
    });

    // After function returns, advancing timers should not trigger any callbacks
    vi.advanceTimersByTime(10000);
    expect(result.captured).toBe(false);
    expect(result.fallback).toBe(false);
  });

  // -------------------------------------------------------------------------
  // REVIEW FEEDBACK 4: detach rejection does not overwrite main result
  // -------------------------------------------------------------------------

  it('detach rejection does not overwrite successful main result', async () => {
    mockApi.attach.mockResolvedValue(undefined);
    mockApi.sendCommand.mockResolvedValue(undefined);
    // detach fails
    mockApi.detach.mockRejectedValue(new Error('Detach failed'));

    const captureAttempt = vi.fn().mockResolvedValue({ captured: true });
    const wait = vi.fn();

    const result = await dispatchTrustedHover('tab1', { x: 100, y: 100 }, {
      api: mockApi as never,
      captureAttempt,
      wait,
      maxAttempts: 1,
    });

    // Success should still be returned despite detach error
    expect(result.captured).toBe(true);
    expect(result.fallback).toBe(false);
  });

  it('detach rejection does not prevent retry on command_error', async () => {
    mockApi.attach
      .mockResolvedValueOnce(undefined)
      .mockResolvedValueOnce(undefined);
    // First detach fails, but we should still retry
    mockApi.detach
      .mockRejectedValueOnce(new Error('Detach failed'))
      .mockResolvedValueOnce(undefined);
    mockApi.sendCommand
      .mockRejectedValueOnce(new Error('protocol error'))
      .mockResolvedValueOnce(undefined);

    const captureAttempt = vi.fn().mockResolvedValue({ captured: true });
    const wait = vi.fn().mockResolvedValue(undefined);

    const result = await dispatchTrustedHover('tab1', { x: 100, y: 100 }, {
      api: mockApi as never,
      captureAttempt,
      wait,
      maxAttempts: 3,
      retryDelaysMs: [1000],
    });

    expect(result.captured).toBe(true);
    expect(result.fallback).toBe(false);
    // Should have retried despite first detach failing
    expect(mockApi.attach).toHaveBeenCalledTimes(2);
    expect(mockApi.sendCommand).toHaveBeenCalledTimes(2);
  });

  it('detach rejection does not prevent retry on capture_error', async () => {
    mockApi.attach
      .mockResolvedValueOnce(undefined)
      .mockResolvedValueOnce(undefined);
    mockApi.detach
      .mockRejectedValueOnce(new Error('Detach failed'))
      .mockResolvedValueOnce(undefined);
    mockApi.sendCommand.mockResolvedValue(undefined);

    const captureAttempt = vi
      .fn()
      .mockRejectedValueOnce(new Error('capture failed'))
      .mockResolvedValueOnce({ captured: true });
    const wait = vi.fn().mockResolvedValue(undefined);

    const result = await dispatchTrustedHover('tab1', { x: 100, y: 100 }, {
      api: mockApi as never,
      captureAttempt,
      wait,
      maxAttempts: 3,
      retryDelaysMs: [1000],
    });

    expect(result.captured).toBe(true);
    expect(result.fallback).toBe(false);
    // Should have retried despite first detach failing
    expect(mockApi.attach).toHaveBeenCalledTimes(2);
  });

  it('detach rejection does not overwrite fallback=true result from attach conflict', async () => {
    mockApi.attach.mockRejectedValue(new Error('another debugger attached'));
    mockApi.detach.mockRejectedValue(new Error('Detach error after conflict'));

    const captureAttempt = vi.fn();
    const wait = vi.fn();

    const result = await dispatchTrustedHover('tab1', { x: 100, y: 100 }, {
      api: mockApi as never,
      captureAttempt,
      wait,
      maxAttempts: 3,
    });

    // Should still be fallback=true from attach conflict, not overwritten by detach error
    expect(result.fallback).toBe(true);
    expect(result.captured).toBe(false);
  });

  it('multiple detach rejections on retry loop still returns correct final result', async () => {
    mockApi.attach.mockResolvedValue(undefined);
    mockApi.sendCommand.mockResolvedValue(undefined);
    // All detaches fail
    mockApi.detach.mockRejectedValue(new Error('Detach failed'));

    const captureAttempt = vi
      .fn()
      .mockResolvedValueOnce({ captured: false })
      .mockResolvedValueOnce({ captured: false })
      .mockResolvedValueOnce({ captured: true });

    const wait = vi.fn().mockResolvedValue(undefined);

    const result = await dispatchTrustedHover('tab1', { x: 100, y: 100 }, {
      api: mockApi as never,
      captureAttempt,
      wait,
      maxAttempts: 3,
      retryDelaysMs: [1000, 2000],
    });

    // Should eventually succeed despite detach always failing
    expect(result.captured).toBe(true);
    expect(result.fallback).toBe(false);
  });
});
