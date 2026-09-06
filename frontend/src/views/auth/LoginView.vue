<script setup lang="ts">
import { ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { ApiError } from '@/api/http'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const username = ref('')
const password = ref('')
const remember = ref(false)
const submitting = ref(false)
const message = ref('')

async function submit() {
  message.value = ''
  submitting.value = true
  try {
    await auth.login(username.value, password.value, remember.value)
    const nextPath = typeof route.query.redirect === 'string' ? route.query.redirect : '/recognition'
    await router.push(nextPath)
  } catch (error) {
    message.value = error instanceof ApiError ? error.message : '登录失败，请稍后重试'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <main class="auth-page">
    <section class="auth-context">
      <div class="auth-brand"><span class="brand-mark">ϟ</span><strong>绿能先锋</strong></div>
      <div><span class="eyebrow">LOCAL INSPECTION SYSTEM / V1</span><h1>光伏巡检控制台</h1><p>本地完成任务编排、识别复核、组件状态管理与巡检报告归档。</p></div>
      <div class="auth-boundary"><b>能力边界</b><span>RGB 可见异常仅作为复检依据；所有业务写操作均需人工确认。</span></div>
    </section>
    <section class="auth-form-panel">
      <form class="auth-form" @submit.prevent="submit">
        <div class="form-heading"><span>控制人员入口</span><h2>登录账户</h2><p>注册成功即可进入巡检控制台，角色和账号状态由后台统一管理。</p></div>
        <label><span>账号</span><input v-model.trim="username" autocomplete="username" required /></label>
        <label><span>密码</span><input v-model="password" type="password" autocomplete="current-password" required /></label>
        <label class="check-row"><input v-model="remember" type="checkbox" /><span>记住登录状态</span></label>
        <p v-if="message" class="form-message error">{{ message }}</p>
        <button class="submit-button" :disabled="submitting">{{ submitting ? '正在验证…' : '进入控制台' }}</button>
        <p class="form-foot">还没有账户？<RouterLink to="/register">提交注册申请</RouterLink></p>
      </form>
    </section>
  </main>
</template>
