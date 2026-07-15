<script setup lang="ts">
import { ref, computed, nextTick } from 'vue'
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import { fetchSources, updateSource, syncSource, type SourceUpdatePayload } from '../api/sources'
import { formatDateTime } from '../lib/format'
import type { Source } from '../types'

interface SourceDraft {
  default_weight: number
  fetch_interval_minutes: number
  config: string
}

const MIN_FETCH_INTERVAL_MINUTES = 5
const DEFAULT_WEIGHT_MIN = 0

const queryClient = useQueryClient()
const { data, isLoading, error } = useQuery({ queryKey: ['sources'], queryFn: fetchSources })
const update = useMutation({
  mutationFn: ({ id, payload }: { id: string; payload: SourceUpdatePayload }) =>
    updateSource(id, payload),
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ['sources'] }),
})
const sync = useMutation({
  mutationFn: syncSource,
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ['sources', 'jobs'] }),
})
const syncingIds = ref<Set<string>>(new Set())
const editingId = ref<string | null>(null)
const draft = ref<SourceDraft | null>({
  default_weight: 1,
  fetch_interval_minutes: MIN_FETCH_INTERVAL_MINUTES,
  config: '{}',
})
const configError = ref<string | null>(null)
const weightError = ref<string | null>(null)
const intervalError = ref<string | null>(null)
const weightInput = ref<HTMLInputElement | null>(null)
const intervalInput = ref<HTMLInputElement | null>(null)
const configTextarea = ref<HTMLTextAreaElement | null>(null)

function startEditing(source: Source) {
  editingId.value = source.id
  draft.value = {
    default_weight: source.default_weight,
    fetch_interval_minutes: source.fetch_interval_minutes,
    config: JSON.stringify(source.config ?? {}, null, 2),
  }
  configError.value = null
  weightError.value = null
  intervalError.value = null
  update.reset()
}

function stopEditing() {
  editingId.value = null
  configError.value = null
  weightError.value = null
  intervalError.value = null
}

function handleSave(source: Source) {
  if (!draft.value) {
    return
  }

  weightError.value = null
  intervalError.value = null
  configError.value = null

  let hasValidationError = false
  if (!Number.isFinite(draft.value.default_weight) || draft.value.default_weight < DEFAULT_WEIGHT_MIN) {
    weightError.value = `权重必须是数字且不小于 ${DEFAULT_WEIGHT_MIN}`
    hasValidationError = true
  }
  if (!Number.isFinite(draft.value.fetch_interval_minutes) || draft.value.fetch_interval_minutes < MIN_FETCH_INTERVAL_MINUTES) {
    intervalError.value = `同步间隔必须是数字且不小于 ${MIN_FETCH_INTERVAL_MINUTES} 分钟`
    hasValidationError = true
  }

  if (hasValidationError) {
    nextTick(() => {
      if (weightError.value) {
        safeFocus(weightInput.value)
      } else if (intervalError.value) {
        safeFocus(intervalInput.value)
      }
    })
    return
  }

  let parsedConfig: Record<string, unknown> | undefined

  if (draft.value.config.trim()) {
    try {
      const parsed = JSON.parse(draft.value.config)
      if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
        throw new Error('配置必须是 JSON 对象')
      }
      parsedConfig = parsed as Record<string, unknown>
    } catch (e) {
      configError.value = e instanceof Error ? e.message : '配置 JSON 解析失败'
      nextTick(() => safeFocus(configTextarea.value))
      return
    }
  }

  update.mutate(
    {
      id: source.id,
      payload: {
        default_weight: draft.value.default_weight,
        fetch_interval_minutes: draft.value.fetch_interval_minutes,
        config: parsedConfig,
      },
    },
    {
      onSuccess: () => stopEditing(),
      onError: () => nextTick(() => safeFocus(configTextarea.value)),
    },
  )
}

function toggleActive(source: Source) {
  update.mutate({ id: source.id, payload: { is_active: !source.is_active } })
}

function handleSync(source: Source) {
  syncingIds.value = new Set([...syncingIds.value, source.id])
  sync.mutate(source.id, {
    onSettled: () => {
      syncingIds.value = new Set([...syncingIds.value].filter((id) => id !== source.id))
    },
  })
}

function safeFocus(element: HTMLElement | null | undefined) {
  if (element && typeof element.focus === 'function') {
    element.focus()
  }
}

const activeCount = computed(() => data.value?.data.filter((s) => s.is_active).length ?? 0)
</script>

<template>
  <div class="page">
    <header class="page-header">
      <div class="page-title">
        <h1>来源</h1>
        <p class="subtitle">RSS、GitHub、arXiv 等信号源</p>
      </div>
      <div v-if="data" class="readout" aria-label="活跃来源数">
        <span class="readout-value">{{ activeCount }}</span>
        <span class="readout-label">个活跃</span>
      </div>
    </header>

    <div v-if="isLoading" class="state state-loading" role="status" aria-live="polite">正在同步信号…</div>

    <div v-else-if="error" class="state state-error" role="alert" aria-live="polite">
      来源接口异常：{{ error?.message }}。请检查后端服务是否运行。
    </div>

    <div v-else-if="data && data.data.length === 0" class="state state-empty">
      还没有配置来源。后端启动时会自动根据采集器注册默认来源。
    </div>

    <ul v-else-if="data" class="source-list" role="list">
      <li v-for="source in data.data" :key="source.id" class="source panel">
        <div class="source-main">
          <div class="source-header">
            <span class="source-name">{{ source.name }}</span>
            <span class="tag">{{ source.source_type }}</span>
            <span class="tag" :class="{ 'tag-signal': source.is_active }">
              {{ source.is_active ? '启用' : '停用' }}
            </span>
          </div>

          <div v-if="editingId === source.id" class="source-form">
            <template v-if="draft">
              <label class="form-row">
                <span>权重</span>
                <input
                  ref="weightInput"
                  v-model.number="draft.default_weight"
                  type="number"
                  step="0.1"
                  name="default_weight"
                  autocomplete="off"
                  data-testid="source-weight"
                  class="form-input"
                  aria-describedby="weight-error"
                />
              </label>
              <label class="form-row">
                <span>同步间隔（分钟）</span>
                <input
                  ref="intervalInput"
                  v-model.number="draft.fetch_interval_minutes"
                  type="number"
                  min="5"
                  name="fetch_interval_minutes"
                  autocomplete="off"
                  data-testid="source-interval"
                  class="form-input"
                  aria-describedby="interval-error"
                />
              </label>
              <label class="form-row">
                <span>配置（JSON）</span>
                <textarea
                  ref="configTextarea"
                  v-model="draft.config"
                  rows="4"
                  name="config"
                  autocomplete="off"
                  spellcheck="false"
                  data-testid="source-config"
                  class="form-textarea"
                  aria-describedby="config-error update-error"
                ></textarea>
              </label>
              <div v-if="weightError" id="weight-error" class="source-error" data-testid="weight-validation-error">
                {{ weightError }}
              </div>
              <div v-if="intervalError" id="interval-error" class="source-error" data-testid="interval-validation-error">
                {{ intervalError }}
              </div>
              <div v-if="configError" id="config-error" class="source-error" data-testid="config-error">
                {{ configError }}
              </div>
              <div v-if="update.error.value" id="update-error" class="source-error" data-testid="update-error">
                {{ update.error.value.message }}
              </div>
              <div v-if="update.isSuccess.value" class="source-success" role="status" aria-live="polite">保存成功</div>
              <div class="form-actions">
                <button
                  type="button"
                  class="btn"
                  data-testid="save-source"
                  :disabled="update.isPending.value"
                  @click="handleSave(source)"
                >
                  保存
                </button>
                <button
                  type="button"
                  class="btn btn-ghost"
                  data-testid="cancel-edit"
                  @click="stopEditing"
                >
                  取消
                </button>
              </div>
            </template>
          </div>

          <div v-else class="source-meta">
            <span class="mono">权重 {{ source.default_weight.toFixed(1) }}</span>
            <span class="mono">每 {{ source.fetch_interval_minutes }} 分钟</span>
            <span>上次同步：{{ formatDateTime(source.last_fetched_at) || '从未同步' }}</span>
          </div>

          <div v-if="source.last_error" class="source-error" role="alert" aria-live="polite">
            {{ source.last_error }}
          </div>
          <div v-if="sync.error.value" class="source-error" data-testid="sync-error" role="alert" aria-live="polite">
            {{ sync.error.value.message }}
          </div>
        </div>
        <div class="source-actions">
          <button
            v-if="editingId !== source.id"
            type="button"
            class="btn btn-ghost"
            data-testid="edit-source"
            @click="startEditing(source)"
          >
            编辑
          </button>
          <button
            type="button"
            class="btn btn-ghost"
            data-testid="toggle-source"
            :disabled="update.isPending.value"
            @click="toggleActive(source)"
          >
            {{ source.is_active ? '停用' : '启用' }}
          </button>
          <button
            type="button"
            class="btn"
            data-testid="sync-source"
            :disabled="!source.is_active || syncingIds.has(source.id)"
            @click="handleSync(source)"
          >
            {{ syncingIds.has(source.id) ? '同步中…' : '立即同步' }}
          </button>
        </div>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.source-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.source {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  transition: transform 0.12s ease, box-shadow 0.12s ease;
}

.source:hover {
  transform: translateY(-1px);
  box-shadow: var(--shadow-md);
}

.source-main {
  min-width: 0;
  flex: 1;
}

.source-header {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 8px;
}

.source-name {
  font-family: var(--font-display);
  font-size: 16px;
  font-weight: 600;
}

.source-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  font-size: 12px;
  color: var(--slate);
}

.source-error {
  margin-top: 8px;
  padding: 8px 10px;
  border-radius: var(--radius-sm);
  background: var(--signal-soft);
  color: var(--signal);
  font-size: 12px;
}

.source-success {
  margin-top: 8px;
  padding: 8px 10px;
  border-radius: var(--radius-sm);
  background: rgba(22, 163, 74, 0.08);
  color: #166534;
  font-size: 12px;
}

.source-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
  flex-shrink: 0;
}

.source-form {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 4px;
}

.form-row {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12px;
  color: var(--slate);
}

.form-input,
.form-textarea {
  padding: 6px 8px;
  border: 1px solid var(--mist);
  border-radius: var(--radius-sm);
  background: rgba(252, 250, 248, 0.92);
  color: var(--ink);
  font-family: var(--font-mono);
  font-size: 13px;
}

.form-textarea {
  resize: vertical;
}

.form-actions {
  display: flex;
  gap: 8px;
}

@media (max-width: 640px) {
  .source {
    flex-direction: column;
  }

  .source-actions {
    width: 100%;
    flex-direction: row;
  }

  .source-actions .btn {
    flex: 1;
  }
}
</style>
