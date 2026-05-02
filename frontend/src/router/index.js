import { createRouter, createWebHistory } from 'vue-router'
import Home from '../views/Home.vue'
import Process from '../views/MainView.vue'
import Personas from '../views/PersonasView.vue'

const routes = [
  { path: '/', name: 'Home', component: Home },
  { path: '/process/:projectId', name: 'Process', component: Process, props: true },
  { path: '/personas/:projectId', name: 'Personas', component: Personas, props: true },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
