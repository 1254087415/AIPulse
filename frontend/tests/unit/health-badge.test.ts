import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import HealthBadge from '../../src/components/health-badge/HealthBadge.vue'

describe('HealthBadge', () => {
  it('renders a healthy variant with semantic aria-label and dot', () => {
    const wrapper = mount(HealthBadge, { props: { status: 'healthy' } })

    expect(wrapper.classes()).toContain('health-badge--healthy')
    const dot = wrapper.find('.health-badge__dot')
    expect(dot.exists()).toBe(true)
    expect(dot.attributes('aria-hidden')).toBe('true')
    expect(wrapper.attributes('aria-label')).toBe('运行正常')
    expect(wrapper.text()).toContain('健康')
  })

  it('renders a warning variant in amber', () => {
    const wrapper = mount(HealthBadge, { props: { status: 'warning' } })

    expect(wrapper.classes()).toContain('health-badge--warning')
    expect(wrapper.text()).toContain('关注')
  })

  it('renders an error variant in red', () => {
    const wrapper = mount(HealthBadge, { props: { status: 'error' } })

    expect(wrapper.classes()).toContain('health-badge--error')
    expect(wrapper.text()).toContain('异常')
  })

  it('renders in compact mode without the label text when compact prop is true', () => {
    const wrapper = mount(HealthBadge, {
      props: { status: 'healthy', compact: true },
    })

    expect(wrapper.classes()).toContain('health-badge--compact')
    expect(wrapper.find('.health-badge__label').exists()).toBe(false)
  })

  it('uses a custom label when provided via the label slot', () => {
    const wrapper = mount(HealthBadge, {
      props: { status: 'warning' },
      slots: { label: '降速运行中' },
    })

    expect(wrapper.text()).toContain('降速运行中')
    expect(wrapper.text()).not.toContain('关注')
  })
})