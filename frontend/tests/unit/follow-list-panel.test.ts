import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const { listFollowedMock, createFollowedMock, removeMock, scanNowMock, setEnabledMock } = vi.hoisted(() => ({
  listFollowedMock: vi.fn(),
  createFollowedMock: vi.fn(),
  removeMock: vi.fn(),
  scanNowMock: vi.fn(),
  setEnabledMock: vi.fn(),
}))

vi.mock('../../src/api/followedUp', () => ({
  listFollowed: () => listFollowedMock(),
  createFollowed: (...args: unknown[]) => createFollowedMock(...args),
}))

vi.mock('../../src/api/follow', () => ({
  followApi: {
    remove: (...args: unknown[]) => removeMock(...args),
    scanNow: (...args: unknown[]) => scanNowMock(...args),
    setEnabled: (...args: unknown[]) => setEnabledMock(...args),
  },
}))

import FollowListPanel from '../../src/components/follow-list-panel/FollowListPanel.vue'
import FollowCard from '../../src/components/follow-list-panel/FollowCard.vue'
import AddFollowForm from '../../src/components/follow-list-panel/AddFollowForm.vue'
import HealthBadge from '../../src/components/health-badge/HealthBadge.vue'
import { router } from '../../src/router'
import { h } from 'vue'

const RouterLinkStub = {
  name: 'RouterLink',
  props: ['to'],
  setup(props: { to?: string }, { slots }: { slots: { default?: () => unknown } }) {
    return () => h('a', { class: 'follow-card__detail-link', href: props.to }, slots.default?.())
  },
}

const sampleFollowed = (overrides = {}) => ({
  id: 'fu_123',
  platform: 'bilibili',
  uid: '1567748478',
  display_name: '李沐',
  profile_url: 'https://space.bilibili.com/1567748478',
  collector_strategy: 'uapi',
  last_cursor_id: null,
  fetch_interval_minutes: 30,
  is_active: true,
  status: 'active',
  health: 'healthy',
  last_checked_at: '2026-07-25T08:00:00Z',
  last_error: null,
  failed_at: null,
  created_at: '2026-07-25T07:00:00Z',
  updated_at: '2026-07-25T08:00:00Z',
  deleted_at: null,
  config: {},
  mid: '1567748478',
  video_count: 12,
  ...overrides,
})

function mountPanel() {
  return mount(FollowListPanel, {
    global: {
      components: {
        RouterLink: RouterLinkStub,
        'router-link': RouterLinkStub,
      },
      stubs: {
        // Avoid rendering HealthBadge from disk; rely on the real component.
        HealthBadge: HealthBadge,
      },
    },
  })
}

describe('FollowListPanel', () => {
  beforeEach(async () => {
    listFollowedMock.mockReset()
    createFollowedMock.mockReset()
    removeMock.mockReset()
    scanNowMock.mockReset()
    setEnabledMock.mockReset()
    await router.push('/dashboard')
  })

  it('renders one FollowCard per followed UP with the 7 required fields', async () => {
    listFollowedMock.mockResolvedValue([sampleFollowed()])

    const wrapper = mountPanel()
    await flushPromises()

    const cards = wrapper.findAllComponents(FollowCard)
    expect(cards).toHaveLength(1)

    const card = cards[0]
    expect(card.props('followed').display_name).toBe('李沐')
    expect(card.props('followed').platform).toBe('bilibili')
    expect(card.props('followed').health).toBe('healthy')
    expect(card.props('followed').uid).toBe('1567748478')

    // The card text contains all 7 required fields:
    // 头像 / 名称 / 平台 / 状态 / 健康徽章 / 上次同步 / 错误信息
    const html = card.html()
    expect(html).toContain('李沐')         // 名称
    expect(html).toContain('bilibili')    // 平台
    expect(html).toContain('启用')         // 状态
    expect(html).toContain('健康')         // 健康徽章
    expect(html).toContain('上次同步')     // 上次同步
    expect(html).toContain('1567748478') // mid
    expect(html).toContain('12')         // 视频数量
    expect(card.find('img').exists()).toBe(true) // 头像

    wrapper.unmount()
  })

  it('shows the empty state when there are no followed UPs', async () => {
    listFollowedMock.mockResolvedValue([])

    const wrapper = mountPanel()
    await flushPromises()

    expect(wrapper.find('[data-testid="empty-state"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('还没有关注')

    wrapper.unmount()
  })

  it('shows the over-limit warning when there are more than 20 follows', async () => {
    const many = Array.from({ length: 21 }, (_, i) =>
      sampleFollowed({ id: `fu_${i}`, uid: `100${i}` }),
    )
    listFollowedMock.mockResolvedValue(many)

    const wrapper = mountPanel()
    await flushPromises()

    expect(wrapper.find('[data-testid="over-limit-warning"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('超过 20')

    wrapper.unmount()
  })

  it('does not show the warning when there are exactly 20 follows', async () => {
    const exactly = Array.from({ length: 20 }, (_, i) =>
      sampleFollowed({ id: `fu_${i}`, uid: `100${i}` }),
    )
    listFollowedMock.mockResolvedValue(exactly)

    const wrapper = mountPanel()
    await flushPromises()

    expect(wrapper.find('[data-testid="over-limit-warning"]').exists()).toBe(false)

    wrapper.unmount()
  })

  it('orders errored cards first, then by updated_at desc', async () => {
    listFollowedMock.mockResolvedValue([
      sampleFollowed({ id: 'a', display_name: 'Old healthy', health: 'healthy', updated_at: '2026-07-25T07:00:00Z' }),
      sampleFollowed({ id: 'b', display_name: 'Healthy recent', health: 'healthy', updated_at: '2026-07-25T09:00:00Z' }),
      sampleFollowed({ id: 'c', display_name: 'Broken one', health: 'error', updated_at: '2026-07-25T06:00:00Z' }),
    ])

    const wrapper = mountPanel()
    await flushPromises()

    const cards = wrapper.findAllComponents(FollowCard)
    expect(cards.map((c) => c.props('followed').id)).toEqual(['c', 'b', 'a'])

    wrapper.unmount()
  })

  it('surfaces a backend 409 conflict as an inline error message', async () => {
    listFollowedMock.mockResolvedValue([])

    const wrapper = mountPanel()
    await flushPromises()

    // Show the form and try to submit a duplicate uid.
    await wrapper.find('[data-testid="open-add-form"]').trigger('click')
    await flushPromises()

    const form = wrapper.findComponent(AddFollowForm)
    expect(form.exists()).toBe(true)

    const apiErr = new Error('Conflict')
    apiErr.name = 'ApiError'
    ;(apiErr as unknown as { status: number }).status = 409
    createFollowedMock.mockRejectedValueOnce(apiErr)

    await form.vm.$emit('submit', {
      platform: 'bilibili',
      uid: '1567748478',
    })
    await flushPromises()

    expect(wrapper.find('[data-testid="create-error"]').exists()).toBe(true)
    expect(wrapper.text()).toMatch(/已存在|重复|409/)

    wrapper.unmount()
  })

  it('renders the 查看详情 router-link with the ghost link style (M-1 挂账)', async () => {
    listFollowedMock.mockResolvedValue([sampleFollowed()])

    const wrapper = mountPanel()
    await flushPromises()

    const link = wrapper.find('.follow-card__detail-link')
    expect(link.exists()).toBe(true)
    // 链接文本 + 目标 uid
    expect(link.text().trim()).toBe('查看详情')
    expect(link.attributes('href')).toBe('/followed-up/1567748478')

    wrapper.unmount()
  })

  it('confirms before DELETE and refreshes after confirming', async () => {
    listFollowedMock
      .mockResolvedValueOnce([sampleFollowed()])
      .mockResolvedValueOnce([])
    removeMock.mockResolvedValue({ ok: true, data: { id: 'fu_123' } })

    const wrapper = mountPanel()
    await flushPromises()
    await wrapper.find('[data-testid="remove-button"]').trigger('click')
    await flushPromises()

    expect(removeMock).not.toHaveBeenCalled()
    expect(wrapper.find('[data-testid="follow-delete-confirm"]').exists()).toBe(true)
    await wrapper.find('[data-testid="follow-delete-confirm-confirm"]').trigger('click')
    await flushPromises()

    expect(removeMock).toHaveBeenCalledWith('fu_123')
    expect(listFollowedMock).toHaveBeenCalledTimes(2)
    expect(wrapper.find('[data-testid="empty-state"]').exists()).toBe(true)
    wrapper.unmount()
  })

  it('calls the real toggle and refreshes the list', async () => {
    listFollowedMock
      .mockResolvedValueOnce([sampleFollowed()])
      .mockResolvedValueOnce([sampleFollowed({ is_active: false })])
    setEnabledMock.mockResolvedValue({ ok: true, data: {} })

    const wrapper = mountPanel()
    await flushPromises()
    await wrapper.find('[data-testid="toggle-enabled-button"]').trigger('click')
    await flushPromises()

    expect(setEnabledMock).toHaveBeenCalledWith('fu_123', false)
    expect(listFollowedMock).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('已暂停')
    wrapper.unmount()
  })

  it('calls immediate sync and refreshes the list', async () => {
    listFollowedMock.mockResolvedValue([sampleFollowed()])
    scanNowMock.mockResolvedValue({ ok: true, data: {} })

    const wrapper = mountPanel()
    await flushPromises()
    await wrapper.find('[data-testid="sync-button"]').trigger('click')
    await flushPromises()

    expect(scanNowMock).toHaveBeenCalledWith('fu_123')
    expect(listFollowedMock).toHaveBeenCalledTimes(2)
    wrapper.unmount()
  })

  it('shows a visible action error when sync fails', async () => {
    listFollowedMock.mockResolvedValue([sampleFollowed()])
    scanNowMock.mockRejectedValueOnce(new Error('sync exploded'))

    const wrapper = mountPanel()
    await flushPromises()
    await wrapper.find('[data-testid="sync-button"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="action-error"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('sync exploded')
    wrapper.unmount()
  })

  it('surfaces delete failures inside the confirm modal', async () => {
    listFollowedMock.mockResolvedValue([sampleFollowed()])
    removeMock.mockRejectedValueOnce(new Error('delete exploded'))

    const wrapper = mountPanel()
    await flushPromises()
    await wrapper.find('[data-testid="remove-button"]').trigger('click')
    await flushPromises()
    await wrapper.find('[data-testid="follow-delete-confirm-confirm"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="follow-delete-confirm-error"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('delete exploded')
    wrapper.unmount()
  })

  it('makes the edit action navigate to the detail view', async () => {
    listFollowedMock.mockResolvedValue([sampleFollowed()])
    const pushSpy = vi.spyOn(router, 'push')
    const wrapper = mountPanel()
    await flushPromises()
    await wrapper.find('[data-testid="edit-button"]').trigger('click')
    await flushPromises()
    expect(wrapper.findComponent(FollowCard).emitted('edit')).toEqual([['fu_123']])
    expect(pushSpy).toHaveBeenCalledWith('/followed-up/1567748478')
    pushSpy.mockRestore()
    wrapper.unmount()
  })
})

describe('FollowCard', () => {
  it('renders the last_error block when present, sanitized via summarizeError', () => {
    const wrapper = mount(FollowCard, {
      props: {
        followed: sampleFollowed({
          health: 'error',
          last_error: 'Bilibili 429 rate limited',
        }),
      },
    })

    const errorBlock = wrapper.find('[data-testid="last-error"]')
    expect(errorBlock.exists()).toBe(true)
    // 429 → "请求过于频繁，请稍后重试"；原始 raw 错误收进 title 供查看
    expect(errorBlock.text()).toContain('请求过于频繁')
    expect(errorBlock.text()).not.toContain('Bilibili 429 rate limited')
    expect(errorBlock.attributes('title')).toBe('Bilibili 429 rate limited')

    wrapper.unmount()
  })

  it('falls back to first-character initial when no profile_url or cached avatar is set', () => {
    const wrapper = mount(FollowCard, {
      props: {
        followed: sampleFollowed({
          profile_url: '',
          config: {},
        }),
      },
    })

    expect(wrapper.find('img.follow-card__avatar-img').exists()).toBe(false)
    const initial = wrapper.find('.follow-card__avatar-initial')
    expect(initial.exists()).toBe(true)
    expect(initial.text()).toBe('李')

    wrapper.unmount()
  })

  it('uses the cached config.avatar_url as the avatar src (L4 self-heal path)', () => {
    const wrapper = mount(FollowCard, {
      props: {
        followed: sampleFollowed({
          profile_url: 'https://space.bilibili.com/1567748478',
          config: {
            avatar_url: 'https://i0.hdslb.com/bfs/face/example.jpg',
          },
        }),
      },
    })

    const img = wrapper.find('img.follow-card__avatar-img')
    expect(img.exists()).toBe(true)
    expect(img.attributes('src')).toBe('https://i0.hdslb.com/bfs/face/example.jpg')
    // initial letter is still rendered behind the image so it acts as a fallback
    expect(wrapper.find('.follow-card__avatar-initial').exists()).toBe(true)

    wrapper.unmount()
  })

  it('falls back to the initial when the avatar image errors (broken URL)', async () => {
    const wrapper = mount(FollowCard, {
      props: {
        followed: sampleFollowed({
          config: { avatar_url: 'https://example.invalid/broken.jpg' },
        }),
      },
    })

    const img = wrapper.find('img.follow-card__avatar-img')
    expect(img.exists()).toBe(true)
    await img.trigger('error')
    await flushPromises()

    // After error: image is removed from v-if, initial is the only visible content
    expect(wrapper.find('img.follow-card__avatar-img').exists()).toBe(false)
    expect(wrapper.find('.follow-card__avatar-initial').text()).toBe('李')

    wrapper.unmount()
  })

  it('emits a remove event when the remove button is clicked', async () => {
    const wrapper = mount(FollowCard, {
      props: { followed: sampleFollowed() },
    })

    await wrapper.find('[data-testid="remove-button"]').trigger('click')

    expect(wrapper.emitted('remove')).toBeTruthy()
    expect(wrapper.emitted('remove')![0]).toEqual(['fu_123'])

    wrapper.unmount()
  })

  it('emits a sync event when the sync button is clicked', async () => {
    const wrapper = mount(FollowCard, {
      props: { followed: sampleFollowed() },
    })

    await wrapper.find('[data-testid="sync-button"]').trigger('click')

    expect(wrapper.emitted('sync')).toBeTruthy()
    expect(wrapper.emitted('sync')![0]).toEqual(['fu_123'])

    wrapper.unmount()
  })

  it('renders mid and video count metadata', () => {
    const wrapper = mount(FollowCard, {
      props: { followed: sampleFollowed({ mid: '7788', video_count: 42 }) },
    })
    expect(wrapper.find('[data-testid="mid"]').text()).toContain('7788')
    expect(wrapper.find('[data-testid="video-count"]').text()).toContain('42')
    wrapper.unmount()
  })
})

describe('AddFollowForm', () => {
  it('does not submit when uid is empty', async () => {
    const wrapper = mount(AddFollowForm, {
      props: { submitting: false },
    })

    await wrapper.find('form').trigger('submit')

    expect(wrapper.emitted('submit')).toBeFalsy()

    wrapper.unmount()
  })

  it('emits a submit event with platform+uid when a valid B站 URL is pasted', async () => {
    const wrapper = mount(AddFollowForm, {
      props: { submitting: false },
    })

    await wrapper.find('[data-testid="url-input"]').setValue('https://space.bilibili.com/1567748478')
    await wrapper.find('form').trigger('submit')

    expect(wrapper.emitted('submit')).toBeTruthy()
    expect(wrapper.emitted('submit')![0]).toEqual([
      { platform: 'bilibili', uid: '1567748478' },
    ])

    wrapper.unmount()
  })

  it('disables the submit button when submitting is true', () => {
    const wrapper = mount(AddFollowForm, {
      props: { submitting: true },
    })

    const button = wrapper.find('[data-testid="submit-button"]')
    expect((button.element as HTMLButtonElement).disabled).toBe(true)

    wrapper.unmount()
  })

  it('emits cancel when the cancel button is clicked', async () => {
    const wrapper = mount(AddFollowForm, {
      props: { submitting: false },
    })

    await wrapper.find('[data-testid="cancel-button"]').trigger('click')

    expect(wrapper.emitted('cancel')).toBeTruthy()

    wrapper.unmount()
  })

  it('shows an inline error when errorMessage prop is set', () => {
    const wrapper = mount(AddFollowForm, {
      props: { submitting: false, errorMessage: '该 UP 主不存在' },
    })

    expect(wrapper.find('[data-testid="form-error"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('该 UP 主不存在')

    wrapper.unmount()
  })
})
