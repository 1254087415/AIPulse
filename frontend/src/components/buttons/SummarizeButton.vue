<script setup lang="ts">
/**
 * SummarizeButton — six-state "总结" button (spec §6.13).
 *
 *   idle     — no summary exists; click to enqueue
 *   pending  — request in flight
 *   queued   — server accepted the job, waiting in the queue
 *   running  — pipeline started; SSE step events stream UI progress
 *   done     — job finished; click jumps to `obsidian://open?path=...`
 *   failed   — server rejected or pipeline failed; click retries
 *
 * The component subscribes to the agent SSE stream keyed by `bvid`:
 *   agent.queue.updated | agent.task.{bvid}.started | .step | .done | .failed
 *
 * It also delegates the enqueue call to `agentApi.enqueueProcess` which
 * hits `POST /api/summary/{bvid}`. Errors propagate through `errorMessage`
 * and a `failed` emit so the parent can surface a toast.
 */
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { agentApi } from '../../api/agent'
import { subscribeSse } from '../../lib/sse-client'

type SummarizeStatus = 'idle' | 'pending' | 'queued' | 'running' | 'done' | 'failed'

interface Props {
  bvid: string
  /** Whether the user already has a finished summary note. */
  hasSummary?: boolean
  /** Vault-relative path for the existing note when `hasSummary` is true. */
  obsidianPath?: string | null
  /** Override the SSE base URL (mainly for tests). */
  sseBaseUrl?: string
}

const props = withDefaults(defineProps<Props>(), {
  hasSummary: false,
  obsidianPath: null,
  sseBaseUrl: '/api/summary/events',
})

const emit = defineEmits<{
  (e: 'queued', jobId: string): void
  (e: 'failed', reason: string): void
  (e: 'done', notePath: string | null): void
}>()

/**
 * Resolve the SSE URL for the current bvid. Uses a query-string `bvid`
 * parameter so a single EventSource can multiplex multiple bvid streams
 * on the backend's agent task bus.
 */
const sseUrl = computed(() => {
  if (props.sseBaseUrl.includes('{bvid}')) {
    return props.sseBaseUrl.replace('{bvid}', encodeURIComponent(props.bvid))
  }
  const sep = props.sseBaseUrl.includes('?') ? '&' : '?'
  return `${props.sseBaseUrl}${sep}bvid=${encodeURIComponent(props.bvid)}`
})

const status = ref<SummarizeStatus>(props.hasSummary ? 'done' : 'idle')
const queuePosition = ref<number | null>(null)
const currentStep = ref<string | null>(null)
const errorMessage = ref<string | null>(null)
const jobId = ref<string | null>(null)

const label = computed(() => {
  if (status.value === 'done') return '查看总结'
  if (status.value === 'failed') return '重试'
  if (status.value === 'queued' && queuePosition.value !== null) {
    return `已入队 #${queuePosition.value}`
  }
  if (
    (status.value === 'running' ||
      status.value === 'pending' ||
      status.value === 'queued') &&
    currentStep.value
  ) {
    return `处理中 · ${currentStep.value}`
  }
  if (status.value === 'pending') return '提交中…'
  return '总结'
})

const isBusy = computed(() =>
  ['pending', 'queued', 'running'].includes(status.value),
)

async function onClick() {
  if (isBusy.value) return
  if (status.value === 'done' && props.obsidianPath) {
    openInObsidian(props.obsidianPath)
    return
  }
  status.value = 'pending'
  errorMessage.value = null
  try {
    const res = await agentApi.enqueueProcess({ bvid: props.bvid })
    jobId.value = res.job_id
    status.value = 'queued'
    queuePosition.value = res.queue_position ?? null
    emit('queued', res.job_id)
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err)
    status.value = 'failed'
    errorMessage.value = message
    emit('failed', message)
  }
}

function openInObsidian(notePath: string) {
  const url = `obsidian://open?path=${encodeURIComponent(notePath)}`
  // browser navigation; Obsidian URI handler picks it up on the desktop
  window.location.href = url
}

let cleanup: (() => void) | null = null

function attachSse() {
  cleanup?.()
  cleanup = subscribeSse<Record<string, unknown>>(sseUrl.value, [
    {
      event: 'agent.queue.updated',
      handler: () => {
        // queue position may shift; the server pushes the canonical value
        // via later events so we don't act on partial updates here.
      },
    },
    {
      event: `agent.task.${props.bvid}.started`,
      handler: () => {
        status.value = 'running'
        currentStep.value = null
        errorMessage.value = null
      },
    },
    {
      event: `agent.task.${props.bvid}.step`,
      handler: (payload) => {
        const step = payload?.step
        if (typeof step === 'string') {
          currentStep.value = step
          // late-arriving step events should also move the button into
          // the running state if started() was missed (network reorder /
          // resume from snapshot)
          if (status.value === 'idle' || status.value === 'queued') {
            status.value = 'running'
          }
        }
      },
    },
    {
      event: `agent.task.${props.bvid}.done`,
      handler: (payload) => {
        status.value = 'done'
        currentStep.value = null
        const note = (payload?.note_path as string | null | undefined) ?? null
        if (note) emit('done', note)
      },
    },
    {
      event: `agent.task.${props.bvid}.failed`,
      handler: (payload) => {
        status.value = 'failed'
        const message =
          (payload?.error as string | undefined) ?? '处理失败，请稍后重试'
        currentStep.value = null
        errorMessage.value = message
        emit('failed', message)
      },
    },
  ])
}

onMounted(() => {
  attachSse()
})
onBeforeUnmount(() => {
  cleanup?.()
  cleanup = null
})
</script>

<template>
  <button
    type="button"
    :class="[
      'btn',
      'summarize-btn',
      `summarize-btn--${status}`,
    ]"
    :disabled="isBusy"
    :aria-busy="isBusy"
    :title="errorMessage ?? label"
    @click="onClick"
  >
    <span v-if="status === 'done'" aria-hidden="true">✓</span>
    <span v-else-if="status === 'failed'" aria-hidden="true">!</span>
    <span
      v-else-if="status === 'running' || status === 'pending'"
      class="summarize-spinner"
      aria-hidden="true"
    />
    {{ label }}
  </button>
</template>

<style scoped>
.summarize-btn {
  min-width: 88px;
  justify-content: center;
}

.summarize-btn--idle {
  background: var(--ink);
  color: var(--paper);
}

.summarize-btn--pending,
.summarize-btn--queued {
  background: var(--state-queued);
  color: white;
  cursor: default;
}

.summarize-btn--running {
  background: var(--state-running);
  color: white;
  cursor: default;
}

.summarize-btn--done {
  background: var(--state-done);
  color: white;
}

.summarize-btn--failed {
  background: var(--state-error);
  color: white;
}

.summarize-btn:focus-visible {
  outline: none;
  box-shadow: 0 0 0 3px rgba(var(--signal-rgb, 249 115 22), 0.25);
}

.summarize-spinner {
  width: 12px;
  height: 12px;
  border: 2px solid rgba(255, 255, 255, 0.4);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  display: inline-block;
  margin-right: 6px;
  vertical-align: middle;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

@media (prefers-reduced-motion: reduce) {
  .summarize-spinner { animation: none; }
}
</style>
