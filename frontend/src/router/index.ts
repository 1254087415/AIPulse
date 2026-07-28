/**
 * Router — central navigation table for the AIPulse webview.
 *
 * Layout (spec §6.14):
 *   /                       → redirect to /dashboard
 *   /dashboard              → DashboardView (default tab=hotspot)
 *   /dashboard/followed     → standalone followed view (deep link)
 *   /followed-up/:uid       → FollowDetailView
 *   /hotspot/:id            → HotspotDetailView
 *   /keywords               → KeywordsView
 *   /sources                → SourcesView
 *   /jobs                   → JobsView
 *   /digests                → DigestsView
 *   /settings               → SettingsView
 *
 * HTML5 history mode is used (spec §8.1). In the Tauri webview the embedded
 * static server returns the SPA shell for any unmatched route; in `vite dev`
 * the dev server already does SPA fallback for any non-asset request.
 */

import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import DashboardView from '../views/DashboardView.vue'
import InputView from '../views/InputView.vue'
import SettingsView from '../views/SettingsView.vue'
import TasksView from '../views/TasksView.vue'
import SourcesView from '../views/SourcesView.vue'
import KeywordsView from '../views/KeywordsView.vue'
import JobsView from '../views/JobsView.vue'
import DigestsView from '../views/DigestsView.vue'
import HotspotDetailView from '../views/HotspotDetailView.vue'

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
  { path: '/hotspot/:id', name: 'hotspot-detail', component: HotspotDetailView, props: true },
  { path: '/keywords', name: 'keywords', component: KeywordsView },
  { path: '/sources', name: 'sources', component: SourcesView },
  { path: '/jobs', name: 'jobs', component: JobsView },
  { path: '/digests', name: 'digests', component: DigestsView },
  { path: '/settings', name: 'settings', component: SettingsView },
  // Legacy Tauri-only windows — kept so existing IPC invocations still land
  // on a rendered page.
  { path: '/input', name: 'input', component: InputView },
  { path: '/tasks', name: 'tasks', component: TasksView },
]

export const router = createRouter({
  history: createWebHistory(),
  routes: ROUTES,
  scrollBehavior() {
    return { top: 0 }
  },
})

export default router