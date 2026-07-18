import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { defineComponent, h, nextTick, ref, type Ref } from 'vue'
import { mount } from '@vue/test-utils'
import { useDebounce } from '../useDebounce'

describe('useDebounce', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  function mountTestComponent(initialValue: string, delay: number) {
    let exposedSource: Ref<string> | undefined
    let exposedDebounced: Ref<string> | undefined

    const TestComponent = defineComponent({
      setup() {
        const source = ref(initialValue)
        const debounced = useDebounce(source, delay)
        exposedSource = source as unknown as Ref<string>
        exposedDebounced = debounced as unknown as Ref<string>
        return () => h('div')
      },
    })

    mount(TestComponent)
    return {
      getSource: () => exposedSource!,
      getDebounced: () => exposedDebounced!,
    }
  }

  it('returns the initial value immediately', () => {
    const { getDebounced } = mountTestComponent('hello', 300)
    expect(getDebounced().value).toBe('hello')
  })

  it('updates debounced value after the delay', async () => {
    const { getSource, getDebounced } = mountTestComponent('hello', 300)

    getSource().value = 'world'
    await nextTick()
    expect(getDebounced().value).toBe('hello')

    vi.advanceTimersByTime(300)
    await nextTick()
    expect(getDebounced().value).toBe('world')
  })

  it('resets the timer when value changes before delay', async () => {
    const { getSource, getDebounced } = mountTestComponent('hello', 300)

    getSource().value = 'first'
    await nextTick()
    vi.advanceTimersByTime(200)
    await nextTick()
    expect(getDebounced().value).toBe('hello')

    getSource().value = 'second'
    await nextTick()
    vi.advanceTimersByTime(200)
    await nextTick()
    expect(getDebounced().value).toBe('hello')

    vi.advanceTimersByTime(100)
    await nextTick()
    expect(getDebounced().value).toBe('second')
  })

  it('clears the timer when component is unmounted', async () => {
    const TestComponent = defineComponent({
      setup() {
        const source = ref('hello')
        const debounced = useDebounce(source, 300)
        return () => h('div', debounced.value)
      },
    })

    const wrapper = mount(TestComponent)
    wrapper.unmount()
    await nextTick()

    expect(vi.getTimerCount()).toBe(0)
  })

  it('updates debounced value synchronously when delay is 0', async () => {
    const { getSource, getDebounced } = mountTestComponent('hello', 0)

    getSource().value = 'world'
    await nextTick()

    vi.advanceTimersByTime(0)
    await nextTick()

    expect(getDebounced().value).toBe('world')
  })
})
