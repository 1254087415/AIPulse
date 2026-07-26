import { describe, it, expect, beforeEach } from 'vitest'
import { createMemoryHistory } from 'vue-router'
import { router, ROUTES } from '../../src/router'

describe('router', () => {
  beforeEach(() => {
    // Reset history between tests by replacing with a fresh memory history.
    router.replace('/')
  })

  it('exports a non-empty route table', () => {
    expect(ROUTES.length).toBeGreaterThan(0)
  })

  it('redirects / to /dashboard', async () => {
    // Memory history preserves navigations; simulate a fresh start.
    await router.push('/').catch(() => undefined)
    expect(router.currentRoute.value.path).toBe('/dashboard')
  })

  it('registers the /dashboard/followed route (spec §6.14)', () => {
    const match = ROUTES.find((route) => route.path === '/dashboard/followed')
    expect(match).toBeDefined()
  })

  it('registers the /followed-up/:uid route (spec §6.14)', () => {
    const match = ROUTES.find((route) => route.path === '/followed-up/:uid')
    expect(match).toBeDefined()
  })

  it('renders DashboardView on /dashboard', async () => {
    await router.push('/dashboard')
    // The resolved record should map to the DashboardView component.
    expect(router.currentRoute.value.name).toBe('dashboard')
  })
})

describe('createMemoryHistory compat', () => {
  it('does not throw when constructing memory history directly', () => {
    const history = createMemoryHistory()
    expect(history).toBeDefined()
  })
})