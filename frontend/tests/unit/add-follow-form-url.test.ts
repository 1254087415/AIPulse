/**
 * AddFollowForm — URL-input variant (spec §6.6).
 *
 * The v0.3 form is a single textbox that accepts a B站 profile URL. The
 * platform is hard-coded to bilibili (spec §1.3 lists the other platforms
 * as out-of-scope). Non-bilibili URLs leave the submit button disabled
 * with an inline hint.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

vi.mock('../../src/api/followedUp', () => ({
  validateFollowed: vi.fn(),
}))

import AddFollowForm from '../../src/components/follow-list-panel/AddFollowForm.vue'
import { validateFollowed } from '../../src/api/followedUp'

const mockedValidate = vi.mocked(validateFollowed)

const mountForm = (propsOverride: Record<string, unknown> = {}) =>
  mount(AddFollowForm, {
    props: { submitting: false, ...propsOverride },
  })

describe('AddFollowForm (URL input)', () => {
  beforeEach(() => {
    mockedValidate.mockReset()
    mockedValidate.mockResolvedValue({
      valid: true,
      display_name: '李沐',
      avatar_url: null,
    })
  })

  it('renders a single URL textbox (no platform dropdown)', () => {
    const wrapper = mountForm()
    expect(wrapper.find('[data-testid="url-input"]').exists()).toBe(true)
    // Spec §1.3 — only B站 is supported in v0.3, so the dropdown is gone.
    expect(wrapper.find('[data-testid="platform-select"]').exists()).toBe(false)
    wrapper.unmount()
  })

  it('keeps the submit button disabled until a valid bilibili URL is entered', async () => {
    const wrapper = mountForm()
    const button = wrapper.find('[data-testid="submit-button"]')
    expect((button.element as HTMLButtonElement).disabled).toBe(true)

    // example.com is not a B站 URL — button stays disabled.
    await wrapper.find('[data-testid="url-input"]').setValue('https://example.com/foo')
    await flushPromises()
    expect((wrapper.find('[data-testid="submit-button"]').element as HTMLButtonElement).disabled).toBe(true)

    // space.bilibili.com — enables the button and resolves the uid.
    await wrapper.find('[data-testid="url-input"]').setValue(
      'https://space.bilibili.com/1567748478?from=search',
    )
    await flushPromises()
    expect((wrapper.find('[data-testid="submit-button"]').element as HTMLButtonElement).disabled).toBe(
      false,
    )

    wrapper.unmount()
  })

  it('surfaces a hint when the URL is not a bilibili profile page', async () => {
    const wrapper = mountForm()
    await wrapper.find('[data-testid="url-input"]').setValue('https://example.com/foo')
    await flushPromises()
    expect(wrapper.find('[data-testid="url-hint"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('请粘贴 B 站主页链接')
    wrapper.unmount()
  })

  it('submits { platform: "bilibili", uid } when the form is submitted', async () => {
    const wrapper = mountForm()
    await wrapper.find('[data-testid="url-input"]').setValue(
      'https://space.bilibili.com/1567748478',
    )
    await flushPromises()
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(wrapper.emitted('submit')).toBeTruthy()
    expect(wrapper.emitted('submit')![0]).toEqual([
      { platform: 'bilibili', uid: '1567748478' },
    ])

    wrapper.unmount()
  })

  it('submits the uid when given just a numeric bilibili mid', async () => {
    const wrapper = mountForm()
    await wrapper.find('[data-testid="url-input"]').setValue('1567748478')
    await flushPromises()
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(wrapper.emitted('submit')![0]).toEqual([
      { platform: 'bilibili', uid: '1567748478' },
    ])

    wrapper.unmount()
  })

  it('does not call the API on its own — the parent owns createFollowed', async () => {
    const wrapper = mountForm()
    await wrapper.find('[data-testid="url-input"]').setValue(
      'https://space.bilibili.com/1567748478',
    )
    await flushPromises()
    // validateFollowed is exposed for parent-driven preview but the form
    // itself must not POST anything by itself.
    expect(mockedValidate).not.toHaveBeenCalled()
    wrapper.unmount()
  })
})