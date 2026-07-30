<script setup lang="ts">
/**
 * FollowDetailView — UP 主详情页（spec §6.12 Q20）
 *
 * 路由：/followed-up/:uid
 *
 *  - 头部：UP 主基本信息卡（64x64 头像 + 昵称 + HealthDot + 状态徽章）
 *  - 元数据 dl：mid / URL / 策略 / 间隔 / last_checked_at / last_error
 *  - 合集区块：<CollectionAccordion /> 折叠列表，展开时显示合集内视频
 *  - 视频区块：<VideoListItem /> 列表，默认 20 条/页（useInfiniteQuery）
 *  - 散落视频区块：collection_id 为空的视频，标 variant="orphan"
 *  - 操作：立即扫描 / 暂停（恢复）/ 编辑占位 / 删除（ConfirmModal）
 *  - 返回按钮：router.back()
 *  - 「在 B 站打开」链接：window.open(https://www.bilibili.com/video/{bvid})
 */
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/vue-query'
import {
  fetchDetail,
  listVideos,
  type FollowedUpVideo,
} from '../api/followDetail'
import { followApi } from '../api/follow'
import VideoListItem from '../components/follow/VideoListItem.vue'
import CollectionAccordion from '../components/follow/CollectionAccordion.vue'
import HealthDot from '../components/follow/HealthDot.vue'
import AppButton from '../components/ui/AppButton.vue'
import ConfirmModal from '../components/ui/ConfirmModal.vue'
import { formatDateTime, formatInterval, formatStatusLabel } from '../lib/format'
import { summarizeError } from '../lib/errorMessage'

const route = useRoute()
const router = useRouter()
const qc = useQueryClient()

const uid = computed(() => String(route.params.uid ?? ''))

const showDeleteModal = ref(false)

const { data: detail, isLoading, isError } = useQuery({
  queryKey: ['follows', uid, 'detail'],
  queryFn: () => fetchDetail(uid.value),
  enabled: computed(() => !!uid.value),
})

const {
  data: videosData,
  fetchNextPage,
  hasNextPage,
  isFetchingNextPage,
} = useInfiniteQuery({
  queryKey: ['follows', uid, 'videos'],
  queryFn: ({ pageParam = 0 }) =>
    listVideos(uid.value, { offset: pageParam, limit: 20 }),
  initialPageParam: 0,
  getNextPageParam: (last) => last.nextOffset ?? null,
  enabled: computed(() => !!uid.value),
})

const scanNowMut = useMutation({
  mutationFn: () => followApi.scanNow(uid.value),
  onSuccess: () => {
    qc.invalidateQueries({ queryKey: ['follows', uid, 'detail'] })
    qc.invalidateQueries({ queryKey: ['follows', uid, 'videos'] })
  },
})

const toggleEnabledMut = useMutation({
  mutationFn: (enabled: boolean) => followApi.setEnabled(uid.value, enabled),
  onSuccess: () => {
    qc.invalidateQueries({ queryKey: ['follows', uid, 'detail'] })
  },
})

const removeMut = useMutation({
  mutationFn: () => followApi.remove(uid.value),
  onSuccess: () => {
    showDeleteModal.value = false
    router.push('/dashboard?tab=follow-list')
  },
})

const allVideos = computed<FollowedUpVideo[]>(() => {
  const pages = videosData.value?.pages ?? []
  return pages.flatMap((p) => p.items)
})

const collections = computed(() => detail.value?.collections ?? [])
const orphanVideos = computed(() => allVideos.value.filter((v) => !v.collection_id))

const lastCheckedText = computed(() => {
  const ts = detail.value?.last_checked_at
  if (!ts) return '尚未扫描'
  return formatDateTime(ts)
})

const lastErrorSummary = computed(() => summarizeError(detail.value?.last_error))

function onScanNow() {
  if (scanNowMut.isPending.value) return
  scanNowMut.mutate()
}

function onToggleEnabled() {
  if (!detail.value || toggleEnabledMut.isPending.value) return
  toggleEnabledMut.mutate(!detail.value.enabled)
}

function onLoadMore() {
  if (hasNextPage.value && !isFetchingNextPage.value) fetchNextPage()
}

function onOpenBilibili(bvid: string) {
  window.open(`https://www.bilibili.com/video/${bvid}`, '_blank', 'noopener,noreferrer')
}

function onBack() {
  router.back()
}

function onOpenDelete() {
  showDeleteModal.value = true
}

function onCancelDelete() {
  showDeleteModal.value = false
}

function onConfirmDelete() {
  removeMut.mutate()
}
</script>

<template>
  <div class="follow-detail-view" data-testid="follow-detail-view">
    <AppButton
      size="sm"
      variant="ghost"
      class="follow-detail-back-btn"
      data-testid="back-btn"
      @click="onBack"
    >
      ← 返回
    </AppButton>

    <div
      v-if="isLoading"
      class="follow-detail-state follow-detail-state--loading"
      data-testid="follow-detail-loading"
    >
      加载中…
    </div>

    <div
      v-else-if="isError || !detail"
      class="follow-detail-state follow-detail-state--error"
      data-testid="follow-detail-error"
      role="alert"
    >
      加载失败，请稍后重试。
    </div>

    <template v-else>
      <header class="follow-detail-header">
        <img
          :src="detail.avatar"
          :alt="detail.name"
          class="follow-detail-avatar"
          data-testid="follow-detail-avatar"
          referrerpolicy="no-referrer"
          @error="($event.target as HTMLImageElement).style.visibility = 'hidden'"
        />
        <div class="follow-detail-id">
          <h1 data-testid="follow-detail-name">{{ detail.name }}</h1>
          <div class="follow-detail-status">
            <HealthDot :status="detail.health" />
            <span
              class="tag"
              :class="`follow-detail-tag--${detail.health}`"
            >
              {{ formatStatusLabel(detail.health) }}
            </span>
            <span v-if="!detail.enabled" class="tag follow-detail-tag--muted">
              已停用
            </span>
          </div>
        </div>
        <div class="follow-detail-actions">
          <AppButton
            size="sm"
            variant="secondary"
            :loading="scanNowMut.isPending.value"
            data-testid="scan-now-btn"
            @click="onScanNow"
          >
            {{ scanNowMut.isPending.value ? '扫描中…' : '立即扫描' }}
          </AppButton>
          <AppButton
            size="sm"
            variant="secondary"
            :loading="toggleEnabledMut.isPending.value"
            data-testid="toggle-enabled-btn"
            @click="onToggleEnabled"
          >
            {{ detail.enabled ? '暂停' : '恢复' }}
          </AppButton>
          <AppButton
            size="sm"
            variant="secondary"
            data-testid="edit-btn"
          >
            编辑
          </AppButton>
          <AppButton
            size="sm"
            variant="danger"
            data-testid="delete-btn"
            @click="onOpenDelete"
          >
            删除
          </AppButton>
        </div>
      </header>

      <section class="follow-detail-meta panel">
        <dl class="follow-detail-meta">
          <dt>mid</dt>
          <dd><code>{{ detail.mid }}</code></dd>
          <dt>主页 URL</dt>
          <dd>
            <a :href="detail.url" target="_blank" rel="noopener noreferrer">
              {{ detail.url }}
            </a>
          </dd>
          <dt>策略</dt>
          <dd><code>{{ detail.strategy }}</code></dd>
          <dt>间隔</dt>
          <dd><code>{{ formatInterval(detail.interval_minutes) }}</code></dd>
          <dt>上次扫描</dt>
          <dd>
            <time
              v-if="detail.last_checked_at"
              :datetime="detail.last_checked_at"
              data-testid="last-checked-at"
            >{{ lastCheckedText }}</time>
            <span v-else class="follow-detail-slate">尚未扫描</span>
          </dd>
          <template v-if="detail.last_error">
            <dt>最近错误</dt>
            <dd
              class="follow-detail-state--error follow-detail-last-error"
              data-testid="last-error"
              :title="lastErrorSummary.technical ?? detail.last_error"
            >
              {{ lastErrorSummary.summary }}
            </dd>
          </template>
        </dl>
      </section>

      <section
        v-if="collections.length > 0"
        class="follow-detail-collections"
        data-testid="collections-section"
      >
        <h2>合集（{{ collections.length }}）</h2>
        <CollectionAccordion
          v-for="grp in collections"
          :key="grp.id"
          :collection="grp"
          @open-bilibili="onOpenBilibili"
        />
      </section>

      <section
        v-if="allVideos.length > 0 || hasNextPage"
        class="follow-detail-videos"
        data-testid="videos-section"
      >
        <h2>
          视频（最近 {{ allVideos.length }} 条）
          <AppButton
            v-if="hasNextPage"
            size="sm"
            variant="secondary"
            class="follow-detail-load-more"
            :loading="isFetchingNextPage"
            data-testid="load-more-btn"
            @click="onLoadMore"
          >
            {{ isFetchingNextPage ? '加载中…' : '加载更多历史' }}
          </AppButton>
        </h2>
        <ul class="follow-detail-video-list">
          <VideoListItem
            v-for="v in allVideos"
            :key="`${v.bvid}--${v.hotspot_id ?? ''}`"
            :video="v"
            @open-bilibili="onOpenBilibili"
          />
        </ul>
      </section>

      <section
        v-if="orphanVideos.length > 0"
        class="follow-detail-orphan"
        data-testid="orphan-videos-section"
      >
        <h3 data-testid="orphan-videos-title">
          散落视频（不在合集内，{{ orphanVideos.length }} 条）
        </h3>
        <ul>
          <VideoListItem
            v-for="v in orphanVideos"
            :key="`orphan-${v.bvid}--${v.hotspot_id ?? ''}`"
            :video="v"
            variant="orphan"
            @open-bilibili="onOpenBilibili"
          />
        </ul>
      </section>
    </template>

    <ConfirmModal
      :show="showDeleteModal"
      title="删除该 UP 主？"
      :message="`「${detail?.name ?? ''}」及其所有关注历史将被删除，此操作不可恢复。`"
      confirm-text="删除"
      danger
      :loading="removeMut.isPending.value"
      test-id-prefix="delete-confirm"
      @cancel="onCancelDelete"
      @confirm="onConfirmDelete"
    />
  </div>
</template>

<style scoped>
.follow-detail-view {
  display: flex;
  flex-direction: column;
  gap: 20px;
  max-width: 960px;
  margin: 0 auto;
  padding: 16px 0;
  height: 100%;
  overflow-y: auto;
}

.follow-detail-back-btn {
  align-self: flex-start;
}

.follow-detail-state {
  padding: 24px;
  background: var(--surface-elevated, #fff);
  border: 1px dashed var(--border-subtle, #e5e5e5);
  border-radius: var(--radius-md, 10px);
  text-align: center;
  color: var(--text-secondary, #6b6b6b);
}

.follow-detail-state--error {
  border-style: solid;
  color: var(--status-red, #ef4444);
}

.follow-detail-last-error {
  color: var(--status-red, #ef4444);
}

.follow-detail-header {
  display: grid;
  grid-template-columns: auto 1fr auto;
  gap: 16px;
  align-items: center;
  background: var(--surface-elevated, #fff);
  border: 1px solid var(--border-subtle, #e5e5e5);
  border-radius: var(--radius-md, 10px);
  padding: 16px;
}

.follow-detail-avatar {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  object-fit: cover;
  background: var(--mist, #e5e5e5);
}

.follow-detail-id h1 {
  margin: 0 0 8px;
  font-size: 22px;
  font-weight: 600;
  color: var(--text-primary, #1a1a1a);
}

.follow-detail-status {
  display: flex;
  align-items: center;
  gap: 8px;
}

.follow-detail-tag--muted,
.follow-detail-tag--healthy,
.follow-detail-tag--warning,
.follow-detail-tag--error {
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 12px;
  border: 1px solid currentColor;
}

.follow-detail-tag--muted {
  background: var(--surface-bg, #fafafa);
  color: var(--text-secondary, #6b6b6b);
  border-color: var(--border-subtle, #e5e5e5);
}

.follow-detail-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.follow-detail-meta.panel {
  display: block;
  background: var(--surface-elevated, #fff);
  border: 1px solid var(--border-subtle, #e5e5e5);
  border-radius: var(--radius-md, 10px);
  padding: 16px;
}

.follow-detail-meta__list {
  display: grid;
  grid-template-columns: 120px 1fr;
  gap: 8px 16px;
  margin: 0;
  font-size: 13px;
}

.follow-detail-meta {
  display: grid;
  grid-template-columns: 120px 1fr;
  gap: 8px 16px;
  margin: 0;
  font-size: 13px;
}

.follow-detail-meta dt {
  color: var(--text-secondary, #6b6b6b);
  font-weight: 500;
}

.follow-detail-meta dd {
  margin: 0;
  word-break: break-all;
  color: var(--text-primary, #1a1a1a);
}

.follow-detail-slate {
  color: var(--text-secondary, #6b6b6b);
}

.follow-detail-collections h2,
.follow-detail-videos h2 {
  margin: 0 0 12px;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary, #1a1a1a);
  display: flex;
  align-items: center;
  gap: 8px;
}

.follow-detail-video-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.follow-detail-orphan {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px dashed var(--border-subtle, #e5e5e5);
}

.follow-detail-orphan h3 {
  font-size: 14px;
  font-weight: 500;
  margin: 0 0 12px;
  color: var(--text-primary, #1a1a1a);
}

.follow-detail-orphan ul {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
</style>
