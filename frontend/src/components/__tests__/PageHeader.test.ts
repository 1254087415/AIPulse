import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import PageHeader from '../ui/PageHeader.vue'

describe('PageHeader', () => {
  it('renders the title as an h2', () => {
    const wrapper = mount(PageHeader, {
      props: { title: '关注列表' },
    })

    const heading = wrapper.find('h2')
    expect(heading.exists()).toBe(true)
    expect(heading.text()).toBe('关注列表')
    expect(heading.classes()).toContain('page-header__title')
  })

  it('renders the subtitle when provided', () => {
    const wrapper = mount(PageHeader, {
      props: { title: '关注列表', subtitle: '2 个 UP 主 · 全部启用' },
    })

    const subtitle = wrapper.find('.page-header__subtitle')
    expect(subtitle.exists()).toBe(true)
    expect(subtitle.text()).toBe('2 个 UP 主 · 全部启用')
  })

  it('omits the subtitle paragraph when no subtitle is given', () => {
    const wrapper = mount(PageHeader, {
      props: { title: '设置' },
    })

    expect(wrapper.find('.page-header__subtitle').exists()).toBe(false)
  })

  it('forwards the headingId to the h2 element', () => {
    const wrapper = mount(PageHeader, {
      props: { title: '处理记录', headingId: 'records-title' },
    })

    expect(wrapper.find('h2').attributes('id')).toBe('records-title')
  })

  it('renders the actions slot content', () => {
    const wrapper = mount(PageHeader, {
      props: { title: '关注列表' },
      slots: {
        actions: '<button class="probe">+ 添加 UP 主</button>',
      },
    })

    expect(wrapper.find('.page-header__actions .probe').exists()).toBe(true)
    expect(wrapper.find('.page-header__actions').exists()).toBe(true)
  })

  it('omits the actions container when no actions slot is supplied', () => {
    const wrapper = mount(PageHeader, {
      props: { title: '设置' },
    })

    expect(wrapper.find('.page-header__actions').exists()).toBe(false)
  })
})