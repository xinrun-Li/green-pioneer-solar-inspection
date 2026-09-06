<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { requestJson } from '@/api/http'
import { useAuthStore } from '@/stores/auth'
import type { AccountNotification } from '@/types/auth'

const auth = useAuthStore()
const router = useRouter()
const notifications = ref<AccountNotification[]>([])
const unreadCount = ref(0)
const statusText = computed(() => ({ pending: '账号已注册', rejected: '资料需要完善', disabled: '账号已停用', approved: '账号状态正常' }[auth.user?.review_status ?? 'pending']))
const statusCode = computed(() => ({ pending: 'APPLICATION / PENDING', rejected: 'APPLICATION / REJECTED', disabled: 'ACCOUNT / DISABLED', approved: 'ACCOUNT / APPROVED' }[auth.user?.review_status ?? 'pending']))

async function logout() { await auth.logout(); await router.push('/login') }
async function loadNotifications() {
  try {
    const payload = await requestJson<{ unread_count: number; results: AccountNotification[] }>('/auth/notifications')
    notifications.value = payload.results
    unreadCount.value = payload.unread_count
  } catch { notifications.value = [] }
}
async function markNotificationsRead() {
  if (!unreadCount.value) return
  await requestJson('/auth/notifications/read', { method: 'POST' })
  notifications.value = notifications.value.map((item) => ({ ...item, is_read: true }))
  unreadCount.value = 0
}
onMounted(loadNotifications)
</script>

<template>
<main class="auth-page"><section class="auth-context"><div class="auth-brand"><span class="brand-mark">ϟ</span><strong>绿能先锋</strong></div><div><span class="eyebrow">ACCOUNT STATUS / CONTROL OPERATOR</span><h1>{{ statusText }}</h1><p>注册成功即可进入巡检控制台，本页用于查看账号状态、后台分配的角色和站内通知。</p></div><div class="auth-steps"><span>01 提交注册</span><span>02 进入工作台</span><span>03 后台管理权限</span></div></section><section class="auth-form-panel"><div class="auth-form result-state"><span class="result-code">{{ statusCode }}</span><h2>{{ auth.user?.display_name }}</h2><p v-if="auth.user?.review_status === 'rejected'">资料完善提醒：{{ auth.user?.rejection_reason || '管理员未填写具体原因' }}</p><p v-else-if="auth.user?.review_status === 'disabled'">当前账号已被后台停用，请联系管理员恢复。</p><p v-else>当前账号可以正常使用巡检控制台，业务角色和账号状态由后台统一调整。</p><div v-if="notifications.length" class="account-notices"><div class="notice-heading"><span>站内通知 <b v-if="unreadCount">{{ unreadCount }} 条未读</b></span><button v-if="unreadCount" type="button" @click="markNotificationsRead">全部标记已读</button></div><article v-for="item in notifications" :key="item.id" :class="{ unread: !item.is_read }"><strong>{{ item.title }}</strong><p>{{ item.content }}</p><time>{{ new Date(item.created_at).toLocaleString('zh-CN', { hour12: false }) }}</time></article></div><RouterLink v-if="auth.user?.review_status === 'rejected'" class="submit-button link-button" to="/register">修改资料并重新提交</RouterLink><RouterLink v-else-if="auth.user?.review_status !== 'disabled'" class="submit-button link-button" to="/recognition">进入巡检控制台</RouterLink><button class="text-button" type="button" @click="logout">退出账号</button></div></section></main>
</template>
