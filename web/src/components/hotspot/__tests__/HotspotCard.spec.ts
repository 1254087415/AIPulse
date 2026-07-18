import { describe, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { RouterLink } from 'vue-router'
import HotspotCard from '../HotspotCard.vue'
import type { Hotspot } from '../../../types'

vi.mock('vue-router', () => ({
  RouterLink: {
    name: 'RouterLink',
    props: ['to'],
    template: '<a :href="to"><slot /></a>',
  },
}))

function createHotspot(overrides: Partial<Hotspot> = {}): Hotspot {
  return {
    id: 'hotspot-1',
    title: 'Test Title',
    url: 'https://example.com/article',
    summary: 'Test summary.',
    source_type: 'news',
    heat_score: 85.5,
    importance: 'high',
    category: 'ai-models',
    published_at: '2024-01-15T08:30:00.000Z',
    ...overrides,
  }
}

function mountCard(hotspot: Hotspot) {
  return mount(HotspotCard, {
    props: { hotspot },
    global: {
      components: { RouterLink },
    },
  })
}

describe('HotspotCard', () => {
  it('renders title, summary and meta tags', () => {
    const hotspot = createHotspot()
    const wrapper = mountCard(hotspot)

    expect(wrapper.find('.reading-title').text()).toBe(hotspot.title)
    expect(wrapper.find('.reading-summary').text()).toBe(hotspot.summary)
    expect(wrapper.text()).toContain(hotspot.source_type)
    expect(wrapper.text()).toContain(hotspot.importance)
  })

  it('renders external link for safe URLs', () => {
    const hotspot = createHotspot({ url: 'https://example.com/article' })
    const wrapper = mountCard(hotspot)

    const link = wrapper.find('a.external')
    expect(link.exists()).toBe(true)
    expect(link.attributes('href')).toBe(hotspot.url)
  })

  it('does not render external link for unsafe URLs', async () => {
    const hotspot = createHotspot({ url: 'javascript:alert(1)' })
    const wrapper = mountCard(hotspot)
    await flushPromises()

    expect(wrapper.find('a.external').exists()).toBe(false)
    expect(wrapper.text()).toContain('原文不可用')
  })

  it('formats published_at with formatDateTime', () => {
    const hotspot = createHotspot({ published_at: '2024-01-15T08:30:00.000Z' })
    const wrapper = mountCard(hotspot)

    expect(wrapper.find('time').exists()).toBe(true)
    expect(wrapper.find('time').text()).toContain('2024')
  })

  it('does not render time when published_at is null', () => {
    const hotspot = createHotspot({ published_at: null })
    const wrapper = mountCard(hotspot)

    expect(wrapper.find('time').exists()).toBe(false)
  })

  it('renders heat bar with 0% width when heat_score is 0', () => {
    const hotspot = createHotspot({ heat_score: 0 })
    const wrapper = mountCard(hotspot)

    expect(wrapper.find('.score-value').text()).toBe('0.0')
    expect(wrapper.find('.score-bar i').attributes('style')).toContain('width: 0%')
  })

  it('caps heat bar width at 100% when heat_score is very large', () => {
    const hotspot = createHotspot({ heat_score: 20 })
    const wrapper = mountCard(hotspot)

    expect(wrapper.find('.score-bar i').attributes('style')).toContain('width: 100%')
  })

  it('does not render summary paragraph when summary is empty', () => {
    const hotspot = createHotspot({ summary: '' })
    const wrapper = mountCard(hotspot)

    expect(wrapper.find('.reading-summary').exists()).toBe(false)
  })
})
