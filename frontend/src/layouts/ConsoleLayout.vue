<script setup lang="ts">
import { RouterLink, RouterView, useRoute } from 'vue-router'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const nav = [
  ['recognition', '巡检中心', '⌁'], ['tasks', '任务中心', '◇'],
  ['reports', '报告中心', '▤'], ['station-map', '电站地图', '⌗'],
  ['training', '模型训练', '△'], ['history', '历史数据', '◷'],
  ['settings', '系统设置', '⚙'],
]

async function signOut() {
  await auth.logout()
  await router.push('/login')
}
</script>

<template>
  <div class="console-shell">
    <aside class="sidebar">
      <div class="brand"><span class="brand-mark">ϟ</span><span>绿能先锋</span></div>
      <nav>
        <RouterLink v-for="item in nav" :key="item[0]" :to="`/${item[0]}`">
          <span class="nav-icon">{{ item[2] }}</span>{{ item[1] }}
        </RouterLink>
      </nav>
      <RouterLink v-if="auth.user?.is_account_manager" class="admin-entry" to="/admin/overview"><span class="nav-icon">⌘</span>人员管理后台</RouterLink>
      <div class="sidebar-foot"><i></i> 本地服务底座</div>
    </aside>
    <main>
      <header>
        <div><small>GREEN PIONEER / V1</small><h1>{{ nav.find((item) => route.path.includes(item[0]))?.[1] }}</h1></div>
        <div class="operator-block">
          <div class="operator"><span>控制人员 · {{ auth.user?.station?.name ?? '未分配电站' }}</span><strong>{{ auth.user?.display_name }}</strong></div>
          <button class="text-button" @click="signOut">退出</button>
        </div>
      </header>
      <RouterView />
    </main>
  </div>
</template>
