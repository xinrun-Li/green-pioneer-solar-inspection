import { createRouter, createWebHistory } from 'vue-router'
import ConsoleLayout from '@/layouts/ConsoleLayout.vue'
import TrainingView from '@/views/TrainingView.vue'
import LoginView from '@/views/auth/LoginView.vue'
import RegisterView from '@/views/auth/RegisterView.vue'
import StationMapView from '@/views/station-map/StationMapView.vue'
import RecognitionView from '@/views/recognition/RecognitionView.vue'
import TaskCenterView from '@/views/tasks/TaskCenterView.vue'
import TaskDetailView from '@/views/tasks/TaskDetailView.vue'
import ReportCenterView from '@/views/reports/ReportCenterView.vue'
import HistoryView from '@/views/history/HistoryView.vue'
import SettingsView from '@/views/settings/SettingsView.vue'
import AccountStatusView from '@/views/auth/AccountStatusView.vue'
import AdminLayout from '@/layouts/AdminLayout.vue'
import AdminHomeView from '@/views/admin/AdminHomeView.vue'
import RegistrationReviewView from '@/views/admin/RegistrationReviewView.vue'
import OperatorsView from '@/views/admin/OperatorsView.vue'
import AuditLogView from '@/views/admin/AuditLogView.vue'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: LoginView, meta: { public: true } },
    { path: '/register', component: RegisterView, meta: { public: true } },
    { path: '/account-status', component: AccountStatusView, meta: { requiresAuth: true } },
    {
      path: '/',
      component: ConsoleLayout,
      meta: { requiresAuth: true },
      children: [
        { path: '', redirect: '/recognition' },
        { path: 'recognition', component: RecognitionView },
        { path: 'reports', component: ReportCenterView },
        { path: 'history', component: HistoryView },
        { path: 'settings', component: SettingsView },
        { path: 'training', component: TrainingView },
        { path: 'tasks', component: TaskCenterView },
        { path: 'tasks/:taskId', component: TaskDetailView },
        { path: 'station-map', component: StationMapView },
      ],
    },
    {
      path: '/admin', component: AdminLayout, meta: { requiresAuth: true, requiresAdmin: true },
      children: [
        { path: '', redirect: '/admin/overview' },
        { path: 'overview', component: AdminHomeView },
        { path: 'review', component: RegistrationReviewView },
        { path: 'operators', component: OperatorsView },
        { path: 'audit', component: AuditLogView },
      ],
    },
  ],
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (!auth.checked) await auth.loadCurrentUser()
  if (to.meta.requiresAuth && !auth.user) return { path: '/login', query: { redirect: to.fullPath } }
  if (to.meta.requiresAdmin && !auth.user?.is_account_manager) return '/recognition'
  if (to.meta.public && auth.user) return '/recognition'
})

export default router
