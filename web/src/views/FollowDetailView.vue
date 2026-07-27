<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import {
  getFollowedUp,
  getFollowedUpOverview,
  updateFollowedUp,
  deleteFollowedUp,
  syncFollowedUp,
} from '../api/follow'
import { ApiError } from '../api/client'
import HealthBadge from '../components/follow/HealthBadge.vue'
import { formatDateTime } from '../lib/format'

const route = useRoute()
const router = useRouter()
const queryClient = useQueryClient()
const id = computed(() => route.params.id as string)

const { data, isLoading, error } = useQuery({
  queryKey: ['followed-up', id],
  queryFn: () => getFollowedUp(id.value),
  enabled: !!id.value,
})

const { data: overview } = useQuery({
  queryKey: ['followed-up', id, 'overview'],
  queryFn: () => getFollowedUpOverview(id.value),
  enabled: !!id.value,
})

const editing = ref(false)
const editInterval = ref(30)
const editStrategy = ref<'uapi' | 'html'>('uapi')

watch(
  () => data.value,
  (next) => {
    if (next) {
      editInterval.value = next.fetch_interval_minutes
      editStrategy.value = next.collector_strategy
    }
  },
)

const update = useMutation({
  mutationFn: () =>
    updateFollowedUp(id.value, {
      fetch_interval_minutes: editInterval.value,
      collector_strategy: editStrategy.value,
    }),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['followed-up', id] })
    editing.value = false
  },
})

const toggleStatus = useMutation({
  mutationFn: (status: 'active' | 'paused') =>
    updateFollowedUp(id.value, { status }),
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ['followed-up', id] }),
})

const remove = useMutation({
  mutationFn: () => deleteFollowedUp(id.value),
  onSuccess: () => router.push('/followed-up'),
})

const sync = useMutation({
  mutationFn: () => syncFollowedUp(id.value),
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ['followed-up', id, 'overview'] }),
})

function handleDelete() {
  if (typeof window !== 'undefined' && !window.confirm('确认删除？')) return
  remove.mutate()
}
</script>

<template>
  <div class="page">
    <button type="button" class="back" aria-label="返回关注列表" @click="router.push('/followed-up')">
      ← 返回关注列表
    </button>

    <div v-if="isLoading" class="state state-loading" role="status" aria-live="polite">
      正在加载…
    </div>

    <div v-else-if="error" class="state state-error" role="alert" aria-live="polite">
      加载失败：{{ error?.message }}
    </div>

    <article v-else-if="data" class="detail">
      <header class="detail-header">
        <div>
          <h1>{{ data.display_name }}</h1>
          <p class="meta">
            <span>{{ data.platform }}</span>
            <span class="dot">·</span>
            <span>{{ data.uid }}</span>
            <span class="dot">·</span>
            <a :href="data.profile_url" target="_blank" rel="noopener noreferrer">主页</a>
          </p>
        </div>
        <HealthBadge :health="data.health" :status="data.status" />
      </header>

      <section class="meta-grid panel">
        <div>
          <label>同步间隔</label>
          <p>{{ data.fetch_interval_minutes }} 分钟</p>
        </div>
        <div>
          <label>采集策略</label>
          <p>{{ data.collector_strategy }}</p>
        </div>
        <div>
          <label>上次检查</label>
          <p>{{ formatDateTime(data.last_checked_at, '从未') }}</p>
        </div>
        <div>
          <label>最后错误</label>
          <p :class="{ error: data.last_error }">{{ data.last_error ?? '—' }}</p>
        </div>
      </section>

      <section class="actions">
        <button
          v-if="data.status === 'active'"
          type="button"
          class="btn"
          @click="toggleStatus.mutate('paused')"
        >
          暂停同步
        </button>
        <button
          v-else
          type="button"
          class="btn"
          @click="toggleStatus.mutate('active')"
        >
          恢复同步
        </button>

        <button
          type="button"
          class="btn"
          :disabled="sync.isPending.value"
          @click="sync.mutate()"
        >
          {{ sync.isPending.value ? '同步中…' : '立即同步' }}
        </button>

        <button type="button" class="btn" @click="editing = !editing">
          {{ editing ? '收起' : '编辑' }}
        </button>

        <button type="button" class="btn danger" @click="handleDelete">删除</button>
      </section>

      <section v-if="editing" class="panel edit-panel">
        <div class="field">
          <label for="edit-interval">同步间隔（分钟）</label>
          <input id="edit-interval" v-model.number="editInterval" type="number" min="1" max="10080" />
        </div>
        <div class="field">
          <label for="edit-strategy">采集策略</label>
          <select id="edit-strategy" v-model="editStrategy">
            <option value="uapi">uapi</option>
            <option value="html">html</option>
          </select>
        </div>
        <div class="actions">
          <button
            type="button"
            class="btn primary"
            :disabled="update.isPending.value"
            @click="update.mutate()"
          >
            {{ update.isPending.value ? '保存中…' : '保存' }}
          </button>
          <button type="button" class="btn ghost" @click="editing = false">取消</button>
        </div>
        <p v-if="update.error.value" class="state state-error" role="alert">
          保存失败：{{ update.error.value?.message }}
        </p>
      </section>

      <section v-if="overview" class="panel overview">
        <h2>最近活动</h2>
        <div class="overview-grid">
          <div>
            <h3>最近任务 ({{ overview.recent_jobs.length }})</h3>
            <ul>
              <li v-for="job in overview.recent_jobs" :key="JSON.stringify(job)">
                <code>{{ JSON.stringify(job).slice(0, 80) }}</code>
              </li>
              <li v-if="overview.recent_jobs.length === 0" class="empty">暂无</li>
            </ul>
          </div>
          <div>
            <h3>学习事件 ({{ overview.recent_learning_events.length }})</h3>
            <ul>
              <li v-for="ev in overview.recent_learning_events" :key="JSON.stringify(ev)">
                <code>{{ JSON.stringify(ev).slice(0, 80) }}</code>
              </li>
              <li v-if="overview.recent_learning_events.length === 0" class="empty">暂无</li>
            </ul>
          </div>
          <div>
            <h3>合集 ({{ overview.recent_collections.length }})</h3>
            <ul>
              <li v-for="col in overview.recent_collections" :key="JSON.stringify(col)">
                <code>{{ JSON.stringify(col).slice(0, 80) }}</code>
              </li>
              <li v-if="overview.recent_collections.length === 0" class="empty">暂无</li>
            </ul>
          </div>
        </div>
      </section>

      <p v-if="sync.error.value" class="state state-error" role="alert">
        同步失败：{{ (sync.error.value as ApiError)?.message ?? '未知错误' }}
      </p>
    </article>
  </div>
</template>

<style scoped>
.back {
  appearance: none;
  background: transparent;
  border: none;
  font-size: 14px;
  color: var(--slate);
  cursor: pointer;
  padding: 0;
  margin-bottom: 16px;
}

.back:hover {
  color: var(--ink);
}

.detail-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 20px;
}

.meta {
  margin: 6px 0 0;
  font-size: 13px;
  color: var(--slate);
}

.dot {
  margin: 0 6px;
}

.panel {
  background: var(--color-surface, #fff);
  border: 1px solid var(--mist);
  border-radius: 10px;
  padding: 16px 18px;
  margin-bottom: 16px;
}

.meta-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 14px;
}

.meta-grid label {
  font-size: 11px;
  color: var(--slate);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  display: block;
  margin-bottom: 4px;
}

.meta-grid p {
  margin: 0;
  font-size: 14px;
}

.meta-grid p.error {
  color: #c2410c;
}

.actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}

.btn {
  padding: 8px 14px;
  border: 1px solid var(--mist);
  border-radius: 6px;
  background: var(--color-surface, #fff);
  font-size: 14px;
  cursor: pointer;
  color: var(--ink);
}

.btn.primary {
  background: var(--signal);
  border-color: var(--signal);
  color: #fff;
}

.btn.ghost {
  background: transparent;
}

.btn.danger {
  border-color: #c2410c;
  color: #c2410c;
}

.btn[disabled] {
  opacity: 0.5;
  cursor: not-allowed;
}

.edit-panel .field {
  margin-bottom: 10px;
}

.edit-panel .field label {
  display: block;
  font-size: 12px;
  color: var(--slate);
  margin-bottom: 4px;
}

.edit-panel .field input,
.edit-panel .field select {
  width: 100%;
  padding: 8px 10px;
  border: 1px solid var(--mist);
  border-radius: 6px;
  font-size: 14px;
}

.overview h2 {
  font-size: 18px;
  margin-bottom: 12px;
}

.overview-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 14px;
}

.overview-grid h3 {
  font-size: 13px;
  margin-bottom: 6px;
  color: var(--slate);
}

.overview-grid ul {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12px;
}

.overview-grid code {
  font-family: var(--font-mono);
  word-break: break-all;
}

.empty {
  color: var(--slate);
  font-style: italic;
}
</style>