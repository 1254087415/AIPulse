/**
 * Round 7 — spec §6.12 FollowDetailView 完整实现 + §2.4 TC-UI-FOLLOW-DETAIL-*
 *
 * 1:1 映射 §2.4 的 15 个权威 TC。所有断言对应 spec 的"预期行为"段。
 *
 * Fetch 桩通过 vi.stubGlobal('fetch', ...) 注入，不走模块 mock；测试启动
 * VueQueryPlugin 让真实的 useQuery / useInfiniteQuery 在 jsdom 里跑起来。
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter, type RouteRecordRaw } from 'vue-router'
import { nextTick } from 'vue'
import { QueryClient, VueQueryPlugin } from '@tanstack/vue-query'

import FollowDetailView from '../../src/views/FollowDetailView.vue'

// ---- fetch stub ----------------------------------------------------------

interface FetchCall {
  url: string
  method: string
  body: string | null
}

let fetchCalls: FetchCall[] = []
let videoCallIdx = 0
let detailFixture: DetailFixture = makeBaseDetail()
let videosPages: VideoItem[][] = [makeVideoPage1(), makeVideoPage2()]
let patchResponseOverride: DetailFixture | null = null
let lastPatchBody: Record<string, unknown> | null = null
let detailEndpointVariants: ReadonlyArray<'detail' | 'overview'> = ['detail']
let videosEndpointVariants: ReadonlyArray<'videos' | 'hotspots'> = ['videos']

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function captureCall(input: RequestInfo | URL, init?: RequestInit): FetchCall {
  const url = typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url
  const method = (init?.method ?? 'GET').toUpperCase()
  const body = typeof init?.body === 'string' ? init.body : null
  const call: FetchCall = { url, method, body }
  fetchCalls.push(call)
  return call
}

function matchesAny(path: string, variants: ReadonlyArray<string>): boolean {
  return variants.some((variant) => path.includes(`/${variant}`))
}

function handleFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const call = captureCall(input, init)
  const url = call.url

  if (matchesAny(url, detailEndpointVariants)) {
    return Promise.resolve(jsonResponse(200, { success: true, data: detailFixture }))
  }
  if (matchesAny(url, videosEndpointVariants)) {
    const page = videosPages[videoCallIdx] ?? []
    const nextOffset = videoCallIdx < videosPages.length - 1 ? (videoCallIdx + 1) * 20 : null
    videoCallIdx++
    return Promise.resolve(jsonResponse(200, { success: true, data: { items: page, nextOffset } }))
  }
  if (url.includes('/sync')) {
    return Promise.resolve(jsonResponse(202, { success: true, data: { queued: true } }))
  }
  if (url.match(/\/api\/followed-up\/[^/?]+(\?|$)/) && call.method === 'PATCH') {
    let parsed: Record<string, unknown> = {}
    try {
      parsed = call.body ? JSON.parse(call.body) : {}
    } catch {
      parsed = {}
    }
    lastPatchBody = parsed
    if (patchResponseOverride) {
      return Promise.resolve(jsonResponse(200, { success: true, data: patchResponseOverride }))
    }
    // The PATCH body carries the new state directly. Mirror the server
    // round-trip by mutating the in-memory fixture so the next /detail
    // refetch returns the same value the PATCH wrote.
    const nextEnabled =
      typeof parsed.enabled === 'boolean' ? parsed.enabled : detailFixture.enabled
    detailFixture = { ...detailFixture, enabled: nextEnabled }
    return Promise.resolve(
      jsonResponse(200, {
        success: true,
        data: { ...detailFixture, enabled: nextEnabled },
      }),
    )
  }
  if (url.match(/\/api\/followed-up\/[^/?]+(\?|$)/) && call.method === 'DELETE') {
    return Promise.resolve(jsonResponse(200, { success: true, data: { id: detailFixture.id } }))
  }
  return Promise.resolve(jsonResponse(200, { success: true, data: {} }))
}

function stubFetch(): ReturnType<typeof vi.fn> {
  const spy = vi.fn(handleFetch)
  vi.stubGlobal('fetch', spy)
  return spy
}

beforeEach(() => {
  fetchCalls = []
  videoCallIdx = 0
  detailFixture = cloneDetailFixture(baseDetail)
  videosPages = [cloneVideoPage(videoPage1), cloneVideoPage(videoPage2)]
  patchResponseOverride = null
  lastPatchBody = null
  detailEndpointVariants = ['detail']
  videosEndpointVariants = ['videos']
})

afterEach(() => {
  vi.unstubAllGlobals()
})

// ---- data shapes ---------------------------------------------------------

interface CollectionFixture {
  id: string
  title: string
  description: string | null
  video_count: number
  videos: Array<{ bvid: string; title: string }>
}

interface DetailFixture {
  id: string
  name: string
  mid: string
  url: string
  avatar: string
  health: 'healthy' | 'warning' | 'error'
  enabled: boolean
  strategy: 'uapi' | 'html'
  interval_minutes: number
  last_checked_at: string | null
  last_error: string | null
  collections: CollectionFixture[]
}

interface VideoItem {
  bvid: string
  title: string
  collection_id: string | null
  status: string
  published_at: string
  hotspot_id: string
}

function cloneDetailFixture(src: DetailFixture): DetailFixture {
  return JSON.parse(JSON.stringify(src))
}

function cloneVideoPage(page: VideoItem[]): VideoItem[] {
  return JSON.parse(JSON.stringify(page))
}

function makeBaseDetail(): DetailFixture {
  return {
    id: 'fup_1',
    name: '跟李沐学AI',
    mid: '1567748478',
    url: 'https://space.bilibili.com/1567748478',
    avatar: 'https://placehold.co/64x64.png',
    health: 'healthy',
    enabled: true,
    strategy: 'uapi',
    interval_minutes: 30,
    last_checked_at: '2026-07-25T14:32:18Z',
    last_error: null,
    collections: [
      {
        id: 'col_1',
        title: 'LLM 系列',
        description: '从零开始的 LLM 教程',
        video_count: 5,
        videos: [
          { bvid: 'BV1inside', title: '合集内视频 1' },
          { bvid: 'BV1inside2', title: '合集内视频 2' },
        ],
      },
    ],
  }
}

function makeVideoPage1(): VideoItem[] {
  return Array.from({ length: 20 }, (_, i) => ({
    bvid: `BV1page1_${String(i).padStart(2, '0')}`,
    title: `第 1 页 第 ${i + 1} 条`,
    collection_id: i < 5 ? 'col_1' : null,
    status: 'pending',
    published_at: '2026-07-25T10:00:00Z',
    hotspot_id: `h_page1_${i}`,
  }))
}

function makeVideoPage2(): VideoItem[] {
  return Array.from({ length: 10 }, (_, i) => ({
    bvid: `BV1page2_${String(i).padStart(2, '0')}`,
    title: `第 2 页 第 ${i + 1} 条`,
    collection_id: null,
    status: 'pending',
    published_at: '2026-07-20T10:00:00Z',
    hotspot_id: `h_page2_${i}`,
  }))
}

const baseDetail: DetailFixture = makeBaseDetail()
const videoPage1: VideoItem[] = makeVideoPage1()
const videoPage2: VideoItem[] = makeVideoPage2()

// ---- mount helper --------------------------------------------------------

async function mountDetailView(opts: { uid?: string } = {}) {
  const uid = opts.uid ?? '1567748478'
  const routes: RouteRecordRaw[] = [
    {
      path: '/followed-up/:uid',
      name: 'follow-detail',
      component: FollowDetailView,
      props: true,
    },
    {
      path: '/dashboard',
      name: 'dashboard',
      component: { template: '<div>dashboard</div>' },
    },
  ]
  const router = createRouter({ history: createMemoryHistory(), routes })
  await router.push(`/followed-up/${uid}`)
  await router.isReady()

  stubFetch()

  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })

  const wrapper = mount(FollowDetailView, {
    global: { plugins: [router, [VueQueryPlugin, { queryClient }]] },
    props: { uid },
    attachTo: document.body,
  })
  await flushPromises()
  await nextTick()
  return { wrapper, router }
}

async function loadMoreTriggered(wrapper: ReturnType<typeof mount>['wrapper']) {
  const btn = wrapper.find('[data-testid="load-more-btn"]')
  expect(btn.exists(), 'expected 加载更多历史 button').toBe(true)
  await btn.trigger('click')
  await flushPromises()
  await nextTick()
}

function findVideosCalls(): FetchCall[] {
  return fetchCalls.filter((c) => c.url.includes('/videos') || c.url.includes('/hotspots'))
}

function findDetailCalls(): FetchCall[] {
  return fetchCalls.filter((c) => c.url.includes('/detail') || c.url.includes('/overview'))
}

// ---- TC-UI-FOLLOW-DETAIL-01 -----------------------------------------------

describe('TC-UI-FOLLOW-DETAIL-01 头部：头像 + 昵称 + 健康徽章', () => {
  it('renders 64x64 avatar <img> + <h1> name + HealthDot', async () => {
    const { wrapper } = await mountDetailView()
    const avatar = wrapper.find('.follow-detail-avatar')
    expect(avatar.exists()).toBe(true)
    expect(avatar.element.tagName).toBe('IMG')
    expect(avatar.attributes('src')).toBe('https://placehold.co/64x64.png')
    expect(avatar.attributes('alt')).toBe('跟李沐学AI')
    expect(wrapper.find('h1').text()).toBe('跟李沐学AI')
    expect(wrapper.find('[data-testid="health-dot"]').exists()).toBe(true)
    wrapper.unmount()
  })
})

// ---- TC-UI-FOLLOW-DETAIL-02 -----------------------------------------------

describe('TC-UI-FOLLOW-DETAIL-02 元数据 dl：mid / URL / 策略 / 间隔 / last_checked_at / last_error', () => {
  it('renders 6 dt/dd pairs; last_error shows red state-error text when present', async () => {
    detailFixture.last_error = 'rate limited'
    const { wrapper } = await mountDetailView()
    const dl = wrapper.find('dl.follow-detail-meta')
    expect(dl.exists()).toBe(true)
    const dts = dl.findAll('dt')
    const dds = dl.findAll('dd')
    expect(dts.length).toBeGreaterThanOrEqual(6)
    expect(dds.length).toBeGreaterThanOrEqual(6)
    const labels = dts.map((d) => d.text())
    expect(labels).toEqual(
      expect.arrayContaining(['mid', '主页 URL', '策略', '间隔', '上次扫描', '最近错误']),
    )
    expect(dl.text()).toContain('1567748478')
    expect(dl.text()).toContain('https://space.bilibili.com/1567748478')
    expect(dl.text()).toContain('uapi')
    expect(dl.text()).toContain('30 分钟')
    expect(dl.text()).toContain('rate limited')
    const errorDD = dds.find((d) => d.text() === 'rate limited')
    expect(errorDD?.classes().join(' ')).toMatch(/state-error|error|red/)
    wrapper.unmount()
  })
})

// ---- TC-UI-FOLLOW-DETAIL-03 -----------------------------------------------

describe('TC-UI-FOLLOW-DETAIL-03 合集区域渲染 <CollectionAccordion> 列表', () => {
  it('renders one <CollectionAccordion> row per collection', async () => {
    detailFixture.collections = [
      { id: 'col_1', title: 'LLM 系列', description: null, video_count: 5, videos: [] },
      { id: 'col_2', title: 'Web Dev', description: null, video_count: 3, videos: [] },
    ]
    const { wrapper } = await mountDetailView()
    const rows = wrapper.findAll('[data-testid="collection-row"]')
    expect(rows.length).toBe(2)
    expect(rows[0].text()).toContain('LLM 系列')
    expect(rows[1].text()).toContain('Web Dev')
    wrapper.unmount()
  })
})

// ---- TC-UI-FOLLOW-DETAIL-04 -----------------------------------------------

describe('TC-UI-FOLLOW-DETAIL-04 合集点击展开视频列表', () => {
  it('toggles <details> open state (aria-expanded) when summary is clicked', async () => {
    detailFixture.collections = [
      {
        id: 'col_1',
        title: 'LLM 系列',
        description: null,
        video_count: 2,
        videos: [
          { bvid: 'BV1collA', title: '合集视频 A' },
          { bvid: 'BV1collB', title: '合集视频 B' },
        ],
      },
    ]
    const { wrapper } = await mountDetailView()
    const row = wrapper.find('[data-testid="collection-row"]')
    const details = row.find('details')
    expect(details.exists()).toBe(true)
    // Before click: closed
    const wasOpen = (details.element as HTMLDetailsElement).open
    expect(wasOpen).toBe(false)
    // Click summary → opens
    await row.find('summary').trigger('click')
    await nextTick()
    const isOpen = (details.element as HTMLDetailsElement).open
    expect(isOpen).toBe(true)
    // And inner video list appears
    expect(row.text()).toContain('BV1collA')
    expect(row.text()).toContain('BV1collB')
    wrapper.unmount()
  })
})

// ---- TC-UI-FOLLOW-DETAIL-05 -----------------------------------------------

describe('TC-UI-FOLLOW-DETAIL-05 视频列表 VideoListItem 渲染最近 20 条', () => {
  it('renders exactly 20 <VideoListItem> nodes from the first page', async () => {
    const { wrapper } = await mountDetailView()
    // Scope to the main video list (exclude collection accordion + orphan)
    const items = wrapper.findAll(
      '.follow-detail-video-list [data-testid="video-list-item"]',
    )
    expect(items.length).toBe(20)
    expect(items[0].text()).toContain('BV1page1_00')
    expect(items[19].text()).toContain('BV1page1_19')
    wrapper.unmount()
  })
})

// ---- TC-UI-FOLLOW-DETAIL-06 -----------------------------------------------

describe('TC-UI-FOLLOW-DETAIL-06 加载更多历史翻页', () => {
  it('clicking 加载更多历史 triggers fetchNextPage + shows 加载中… + disabled', async () => {
    // Slow down the second page so the loading state is observable
    const slowHandler = (input: RequestInfo | URL, init?: RequestInit) => {
      const call = captureCall(input, init)
      const url = call.url
      if (matchesAny(url, detailEndpointVariants)) {
        return Promise.resolve(jsonResponse(200, { success: true, data: detailFixture }))
      }
      if (matchesAny(url, videosEndpointVariants) && videoCallIdx === 1) {
        return new Promise((resolve) => {
          setTimeout(
            () =>
              resolve(
                jsonResponse(200, {
                  success: true,
                  data: { items: videoPage2, nextOffset: null },
                }),
              ),
            50,
          )
        })
      }
      return handleFetch(input, init)
    }
    vi.stubGlobal('fetch', vi.fn(slowHandler))

    const { wrapper } = await mountDetailView()
    const btn = wrapper.find('[data-testid="load-more-btn"]')
    expect(btn.exists()).toBe(true)
    expect(btn.text()).toBe('加载更多历史')

    // Click and immediately observe the loading state
    const clickPromise = btn.trigger('click')
    await nextTick()
    // Re-query because Vue may have replaced the button instance
    const btnAfter = wrapper.find('[data-testid="load-more-btn"]')
    expect(btnAfter.text()).toBe('加载中…')
    expect((btnAfter.element as HTMLButtonElement).disabled).toBe(true)

    await clickPromise
    await flushPromises()
    await nextTick()
    wrapper.unmount()
  })
})

// ---- TC-UI-FOLLOW-DETAIL-07 -----------------------------------------------

describe('TC-UI-FOLLOW-DETAIL-07 立即扫描按钮', () => {
  it('clicking 立即扫描 calls POST /api/followed-up/{uid}/sync', async () => {
    const { wrapper } = await mountDetailView()
    const btn = wrapper.find('[data-testid="scan-now-btn"]')
    expect(btn.exists()).toBe(true)
    expect(btn.text()).toBe('立即扫描')
    await btn.trigger('click')
    await flushPromises()
    const syncCall = fetchCalls.find(
      (c) => c.url.includes('/sync') && c.method === 'POST',
    )
    expect(syncCall, 'expected POST /sync').toBeTruthy()
    expect(syncCall?.url).toContain('1567748478')
    wrapper.unmount()
  })
})

// ---- TC-UI-FOLLOW-DETAIL-08 -----------------------------------------------

describe('TC-UI-FOLLOW-DETAIL-08 暂停 / 恢复切换启用状态', () => {
  it('clicking 暂停 PATCHes enabled: false and label flips to 恢复', async () => {
    const { wrapper } = await mountDetailView()
    const btn = wrapper.find('[data-testid="toggle-enabled-btn"]')
    expect(btn.exists()).toBe(true)
    expect(btn.text()).toBe('暂停')
    await btn.trigger('click')
    // Wait for PATCH to be issued
    for (let i = 0; i < 20; i++) {
      await flushPromises()
      await nextTick()
      if (
        fetchCalls.find(
          (c) =>
            c.url.match(/\/api\/followed-up\/[^/?]+(\?|$)/) && c.method === 'PATCH',
        )
      ) {
        break
      }
    }
    const patchCall = fetchCalls.find(
      (c) => c.url.match(/\/api\/followed-up\/[^/?]+(\?|$)/) && c.method === 'PATCH',
    )
    expect(patchCall, 'expected PATCH').toBeTruthy()
    expect(patchCall?.body).toContain('"enabled":false')
    expect(lastPatchBody).toEqual({ enabled: false })
    // After the mutation + query refetch, the label should now read 恢复
    await vi.waitFor(
      () => wrapper.find('[data-testid="toggle-enabled-btn"]').text() === '恢复',
      { timeout: 2000, interval: 20 },
    ).catch(() => undefined)
    const btnAfter = wrapper.find('[data-testid="toggle-enabled-btn"]')
    expect(btnAfter.text()).toBe('恢复')
    wrapper.unmount()
  })
})

// ---- TC-UI-FOLLOW-DETAIL-09 -----------------------------------------------

describe('TC-UI-FOLLOW-DETAIL-09 删除走二次确认 modal', () => {
  it('clicking 删除 opens confirm modal; confirm → DELETE + router.push /dashboard?tab=follow-list', async () => {
    const { wrapper, router } = await mountDetailView()
    // Make sure we have a known prior history entry to navigate back from
    await router.push('/dashboard?tab=follow-list')
    await router.push('/followed-up/1567748478')
    await flushPromises()

    const deleteBtn = wrapper.find('[data-testid="delete-btn"]')
    expect(deleteBtn.exists()).toBe(true)
    await deleteBtn.trigger('click')
    await flushPromises()
    await nextTick()

    const confirm = wrapper.find('[data-testid="delete-confirm"]')
    expect(confirm.exists(), 'expected delete confirm modal').toBe(true)

    const confirmBtn = wrapper.find('[data-testid="delete-confirm-confirm"]')
    expect(confirmBtn.exists()).toBe(true)
    await confirmBtn.trigger('click')
    await flushPromises()
    await nextTick()

    const deleteCall = fetchCalls.find(
      (c) => c.url.match(/\/api\/followed-up\/[^/?]+(\?|$)/) && c.method === 'DELETE',
    )
    expect(deleteCall, 'expected DELETE').toBeTruthy()
    expect(router.currentRoute.value.fullPath).toBe('/dashboard?tab=follow-list')
    wrapper.unmount()
  })
})

// ---- TC-UI-FOLLOW-DETAIL-10 -----------------------------------------------

describe('TC-UI-FOLLOW-DETAIL-10 散落视频区块 (variant="orphan")', () => {
  it('renders 散落视频 h3 with correct count and orphan variant items', async () => {
    // page1: 5 in col_1, 15 orphan
    const { wrapper } = await mountDetailView()
    const orphanH3 = wrapper.find('[data-testid="orphan-videos-title"]')
    expect(orphanH3.exists()).toBe(true)
    expect(orphanH3.text()).toMatch(/散落视频（不在合集内，15 条）/)
    const orphanItems = wrapper.findAll(
      '.follow-detail-orphan [data-testid="video-list-item"][data-variant="orphan"]',
    )
    expect(orphanItems.length).toBe(15)
    wrapper.unmount()
  })
})

// ---- TC-UI-FOLLOW-DETAIL-11 -----------------------------------------------

describe('TC-UI-FOLLOW-DETAIL-11 useInfiniteQuery getNextPageParam 解析 nextOffset', () => {
  it('next page request uses offset=20 when first page returns nextOffset: 20', async () => {
    const { wrapper } = await mountDetailView()
    const firstVideos = findVideosCalls()
    expect(firstVideos.length).toBeGreaterThanOrEqual(1)
    const initialUrl = new URL(firstVideos[0].url, 'http://x')
    expect(initialUrl.searchParams.get('offset')).toBe('0')
    expect(initialUrl.searchParams.get('limit')).toBe('20')
    // Trigger load more → second call
    await loadMoreTriggered(wrapper)
    const secondVideos = findVideosCalls()
    expect(secondVideos.length).toBe(2)
    const secondUrl = new URL(secondVideos[1].url, 'http://x')
    expect(secondUrl.searchParams.get('offset')).toBe('20')
    expect(secondUrl.searchParams.get('limit')).toBe('20')
    wrapper.unmount()
  })
})

// ---- TC-UI-FOLLOW-DETAIL-12 -----------------------------------------------

describe('TC-UI-FOLLOW-DETAIL-12 enabled: !!uid.value 防止空 uid 触发请求', () => {
  it('mounts without calling /detail or /videos when uid is empty', async () => {
    // Push a route that yields uid === '' via the empty path segment.
    // vue-router treats /followed-up/ as a non-match for /followed-up/:uid,
    // so we instead mount the component with a falsy uid via a synthetic
    // route that satisfies the param matcher.
    const routes: RouteRecordRaw[] = [
      {
        path: '/followed-up/:uid?',
        name: 'follow-detail-optional',
        component: FollowDetailView,
        props: true,
      },
    ]
    const router = createRouter({ history: createMemoryHistory(), routes })
    await router.push('/followed-up/')
    await router.isReady()

    stubFetch()
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, gcTime: 0 } },
    })
    const wrapper = mount(FollowDetailView, {
      global: { plugins: [router, [VueQueryPlugin, { queryClient }]] },
      props: { uid: '' },
      attachTo: document.body,
    })
    await flushPromises()
    await nextTick()
    const detailCalls = findDetailCalls()
    const videoCalls = findVideosCalls()
    expect(detailCalls.length).toBe(0)
    expect(videoCalls.length).toBe(0)
    wrapper.unmount()
  })
})

// ---- TC-UI-FOLLOW-DETAIL-13 -----------------------------------------------

describe('TC-UI-FOLLOW-DETAIL-13 返回按钮调 router.back()', () => {
  it('clicking ← 返回 navigates back in history', async () => {
    const { wrapper, router } = await mountDetailView()
    // Pre-seed history: dashboard then detail
    await router.push('/dashboard?tab=follow-list')
    await router.push('/followed-up/1567748478')
    await flushPromises()

    const back = wrapper.find('[data-testid="back-btn"]')
    expect(back.exists()).toBe(true)
    expect(back.text()).toMatch(/返回/)
    await back.trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/dashboard')
    wrapper.unmount()
  })
})

// ---- TC-UI-FOLLOW-DETAIL-14 -----------------------------------------------

describe('TC-UI-FOLLOW-DETAIL-14 时间渲染 toLocaleString(zh-CN)', () => {
  it('renders last_checked_at as a zh-CN formatted date string', async () => {
    detailFixture.last_checked_at = '2026-07-25T14:32:18Z'
    const { wrapper } = await mountDetailView()
    const time = wrapper.find('time, [data-testid="last-checked-at"]')
    expect(time.exists()).toBe(true)
    expect(time.text()).toMatch(/2026[\/年-]\s*7[\/月-]\s*25\s+\d{1,2}:\d{2}:\d{2}/)
    wrapper.unmount()
  })
})

// ---- TC-UI-FOLLOW-DETAIL-15 -----------------------------------------------

describe('TC-UI-FOLLOW-DETAIL-15 在 B 站打开 按钮', () => {
  it('clicking 在 B 站打开 calls window.open with https://www.bilibili.com/video/{bvid}, target=_blank', async () => {
    const openSpy = vi
      .spyOn(window, 'open')
      .mockImplementation(() => null)
    const { wrapper } = await mountDetailView()
    // Scope to the main video list (not the collection's first video)
    const link = wrapper.find(
      '.follow-detail-video-list [data-testid="open-bilibili-link"]',
    )
    expect(link.exists()).toBe(true)
    expect(link.attributes('href')).toContain('https://www.bilibili.com/video/BV1page1_00')
    expect(link.attributes('target')).toBe('_blank')
    await link.trigger('click')
    expect(openSpy).toHaveBeenCalled()
    const urlArg = String(openSpy.mock.calls[0]?.[0] ?? '')
    expect(urlArg).toBe('https://www.bilibili.com/video/BV1page1_00')
    openSpy.mockRestore()
    wrapper.unmount()
  })
})
