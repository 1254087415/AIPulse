import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import StatusBadge from '../ui/StatusBadge.vue'

describe('StatusBadge', () => {
  it.each(['success', 'warning', 'danger', 'neutral'] as const)(
    'renders the %s semantic tone',
    (tone) => {
      const wrapper = mount(StatusBadge, {
        props: { tone, label: '状态' },
      })

      expect(wrapper.text()).toBe('状态')
      expect(wrapper.classes()).toContain(`status-badge--${tone}`)
      expect(wrapper.attributes('role')).toBe('status')
    },
  )

  it('uses neutral styling by default', () => {
    const wrapper = mount(StatusBadge, {
      slots: { default: '未知' },
    })

    expect(wrapper.text()).toBe('未知')
    expect(wrapper.classes()).toContain('status-badge--neutral')
  })
})
