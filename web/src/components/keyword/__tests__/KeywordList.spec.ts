import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import KeywordList from '../KeywordList.vue'
import type { Keyword } from '../../../types'

function createKeyword(overrides: Partial<Keyword> = {}): Keyword {
  return {
    id: 'keyword-1',
    value: 'Kimi',
    is_active: true,
    notify_on_match: true,
    ...overrides,
  }
}

function mountKeywordList(props: { keywords?: Keyword[]; updating?: Record<string, boolean> } = {}) {
  return mount(KeywordList, {
    props: {
      keywords: [],
      ...props,
    },
  })
}

describe('KeywordList', () => {
  beforeEach(() => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders empty list without crashing', () => {
    const wrapper = mountKeywordList()

    expect(wrapper.findAll('li').length).toBe(0)
  })

  it('renders keyword value and notification tag', () => {
    const wrapper = mountKeywordList({ keywords: [createKeyword()] })

    expect(wrapper.text()).toContain('Kimi')
    const tag = wrapper.find('.keyword-main .tag')
    expect(tag.text()).toBe('通知')
    expect(tag.classes()).toContain('tag-signal')
  })

  it('renders silent tag when notify_on_match is false', () => {
    const wrapper = mountKeywordList({ keywords: [createKeyword({ notify_on_match: false })] })

    const tag = wrapper.find('.keyword-main .tag')
    expect(tag.text()).toBe('静默')
    expect(tag.classes()).not.toContain('tag-signal')
  })

  it('applies inactive style when is_active is false', () => {
    const wrapper = mountKeywordList({ keywords: [createKeyword({ is_active: false })] })

    expect(wrapper.find('.keyword-value.inactive').exists()).toBe(true)
  })

  it('emits toggleNotify with the keyword payload', async () => {
    const keyword = createKeyword()
    const wrapper = mountKeywordList({ keywords: [keyword] })

    await wrapper.find('button:first-of-type').trigger('click')
    await flushPromises()

    expect(wrapper.emitted('toggleNotify')).toHaveLength(1)
    expect(wrapper.emitted('toggleNotify')![0]).toEqual([keyword])
  })

  it('emits toggleActive with the keyword payload', async () => {
    const keyword = createKeyword()
    const wrapper = mountKeywordList({ keywords: [keyword] })

    const buttons = wrapper.findAll('button')
    await buttons[1].trigger('click')
    await flushPromises()

    expect(wrapper.emitted('toggleActive')).toHaveLength(1)
    expect(wrapper.emitted('toggleActive')![0]).toEqual([keyword])
  })

  it('emits delete with the keyword payload', async () => {
    const keyword = createKeyword()
    const wrapper = mountKeywordList({ keywords: [keyword] })

    await wrapper.find('button.action-danger').trigger('click')
    await flushPromises()

    expect(wrapper.emitted('delete')).toHaveLength(1)
    expect(wrapper.emitted('delete')![0]).toEqual([keyword])
  })

  it('does not emit delete when the user cancels the confirmation', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(false)
    const keyword = createKeyword()
    const wrapper = mountKeywordList({ keywords: [keyword] })

    await wrapper.find('button.action-danger').trigger('click')
    await flushPromises()

    expect(wrapper.emitted('delete')).toBeFalsy()
  })

  it('disables all action buttons when keyword is updating', () => {
    const wrapper = mountKeywordList({
      keywords: [createKeyword()],
      updating: { 'keyword-1': true },
    })

    const buttons = wrapper.findAll('button')
    expect(buttons.length).toBe(3)
    buttons.forEach((button) => {
      expect((button.element as HTMLButtonElement).disabled).toBe(true)
    })
  })

  it('renders multiple keywords in order', () => {
    const keywords = [
      createKeyword({ id: 'k1', value: 'Alpha' }),
      createKeyword({ id: 'k2', value: 'Beta' }),
      createKeyword({ id: 'k3', value: 'Gamma' }),
    ]
    const wrapper = mountKeywordList({ keywords })

    const items = wrapper.findAll('li')
    expect(items.length).toBe(3)
    expect(items[0].text()).toContain('Alpha')
    expect(items[1].text()).toContain('Beta')
    expect(items[2].text()).toContain('Gamma')
  })

  it('does not disable buttons for keywords not marked as updating', () => {
    const wrapper = mountKeywordList({
      keywords: [createKeyword({ id: 'k1' })],
      updating: { 'keyword-2': true },
    })

    const buttons = wrapper.findAll('button')
    buttons.forEach((button) => {
      expect((button.element as HTMLButtonElement).disabled).toBe(false)
    })
  })
})
