import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import InputView from '../InputView.vue'

vi.mock('@tauri-apps/api/core', () => ({ invoke: vi.fn() }))
vi.mock('@tauri-apps/api/event', () => ({ listen: vi.fn(() => vi.fn()) }))

describe('InputView', () => {
  it('renders an input field with the input-field class', async () => {
    const wrapper = mount(InputView)
    expect(wrapper.find('.input-field').exists()).toBe(true)
    wrapper.unmount()
  })
})
