/**
 * Router — central navigation table for the AIPulse Tauri webview.
 *
 * Layout (spec §6.14):
 *   /                       → redirect to /dashboard
 *   /dashboard              → DashboardView (default tab=hotspot)
 *   /dashboard/followed     → standalone followed view (deep link)
 *   /followed-up/:uid       → FollowDetailView (Phase 2)
 *   /hotspot/:id            → HotspotDetailView (existing)
 *   /keywords               → KeywordsView (existing)
 *   /sources                → SourcesView (existing)
 *   /jobs                   → JobsView (existing)
 *   /digests                → DigestsView (existing)
 *   /settings               → SettingsView (existing)
 *
 * Hash history is used because the Tauri webview ships as a single HTML
 * document; HTML5 history mode requires a server-side fallback that we don't
 * have inside the bundle.
 */

import { createRouter, createWebHashHistory, type RouteRecordRaw } from 'vue-router'
import DashboardView from '../views/DashboardView.vue'
import InputView from '../views/InputView.vue'
import SettingsView from '../views/SettingsView.vue'
import TasksView from '../views/TasksView.vue'

export const ROUTES: RouteRecordRaw[] = [
  { path: '/', redirect: '/dashboard' },
  { path: '/dashboard', name: 'dashboard', component: DashboardView },
  {
    path: '/dashboard/followed',
    name: 'dashboard-followed',
    component: DashboardView,
  },
  {
    path: '/followed-up/:uid',
    name: 'follow-detail',
    component: () => import('../views/FollowDetailView.vue'),
    props: true,
  },
  { path: '/hotspot/:id', name: 'hotspot-detail', component: TasksView, props: true },
  { path: '/keywords', name: 'keywords', component: SettingsView },
  { path: '/sources', name: 'sources', component: SettingsView },
  { path: '/jobs', name: 'jobs', component: TasksView },
  { path: '/digests', name: 'digests', component: SettingsView },
  { path: '/settings', name: 'settings', component: SettingsView },
  // Legacy Tauri-only windows — kept so existing IPC invocations still land
  // on a rendered page.
  { path: '/input', name: 'input', component: InputView },
  { path: '/tasks', name: 'tasks', component: TasksView },
]

export const router = createRouter({
  history: createWebHashHistory(),
  routes: ROUTES,
  scrollBehavior() {
    return { top: 0 }
  },
})

export default router