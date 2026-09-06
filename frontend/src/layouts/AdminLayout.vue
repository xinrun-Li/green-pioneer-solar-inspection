<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'
import { getJson } from '@/api/http'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const pendingCount = ref(0)
const nav = [
  ['overview', '管理首页', '01'], ['review', '注册与权限', '02'],
  ['operators', '控制人员', '03'], ['audit', '操作日志', '04'],
]
const title = computed(() => nav.find(([key]) => route.path.endsWith(`/${key}`))?.[1] ?? '管理首页')

async function signOut() {
  await auth.logout()
  await router.push('/login')
}

onMounted(async () => {
  try {
    const payload = await getJson<{ count?: number }>('/accounts/operators/?status=pending&page_size=1')
    pendingCount.value = payload.count ?? 0
  } catch { pendingCount.value = 0 }
})
</script>

<template>
  <div class="admin-shell">
    <aside class="admin-sidebar">
      <div class="admin-brand"><span class="admin-mark">GP</span><div><strong>绿能先锋</strong><small>INSPECTION CONSOLE</small></div></div>
      <div class="admin-scope"><small>管理范围</small><strong>控制人员中心</strong><span>权限服务运行中</span></div>
      <p class="admin-nav-title">人员中心</p>
      <nav class="admin-nav">
        <RouterLink v-for="item in nav" :key="item[0]" :to="`/admin/${item[0]}`"><b>{{ item[2] }}</b><span>{{ item[1] }}</span><small v-if="item[0] === 'review'">{{ pendingCount.toString().padStart(2, '0') }}</small></RouterLink>
      </nav>
      <p class="admin-nav-title secondary-title">快捷操作</p>
      <nav class="admin-nav">
        <RouterLink to="/admin/operators"><b>＋</b><span>新增控制人员</span><small>→</small></RouterLink>
        <RouterLink to="/admin/review"><b>!</b><span>查看待审核</span><small>{{ pendingCount.toString().padStart(2, '0') }}</small></RouterLink>
      </nav>
      <div class="admin-sidebar-foot"><i></i>账号服务 · 运行中<br><span>superuser: {{ auth.user?.username }}</span></div>
    </aside>
    <main class="admin-main">
      <header class="admin-topbar"><div><small>绿能先锋 / 人员中心</small><h1>{{ title }}</h1></div><div class="admin-top-actions"><span class="admin-notice">待审核 <b>{{ pendingCount.toString().padStart(2, '0') }}</b></span><span class="admin-avatar">管</span><button class="admin-logout" @click="signOut">退出</button></div></header>
      <RouterView />
    </main>
  </div>
</template>
