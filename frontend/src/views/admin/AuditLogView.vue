<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { getJson } from '@/api/http'
import type { AuditLogRecord } from '@/types/admin'
import { formatAdminDate, unwrapList } from './helpers'

const logs = ref<AuditLogRecord[]>([])
const search = ref('')
const action = ref('')
const dateFrom = ref('')
const dateTo = ref('')
const loading = ref(true)
const message = ref('')

async function load() {
  loading.value = true
  const params = new URLSearchParams({ page_size: '100' })
  if (action.value) params.set('action_type', action.value)
  if (search.value.trim()) params.set('search', search.value.trim())
  if (dateFrom.value) params.set('date_from', dateFrom.value)
  if (dateTo.value) params.set('date_to', dateTo.value)
  try { logs.value = unwrapList<AuditLogRecord>(await getJson<unknown>(`/accounts/audit-logs/?${params.toString()}`)) }
  catch (reason) { message.value = reason instanceof Error ? reason.message : '审计日志加载失败' }
  finally { loading.value = false }
}
onMounted(load)
</script>

<template>
  <section class="admin-page"><div class="admin-page-head"><div><span class="admin-eyebrow">GREEN PIONEER / AUDIT LOG</span><h2>操作日志</h2><p>审核、驳回、角色变更、停用、删除和密码重置都会记录操作者、时间与原因。</p></div><div class="admin-actions"><button class="admin-button" @click="message = '导出日志接口已预留'">导出日志</button></div></div><div v-if="message" class="admin-message">{{ message }}</div><div class="admin-filters"><div class="admin-filter-set"><input v-model="search" placeholder="搜索操作者或目标账号" @keyup.enter="load" /><select v-model="action" @change="load"><option value="">全部操作类型</option><option value="approve">审核通过</option><option value="reject">驳回</option><option value="role_change">角色变更</option><option value="disable">停用</option><option value="delete">删除</option><option value="reset_password">重置密码</option></select><input v-model="dateFrom" type="date" aria-label="开始日期" /><input v-model="dateTo" type="date" aria-label="结束日期" /><button class="admin-button" @click="load">查询</button></div><span class="admin-filter-note">共 {{ logs.length }} 条记录</span></div><article class="admin-panel"><div v-if="loading" class="admin-empty">正在读取审计日志…</div><div v-else class="admin-audit-log"><div class="admin-audit-row head"><span>时间</span><span>操作内容</span><span>操作者</span><span>结果</span></div><div v-for="log in logs" :key="log.id" class="admin-audit-row"><span>{{ formatAdminDate(log.created_at) }}</span><div><strong>{{ log.action_label || log.action_type }} · {{ log.target_user?.display_name || '系统' }}</strong><small>{{ log.reason || '未填写原因' }} · AUD-{{ log.id }}</small></div><span>{{ log.operator?.display_name || log.operator?.username || '系统' }}</span><span class="admin-status">已记录</span></div><div v-if="!logs.length" class="admin-empty">暂无符合条件的操作日志</div></div></article></section>
</template>

<style scoped>
.admin-message { margin:14px 0; padding:10px 12px; color:var(--admin-brand); background:var(--admin-brand-soft); border:1px solid var(--admin-line); border-radius:5px; font-size:10px; }.admin-filter-note { color:var(--admin-muted); font:9px ui-monospace,monospace; }.admin-audit-log { width:100%; }.admin-empty { min-height:280px; }
</style>
