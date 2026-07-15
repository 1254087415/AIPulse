<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import { fetchKeywords, createKeyword, updateKeyword, deleteKeyword } from '../api/keywords'
import KeywordList from '../components/keyword/KeywordList.vue'
import type { Keyword } from '../types'

const newKeyword = ref('')
const createError = ref<string | null>(null)
const deleteError = ref<string | null>(null)
const queryClient = useQueryClient()
const { data, isLoading, error } = useQuery({ queryKey: ['keywords'], queryFn: fetchKeywords })
const create = useMutation({
  mutationFn: createKeyword,
  onSuccess: () => {
    createError.value = null
    newKeyword.value = ''
    queryClient.invalidateQueries({ queryKey: ['keywords'] })
  },
  onError: (err: unknown) => {
    createError.value = err instanceof Error ? err.message : '添加失败'
  },
})
const update = useMutation({
  mutationFn: ({ id, payload }: { id: string; payload: { is_active?: boolean; notify_on_match?: boolean } }) =>
    updateKeyword(id, payload),
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ['keywords'] }),
})
const remove = useMutation({
  mutationFn: deleteKeyword,
  onMutate: () => {
    deleteError.value = null
  },
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ['keywords'] }),
  onError: (err: unknown) => {
    deleteError.value = err instanceof Error ? err.message : '删除失败'
  },
})

const updatingIds = computed(() => ({
  ...Object.fromEntries(update.variables.value ? [[update.variables.value.id, true]] : []),
  ...Object.fromEntries(remove.variables.value ? [[remove.variables.value, true]] : []),
}))

watch(newKeyword, () => {
  createError.value = null
})

function submit() {
  const value = newKeyword.value.trim()
  if (!value) return
  createError.value = null
  create.mutate(value)
}

function toggleNotify(keyword: Keyword) {
  update.mutate({ id: keyword.id, payload: { notify_on_match: !keyword.notify_on_match } })
}

function toggleActive(keyword: Keyword) {
  update.mutate({ id: keyword.id, payload: { is_active: !keyword.is_active } })
}

function onDelete(keyword: Keyword) {
  remove.mutate(keyword.id)
}
</script>

<template>
  <div class="page">
    <header class="page-header">
      <div class="page-title">
        <h1>关键词</h1>
        <p class="subtitle">关注词与通知开关</p>
      </div>
      <div v-if="data" class="readout" aria-label="已有关键词">
        <span class="readout-value">{{ data.data.length }}</span>
        <span class="readout-label">个关注</span>
      </div>
    </header>

    <form class="panel control-row" @submit.prevent="submit">
      <label for="new-keyword" class="visually-hidden">新关键词</label>
      <input
        id="new-keyword"
        v-model="newKeyword"
        class="input"
        name="keyword"
        autocomplete="off"
        placeholder="输入关键词，例如 Kimi…"
        aria-describedby="keyword-error"
        :disabled="create.isPending.value"
      />
      <button
        type="submit"
        class="btn"
        :disabled="create.isPending.value || !newKeyword.trim()"
        :aria-disabled="create.isPending.value || !newKeyword.trim()"
      >
        {{ create.isPending.value ? '添加中…' : '添加' }}
      </button>
    </form>

    <div v-if="create.isSuccess.value" class="state state-success" role="status" aria-live="polite">
      关键词已添加
    </div>

    <div
      v-if="createError"
      id="keyword-error"
      class="state state-error"
      role="alert"
      aria-live="polite"
    >
      添加关键词失败：{{ createError }}
    </div>

    <div v-if="isLoading" class="state state-loading" role="status" aria-live="polite">
      正在同步信号…
    </div>

    <div
      v-else-if="error"
      class="state state-error"
      role="alert"
      aria-live="polite"
    >
      关键词接口异常：{{ (error as Error).message }}。请检查后端服务是否运行。
    </div>

    <div
      v-else-if="data && data.data.length === 0"
      class="state state-empty"
    >
      还没有关键词。添加一个关注词，系统会据此筛选 AI 热点。
    </div>

    <KeywordList
      v-else
      :keywords="data?.data ?? []"
      :updating="updatingIds"
      aria-describedby="delete-error"
      @toggle-notify="toggleNotify"
      @toggle-active="toggleActive"
      @delete="onDelete"
    />

    <div
      v-if="deleteError"
      id="delete-error"
      class="state state-error"
      role="alert"
      aria-live="polite"
    >
      删除关键词失败：{{ deleteError }}
    </div>
  </div>
</template>

<style scoped>
.control-row {
  display: flex;
  gap: 10px;
  margin-bottom: 16px;
}

.control-row .input {
  flex: 1;
}

.control-row .btn {
  flex-shrink: 0;
}
</style>
