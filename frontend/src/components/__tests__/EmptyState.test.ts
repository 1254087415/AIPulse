import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import EmptyState from '../ui/EmptyState.vue'

describe('EmptyState', () => {
  it('renders an icon, title, and description', () => {
    const wrapper = mount(EmptyState, {
      props: {
        title: '暂无内容',
        description: '添加内容后会显示在这里。',
      },
    })

    expect(wrapper.get('[data-testid="empty-state-icon"]').attributes('aria-hidden')).toBe('true')
    expect(wrapper.get('[data-testid="empty-state-title"]').text()).toBe('暂无内容')
    expect(wrapper.get('[data-testid="empty-state-description"]').text()).toBe('添加内容后会显示在这里。')
    expect(wrapper.find('a').exists()).toBe(false)
  })

  it('renders an optional navigation action', () => {
    const wrapper = mount(EmptyState, {
      props: {
        title: '暂无热点',
        description: '添加关注词后会自动同步。',
        actionLabel: '前往添加关注词',
        actionHref: '/keywords',
      },
    })

    const action = wrapper.get('a')
    expect(action.text()).toBe('前往添加关注词')
    expect(action.attributes('href')).toBe('/keywords')
  })

  it('supports compact presentation for nested empty content', () => {
    const wrapper = mount(EmptyState, {
      props: {
        title: '暂无摘要内容',
        description: '该条摘要尚未生成。',
        compact: true,
      },
    })

    expect(wrapper.classes()).toContain('empty-state--compact')
    expect(wrapper.attributes('role')).toBeUndefined()
  })
})
