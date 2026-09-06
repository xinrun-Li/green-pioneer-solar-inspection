<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { getJson } from '@/api/http'
import type { HealthResponse } from '@/types/health'

const route = useRoute()
const health = ref<HealthResponse | null>(null)
const error = ref('')
const title = computed(() => route.path === '/recognition' ? '系统底座已就绪' : '模块基础路由已就绪')

onMounted(async () => {
  try { health.value = await getJson<HealthResponse>('/health') }
  catch (reason) { error.value = reason instanceof Error ? reason.message : '无法连接后端' }
})
</script>

<template>
  <section class="workspace">
    <div class="hero-card">
      <div><span class="eyebrow">FOUNDATION / STAGE 1</span><h2>{{ title }}</h2></div>
      <p>Vue 3 控制台已接入 Django REST API。当前阶段建立稳定工程边界，后续业务模块将在此基础上逐步接入。</p>
    </div>
    <div class="status-grid">
      <article><span>前端</span><strong class="ok">运行中</strong><small>Vue 3 · TypeScript · Vite</small></article>
      <article><span>后端 API</span><strong :class="health ? 'ok' : 'warn'">{{ health ? '运行中' : '等待连接' }}</strong><small>Django · REST Framework</small></article>
      <article><span>基础设施</span><strong :class="health?.status === 'ok' ? 'ok' : 'warn'">{{ health?.status === 'ok' ? '健康' : '待 Docker 启动' }}</strong><small>PostgreSQL · Redis</small></article>
    </div>
    <div class="panel">
      <div class="panel-head"><h3>服务连通性</h3><span>GET /api/v1/health</span></div>
      <p v-if="error" class="error">{{ error }}。请先启动后端服务。</p>
      <pre v-else>{{ health ?? '正在检查…' }}</pre>
    </div>
  </section>
</template>

