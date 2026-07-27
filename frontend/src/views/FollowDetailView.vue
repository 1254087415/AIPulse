<script setup lang="ts">
/**
 * FollowDetailView — UP 主详情页（spec §6.12 + Round-2-Red fixes）
 *
 * 路由：/followed-up/:uid （uid = 数据库 FollowedUp.id 或 B站 mid，
 *        分别走 /overview 与 /by-uid/{platform}/{uid}/overview）
 *
 * 头部：avatar + 昵称 + HealthDot + 启用/停用 tag
 * 元数据 dl：mid / URL / 间隔 / last_checked_at / last_error
 * 合集区块：<CollectionAccordion /> 折叠列表
 * 视频区块：recent_jobs 中提取视频条目，每条带
 *          - 状态徽章
 *          - "在 B 站打开" 链接
 *          - <SummarizeButton /> 集成 spec §6.13
 * 操作：编辑 / 暂停(启用切) / 立即扫描 / 加载更多历史 / 删除
 *
 * 数据来源：GET /api/followed-up/{id}/overview
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  fetchOverview,
  type FollowedUpOverview,
} from '../api/followDetail'
import { followApi } from '../api/follow'
import { safeHref } from '../lib/safeUrl'
import HealthDot from '../components/follow/HealthDot.vue'
import CollectionAccordion from '../components/follow/CollectionAccordion.vue'
import SummarizeButton from '../components/buttons/SummarizeButton.vue'

const route = useRoute()
const router = useRouter()
const uid = computed<string>(() => String(route.params.uid ?? ''))

const overview = ref<FollowedUpOverview | null>(null)
const isLoading = ref<boolean>(true)
const isError = ref<boolean>(false)
const loadError = ref<string>('')
const enablePending = ref<boolean>(false)
const scanPending = ref<boolean>(false)
const loadMorePending = ref<boolean>(false)
const actionMessage = ref<string>('')
const showDeleteConfirm = ref<boolean>(false)

// `enabled` flag is derived from `is_active` server-side; the v0.3 detail
// payload returns `health.is_active`. spec §Q20 expects a UI distinction
// between 启用 / 停用 tags so we compute it inline.
const isEnabled = computed<boolean>(() => overview.value?.health.is_active ?? true)
const isPaused = computed<boolean>(
  () => overview.value?.health.status === 'paused',
)

const initial = computed<string>(() => {
  const name = overview.value?.display_name ?? uid.value
  return (name || '?').slice(0, 1).toUpperCase()
})

const lastCheckedAtText = computed<string>(() => {
  const ts = overview.value?.health.last_checked_at
  if (!ts) return '尚未扫描'
  return new Date(ts).toLocaleString('zh-CN')
})

const recentCollections = computed(
  () => overview.value?.recent_collections ?? [],
)
const recentJobs = computed(() => overview.value?.recent_jobs ?? [])

const safeProfileUrl = computed<string | null>(() =>
  safeHref(overview.value?.profile_url),
)

let loadToken = 0

async function load(targetUid: string): Promise<void> {
  const token = ++loadToken
  if (!targetUid) {
    isError.value = true
    loadError.value = '缺少 UP 主 ID'
    isLoading.value = false
    return
  }
  isLoading.value = true
  isError.value = false
  loadError.value = ''
  try {
    const data = await fetchOverview(targetUid)
    if (token !== loadToken) return
    overview.value = data
  } catch {
    if (token !== loadToken) return
    isError.value = true
    loadError.value = '加载失败，请重试'
  } finally {
    if (token === loadToken) isLoading.value = false
  }
}

onMounted(() => void load(uid.value))
watch(() => uid.value, (next) => void load(next))

// ---- action handlers -----------------------------------------------------

async function onToggleEnabled() {
  if (!overview.value || enablePending.value) return
  enablePending.value = true
  try {
    await followApi.setEnabled(overview.value.id, !isEnabled.value)
    await load(uid.value)
    actionMessage.value = isEnabled.value ? '已恢复' : '已暂停'
  } catch (e: unknown) {
    actionMessage.value = e instanceof Error ? e.message : String(e)
  } finally {
    enablePending.value = false
  }
}

async function onScanNow() {
  if (!overview.value || scanPending.value) return
  scanPending.value = true
  try {
    await followApi.scanNow(overview.value.id)
    actionMessage.value = '已加入扫描队列'
    await load(uid.value)
  } catch (e: unknown) {
    actionMessage.value = e instanceof Error ? e.message : String(e)
  } finally {
    scanPending.value = false
  }
}

async function onLoadMoreHistory() {
  if (!overview.value || loadMorePending.value) return
  loadMorePending.value = true
  try {
    const res = await followApi.loadMoreHistory(overview.value.id, 50)
    if (res.ok) {
      actionMessage.value = `新增 ${res.data.added ?? 0} 条历史视频`
    } else {
      actionMessage.value =
        (res.data.message as string | undefined) ??
        '加载更多历史功能即将上线'
    }
    await load(uid.value)
  } catch (e: unknown) {
    actionMessage.value = e instanceof Error ? e.message : String(e)
  } finally {
    loadMorePending.value = false
  }
}

async function onDelete() {
  if (!overview.value) return
  try {
    await followApi.remove(overview.value.id)
    await router.push({ name: 'dashboard', query: { tab: 'follow-list' } })
  } catch (e: unknown) {
    actionMessage.value = e instanceof Error ? e.message : String(e)
  } finally {
    showDeleteConfirm.value = false
  }
}

function onOpenInBilibili(bvid: string) {
  // safeHref blocks javascript:/vbscript: schemes; bilibili host is allowed
  const url = safeHref(`https://www.bilibili.com/video/${bvid}`)
  if (url) window.open(url, '_blank', 'noopener,noreferrer')
}
</script>

<template>
  <section class="follow-detail-view">
    <div
      v-if="isLoading"
      class="follow-detail-state"
      data-testid="follow-detail-loading"
    >
      加载中…
    </div>

    <div
      v-else-if="isError"
      class="follow-detail-state follow-detail-state--error"
      data-testid="follow-detail-error"
      role="alert"
    >
      <p class="follow-detail-state__title">{{ loadError }}</p>
      <p v-if="uid" class="follow-detail-state__hint">
        未找到 ID <code>{{ uid }}</code> 的关注记录（尝试过数据库 UUID 与 B站 mid 两种 key）。
      </p>
      <p class="follow-detail-state__hint">
        请回
        <router-link to="/dashboard">关注列表</router-link>
        重新选择 UP 主。
      </p>
    </div>

    <template v-else-if="overview">
      <header class="follow-detail-header">
        <div class="follow-detail-avatar" aria-hidden="true">{{ initial }}</div>
        <div class="follow-detail-id">
          <h1
            class="follow-detail-name"
            data-testid="follow-detail-name"
          >
            {{ overview.display_name }}
          </h1>
          <div class="follow-detail-tags">
            <HealthDot
              :status="overview.health.health"
              data-testid="follow-detail-health-dot"
            />
            <span
              class="follow-detail-tag"
              data-testid="follow-detail-platform"
            >
              {{ overview.platform }}
            </span>
            <span class="follow-detail-tag follow-detail-tag--muted">
              健康：{{ overview.health.health }}
            </span>
            <span
              v-if="!isEnabled"
              class="follow-detail-tag follow-detail-tag--muted"
              data-testid="follow-detail-disabled-tag"
            >
              已停用
            </span>
            <span
              v-else-if="isPaused"
              class="follow-detail-tag follow-detail-tag--muted"
            >
              已暂停
            </span>
          </div>
        </div>
        <div class="follow-detail-actions">
          <button
            class="follow-detail-btn"
            type="button"
            data-testid="scan-now-btn"
            :disabled="scanPending"
            @click="onScanNow"
          >
            {{ scanPending ? '扫描中…' : '立即扫描' }}
          </button>
          <button
            class="follow-detail-btn"
            type="button"
            data-testid="toggle-enabled-btn"
            :disabled="enablePending"
            @click="onToggleEnabled"
          >
            {{ isEnabled ? '暂停' : '恢复' }}
          </button>
          <button class="follow-detail-btn" type="button">编辑</button>
          <button
            class="follow-detail-btn follow-detail-btn--danger"
            type="button"
            data-testid="delete-btn"
            @click="showDeleteConfirm = true"
          >
            删除
          </button>
        </div>
      </header>

      <p
        v-if="actionMessage"
        class="follow-detail-action-message"
        data-testid="follow-detail-action-message"
        role="status"
      >
        {{ actionMessage }}
      </p>

      <section class="follow-detail-meta">
        <dl>
          <dt>mid</dt>
          <dd><code>{{ overview.uid }}</code></dd>
          <dt>主页 URL</dt>
          <dd>
            <a
              v-if="safeProfileUrl"
              :href="safeProfileUrl"
              target="_blank"
              rel="noopener noreferrer"
            >
              {{ overview.profile_url }}
            </a>
            <span v-else>{{ overview.profile_url }}</span>
          </dd>
          <dt>采集策略</dt>
          <dd>
            <code>
              {{ overview.health.fetch_interval_minutes }} 分钟 / 次
            </code>
          </dd>
          <dt>上次扫描</dt>
          <dd>{{ lastCheckedAtText }}</dd>
          <template v-if="overview.health.last_error">
            <dt>最近错误</dt>
            <dd class="follow-detail-meta-error">
              {{ overview.health.last_error }}
            </dd>
          </template>
        </dl>
      </section>

      <section
        v-if="recentCollections.length > 0"
        class="follow-detail-collections"
      >
        <h2>合集（{{ recentCollections.length }}）</h2>
        <div class="follow-detail-collection-list">
          <CollectionAccordion
            v-for="c in recentCollections"
            :key="c.id"
            :collection="c"
          />
        </div>
        <button
          class="follow-detail-btn"
          type="button"
          data-testid="load-more-history-btn"
          :disabled="loadMorePending"
          @click="onLoadMoreHistory"
        >
          {{
            loadMorePending
              ? '加载中…'
              : '加载更多历史'
          }}
        </button>
      </section>

      <section
        v-else
        class="follow-detail-empty"
        data-testid="follow-detail-empty-state"
      >
        <p>暂无合集与历史视频，点击<strong>立即扫描</strong>开始首次抓取。</p>
      </section>

      <section
        v-if="recentJobs.length > 0"
        class="follow-detail-jobs"
      >
        <h2>最近任务（{{ recentJobs.length }}）</h2>
        <ul class="follow-detail-job-list">
          <li
            v-for="j in recentJobs"
            :key="j.id"
            class="follow-detail-job-row"
            data-testid="recent-job"
          >
            <span class="follow-detail-job-title">
              {{ j.title || j.video_id }}
            </span>
            <span
              class="follow-detail-job-status"
              :data-status="j.status"
            >
              {{ j.status }}
            </span>
            <a
              class="follow-detail-open-link"
              :href="`https://www.bilibili.com/video/${j.video_id}`"
              target="_blank"
              rel="noopener noreferrer"
              data-testid="open-bilibili-link"
              @click="(e) => { if (e.metaKey || e.ctrlKey) return; e.preventDefault(); onOpenInBilibili(j.video_id) }"
            >
              在 B 站打开
            </a>
            <SummarizeButton
              :bvid="j.video_id"
              :has-summary="j.status === 'completed' && !!j.note_path"
              :obsidian-path="j.note_path"
              data-testid="summarize-button"
            />
          </li>
        </ul>
      </section>
      <p
        v-else-if="recentCollections.length === 0"
        class="follow-detail-empty-jobs"
        data-testid="follow-detail-empty-jobs"
      >
        尚无总结任务。<strong>立即扫描</strong>后会出现第一批可处理视频。
      </p>
    </template>

    <div
      v-if="showDeleteConfirm"
      class="follow-detail-confirm"
      role="alertdialog"
      data-testid="delete-confirm"
    >
      <p>
        删除该 UP 主？「{{ overview?.display_name }}」及其所有关注历史将被删除，
        此操作不可恢复。
      </p>
      <div class="follow-detail-confirm__actions">
        <button
          type="button"
          class="follow-detail-btn"
          data-testid="cancel-delete"
          @click="showDeleteConfirm = false"
        >
          取消
        </button>
        <button
          type="button"
          class="follow-detail-btn follow-detail-btn--danger"
          data-testid="confirm-delete"
          @click="onDelete"
        >
          删除
        </button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.follow-detail-view {
  display: flex;
  flex-direction: column;
  gap: 20px;
  max-width: 880px;
  margin: 0 auto;
  padding: 4px 0;
}

.follow-detail-state {
  padding: 24px;
  background: var(--surface-elevated);
  border: 1px dashed var(--border-subtle);
  border-radius: var(--radius-md);
  text-align: center;
  color: var(--text-secondary);
}

.follow-detail-state--error {
  border-style: solid;
  color: var(--status-red);
  display: flex;
  flex-direction: column;
  gap: 8px;
  align-items: center;
}

.follow-detail-state__title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
}

.follow-detail-state__hint {
  margin: 0;
  font-size: 13px;
  color: var(--text-secondary);
}

.follow-detail-state__hint a {
  color: var(--accent-coral);
  text-decoration: underline;
}

.follow-detail-action-message {
  margin: 0;
  padding: 8px 12px;
  border-radius: var(--radius-sm);
  background: var(--surface-bg);
  border: 1px solid var(--border-subtle);
  color: var(--text-secondary);
  font-size: 13px;
}

.follow-detail-header {
  display: grid;
  grid-template-columns: auto 1fr auto;
  gap: 16px;
  align-items: center;
  background: var(--surface-elevated);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  padding: 16px;
}

.follow-detail-avatar {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background: var(--accent-coral);
  color: var(--surface-elevated);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
  font-weight: 600;
  text-transform: uppercase;
}

.follow-detail-id h1 {
  margin: 0 0 8px;
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
}

.follow-detail-tags {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.follow-detail-tag {
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 12px;
  background: color-mix(in srgb, var(--accent-coral) 16%, transparent);
  color: var(--accent-coral);
  border: 1px solid color-mix(in srgb, var(--accent-coral) 28%, transparent);
}

.follow-detail-tag--muted {
  background: var(--surface-bg);
  color: var(--text-secondary);
  border-color: var(--border-subtle);
}

.follow-detail-actions {
  display: flex;
  gap: 8px;
}

.follow-detail-btn {
  height: 32px;
  padding: 0 12px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-subtle);
  background: transparent;
  color: var(--text-primary);
  font-size: 13px;
  cursor: pointer;
}

.follow-detail-btn:hover:not(:disabled) {
  background: var(--surface-elevated-hover, rgba(0, 0, 0, 0.04));
}

.follow-detail-btn:disabled {
  cursor: default;
  opacity: 0.55;
}

.follow-detail-btn--danger {
  color: var(--status-red);
  border-color: color-mix(in srgb, var(--status-red) 30%, transparent);
}

.follow-detail-btn--danger:hover:not(:disabled) {
  background: color-mix(in srgb, var(--status-red) 12%, transparent);
}

.follow-detail-meta {
  background: var(--surface-elevated);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  padding: 16px;
}

.follow-detail-meta dl {
  display: grid;
  grid-template-columns: 120px 1fr;
  gap: 8px 16px;
  margin: 0;
  font-size: 13px;
}

.follow-detail-meta dt {
  color: var(--text-secondary);
  font-weight: 500;
}

.follow-detail-meta dd {
  margin: 0;
  word-break: break-all;
  color: var(--text-primary);
}

.follow-detail-meta a {
  color: var(--accent-coral);
  text-decoration: none;
}

.follow-detail-meta a:hover {
  text-decoration: underline;
}

.follow-detail-meta-error {
  color: var(--status-red);
}

.follow-detail-collections h2,
.follow-detail-jobs h2 {
  margin: 0 0 12px;
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.follow-detail-collection-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 12px;
}

.follow-detail-empty,
.follow-detail-empty-jobs {
  margin: 0;
  padding: 16px;
  background: var(--surface-bg);
  border: 1px dashed var(--border-subtle);
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  font-size: 13px;
  text-align: center;
}

.follow-detail-job-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.follow-detail-job-row {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 12px;
  padding: 10px 14px;
  background: var(--surface-elevated);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
}

.follow-detail-job-title {
  color: var(--text-primary);
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
  min-width: 0;
}

.follow-detail-job-status {
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 500;
  background: var(--surface-bg);
  color: var(--text-secondary);
  border: 1px solid var(--border-subtle);
  text-transform: lowercase;
}

.follow-detail-job-status[data-status='done'],
.follow-detail-job-status[data-status='completed'] {
  background: color-mix(in srgb, var(--status-green, #4caf50) 16%, transparent);
  color: var(--status-green, #4caf50);
  border-color: color-mix(in srgb, var(--status-green, #4caf50) 30%, transparent);
}

.follow-detail-job-status[data-status='failed'] {
  background: color-mix(in srgb, var(--status-red) 16%, transparent);
  color: var(--status-red);
  border-color: color-mix(in srgb, var(--status-red) 30%, transparent);
}

.follow-detail-job-status[data-status='running'],
.follow-detail-job-status[data-status='pending'] {
  background: color-mix(in srgb, var(--status-amber, #ffb300) 16%, transparent);
  color: var(--status-amber, #ffb300);
  border-color: color-mix(in srgb, var(--status-amber, #ffb300) 30%, transparent);
}

.follow-detail-open-link {
  color: var(--accent-coral);
  text-decoration: none;
  font-size: 13px;
  white-space: nowrap;
}

.follow-detail-open-link:hover {
  text-decoration: underline;
}

.follow-detail-confirm {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.35);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}

.follow-detail-confirm::after {
  content: '';
}

.follow-detail-confirm {
  margin: auto;
  max-width: 420px;
  background: var(--surface-elevated);
  border-radius: var(--radius-md);
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.18);
}

.follow-detail-confirm p {
  margin: 0;
  color: var(--text-primary);
  font-size: 14px;
  line-height: 1.5;
}

.follow-detail-confirm__actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}
</style>
