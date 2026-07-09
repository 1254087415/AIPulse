import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { VueQueryPlugin } from '@tanstack/vue-query'
import DashboardView from '../DashboardView.vue'

describe('DashboardView', () => {
  it('renders page title', () => {
    const wrapper = mount(DashboardView, { global: { plugins: [VueQueryPlugin] } })
    expect(wrapper.find('h1').text()).toBe('AI 热点')
  })
})
