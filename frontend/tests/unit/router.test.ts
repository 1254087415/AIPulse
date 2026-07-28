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

describe('route table integrity (spec §6.14 / §8.1)', () => {
  // Each of these 5 routes must map to its own dedicated view, not be aliased
  // to a catch-all page like SettingsView or TasksView. We assert by name
  // string, which keeps the test resilient to component refactors.
  const expected: Record<string, string> = {
    '/hotspot/:id': 'hotspot-detail',
    '/keywords': 'keywords',
    '/sources': 'sources',
    '/jobs': 'jobs',
    '/digests': 'digests',
  }

  for (const [path, name] of Object.entries(expected)) {
    it(`registers ${path} → ${name}`, () => {
      const match = ROUTES.find((route) => route.path === path)
      expect(match).toBeDefined()
      expect(match?.name).toBe(name)
    })
  }

  it('does not alias /sources /keywords /jobs /digests /hotspot/:id to SettingsView', async () => {
    // Spec §8.1: each route must land on its own view. Navigating to one of
    // these paths must NOT resolve to the SettingsView component.
    const settingsComponent = ROUTES.find((r) => r.path === '/settings')?.component
    const targets = ['/sources', '/keywords', '/jobs', '/digests', '/hotspot/abc123']
    for (const path of targets) {
      await router.push(path).catch(() => undefined)
      expect(router.currentRoute.value.matched[0]?.components?.default).not.toBe(
        settingsComponent,
      )
    }
  })
})

describe('createMemoryHistory compat', () => {
  it('does not throw when constructing memory history directly', () => {
    const history = createMemoryHistory()
    expect(history).toBeDefined()
  })
})