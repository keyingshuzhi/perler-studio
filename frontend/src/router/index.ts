import { createRouter, createWebHistory } from 'vue-router'

import ConvertView from '@/views/ConvertView.vue'
import AuthView from '@/views/AuthView.vue'
import AdminView from '@/views/AdminView.vue'
import CreateView from '@/views/CreateView.vue'
import EditorView from '@/views/EditorView.vue'
import ExportView from '@/views/ExportView.vue'
import GalleryView from '@/views/GalleryView.vue'
import HomeView from '@/views/HomeView.vue'
import NotFoundView from '@/views/NotFoundView.vue'
import ProjectsView from '@/views/ProjectsView.vue'
import PublicationView from '@/views/PublicationView.vue'
import AccountView from '@/views/AccountView.vue'
import ShareView from '@/views/ShareView.vue'
import TemplateMarketView from '@/views/TemplateMarketView.vue'
import { useAuthStore } from '@/stores/auth'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: HomeView, meta: { title: '拼豆图纸工作台' } },
    { path: '/auth', component: AuthView, meta: { title: '登录或注册', guestOnly: true } },
    { path: '/gallery', component: GalleryView, meta: { title: '作品社区' } },
    { path: '/account', component: AccountView, meta: { title: '我的账户', requiresAuth: true } },
    { path: '/admin', component: AdminView, meta: { title: '平台管理', requiresAuth: true, requiresAdmin: true } },
    { path: '/convert', component: ConvertView, meta: { title: '从图片转换', requiresAuth: true } },
    { path: '/create', component: CreateView, meta: { title: '创作工作室', requiresAuth: true } },
    { path: '/templates', component: TemplateMarketView, meta: { title: '模板市场', requiresAuth: true } },
    { path: '/editor/:projectId', component: EditorView, meta: { title: '专业编辑器', requiresAuth: true } },
    { path: '/projects', component: ProjectsView, meta: { title: '项目库', requiresAuth: true } },
    { path: '/export/:projectId', component: ExportView, meta: { title: '导出图纸', requiresAuth: true } },
    { path: '/share/:token', component: ShareView, meta: { title: '图纸确认' } },
    { path: '/p/:token', component: PublicationView, meta: { title: '公开拼豆作品' } },
    { path: '/:pathMatch(.*)*', component: NotFoundView, meta: { title: '未找到页面' } },
  ],
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  await auth.restore()
  if (to.meta.requiresAuth && !auth.isAuthenticated) return { path: '/auth', query: { next: to.fullPath } }
  if (to.meta.requiresAdmin && !auth.isAdmin) return '/projects'
  if (to.meta.guestOnly && auth.isAuthenticated) return '/projects'
  return true
})
