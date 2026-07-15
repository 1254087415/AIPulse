<script setup lang="ts">
import { computed, ref } from 'vue'
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import { fetchDigests, fetchLatestDigest, generateDigest } from '../api/digests'
import { formatDateTime } from '../lib/format'

const queryClient = useQueryClient()
const { data: digests, isLoading: listLoading, error } = useQuery({ queryKey: ['digests'], queryFn: () => fetchDigests(10) })
const { data: latest, isLoading: latestLoading } = useQuery({ queryKey: ['digests', 'latest'], queryFn: fetchLatestDigest })
const generate = useMutation({
  mutationFn: generateDigest,
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['digests'] })
    queryClient.invalidateQueries({ queryKey: ['digests', 'latest'] })
  },
})

const selectedId = ref<string | null>(null)
const selectedDigest = computed(() => {
  if (selectedId.value && digests.value) {
    return digests.value.data.find((d) => d.id === selectedId.value) ?? null
  }
  return latest.value?.data ?? null
})

const contentParagraphs = computed(() => (selectedDigest.value?.content ?? '').split('\n'))
</script>

<template>
  <div class="page">
    <header class="page-header">
      <div class="page-title">
        <h1>每日摘要</h1>
        <p class="subtitle">每日 AI 热点的自动汇总</p>
      </div>
      <button
        type="button"
        class="btn"
        :disabled="generate.isPending.value"
        @click="generate.mutate()"
      >
        {{ generate.isPending.value ? '生成中…' : '生成今日摘要' }}
      </button>
    </header>

    <div v-if="listLoading || latestLoading" class="state state-loading" role="status" aria-live="polite">
      正在同步信号…
    </div>

    <div v-else-if="error" class="state state-error" role="alert" aria-live="polite">
      摘要接口异常：{{ error?.message }}。请检查后端服务是否运行。
    </div>

    <div v-else-if="generate.error.value" class="state state-error" role="alert" aria-live="polite">
      生成摘要失败：{{ generate.error.value?.message }}。请稍后重试。
    </div>

    <div v-if="generate.isSuccess.value" class="state state-success" role="status" aria-live="polite">
      摘要生成成功
    </div>

    <div v-else-if="!selectedDigest" class="state state-empty">
      还没有每日摘要。点击右上角「生成今日摘要」手动创建第一份日报。
    </div>

    <div v-else class="digest-layout">
      <aside class="digest-sidebar">
        <ul v-if="digests && digests.data.length > 0" class="digest-list" role="list">
          <li v-for="digest in digests.data" :key="digest.id">
            <button
              type="button"
              class="digest-item"
              :class="{ active: selectedId === digest.id || (!selectedId && latest?.data.id === digest.id) }"
              :aria-pressed="selectedId === digest.id || (!selectedId && latest?.data.id === digest.id)"
              @click="selectedId = digest.id"
            >
              <span class="digest-title">{{ digest.title }}</span>
              <span class="digest-date">{{ formatDateTime(digest.generated_at) }}</span>
            </button>
          </li>
        </ul>
      </aside>
      <article class="digest-content panel">
        <h2>{{ selectedDigest.title }}</h2>
        <time class="digest-time">{{ formatDateTime(selectedDigest.generated_at) }}</time>
        <div class="markdown">
          <p v-for="(paragraph, index) in contentParagraphs" :key="`${selectedDigest.id}-${index}`">{{ paragraph }}</p>
        </div>
      </article>
    </div>
  </div>
</template>

<style scoped>
.digest-layout {
  display: grid;
  grid-template-columns: 280px 1fr;
  gap: 16px;
  align-items: start;
}

.digest-sidebar {
  position: sticky;
  top: 16px;
}

.digest-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.digest-list > li {
  display: block;
}

.digest-item {
  display: block;
  width: 100%;
  text-align: left;
  font: inherit;
  padding: 12px;
  border-radius: var(--radius-md);
  border: 1px solid var(--mist);
  background: rgba(252, 250, 248, 0.92);
  cursor: pointer;
  transition: border-color 0.12s ease, background 0.12s ease;
}

.digest-item:hover {
  border-color: var(--grid);
  background: #ffffff;
}

.digest-item.active {
  border-color: var(--signal);
  background: var(--signal-soft);
}

.digest-title {
  display: block;
  font-family: var(--font-display);
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 4px;
}

.digest-date {
  font-size: 11px;
  color: var(--slate);
}

.digest-content {
  min-width: 0;
}

.digest-content h2 {
  font-size: 22px;
  margin-bottom: 6px;
}

.digest-time {
  display: block;
  font-size: 12px;
  color: var(--slate);
  margin-bottom: 16px;
}

.markdown {
  font-size: 15px;
  line-height: 1.7;
  color: var(--ink);
}

@media (max-width: 640px) {
  .digest-layout {
    grid-template-columns: 1fr;
  }

  .digest-sidebar {
    position: static;
  }
}
</style>
