import { createRouter, createWebHashHistory } from 'vue-router'
import InputView from './views/InputView.vue'
import SettingsView from './views/SettingsView.vue'
import TasksView from './views/TasksView.vue'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', redirect: '/input' },
    { path: '/input', component: InputView },
    { path: '/settings', component: SettingsView },
    { path: '/tasks', component: TasksView },
  ],
})

export default router
