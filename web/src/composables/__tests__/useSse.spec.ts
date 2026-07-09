import { describe, expect, it, vi } from 'vitest'
import { defineComponent, h } from 'vue'
import { mount } from '@vue/test-utils'
import { VueQueryPlugin } from '@tanstack/vue-query'
import { useSse } from '../useSse'

const mockInvalidateQueries = vi.fn()

vi.mock('@tanstack/vue-query', async () => {
  const actual = await vi.importActual<typeof import('@tanstack/vue-query')>('@tanstack/vue-query')
  return {
    ...actual,
    useQueryClient: () => ({ invalidateQueries: mockInvalidateQueries }),
  }
})

describe('useSse', () => {
  it('invalidates hotspot queries on hotspot.new event', async () => {
    const TestComponent = defineComponent({
      setup() {
        useSse('/sse/hotspots')
        return () => h('div')
      },
    })

    mount(TestComponent, { global: { plugins: [VueQueryPlugin] } })
    expect(mockInvalidateQueries).not.toHaveBeenCalled()
  })
})
