<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { fetchUpDetail, fetchUpHotspots, fetchUpSyncHistory, type UpHotspot, type UpSyncHistory } from '../api/upDetail'
import { syncFollowed } from '../api/followedUp'

const route = useRoute()
const key = computed(() => String(route.params.uid ?? ''))
const followed = ref<Awaited<ReturnType<typeof fetchUpDetail>> | null>(null)
const hotspots = ref<UpHotspot[]>([])
const history = ref<UpSyncHistory[]>([])
const loading = ref(true)
const error = ref('')
const syncing = ref(false)
const message = ref('')

async function load(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    const [detail, relatedHotspots, syncHistory] = await Promise.all([
      fetchUpDetail(key.value),
      fetchUpHotspots(key.value),
      fetchUpSyncHistory(key.value),
    ])
    followed.value = detail
    hotspots.value = relatedHotspots
    history.value = syncHistory
  } catch (cause: unknown) {
    error.value = cause instanceof Error ? cause.message : '加载 UP 主详情失败'
  } finally {
    loading.value = false
  }
}

async function sync(): Promise<void> {
  if (!followed.value || syncing.value) return
  syncing.value = true
  message.value = ''
  try {
    await syncFollowed(followed.value.id)
    message.value = '同步已提交'
    await load()
  } catch (cause: unknown) {
    message.value = cause instanceof Error ? cause.message : '同步失败'
  } finally {
    syncing.value = false
  }
}

onMounted(() => void load())
</script>

<template>
  <main class="up-detail" data-testid="up-detail">
    <nav class="up-detail__nav"><router-link to="/dashboard?tab=follow-list">← 返回关注列表</router-link></nav>
    <p v-if="loading" class="up-detail__state">加载中…</p>
    <p v-else-if="error" class="up-detail__state up-detail__state--error" role="alert">{{ error }}</p>
    <template v-else-if="followed">
      <header class="up-detail__hero">
        <div>
          <p class="up-detail__eyebrow">{{ followed.platform }}</p>
          <h1>{{ followed.display_name }}</h1>
          <p class="up-detail__uid">uid: {{ followed.uid }}</p>
          <a :href="followed.profile_url" target="_blank" rel="noopener noreferrer">打开主页</a>
        </div>
        <div class="up-detail__status">
          <span>健康：{{ followed.health }}</span>
          <span>{{ followed.is_active ? '启用' : '已暂停' }}</span>
          <button type="button" data-testid="sync-up" :disabled="syncing" @click="sync">{{ syncing ? '同步中…' : '立即同步' }}</button>
        </div>
      </header>
      <p v-if="message" class="up-detail__message" role="status">{{ message }}</p>
      <section aria-labelledby="hotspots-title">
        <div class="up-detail__section-heading"><h2 id="hotspots-title">关联热点</h2><span>{{ hotspots.length }} 条</span></div>
        <p v-if="hotspots.length === 0" class="up-detail__empty">暂无关联热点</p>
        <ul v-else class="up-detail__list">
          <li v-for="hotspot in hotspots" :key="hotspot.id"><a :href="hotspot.url" target="_blank" rel="noopener noreferrer">{{ hotspot.title }}</a><span>{{ hotspot.source_type }}</span></li>
        </ul>
      </section>
      <section aria-labelledby="history-title">
        <div class="up-detail__section-heading"><h2 id="history-title">同步历史</h2><span>{{ history.length }} 次</span></div>
        <p v-if="history.length === 0" class="up-detail__empty">暂无同步记录</p>
        <ol v-else class="up-detail__timeline">
          <li v-for="entry in history" :key="entry.id"><strong>{{ entry.status }}</strong><span>{{ entry.title || entry.video_id }}</span><time>{{ entry.created_at ? new Date(entry.created_at).toLocaleString('zh-CN') : '时间未知' }}</time></li>
        </ol>
      </section>
    </template>
  </main>
</template>

<style scoped>
.up-detail { max-width: 1000px; margin: 0 auto; padding: 28px 32px 56px; color: var(--text-primary); }
.up-detail__nav { margin-bottom: 20px; font-size: 13px; }
.up-detail a { color: var(--accent-coral); }
.up-detail__hero { display: flex; justify-content: space-between; gap: 24px; padding: 28px; border: 1px solid var(--border-subtle); border-radius: var(--radius-md); background: var(--surface-elevated); }
.up-detail h1 { margin: 4px 0 8px; font-size: 30px; }
.up-detail__eyebrow, .up-detail__uid { margin: 0; color: var(--text-secondary); font-size: 13px; }
.up-detail__status { display: flex; align-items: flex-end; flex-direction: column; gap: 12px; font-size: 13px; color: var(--text-secondary); }
.up-detail button { padding: 9px 15px; border: 0; border-radius: var(--radius-sm); background: var(--accent-coral); color: white; cursor: pointer; }
.up-detail button:disabled { opacity: .6; cursor: wait; }
.up-detail__message { color: var(--status-green, #4d9f72); }
.up-detail section { margin-top: 24px; padding: 22px 24px; border: 1px solid var(--border-subtle); border-radius: var(--radius-md); background: var(--surface-elevated); }
.up-detail__section-heading { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }
.up-detail h2 { margin: 0 0 14px; font-size: 18px; }
.up-detail__section-heading span, .up-detail__list li span, .up-detail__timeline time { color: var(--text-secondary); font-size: 12px; }
.up-detail__list, .up-detail__timeline { display: grid; gap: 10px; margin: 0; padding: 0; list-style: none; }
.up-detail__list li, .up-detail__timeline li { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 10px 0; border-bottom: 1px solid var(--border-subtle); }
.up-detail__timeline li { justify-content: flex-start; flex-wrap: wrap; }
.up-detail__timeline strong { color: var(--accent-coral); }
.up-detail__timeline time { margin-left: auto; }
.up-detail__empty, .up-detail__state { color: var(--text-secondary); }
.up-detail__state--error { color: var(--status-red); }
@media (max-width: 640px) { .up-detail { padding: 20px 16px; } .up-detail__hero { flex-direction: column; } .up-detail__status { align-items: flex-start; } .up-detail__timeline time { margin-left: 0; width: 100%; } }
</style>
