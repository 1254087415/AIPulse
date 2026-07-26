import { describe, it, expect, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createWebHistory } from 'vue-router'
import Sidebar from '../../src/components/sidebar/Sidebar.vue'
import SidebarNav from '../../src/components/sidebar/SidebarNav.vue'

const createTestRouter = () =>
  createRouter({
    history: createWebHistory(),
    routes: [
      { path: '/', redirect: '/dashboard' },
      { path: '/dashboard', component: { template: '<div>Dashboard</div>' } },
      { path: '/sources', component: { template: '<div>Sources</div>' } },
      { path: '/keywords', component: { template: '<div>Keywords</div>' } },
      { path: '/jobs', component: { template: '<div>Jobs</div>' } },
      { path: '/digests', component: { template: '<div>Digests</div>' } },
      { path: '/settings', component: { template: '<div>Settings</div>' } },
    ],
  })

async function pushAndWait(router: ReturnType<typeof createTestRouter>, path: string) {
  await router.push(path)
  await flushPromises()
}

describe('Sidebar', () => {
  let router: ReturnType<typeof createTestRouter>

  beforeEach(() => {
    router = createTestRouter()
  })

  it('renders with a fixed 200px width', async () => {
    const wrapper = mount(Sidebar, {
      global: { plugins: [router] },
      attachTo: document.body,
    })
    await flushPromises()

    const aside = wrapper.find('aside.app-sidebar')
    expect(aside.exists()).toBe(true)
    // jsdom doesn't compute layout; verify the width is bound to the design
    // token through an explicit inline style.
    const style = aside.attributes('style') ?? ''
    expect(style).toContain('var(--sidebar-width)')

    wrapper.unmount()
  })

  it('renders the six expected navigation items per spec §6.9', async () => {
    const wrapper = mount(Sidebar, {
      global: { plugins: [router] },
    })
    await flushPromises()

    const items = wrapper.findAll('.app-sidebar__item')
    expect(items).toHaveLength(6)
    expect(items[0].text()).toContain('AI 热点')
    expect(items[1].text()).toContain('来源')
    expect(items[2].text()).toContain('关键词')
    expect(items[3].text()).toContain('定时任务')
    expect(items[4].text()).toContain('摘要')
    expect(items[5].text()).toContain('系统')
    // The follow-up tabs live inside DashboardView, not here.
    const combined = items.map((i) => i.text()).join(' | ')
    expect(combined).not.toContain('关注列表')
    expect(combined).not.toContain('即将学习')

    wrapper.unmount()
  })

  it('marks the AI 热点 entry as active when on /dashboard', async () => {
    const wrapper = mount(Sidebar, {
      global: { plugins: [router] },
    })
    await pushAndWait(router, '/dashboard')

    const items = wrapper.findAll('.app-sidebar__item')
    expect(items[0].classes()).toContain('app-sidebar__item--active')
    expect(items[0].text()).toContain('AI 热点')

    wrapper.unmount()
  })

  it('marks each non-dashboard entry as active when on its route', async () => {
    const wrapper = mount(Sidebar, {
      global: { plugins: [router] },
    })

    const cases: Array<[string, number]> = [
      ['/sources', 1],
      ['/keywords', 2],
      ['/jobs', 3],
      ['/digests', 4],
      ['/settings', 5],
    ]
    for (const [path, index] of cases) {
      await pushAndWait(router, path)
      const items = wrapper.findAll('.app-sidebar__item')
      items.forEach((item, i) => {
        if (i === index) {
          expect(item.classes()).toContain('app-sidebar__item--active')
        } else {
          expect(item.classes()).not.toContain('app-sidebar__item--active')
        }
      })
    }

    wrapper.unmount()
  })

  it('switches the active item when the route changes', async () => {
    const wrapper = mount(Sidebar, {
      global: { plugins: [router] },
    })

    await pushAndWait(router, '/sources')
    expect(wrapper.findAll('.app-sidebar__item')[1].classes()).toContain(
      'app-sidebar__item--active',
    )

    await pushAndWait(router, '/settings')
    const updated = wrapper.findAll('.app-sidebar__item')
    expect(updated[1].classes()).not.toContain('app-sidebar__item--active')
    expect(updated[5].classes()).toContain('app-sidebar__item--active')

    wrapper.unmount()
  })

  it('renders sidebar items as focusable anchors for keyboard users', async () => {
    const wrapper = mount(Sidebar, {
      global: { plugins: [router] },
    })
    await flushPromises()

    const items = wrapper.findAll('.app-sidebar__item')
    items.forEach((item) => {
      expect(item.element.tagName).toBe('A')
    })

    wrapper.unmount()
  })

  it('navigates when an item is clicked', async () => {
    const wrapper = mount(Sidebar, {
      global: { plugins: [router] },
    })
    await flushPromises()

    const sourcesLink = wrapper.findAll('.app-sidebar__item')[1]
    await sourcesLink.trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.path).toBe('/sources')

    wrapper.unmount()
  })

  it('collapses when the collapse button is clicked', async () => {
    const wrapper = mount(Sidebar, {
      global: { plugins: [router] },
      attachTo: document.body,
    })
    await flushPromises()

    const aside = wrapper.find('aside.app-sidebar')
    expect(aside.classes()).toContain('app-sidebar')
    expect(aside.classes()).not.toContain('app-sidebar--collapsed')

    const toggle = wrapper.find('[data-testid="sidebar-toggle"]')
    expect(toggle.exists()).toBe(true)
    await toggle.trigger('click')
    await flushPromises()

    expect(wrapper.find('aside.app-sidebar').classes()).toContain('app-sidebar--collapsed')

    // jsdom doesn't compute layout, so verify the inline style switches to
    // the collapsed width token (--sidebar-width-collapsed = 56px).
    const collapsedStyle = wrapper.find('aside.app-sidebar').attributes('style') ?? ''
    expect(collapsedStyle).toContain('var(--sidebar-width-collapsed)')

    // Click again to expand.
    await wrapper.find('[data-testid="sidebar-toggle"]').trigger('click')
    await flushPromises()
    const expandedStyle = wrapper.find('aside.app-sidebar').attributes('style') ?? ''
    expect(expandedStyle).toContain('var(--sidebar-width)')

    wrapper.unmount()
  })

  it('uses --sidebar-width token for its expanded layout', async () => {
    const wrapper = mount(Sidebar, {
      global: { plugins: [router] },
    })
    await flushPromises()

    const aside = wrapper.find('aside.app-sidebar')
    const styleAttr = aside.attributes('style') ?? ''
    // The width is bound to the design token so swapping the CSS variable
    // changes the layout in one place.
    expect(styleAttr).toContain('var(--sidebar-width)')

    wrapper.unmount()
  })
})

describe('SidebarNav', () => {
  it('renders nav items passed via props', async () => {
    const wrapper = mount(SidebarNav, {
      props: {
        items: [
          { key: 'home', label: 'Home', to: '/home' },
          { key: 'about', label: 'About', to: '/about' },
        ],
        activeKey: 'home',
      },
    })

    const items = wrapper.findAll('.app-sidebar__item')
    expect(items).toHaveLength(2)
    expect(items[0].classes()).toContain('app-sidebar__item--active')
    expect(items[1].classes()).not.toContain('app-sidebar__item--active')

    wrapper.unmount()
  })

  it('emits a navigate event when an item is clicked', async () => {
    const wrapper = mount(SidebarNav, {
      props: {
        items: [
          { key: 'home', label: 'Home', to: '/home' },
          { key: 'about', label: 'About', to: '/about' },
        ],
        activeKey: 'home',
      },
    })

    await wrapper.findAll('.app-sidebar__item')[1].trigger('click')

    expect(wrapper.emitted('navigate')).toBeTruthy()
    expect(wrapper.emitted('navigate')![0]).toEqual(['/about'])

    wrapper.unmount()
  })
})