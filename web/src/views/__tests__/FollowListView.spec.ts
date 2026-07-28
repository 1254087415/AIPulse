import { describe, expect, it, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import { VueQueryPlugin } from '@tanstack/vue-query'
import FollowListView from '../FollowListView.vue'

function mockJsonResponse(data: unknown, status = 200) {
  return new Response(JSON.stringify({ success: true, data }), { status })
}

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/followed-up', component: FollowListView },
      { path: '/followed-up/:id', component: { template: '<div />' } },
    ],
  })
}

describe('FollowListView', () => {
  beforeEach(() => {
    vi.unstubAllGlobals()
  })

  it('renders empty state when no followed ups', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => mockJsonResponse([])))
    const router = makeRouter()
    await router.push('/followed-up')
    await router.isReady()

    const wrapper = mount(FollowListView, {
      global: { plugins: [router, VueQueryPlugin] },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('还没有关注任何 UP 主')
  })

  it('surfaces 409 duplicate error inline', async () => {
    let createCalls = 0
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        if (
          init?.method === 'POST' &&
          String(input).includes('/followed-up') &&
          !String(input).match(/\/followed-up\/[^/]+$/)
        ) {
          createCalls += 1
          return new Response(
            JSON.stringify({ success: false, error: 'duplicate' }),
            { status: 409 },
          )
        }
        return mockJsonResponse([])
      }),
    )

    const router = makeRouter()
    await router.push('/followed-up')
    await router.isReady()

    const wrapper = mount(FollowListView, {
      global: { plugins: [router, VueQueryPlugin] },
    })
    await flushPromises()

    await wrapper.find('button.primary').trigger('click')
    await wrapper.find('form.follow-form input#uid').setValue('12345')
    await wrapper.find('form.follow-form').trigger('submit.prevent')
    await flushPromises()

    expect(createCalls).toBeGreaterThan(0)
    expect(wrapper.text()).toContain('该 UP 主已关注')
  })
})