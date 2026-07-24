import { describe, it, expect, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createWebHashHistory } from 'vue-router'
import Sidebar from '../../src/components/sidebar/Sidebar.vue'
import SidebarNav from '../../src/components/sidebar/SidebarNav.vue'

const createTestRouter = () =>
  createRouter({
    history: createWebHashHistory(),
    routes: [
      { path: '/', redirect: '/dashboard' },
      { path: '/dashboard', component: { template: '<div>Dashboard</div>' } },
      { path: '/followed', component: { template: '<div>Followed</div>' } },
      { path: '/upcoming', component: { template: '<div>Upcoming</div>' } },
      { path: '/failed', component: { template: '<div>Failed</div>' } },
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

  it('renders the four expected navigation items: 首页 / 关注 / 即将学习 / 失败', async () => {
    const wrapper = mount(Sidebar, {
      global: { plugins: [router] },
    })
    await flushPromises()

    const items = wrapper.findAll('.app-sidebar__item')
    expect(items).toHaveLength(4)
    expect(items[0].text()).toContain('首页')
    expect(items[1].text()).toContain('关注')
    expect(items[2].text()).toContain('即将学习')
    expect(items[3].text()).toContain('失败')

    wrapper.unmount()
  })

  it('marks the active item based on the current route', async () => {
    const wrapper = mount(Sidebar, {
      global: { plugins: [router] },
    })
    await pushAndWait(router, '/followed')

    const items = wrapper.findAll('.app-sidebar__item')
    expect(items[0].classes()).not.toContain('app-sidebar__item--active')
    expect(items[1].classes()).toContain('app-sidebar__item--active')

    wrapper.unmount()
  })

  it('switches the active item when the route changes', async () => {
    const wrapper = mount(Sidebar, {
      global: { plugins: [router] },
    })

    await pushAndWait(router, '/upcoming')
    const items = wrapper.findAll('.app-sidebar__item')
    expect(items[2].classes()).toContain('app-sidebar__item--active')

    await pushAndWait(router, '/failed')
    const updated = wrapper.findAll('.app-sidebar__item')
    expect(updated[2].classes()).not.toContain('app-sidebar__item--active')
    expect(updated[3].classes()).toContain('app-sidebar__item--active')

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

    const followedLink = wrapper.findAll('.app-sidebar__item')[1]
    await followedLink.trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.path).toBe('/followed')

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