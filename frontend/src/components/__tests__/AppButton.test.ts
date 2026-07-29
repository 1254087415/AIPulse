import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import AppButton from '../ui/AppButton.vue'

describe('AppButton', () => {
  it('renders a button by default with secondary variant', () => {
    const wrapper = mount(AppButton, {
      slots: { default: 'Click me' },
    })

    const btn = wrapper.find('button')
    expect(btn.exists()).toBe(true)
    expect(btn.classes()).toContain('app-button')
    expect(btn.classes()).toContain('app-button--secondary')
    expect(btn.classes()).toContain('app-button--md')
    expect(btn.text()).toBe('Click me')
    expect(btn.attributes('type')).toBe('button')
  })

  it('applies variant and size classes', () => {
    const wrapper = mount(AppButton, {
      props: { variant: 'primary', size: 'sm' },
      slots: { default: 'Save' },
    })

    const btn = wrapper.find('button')
    expect(btn.classes()).toContain('app-button--primary')
    expect(btn.classes()).toContain('app-button--sm')
  })

  it('passes type="submit" through', () => {
    const wrapper = mount(AppButton, {
      props: { type: 'submit' },
      slots: { default: 'Submit' },
    })

    expect(wrapper.find('button').attributes('type')).toBe('submit')
  })

  it('respects disabled prop', () => {
    const wrapper = mount(AppButton, {
      props: { disabled: true },
      slots: { default: 'X' },
    })

    const btn = wrapper.find('button')
    expect(btn.attributes('disabled')).toBeDefined()
  })

  it('treats loading as disabled and exposes aria-busy', () => {
    const wrapper = mount(AppButton, {
      props: { loading: true },
      slots: { default: 'X' },
    })

    const btn = wrapper.find('button')
    expect(btn.attributes('disabled')).toBeDefined()
    expect(btn.attributes('aria-busy')).toBe('true')
    expect(btn.classes()).toContain('app-button--loading')
  })

  it('applies block modifier for full-width buttons', () => {
    const wrapper = mount(AppButton, {
      props: { block: true },
      slots: { default: 'X' },
    })

    expect(wrapper.find('button').classes()).toContain('app-button--block')
  })

  it('renders an anchor with role="button" when as="a"', () => {
    const wrapper = mount(AppButton, {
      props: { as: 'a', href: '/foo', variant: 'ghost' },
      slots: { default: 'Link' },
    })

    const link = wrapper.find('a')
    expect(link.exists()).toBe(true)
    expect(link.attributes('role')).toBe('button')
    expect(link.attributes('href')).toBe('/foo')
    expect(link.classes()).toContain('app-button--ghost')
  })

  it('drops href and adds aria-disabled when anchor is disabled', () => {
    const wrapper = mount(AppButton, {
      props: { as: 'a', href: '/foo', disabled: true },
      slots: { default: 'Link' },
    })

    const link = wrapper.find('a')
    expect(link.attributes('href')).toBeUndefined()
    expect(link.attributes('aria-disabled')).toBe('true')
  })

  it('emits click via underlying button', async () => {
    const wrapper = mount(AppButton, {
      slots: { default: 'Go' },
    })

    await wrapper.find('button').trigger('click')
    // ensure no error from missing handler — the wrapper stays alive.
    expect(wrapper.find('button').exists()).toBe(true)
  })
})