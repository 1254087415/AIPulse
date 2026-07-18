import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import HotspotList from '../HotspotList.vue'
import type { Hotspot } from '../../../types'

vi.mock('../HotspotCard.vue', () => ({
  default: {
    name: 'HotspotCard',
    props: ['hotspot'],
    template: '<article class="hotspot-card-stub" :data-id="hotspot.id">{{ hotspot.title }}</article>',
  },
}))

function createHotspot(overrides: Partial<Hotspot> = {}): Hotspot {
  return {
    id: 'hotspot-1',
    title: 'Test Hotspot',
    url: 'https://example.com/article',
    summary: null,
    source_type: 'news',
    heat_score: 50,
    importance: 'medium',
    category: null,
    published_at: null,
    ...overrides,
  }
}

function mountHotspotList(props: { hotspots?: Hotspot[]; loading?: boolean } = {}) {
  return mount(HotspotList, {
    props: {
      hotspots: [],
      ...props,
    },
  })
}

describe('HotspotList', () => {
  it('renders empty list without crashing', () => {
    const wrapper = mountHotspotList()

    expect(wrapper.findAll('article').length).toBe(0)
    expect(wrapper.find('.state-loading').exists()).toBe(false)
  })

  it('renders a HotspotCard for each hotspot', () => {
    const hotspots = [
      createHotspot({ id: 'h1', title: 'First' }),
      createHotspot({ id: 'h2', title: 'Second' }),
    ]
    const wrapper = mountHotspotList({ hotspots })

    const cards = wrapper.findAll('article')
    expect(cards.length).toBe(2)
    expect(cards[0].attributes('data-id')).toBe('h1')
    expect(cards[1].attributes('data-id')).toBe('h2')
  })

  it('shows loading state when loading prop is true', () => {
    const wrapper = mountHotspotList({ loading: true })

    expect(wrapper.find('.state-loading').exists()).toBe(true)
    expect(wrapper.find('.state-loading').text()).toContain('正在同步信号')
  })

  it('does not show loading state when loading prop is false', () => {
    const wrapper = mountHotspotList({ hotspots: [createHotspot()], loading: false })

    expect(wrapper.find('.state-loading').exists()).toBe(false)
  })

  it('applies increasing animation delays to cards', () => {
    const hotspots = [
      createHotspot({ id: 'h1' }),
      createHotspot({ id: 'h2' }),
      createHotspot({ id: 'h3' }),
    ]
    const wrapper = mountHotspotList({ hotspots })

    const cards = wrapper.findAll('article')
    expect(cards[0].attributes('style')).toContain('animation-delay: 0ms')
    expect(cards[1].attributes('style')).toContain('animation-delay: 40ms')
    expect(cards[2].attributes('style')).toContain('animation-delay: 80ms')
  })

  it('renders section with aria-label', () => {
    const wrapper = mountHotspotList()

    expect(wrapper.find('section[aria-label="热点列表"]').exists()).toBe(true)
  })
})
