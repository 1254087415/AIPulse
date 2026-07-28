import { flushPromises, mount } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import UpDetailView from '../UpDetailView.vue'
import * as upDetailApi from '../../api/upDetail'
import * as followedUpApi from '../../api/followedUp'

vi.mock('../../api/upDetail')
vi.mock('../../api/followedUp')

const followed = {
  id: 'record-1', platform: 'bilibili', uid: '1567748478', display_name: '跟李沐学AI',
  profile_url: 'https://space.bilibili.com/1567748478', collector_strategy: 'uapi',
  last_cursor_id: null, fetch_interval_minutes: 30, is_active: true, status: 'active',
  health: 'healthy', last_checked_at: '2026-07-28T01:00:00Z', last_error: null,
  failed_at: null, created_at: '2026-07-20T00:00:00Z', updated_at: '2026-07-28T01:00:00Z', deleted_at: null,
} as const

async function mountView() {
  const router = createRouter({ history: createMemoryHistory(), routes: [
    { path: '/up/:uid', component: UpDetailView },
    { path: '/dashboard', component: { template: '<div>dashboard</div>' } },
  ] })
  await router.push('/up/1567748478')
  await router.isReady()
  return mount(UpDetailView, { global: { plugins: [router] } })
}

describe('UpDetailView', () => {
  beforeEach(() => {
    vi.mocked(upDetailApi.fetchUpDetail).mockResolvedValue(followed)
    vi.mocked(upDetailApi.fetchUpHotspots).mockResolvedValue([
      { id: 'hot-1', title: 'AI 视频', url: 'https://example.com/video', summary: null, source_type: 'bilibili', published_at: null, created_at: '2026-07-28T00:00:00Z', heat_score: 10 },
    ])
    vi.mocked(upDetailApi.fetchUpSyncHistory).mockResolvedValue([
      { id: 'sync-1', video_id: 'BV1', title: 'AI 视频', status: 'completed', error: null, created_at: '2026-07-28T00:00:00Z', started_at: null, completed_at: '2026-07-28T00:01:00Z' },
    ])
    vi.mocked(followedUpApi.syncFollowed).mockResolvedValue({ queued: true, scan_id: 'scan-1' })
  })

  it('renders UP profile, hotspots and sync history', async () => {
    const wrapper = await mountView()
    await flushPromises()
    expect(wrapper.text()).toContain('跟李沐学AI')
    expect(wrapper.text()).toContain('1567748478')
    expect(wrapper.text()).toContain('健康')
    expect(wrapper.text()).toContain('AI 视频')
    expect(wrapper.text()).toContain('completed')
  })

  it('syncs by record id and refreshes detail data', async () => {
    const wrapper = await mountView()
    await flushPromises()
    await wrapper.get('[data-testid="sync-up"]').trigger('click')
    await flushPromises()
    expect(followedUpApi.syncFollowed).toHaveBeenCalledWith('record-1')
    expect(upDetailApi.fetchUpDetail).toHaveBeenCalledTimes(3)
  })
})
