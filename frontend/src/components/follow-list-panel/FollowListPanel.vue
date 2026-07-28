<script setup lang="ts">
/**
 * FollowListPanel — the "关注列表" tab (spec §6.3 / §6.11).
 *
 * Owns:
 *  - Loading / error / empty states
 *  - Sorting (errored pinned first, then by updated_at desc)
 *  - Over-limit warning (>= 20 UPs)
 *  - Add form lifecycle + inline 409 conflict feedback
 *  - Delete / sync action delegation
 *
 * Card-level rendering is delegated to FollowCard; this file only composes
 * the list and the surrounding chrome.
 */
import { computed, ref, onMounted } from 'vue'
import AddFollowForm from './AddFollowForm.vue'
import FollowCard from './FollowCard.vue'
import HealthBadge from '../health-badge/HealthBadge.vue'
import { listFollowed, createFollowed, type FollowedUp, type FollowedUpCreate } from '../../api/followedUp'

interface PanelError {
  message: string
  status?: number
}

const MAX_FOLLOW_LIMIT = 20

const items = ref<FollowedUp[]>([])
const isLoading = ref<boolean>(true)
const isError = ref<boolean>(false)
const loadError = ref<string>('')
const showAddForm = ref<boolean>(false)
const submitting = ref<boolean>(false)
const createError = ref<PanelError | null>(null)

const sortedItems = computed<FollowedUp[]>(() => {
  return [...items.value].sort((a, b) => {
    if (a.health === 'error' && b.health !== 'error') return -1
    if (b.health === 'error' && a.health !== 'error') return 1
    return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
  })
})

const isOverLimit = computed<boolean>(() => sortedItems.value.length > MAX_FOLLOW_LIMIT)

const fetchList = async (): Promise<void> => {
  isLoading.value = true
  isError.value = false
  loadError.value = ''
  try {
    items.value = await listFollowed()
  } catch (error: unknown) {
    isError.value = true
    loadError.value = extractMessage(error, '加载关注列表失败')
  } finally {
    isLoading.value = false
  }
}

const openAddForm = (): void => {
  showAddForm.value = true
  createError.value = null
}

const cancelAddForm = (): void => {
  showAddForm.value = false
  createError.value = null
}

const submitAddForm = async (payload: FollowedUpCreate): Promise<void> => {
  submitting.value = true
  createError.value = null
  try {
    await createFollowed(payload)
    showAddForm.value = false
    await fetchList()
  } catch (error: unknown) {
    createError.value = {
      message: extractMessage(error, '添加失败'),
      status: extractStatus(error),
    }
  } finally {
    submitting.value = false
  }
}

const onRemove = async (id: string): Promise<void> => {
  items.value = items.value.filter((item) => item.id !== id)
}

const onSync = async (_id: string): Promise<void> => {
  // Sync is delegated to a parent-driven mutation in later phases; for now
  // surface a lightweight feedback through loadError so the user sees action.
  await fetchList()
}

const onEdit = (id: string): void => {
  // Phase 2+ — wire to the detail view. For Phase 1 we simply surface a hint.
  loadError.value = `编辑 ${id} 将在 Phase 2 启用`
}

function extractMessage(error: unknown, fallback: string): string {
  if (error instanceof Error) return error.message
  return fallback
}

function extractStatus(error: unknown): number | undefined {
  if (error && typeof error === 'object' && 'status' in error) {
    const status = (error as { status?: unknown }).status
    if (typeof status === 'number') return status
  }
  return undefined
}

function formatCreateError(error: PanelError): string {
  if (error.status === 409) {
    return '该 UID 已经在关注列表中（后端返回 409 冲突）'
  }
  return error.message
}

onMounted(() => {
  void fetchList()
})
</script>

<template>
  <section class="follow-list-panel">
    <header class="follow-list-panel__header">
      <div>
        <h2 class="follow-list-panel__title">关注列表</h2>
        <p class="follow-list-panel__subtitle">
          <span data-testid="count">{{ sortedItems.length }}</span> 个 UP 主
          <span v-if="sortedItems.length > 0" class="follow-list-panel__hint">
            ·
            <span v-if="isOverLimit" data-testid="over-limit-warning" class="follow-list-panel__warning">
              超过 {{ MAX_FOLLOW_LIMIT }} 个，关注节奏可能影响扫描频率
            </span>
            <span v-else>全部启用</span>
          </span>
        </p>
      </div>
      <button
        v-if="!showAddForm"
        type="button"
        class="follow-list-panel__btn follow-list-panel__btn--primary"
        data-testid="open-add-form"
        @click="openAddForm"
      >
        ➕ 添加 UP 主
      </button>
    </header>

    <div v-if="isLoading" class="follow-list-panel__state">加载中…</div>
    <div v-else-if="isError" class="follow-list-panel__state follow-list-panel__state--error">
      {{ loadError }}
      <button type="button" class="follow-list-panel__btn" @click="fetchList()">重试</button>
    </div>
    <div
      v-else-if="sortedItems.length === 0 && !showAddForm"
      class="follow-list-panel__state"
      data-testid="empty-state"
    >
      还没有关注的 UP 主。点击「添加 UP 主」开始。
    </div>

    <AddFollowForm
      v-if="showAddForm"
      :submitting="submitting"
      :error-message="createError ? formatCreateError(createError) : null"
      @submit="submitAddForm"
      @cancel="cancelAddForm"
    />

    <p
      v-if="createError"
      class="follow-list-panel__create-error"
      data-testid="create-error"
      role="alert"
    >
      {{ formatCreateError(createError) }}
    </p>

    <ul v-if="sortedItems.length > 0" class="follow-list-panel__list">
      <li v-for="item in sortedItems" :key="item.id" class="follow-list-panel__item">
        <FollowCard
          :followed="item"
          @remove="onRemove"
          @sync="onSync"
          @edit="onEdit"
        >
          <template #health>
            <HealthBadge :status="item.health" />
          </template>
          <template #detail>
            <router-link class="follow-card__detail-link" :to="`/followed-up/${encodeURIComponent(item.uid)}`">
              查看详情
            </router-link>
          </template>
        </FollowCard>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.follow-list-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.follow-list-panel__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.follow-list-panel__title {
  margin: 0 0 4px;
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
}

.follow-list-panel__subtitle {
  margin: 0;
  font-size: 13px;
  color: var(--text-secondary);
}

.follow-list-panel__hint {
  margin-left: 4px;
}

.follow-list-panel__warning {
  color: var(--status-amber);
  font-weight: 500;
}

.follow-list-panel__btn {
  appearance: none;
  height: 36px;
  padding: 0 16px;
  border-radius: var(--radius-sm);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: background-color 150ms ease, color 150ms ease, border-color 150ms ease;
  background: var(--surface-elevated);
  border: 1px solid var(--border-subtle);
  color: var(--text-primary);
}

.follow-list-panel__btn:hover {
  background: var(--surface-elevated-hover);
}

.follow-list-panel__btn--primary {
  background: var(--accent-coral);
  border-color: var(--accent-coral);
  color: var(--surface-elevated);
}

.follow-list-panel__btn--primary:hover {
  background: color-mix(in srgb, var(--accent-coral) 88%, black);
}

.follow-list-panel__state {
  padding: 24px;
  background: var(--surface-elevated);
  border: 1px dashed var(--border-subtle);
  border-radius: var(--radius-md);
  text-align: center;
  color: var(--text-secondary);
}

.follow-list-panel__state--error {
  border-style: solid;
  color: var(--status-red);
  display: flex;
  flex-direction: column;
  gap: 8px;
  align-items: center;
}

.follow-list-panel__create-error {
  margin: 0;
  padding: 8px 12px;
  background: color-mix(in srgb, var(--status-red) 12%, transparent);
  border-radius: var(--radius-sm);
  color: var(--status-red);
  font-size: 13px;
}

.follow-list-panel__list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
</style>