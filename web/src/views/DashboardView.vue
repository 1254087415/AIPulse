<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useQuery } from '@tanstack/vue-query'
import { fetchHotspots, HOTSPOT_PAGE_LIMIT } from '../api/hotspots'
import HotspotList from '../components/hotspot/HotspotList.vue'
import { useSse } from '../composables/useSse'
import { useDebounce } from '../composables/useDebounce'

const route = useRoute()
const router = useRouter()

interface QueryParams {
  q: string
  source: string
  importance: string
  category: string
  sort: string
  order: string
  page: number
}

function parseQueryParam(value: unknown): string {
  if (Array.isArray(value)) {
    return value.length > 0 && value[0] ? String(value[0]) : ''
  }
  return value ? String(value) : ''
}

function parseQueryParams(query: Record<string, unknown>): QueryParams {
  const parsedPage = parseInt(parseQueryParam(query.page), 10)
  return {
    q: parseQueryParam(query.q),
    source: parseQueryParam(query.source),
    importance: parseQueryParam(query.importance),
    category: parseQueryParam(query.category),
    sort: parseQueryParam(query.sort) || 'heat_score',
    order: parseQueryParam(query.order) || 'desc',
    page: Number.isFinite(parsedPage) && parsedPage > 0 ? parsedPage : 1,
  }
}

function buildQueryParams(
  filters: Omit<QueryParams, 'page'>,
  currentPage: number,
): Record<string, string> {
  const query: Record<string, string> = {}
  if (filters.q) query.q = filters.q
  if (filters.source) query.source = filters.source
  if (filters.importance) query.importance = filters.importance
  if (filters.category) query.category = filters.category
  if (filters.sort && filters.sort !== 'heat_score') query.sort = filters.sort
  if (filters.order && filters.order !== 'desc') query.order = filters.order
  if (currentPage > 1) query.page = String(currentPage)
  return query
}

const initialParams = parseQueryParams(route.query as Record<string, unknown>)

const q = ref(initialParams.q)
const debouncedQ = useDebounce(q, 300)
const source = ref(initialParams.source)
const importance = ref(initialParams.importance)
const category = ref(initialParams.category)
const sort = ref(initialParams.sort)
const order = ref(initialParams.order)
const page = ref(initialParams.page)

watch(
  () => [q.value, source.value, importance.value, category.value, sort.value],
  () => {
    page.value = 1
  },
)

watch(
  () => [q.value, source.value, importance.value, category.value, sort.value, order.value, page.value],
  () => {
    const nextQuery = buildQueryParams(
      {
        q: q.value,
        source: source.value,
        importance: importance.value,
        category: category.value,
        sort: sort.value,
        order: order.value,
      },
      page.value,
    )
    if (JSON.stringify(nextQuery) !== JSON.stringify(route.query)) {
      router.replace({ query: nextQuery })
    }
  },
)

watch(
  () => route.query,
  (newQuery) => {
    const parsed = parseQueryParams(newQuery as Record<string, unknown>)
    q.value = parsed.q
    source.value = parsed.source
    importance.value = parsed.importance
    category.value = parsed.category
    sort.value = parsed.sort
    order.value = parsed.order
    page.value = parsed.page
  },
  { deep: true },
)

function toggleOrder() {
  order.value = order.value === 'desc' ? 'asc' : 'desc'
}

function nextPage() {
  page.value += 1
}

function prevPage() {
  if (page.value > 1) {
    page.value -= 1
  }
}

const { data, isLoading, error } = useQuery({
  queryKey: ['hotspots', page, debouncedQ, source, importance, category, sort, order],
  queryFn: () =>
    fetchHotspots({
      page: String(page.value),
      limit: String(HOTSPOT_PAGE_LIMIT),
      ...(debouncedQ.value ? { q: debouncedQ.value } : {}),
      ...(source.value ? { source: source.value } : {}),
      ...(importance.value ? { importance: importance.value } : {}),
      ...(category.value ? { category: category.value } : {}),
      sort: sort.value,
      order: order.value,
    }),
})

useSse('/sse/hotspots')

const totalPages = computed(() => {
  if (!data.value) return 0
  return Math.ceil(data.value.meta.total / data.value.meta.limit)
})
</script>

<template>
  <div class="page">
    <header class="page-header">
      <div class="page-title">
        <h1>AI 热点</h1>
        <p class="subtitle">实时 AI 热度监测</p>
      </div>
      <div v-if="data" class="readout" aria-label="热点总数">
        <span class="readout-value">{{ data.meta.total }}</span>
        <span class="readout-label">条热点</span>
      </div>
    </header>

    <section class="filter-bar" aria-label="筛选与排序">
      <input
        v-model="q"
        type="search"
        placeholder="搜索标题或摘要…"
        aria-label="搜索标题或摘要"
        autocomplete="off"
        class="filter-input"
      />

      <select v-model="source" data-testid="source-filter" aria-label="来源" class="filter-select">
        <option value="">全部来源</option>
        <option value="news">news</option>
        <option value="github">github</option>
        <option value="arxiv">arxiv</option>
        <option value="huggingface">huggingface</option>
        <option value="social">social</option>
      </select>

      <select
        v-model="importance"
        data-testid="importance-filter"
        aria-label="重要性"
        class="filter-select"
      >
        <option value="">全部重要性</option>
        <option value="low">low</option>
        <option value="medium">medium</option>
        <option value="high">high</option>
        <option value="critical">critical</option>
      </select>

      <select
        v-model="category"
        data-testid="category-filter"
        aria-label="分类"
        class="filter-select"
      >
        <option value="">全部分类</option>
        <option value="ai-models">ai-models</option>
        <option value="ai-products">ai-products</option>
        <option value="industry">industry</option>
        <option value="paper">paper</option>
        <option value="tip">tip</option>
      </select>

      <div class="sort-group">
        <select v-model="sort" data-testid="sort-select" aria-label="排序字段" class="filter-select">
          <option value="heat_score">热度</option>
          <option value="published_at">时间</option>
        </select>
        <button
          type="button"
          data-testid="sort-order"
          aria-label="切换排序方向"
          class="btn"
          @click="toggleOrder"
        >
          {{ order === 'desc' ? '降序' : '升序' }}
        </button>
      </div>
    </section>

    <div v-if="isLoading" class="state state-loading" role="status" aria-live="polite">
      正在同步信号…
    </div>

    <div v-else-if="error" class="state state-error" role="alert" aria-live="polite">
      信号中断：{{ error?.message }}。请检查后端服务是否运行。
    </div>

    <div v-else-if="data && data.data.length === 0" class="state state-empty">
      还没有热点。去「关键词」添加关注词，系统每 30 分钟会同步一次。
    </div>

    <HotspotList v-else :hotspots="data?.data ?? []" />

    <nav
      v-if="data && totalPages > 1"
      data-testid="pagination"
      class="pagination"
      aria-label="分页"
    >
      <button
        type="button"
        class="btn"
        :disabled="page <= 1"
        aria-label="上一页"
        @click="prevPage"
      >
        上一页
      </button>
      <span data-testid="page-info" class="page-info">第 {{ page }} / {{ totalPages }} 页</span>
      <button
        type="button"
        data-testid="next-page"
        class="btn"
        :disabled="page >= totalPages"
        aria-label="下一页"
        @click="nextPage"
      >
        下一页
      </button>
    </nav>
  </div>
</template>

<style scoped>
.filter-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin-bottom: 20px;
}

.filter-input,
.filter-select {
  min-width: 140px;
  padding: 8px 12px;
  border: 1px solid var(--color-border, #d1d5db);
  border-radius: 6px;
  background: var(--color-surface, #fff);
  color: var(--color-text, #111827);
  font-size: 14px;
}

.filter-input {
  flex: 1 1 200px;
}

.sort-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
  margin-top: 24px;
}

.page-info {
  font-size: 14px;
  color: var(--color-text-secondary, #6b7280);
}
</style>
