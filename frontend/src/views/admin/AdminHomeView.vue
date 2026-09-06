<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { getJson } from '@/api/http'
import type { AuditLogRecord, OperatorRecord, OperatorRole } from '@/types/admin'
import { operatorRoleLabels } from '@/types/admin'
import { formatAdminDate, unwrapList } from './helpers'

const operators = ref<OperatorRecord[]>([])
const logs = ref<AuditLogRecord[]>([])
const loading = ref(true)
const error = ref('')
const pending = computed(() => operators.value.filter((operator) => operator.review_status === 'pending'))
const approved = computed(() => operators.value.filter((operator) => operator.review_status === 'approved'))
const disabled = computed(() => operators.value.filter((operator) => operator.review_status === 'disabled'))
const roles = computed(() => (['admin', 'reviewer', 'inspector', 'viewer'] as OperatorRole[]).map((role) => ({ role, count: approved.value.filter((operator) => operator.role === role).length })))

async function load() {
  loading.value = true
  try {
    const [operatorPayload, logPayload] = await Promise.all([
      getJson<unknown>('/accounts/operators/?page_size=100'),
      getJson<unknown>('/accounts/audit-logs/?page_size=5'),
    ])
    operators.value = unwrapList<OperatorRecord>(operatorPayload)
    logs.value = unwrapList<AuditLogRecord>(logPayload).slice(0, 5)
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '管理数据加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <section class="admin-page">
    <div class="admin-page-head"><div><span class="admin-eyebrow">GREEN PIONEER / CONTROL CENTER</span><h2>管理首页</h2><p>以注册审核、人员状态和权限风险为核心的控制人员工作台。</p></div><div class="admin-actions"><RouterLink class="admin-button" to="/admin/audit">查看日志</RouterLink><RouterLink class="admin-button primary" to="/admin/review">处理待审核</RouterLink></div></div>
    <div class="admin-notice-bar"><span>REVIEW / {{ String(pending.length).padStart(2, '0') }}</span><p>前台注册默认申请为巡检员，管理员审核通过时可以重新分配角色。</p><RouterLink class="admin-link-button" to="/admin/review">进入审核 →</RouterLink></div>
    <p v-if="error" class="admin-error">{{ error }}</p>
    <div class="admin-stats"><article class="admin-stat warn"><small>待审核</small><strong>{{ pending.length.toString().padStart(2, '0') }}</strong><span>待管理员处理</span></article><article class="admin-stat"><small>正常账号</small><strong>{{ approved.length.toString().padStart(2, '0') }}</strong><span>已通过审核</span></article><article class="admin-stat danger"><small>已停用</small><strong>{{ disabled.length.toString().padStart(2, '0') }}</strong><span>可恢复历史账号</span></article><article class="admin-stat info"><small>总控制人员</small><strong>{{ operators.length.toString().padStart(2, '0') }}</strong><span>包含待审核账号</span></article></div>
    <div v-if="loading" class="admin-panel admin-empty">正在读取人员中心…</div>
    <div v-else class="admin-grid"><article class="admin-panel"><div class="admin-panel-head"><h3>待审核队列</h3><span>待审核优先 · 注册时间倒序</span></div><div class="admin-panel-body"><table class="admin-table"><thead><tr><th>申请人</th><th>手机号</th><th>申请角色</th><th>注册时间</th><th>操作</th></tr></thead><tbody><tr v-for="operator in pending.slice(0, 5)" :key="operator.id"><td><strong>{{ operator.display_name }}</strong><small>{{ operator.username }}</small></td><td>{{ operator.phone || '未填写' }}</td><td><span class="admin-status warn">{{ operatorRoleLabels[operator.role] }}</span></td><td>{{ formatAdminDate(operator.created_at) }}</td><td><RouterLink class="admin-link-button" :to="`/admin/review?operator=${operator.id}`">审核 →</RouterLink></td></tr><tr v-if="!pending.length"><td colspan="5" class="admin-muted-cell">暂无待审核申请</td></tr></tbody></table></div></article><article class="admin-panel"><div class="admin-panel-head"><h3>角色分布</h3><span>已通过账号</span></div><div class="admin-panel-body"><div class="admin-chart"><div v-for="item in roles" :key="item.role" class="admin-role-row"><span>{{ operatorRoleLabels[item.role] }}</span><div class="admin-role-bar"><i :style="{ width: `${approved.length ? item.count / approved.length * 100 : 0}%` }"></i></div><b>{{ item.count }}</b></div></div></div></article></div>
    <article class="admin-panel admin-home-activity"><div class="admin-panel-head"><h3>最近操作</h3><RouterLink class="admin-link-button" to="/admin/audit">查看全部 →</RouterLink></div><div class="admin-panel-body"><div class="admin-activity"><div v-for="log in logs" :key="log.id" class="admin-activity-item"><strong>{{ log.action_label || log.action_type }} · {{ log.target_user?.display_name || '系统' }}</strong><small>{{ log.reason || '未填写原因' }}</small><time>{{ formatAdminDate(log.created_at) }} · {{ log.operator?.display_name || log.operator?.username || '系统' }}</time></div><div v-if="!logs.length" class="admin-muted-cell">暂无操作日志</div></div></div></article>
  </section>
</template>

<style scoped>
.admin-home-activity { margin-top: 12px; }
.admin-error { padding: 10px 12px; color: var(--admin-danger); background: #3a1715; border: 1px solid var(--admin-danger); border-radius: 5px; font-size: 10px; }
.admin-muted-cell { padding: 20px 0 !important; color: var(--admin-muted); text-align: center; }
</style>
