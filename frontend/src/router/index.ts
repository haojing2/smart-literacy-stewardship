import { createRouter, createWebHistory } from 'vue-router'
import Index from '@/views/Index.vue'
import HomeView from '@/views/HomeView.vue'
import LoginView from '@/views/LoginView.vue'
import ProjectContextView from '@/views/ProjectContextView.vue'
import ComingSoonView from '@/views/ComingSoonView.vue'

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
    { path: '/login', name: 'login', component: LoginView },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

router.beforeEach((to) => {
  const isAuthenticated = Boolean(sessionStorage.getItem('access_token'))
  if (to.meta.requiresAuth && !isAuthenticated) return { name: 'login' }
  if (to.name === 'login' && isAuthenticated) return { name: 'home' }
})

export default router
