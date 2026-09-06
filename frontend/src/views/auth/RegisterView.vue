<script setup lang="ts">
import { ref } from 'vue'
import { RouterLink } from 'vue-router'
import { ApiError, requestJson } from '@/api/http'

const form = ref({ username: '', display_name: '', phone: '', password: '', password_confirm: '' })
const submitting = ref(false)
const message = ref('')
const completed = ref(false)

async function submit() {
  message.value = ''
  submitting.value = true
  try {
    const response = await requestJson<{ message: string }>('/auth/register', { method: 'POST', body: JSON.stringify(form.value) })
    message.value = response.message
    completed.value = true
  } catch (error) {
    message.value = error instanceof ApiError ? error.message : '注册失败，请检查输入'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <main class="auth-page">
    <section class="auth-context">
      <div class="auth-brand"><span class="brand-mark">ϟ</span><strong>绿能先锋</strong></div>
      <div><span class="eyebrow">ACCOUNT APPLICATION</span><h1>控制人员注册</h1><p>提交最小必要账户信息。所属电站由管理员审核时分配，注册人无法自行选择。</p></div>
      <div class="auth-steps"><span>01 提交申请</span><span>02 管理员审核</span><span>03 登录工作台</span></div>
    </section>
    <section class="auth-form-panel">
      <div v-if="completed" class="auth-form result-state">
        <span class="result-code">APPLICATION RECEIVED</span><h2>等待管理员审核</h2><p>{{ message }}</p><RouterLink class="submit-button link-button" to="/login">返回登录</RouterLink>
      </div>
      <form v-else class="auth-form" @submit.prevent="submit">
        <div class="form-heading"><span>注册申请</span><h2>创建账户</h2><p>密码不少于 8 位，避免使用常见或纯数字密码。</p></div>
        <div class="field-pair">
          <label><span>账号</span><input v-model.trim="form.username" autocomplete="username" minlength="3" required /></label>
          <label><span>姓名</span><input v-model.trim="form.display_name" autocomplete="name" minlength="2" required /></label>
        </div>
        <label><span>手机号</span><input v-model.trim="form.phone" autocomplete="tel" inputmode="tel" required /></label>
        <label><span>密码</span><input v-model="form.password" type="password" autocomplete="new-password" minlength="8" required /></label>
        <label><span>确认密码</span><input v-model="form.password_confirm" type="password" autocomplete="new-password" minlength="8" required /></label>
        <p v-if="message" class="form-message error">{{ message }}</p>
        <button class="submit-button" :disabled="submitting">{{ submitting ? '正在提交…' : '提交注册申请' }}</button>
        <p class="form-foot">已有账户？<RouterLink to="/login">返回登录</RouterLink></p>
      </form>
    </section>
  </main>
</template>
