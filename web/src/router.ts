import { createRouter, createWebHashHistory } from 'vue-router'
import DashboardView from './views/DashboardView.vue'
import HotspotDetailView from './views/HotspotDetailView.vue'
import FollowListView from './views/FollowListView.vue'
import FollowDetailView from './views/FollowDetailView.vue'
import KeywordsView from './views/KeywordsView.vue'
import SourcesView from './views/SourcesView.vue'
import JobsView from './views/JobsView.vue'
import DigestsView from './views/DigestsView.vue'
import SettingsView from './views/SettingsView.vue'

export default createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', redirect: '/dashboard' },
    { path: '/dashboard', component: DashboardView },
    { path: '/hotspot/:id', component: HotspotDetailView },
    { path: '/followed-up', component: FollowListView },
    { path: '/followed-up/:id', component: FollowDetailView },
    { path: '/keywords', component: KeywordsView },
    { path: '/sources', component: SourcesView },
    { path: '/jobs', component: JobsView },
    { path: '/digests', component: DigestsView },
    { path: '/settings', component: SettingsView },
  ],
})