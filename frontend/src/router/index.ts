import { createRouter, createWebHistory } from 'vue-router'
import WorklogDashboard from '@/views/WorklogDashboard.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      redirect: '/worklog'
    },
    {
      path: '/worklog',
      name: 'worklog',
      component: WorklogDashboard
    },
    {
      path: '/bug',
      name: 'bug',
      component: () => import('@/views/BugView.vue')
    }
  ]
})

export default router
