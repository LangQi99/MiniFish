import { createRouter, createWebHistory } from 'vue-router'
import Home from '../views/Home.vue'
import Dashboard from '../views/Dashboard.vue'

const routes = [
  { path: '/', name: 'Home', component: Home },
  { path: '/dashboard/:projectId', name: 'Dashboard', component: Dashboard, props: true },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
