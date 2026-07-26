/**
 * agentApi — typed wrapper around `/api/summary/{video_id}`.
 *
 * The AIPulse backend exposes a single POST endpoint that enqueues a
 * summarisation job for a Bilibili video. The returned `job_id` keys the
 * per-job SSE stream that fronts `started/completed/partial/failed/timeout`.
 * The frontend also maps the response into the spec §6.13 vocabulary so the
 * SummarizeButton can render a six-state machine.
 */

import { apiFetch } from '../lib/apiFetch'

export interface EnqueueProcessRequest {
  /** Bilibili `bvid` (e.g. `BV1xx411c7mD`). */
  bvid: string
}

export interface EnqueueProcessResponse {
  job_id: string
  /** 1-based position in the queue at submission time. */
  queue_position?: number | null
  /** Pre-mapped initial status (snake_case per spec §6.13). */
  status?: 'idle' | 'pending' | 'queued' | 'running' | 'done' | 'failed'
}

/**
 * Enqueue a summarisation job for the supplied `bvid`. Resolves with the
 * `job_id`; the caller must subscribe to `/api/summary/events/{job_id}` to
 * observe state transitions.
 */
export async function enqueueProcess(
  req: EnqueueProcessRequest,
): Promise<EnqueueProcessResponse> {
  const body = await apiFetch<{
    success: boolean
    data: {
      job_id: string
      queue_position?: number | null
      status?: string
    }
  }>(`/api/summary/${encodeURIComponent(req.bvid)}`, {
    method: 'POST',
  })
  const data = body.data
  return {
    job_id: data.job_id,
    queue_position: data.queue_position ?? null,
    status: (data.status as EnqueueProcessResponse['status']) ?? 'queued',
  }
}

export const agentApi = { enqueueProcess }
