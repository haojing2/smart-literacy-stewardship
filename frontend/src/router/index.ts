import { createRouter, createWebHistory } from 'vue-router'
import Index from '@/views/Index.vue'
import HomeView from '@/views/HomeView.vue'
import LogoutView from '@/views/LogoutView.vue'
import ProjectContextView from '@/views/ProjectContextView.vue'
import ComingSoonView from '@/views/ComingSoonView.vue'
import AdminLayout from '@/views/admin/AdminLayout.vue'
import AdminDashboard from '@/views/admin/AdminDashboard.vue'
import AdminUsers from '@/views/admin/AdminUsers.vue'
import AdminSystem from '@/views/admin/AdminSystem.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/', name: 'index', component: Index },
    { path: '/projects', name: 'home', component: HomeView, meta: { requiresAuth: true } },
    { path: '/research', name: 'research-no-project', component: HomeView, meta: { requiresAuth: true } },
    { path: '/course-design', name: 'course-design', component: HomeView, meta: { requiresAuth: true } },
    { path: '/resource-creation', name: 'resource-creation', component: HomeView, meta: { requiresAuth: true } },
    { path: '/projects/:projectId/resource-creation', name: 'project-resource-creation', component: HomeView, meta: { requiresAuth: true } },
    { path: '/projects/:projectId/context', name: 'project-context', component: ProjectContextView, meta: { requiresAuth: true } },
    { path: '/projects/:projectId/research', name: 'project-research', component: HomeView, meta: { requiresAuth: true } },
    { path: '/projects/:projectId/course-design', name: 'project-course-design', component: HomeView, meta: { requiresAuth: true } },
    { path: '/projects/:projectId/:pathMatch(.*)*', name: 'project-coming-soon', component: ComingSoonView, meta: { requiresAuth: true } },
    { path: '/workspace', redirect: { name: 'home' } },
    { path: '/login', name: 'login', component: Index },
    { path: '/logout', name: 'logout', component: LogoutView },
    {
      path: '/admin',
      component: AdminLayout,
      meta: { requiresAuth: true, roles: ['ADMIN'] },
      children: [
        { path: '', name: 'admin-dashboard', component: AdminDashboard },
        { path: 'users', name: 'admin-users', component: AdminUsers },
        { path: 'system', name: 'admin-system', component: AdminSystem },
      ],
    },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

router.beforeEach((to) => {
  let isAuthenticated = Boolean(sessionStorage.getItem('access_token'))
  let role = ''
  try {
    role = JSON.parse(sessionStorage.getItem('current_user') ?? '{}').role ?? ''
  } catch {
    sessionStorage.removeItem('access_token')
    sessionStorage.removeItem('current_user')
    isAuthenticated = false
  }
  if (to.meta.requiresAuth && !isAuthenticated) return { name: 'login' }
  if (Array.isArray(to.meta.roles) && !to.meta.roles.includes(role)) return { name: 'home' }
  if (to.name === 'login' && isAuthenticated) return { name: role === 'ADMIN' ? 'admin-dashboard' : 'home' }
})

export default router
