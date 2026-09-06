<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ApiError, getJson, requestJson } from '@/api/http'
import type { OperatorRecord, OperatorRole } from '@/types/admin'
import { operatorRoleLabels } from '@/types/admin'
import { formatAdminDate, unwrapList } from './helpers'

const operators = ref<OperatorRecord[]>([])
const route = useRoute()
const selected = ref<OperatorRecord | null>(null)
const selectedIds = ref<number[]>([])
const search = ref('')
const roleFilter = ref<'all' | OperatorRole>('all')
const role = ref<OperatorRole>('inspector')
const rejectionReason = ref('')
const showReject = ref(false)
const loading = ref(true)
const busy = ref(false)
const message = ref('')
const filtered = computed(() => operators.value.filter((operator) => {
  const haystack = `${operator.display_name} ${operator.username} ${operator.phone}`.toLowerCase()
  const matchesSearch = !search.value || haystack.includes(search.value.toLowerCase())
  return matchesSearch && (roleFilter.value === 'all' || operator.role === roleFilter.value)
}))

async function load() {
  loading.value = true
  try {
    const payload = await getJson<unknown>('/accounts/operators/?status=pending&page_size=100')
    operators.value = unwrapList<OperatorRecord>(payload)
    const requestedId = Number(route.query.operator)
    const requested = requestedId ? operators.value.find((operator) => operator.id === requestedId) : null
    if (!selected.value && requested) select(requested)
    else if (!selected.value && operators.value.length) select(operators.value[0])
    if (selected.value) selected.value = operators.value.find((operator) => operator.id === selected.value?.id) ?? null
  } catch (reason) {
    message.value = reason instanceof Error ? reason.message : '注册申请加载失败'
  } finally { loading.value = false }
}

function select(operator: OperatorRecord) { selected.value = operator; role.value = operator.role }
function toggle(id: number) { selectedIds.value = selectedIds.value.includes(id) ? selectedIds.value.filter((item) => item !== id) : [...selectedIds.value, id] }
function notify(text: string) { message.value = text; window.setTimeout(() => { if (message.value === text) message.value = '' }, 2400) }

async function approve(operator = selected.value) {
  if (!operator) return
  busy.value = true
  try {
    await requestJson(`/accounts/operators/${operator.id}/approve/`, { method: 'POST', body: JSON.stringify({ role: role.value }) })
    notify(`已通过 ${operator.display_name}，角色为${operatorRoleLabels[role.value]}`)
    await load()
  } catch (reason) { notify(reason instanceof ApiError ? reason.message : '审核通过失败') }
  finally { busy.value = false }
}

async function batchApprove() {
  const ids = selectedIds.value.filter((id) => operators.value.some((operator) => operator.id === id))
  if (!ids.length) { notify('请先选择待审核人员'); return }
  busy.value = true
  try {
    for (const id of ids) await requestJson(`/accounts/operators/${id}/approve/`, { method: 'POST', body: JSON.stringify({ role: 'inspector' }) })
    selectedIds.value = []
    notify(`已批量通过 ${ids.length} 个申请，默认角色为巡检员`)
    await load()
  } catch (reason) { notify(reason instanceof ApiError ? reason.message : '批量审核失败') }
  finally { busy.value = false }
}

async function reject() {
  if (!selected.value || !rejectionReason.value.trim()) { notify('请填写驳回原因'); return }
  busy.value = true
  try {
    await requestJson(`/accounts/operators/${selected.value.id}/reject/`, { method: 'POST', body: JSON.stringify({ reason: rejectionReason.value.trim() }) })
    notify(`已驳回 ${selected.value.display_name}，用户可修改资料后重新提交`)
    showReject.value = false; rejectionReason.value = ''; await load()
  } catch (reason) { notify(reason instanceof ApiError ? reason.message : '驳回失败') }
  finally { busy.value = false }
}

onMounted(load)
</script>

<template>
  <section class="admin-page"><div class="admin-page-head"><div><span class="admin-eyebrow">GREEN PIONEER / REVIEW</span><h2>注册审核</h2><p>前台注册默认申请为巡检员，审核通过时由管理员重新分配业务角色。</p></div><div class="admin-actions"><button class="admin-button" @click="notify('列表导出接口已预留')">导出列表</button><button class="admin-button primary" :disabled="busy" @click="batchApprove">批量通过</button></div></div><div v-if="message" class="admin-message">{{ message }}</div><div class="admin-filters"><div class="admin-filter-set"><input v-model="search" placeholder="搜索姓名、用户名或手机号" /><select><option>全部状态</option><option>待审核</option><option>已驳回</option></select><select v-model="roleFilter"><option value="all">全部申请角色</option><option v-for="(label, key) in operatorRoleLabels" :key="key" :value="key">申请角色：{{ label }}</option></select></div><span class="admin-filter-note">待审核优先 · 注册时间倒序</span></div><div class="admin-review-grid"><article class="admin-panel"><div class="admin-panel-head"><h3>注册申请 <span class="admin-status warn" style="margin-left:6px">{{ filtered.length.toString().padStart(2, '0') }} 待处理</span></h3><span>可批量选择</span></div><div v-if="loading" class="admin-empty">正在读取申请…</div><table v-else class="admin-table"><thead><tr><th><input type="checkbox" :checked="selectedIds.length === filtered.length && filtered.length > 0" @change="selectedIds = selectedIds.length === filtered.length ? [] : filtered.map((item) => item.id)" /></th><th>申请人</th><th>手机号</th><th>申请角色</th><th>注册时间</th><th>状态</th><th>操作</th></tr></thead><tbody><tr v-for="operator in filtered" :key="operator.id" :class="{ selected: selected?.id === operator.id }" @click="select(operator)"><td><input type="checkbox" :checked="selectedIds.includes(operator.id)" @click.stop @change="toggle(operator.id)" /></td><td><strong>{{ operator.display_name }}</strong><small>{{ operator.username }}</small></td><td>{{ operator.phone || '未填写' }}</td><td><span class="admin-status warn">{{ operatorRoleLabels[operator.role] }}</span></td><td>{{ formatAdminDate(operator.created_at) }}</td><td><span class="admin-status warn">待审核</span></td><td><div class="admin-row-actions"><button @click.stop="select(operator)">审核</button><button class="danger" @click.stop="selected = operator; showReject = true">驳回</button></div></td></tr><tr v-if="!filtered.length"><td colspan="7" class="admin-muted-cell">暂无待审核注册</td></tr></tbody></table></article><aside class="admin-drawer"><template v-if="selected"><div class="admin-drawer-head"><div><h3>{{ selected.display_name }} <span class="admin-status warn">待审核</span></h3><small>注册申请 · {{ formatAdminDate(selected.created_at) }}</small></div><button class="admin-drawer-close" @click="selected = null">×</button></div><div class="admin-drawer-body"><div class="admin-drawer-title">申请资料</div><div class="admin-fields"><div class="admin-field-row"><span>用户名</span><strong>{{ selected.username }}</strong></div><div class="admin-field-row"><span>姓名</span><strong>{{ selected.display_name }}</strong></div><div class="admin-field-row"><span>手机号</span><strong>{{ selected.phone || '未填写' }}</strong></div><div class="admin-field-row"><span>申请角色</span><strong>{{ operatorRoleLabels[selected.role] }}</strong></div></div><div class="admin-drawer-title">审核分配</div><div class="admin-field-row"><span>通过后角色</span><select v-model="role"><option v-for="(label, key) in operatorRoleLabels" :key="key" :value="key">{{ label }}</option></select></div><div class="admin-drawer-actions"><button class="approve" :disabled="busy" @click="approve()">通过并分配角色</button><button class="reject" :disabled="busy" @click="showReject = true">驳回并填写原因</button><button class="quiet" @click="notify('用户可在前端查看审核通知')">查看用户通知状态</button></div></div></template><div v-else class="admin-empty">选择一条申请查看详情</div></aside></div><div v-if="showReject" class="admin-modal-backdrop"><div class="admin-modal"><h3>驳回注册申请</h3><p class="admin-modal-help">驳回后用户可以看到原因，修改资料后重新提交。</p><textarea v-model="rejectionReason" placeholder="请输入驳回原因（必填）"></textarea><div class="admin-modal-actions"><button class="admin-button" @click="showReject = false">取消</button><button class="admin-button primary" @click="reject">确认驳回</button></div></div></div></section>
</template>

<style scoped>
.admin-message { margin:14px 0; padding:10px 12px; color:var(--admin-brand); background:var(--admin-brand-soft); border:1px solid var(--admin-line); border-radius:5px; font-size:10px; }
.admin-filter-note { color:var(--admin-muted); font:9px ui-monospace,monospace; }
.admin-modal-help { margin:0 0 10px; color:var(--admin-muted); font-size:10px; }.admin-modal textarea { width:100%; min-height:92px; resize:vertical; }
.admin-table tbody tr { cursor:pointer; }.admin-table tbody tr:hover { background:var(--admin-brand-soft); }.admin-table td:first-child { width:34px; }
</style>
