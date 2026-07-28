<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import {
  listFollowedUps,
  createFollowedUp,
  deleteFollowedUp,
  syncFollowedUp,
} from '../api/follow'
import { ApiError } from '../api/client'
import type { FollowedUpCreate } from '../types'
import FollowCard from '../components/follow/FollowCard.vue'
import FollowForm from '../components/follow/FollowForm.vue'

const router = useRouter()
const queryClient = useQueryClient()

const showForm = ref(false)
const formError = ref<string | null>(null)
const syncingIds = ref<Record<string, boolean>>({})

const { data, isLoading, error } = useQuery({
  queryKey: ['followed-ups'],
  queryFn: listFollowedUps,
})

const create = useMutation({
  mutationFn: (payload: FollowedUpCreate) => createFollowedUp(payload),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['followed-ups'] })
    showForm.value = false
    formError.value = null
  },
  onError: (err) => {
    if (err instanceof ApiError && err.status === 409) {
      formError.value = '该 UP 主已关注，请勿重复添加'
    } else if (err instanceof Error) {
      formError.value = `添加失败：${err.message}`
    } else {
      formError.value = '添加失败'
    }
  },
})

const remove = useMutation({
  mutationFn: (id: string) => deleteFollowedUp(id),
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ['followed-ups'] }),
})

const sync = useMutation({
  mutationFn: async (id: string) => {
    syncingIds.value = { ...syncingIds.value, [id]: true }
    try {
      return await syncFollowedUp(id)
    } finally {
      syncingIds.value = { ...syncingIds.value, [id]: false }
    }
  },
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['followed-ups'] })
  },
})

function openDetail(id: string) {
  router.push(`/followed-up/${id}`)
}

function handleDelete(id: string) {
  if (typeof window !== 'undefined' && !window.confirm('确认删除该 UP 主？同步任务将停止。')) {
    return
  }
  remove.mutate(id)
}

function handleSync(id: string) {
  sync.mutate(id)
}

function handleSubmit(payload: FollowedUpCreate) {
  create.mutate(payload)
}
</script>

<template>
  <div class="page">
    <header class="page-header">
      <div class="page-title">
        <h1>关注列表</h1>
        <p class="subtitle">管理需要持续同步内容的 UP 主</p>
      </div>
      <button
        type="button"
        class="btn primary"
        :disabled="create.isPending.value"
        @click="showForm = !showForm"
      >
        {{ showForm ? '收起表单' : '➕ 添加 UP 主' }}
      </button>
    </header>

    <section v-if="showForm" class="form-panel" aria-label="添加 UP 主表单">
      <FollowForm
        @submit="handleSubmit"
        @cancel="showForm = false"
      />
      <p v-if="formError" class="state state-error" role="alert">{{ formError }}</p>
    </section>

    <div v-if="isLoading" class="state state-loading" role="status" aria-live="polite">
      正在加载关注列表…
    </div>

    <div v-else-if="error" class="state state-error" role="alert" aria-live="polite">
      加载失败：{{ error?.message }}
    </div>

    <div v-else-if="data && data.length === 0" class="state state-empty">
      还没有关注任何 UP 主。点击右上角「➕ 添加 UP 主」开始。
    </div>

    <section v-else class="grid" aria-label="关注列表">
      <FollowCard
        v-for="(item, index) in (data ?? [])"
        :key="item.id"
        :followed-up="item"
        :syncing="!!syncingIds[item.id]"
        :style="{ animationDelay: `${index * 40}ms` }"
        class="card-enter"
        @open="openDetail"
        @sync="handleSync"
        @delete="handleDelete"
      />
    </section>
  </div>
</template>

<style scoped>
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 20px;
}

.subtitle {
  font-size: 13px;
  color: var(--slate);
  margin: 4px 0 0;
}

.btn.primary {
  background: var(--signal);
  border: 1px solid var(--signal);
  color: #fff;
  padding: 8px 14px;
  border-radius: 6px;
  font-size: 14px;
  cursor: pointer;
}

.btn.primary[disabled] {
  opacity: 0.5;
  cursor: not-allowed;
}

.form-panel {
  border: 1px solid var(--mist);
  border-radius: 10px;
  padding: 18px;
  background: var(--color-surface, #fff);
  margin-bottom: 20px;
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 14px;
}

.card-enter {
  opacity: 0;
  transform: translateY(8px);
  animation: cardIn 0.35s ease forwards;
}

@media (prefers-reduced-motion: reduce) {
  .card-enter {
    opacity: 1;
    transform: none;
    animation: none;
  }
}

@keyframes cardIn {
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>