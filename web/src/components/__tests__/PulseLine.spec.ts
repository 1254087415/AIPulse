import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import PulseLine from '../PulseLine.vue'

function mountPulseLine(props: { alive?: boolean } = {}) {
  return mount(PulseLine, { props })
}

describe('PulseLine', () => {
  it('renders alive state by default', () => {
    const wrapper = mountPulseLine()

    expect(wrapper.find('.pulse-line').exists()).toBe(true)
    expect(wrapper.find('.pulse-line.flatline').exists()).toBe(false)
  })

  it('renders flatline state when alive is false', () => {
    const wrapper = mountPulseLine({ alive: false })

    expect(wrapper.find('.pulse-line.flatline').exists()).toBe(true)
  })

  it('renders an svg trace and a dot', () => {
    const wrapper = mountPulseLine()

    expect(wrapper.find('svg.trace').exists()).toBe(true)
    expect(wrapper.find('span.dot').exists()).toBe(true)
  })

  it('is marked as aria-hidden', () => {
    const wrapper = mountPulseLine()

    expect(wrapper.find('.pulse-line').attributes('aria-hidden')).toBe('true')
  })
})
