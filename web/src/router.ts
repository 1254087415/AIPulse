import { createRouter, createWebHashHistory } from 'vue-router'
import DashboardView from './views/DashboardView.vue'
import HotspotDetailView from './views/HotspotDetailView.vue'
import KeywordsView from './views/KeywordsView.vue'
import SourcesView from './views/SourcesView.vue'
import JobsView from './views/JobsView.vue'
import DigestsView from './views/DigestsView.vue'

export default createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', redirect: '/dashboard' },
    { path: '/dashboard', component: DashboardView },
    { path: '/hotspot/:id', component: HotspotDetailView },
    { path: '/keywords', component: KeywordsView },
    { path: '/sources', component: SourcesView },
    { path: '/jobs', component: JobsView },
    { path: '/digests', component: DigestsView },
  ],
})
