<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ApiError, getJson, requestJson } from '@/api/http'
import { useAuthStore } from '@/stores/auth'
import type { OperatorRecord, OperatorRole, OperatorStatus } from '@/types/admin'
import { operatorRoleLabels, operatorStatusLabels } from '@/types/admin'
import { formatAdminDate, unwrapList } from './helpers'

const auth = useAuthStore()
const operators = ref<OperatorRecord[]>([])
const search = ref('')
const status = ref<'all' | OperatorStatus>('all')
const role = ref<'all' | OperatorRole>('all')
const selectedIds = ref<number[]>([])
const editing = ref<OperatorRecord | null>(null)
const busy = ref(false)
const message = ref('')
const filtered = computed(() => operators.value.filter((operator) => {
  const matchesSearch = !search.value || `${operator.display_name} ${operator.username} ${operator.phone}`.toLowerCase().includes(search.value.toLowerCase())
  return matchesSearch && (status.value === 'all' || operator.review_status === status.value) && (role.value === 'all' || operator.role === role.value)
}))

async function load() {
  try { operators.value = unwrapList<OperatorRecord>(await getJson<unknown>('/accounts/operators/?page_size=100')) }
  catch (reason) { notify(reason instanceof Error ? reason.message : '控制人员加载失败') }
}
function notify(text: string) { message.value = text; window.setTimeout(() => { if (message.value === text) message.value = '' }, 2400) }
function toggle(id: number) { selectedIds.value = selectedIds.value.includes(id) ? selectedIds.value.filter((item) => item !== id) : [...selectedIds.value, id] }
function openEdit(operator: OperatorRecord) { editing.value = { ...operator } }
async function saveEdit() { if (!editing.value) return; busy.value = true; try { await requestJson(`/accounts/operators/${editing.value.id}/`, { method: 'PATCH', body: JSON.stringify({ display_name: editing.value.display_name, phone: editing.value.phone, role: editing.value.role, status: editing.value.review_status }) }); notify('控制人员资料已保存，已写入操作日志'); editing.value = null; await load() } catch (reason) { notify(reason instanceof ApiError ? reason.message : '保存失败') } finally { busy.value = false } }
async function changeStatus(operator: OperatorRecord) { busy.value = true; try { const action = operator.review_status === 'disabled' ? 'restore' : 'disable'; await requestJson(`/accounts/operators/${operator.id}/${action}/`, { method: 'POST', body: JSON.stringify({ reason: operator.review_status === 'disabled' ? '管理员恢复账号' : '管理员停用账号' }) }); notify(operator.review_status === 'disabled' ? '账号已恢复' : '账号已停用'); await load() } catch (reason) { notify(reason instanceof ApiError ? reason.message : '账号状态更新失败') } finally { busy.value = false } }
async function resetPassword(operator: OperatorRecord) { busy.value = true; try { const response = await requestJson<{ temporary_password?: string }>(`/accounts/operators/${operator.id}/reset-password/`, { method: 'POST' }); notify(response.temporary_password ? `临时密码：${response.temporary_password}` : '密码已重置，请通知用户'); } catch (reason) { notify(reason instanceof ApiError ? reason.message : '密码重置失败') } finally { busy.value = false } }
async function deleteOperator(operator: OperatorRecord) { if (!auth.user?.is_superuser) { notify('只有 Django superuser 可以彻底删除账号'); return } if (!window.confirm(`确认彻底删除 ${operator.display_name}？`)) return; try { await requestJson(`/accounts/operators/${operator.id}/`, { method: 'DELETE' }); notify('账号已删除，审计记录已保留'); await load() } catch (reason) { notify(reason instanceof ApiError ? reason.message : '删除失败') } }
async function batchDisable() { const ids = selectedIds.value; if (!ids.length) { notify('请先选择控制人员'); return } for (const id of ids) { const operator = operators.value.find((item) => item.id === id); if (operator && operator.review_status === 'approved') await changeStatus(operator) } selectedIds.value = []; notify(`已提交 ${ids.length} 个账号的停用操作`) }
onMounted(load)
</script>

<template>
  <section class="admin-page"><div class="admin-page-head"><div><span class="admin-eyebrow">GREEN PIONEER / OPERATORS</span><h2>控制人员</h2><p>管理姓名、手机号、角色和账号状态。用户名创建后不可修改，普通管理员只能停用账号。</p></div><div class="admin-actions"><button class="admin-button" @click="notify('导入模板接口已预留')">导入人员</button><button class="admin-button primary" @click="notify('新增控制人员表单接口已预留')">新增控制人员</button></div></div><div v-if="message" class="admin-message">{{ message }}</div><div class="admin-filters"><div class="admin-filter-set"><input v-model="search" placeholder="搜索姓名、用户名或手机号" /><select v-model="status"><option value="all">全部状态</option><option value="approved">正常</option><option value="pending">待审核</option><option value="disabled">已停用</option><option value="rejected">已驳回</option></select><select v-model="role"><option value="all">全部角色</option><option v-for="(label, key) in operatorRoleLabels" :key="key" :value="key">{{ label }}</option></select><button class="admin-button" @click="notify('筛选条件已保存')">保存筛选</button></div><div class="admin-density"><span>批量操作</span><button class="admin-button" @click="batchDisable">批量停用</button></div></div><article class="admin-panel"><div class="admin-panel-head"><h3>控制人员 <span class="admin-status" style="margin-left:6px">{{ filtered.length }}</span></h3><span>待审核优先 · 注册时间倒序</span></div><table class="admin-table"><thead><tr><th><input type="checkbox" :checked="selectedIds.length === filtered.length && filtered.length > 0" @change="selectedIds = selectedIds.length === filtered.length ? [] : filtered.map((item) => item.id)" /></th><th>人员</th><th>手机号</th><th>角色</th><th>状态</th><th>注册时间</th><th>操作</th></tr></thead><tbody><tr v-for="operator in filtered" :key="operator.id"><td><input type="checkbox" :checked="selectedIds.includes(operator.id)" @change="toggle(operator.id)" /></td><td><strong>{{ operator.display_name }}</strong><small>{{ operator.username }}</small></td><td>{{ operator.phone || '未填写' }}</td><td><span class="admin-status" :class="{ warn: operator.role === 'inspector' }">{{ operatorRoleLabels[operator.role] }}</span></td><td><span class="admin-status" :class="{ warn: operator.review_status === 'pending', danger: operator.review_status === 'disabled' || operator.review_status === 'rejected' }">{{ operatorStatusLabels[operator.review_status] }}</span></td><td>{{ formatAdminDate(operator.created_at) }}</td><td><div class="admin-row-actions"><button @click="openEdit(operator)">编辑</button><button @click="resetPassword(operator)">重置密码</button><button @click="changeStatus(operator)">{{ operator.review_status === 'disabled' ? '恢复' : '停用' }}</button><button v-if="auth.user?.is_superuser" class="danger" @click="deleteOperator(operator)">删除</button></div></td></tr><tr v-if="!filtered.length"><td colspan="7" class="admin-muted-cell">没有符合条件的控制人员</td></tr></tbody></table></article><div class="admin-notice-bar" style="margin-top:12px"><span>SUPERUSER ONLY</span><p>彻底删除账号会保留审计记录，只有 Django superuser 可以执行；普通管理员只能停用。</p><RouterLink class="admin-link-button" to="/admin/audit">查看日志 →</RouterLink></div><div v-if="editing" class="admin-modal-backdrop"><div class="admin-modal"><h3>编辑控制人员</h3><label>用户名（不可修改）<input :value="editing.username" disabled /></label><label>姓名<input v-model="editing.display_name" /></label><label>手机号<input v-model="editing.phone" /></label><label>角色<select v-model="editing.role"><option v-for="(label, key) in operatorRoleLabels" :key="key" :value="key">{{ label }}</option></select></label><label>账号状态<select v-model="editing.review_status"><option v-for="(label, key) in operatorStatusLabels" :key="key" :value="key">{{ label }}</option></select></label><div class="admin-modal-actions"><button class="admin-button" @click="editing = null">取消</button><button class="admin-button primary" :disabled="busy" @click="saveEdit">保存修改</button></div></div></div></section>
</template>

<script lang="ts">
import { RouterLink } from 'vue-router'
export default { components: { RouterLink } }
</script>

<style scoped>
.admin-message { margin:14px 0; padding:10px 12px; color:var(--admin-brand); background:var(--admin-brand-soft); border:1px solid var(--admin-line); border-radius:5px; font-size:10px; }.admin-muted-cell { padding:22px !important; color:var(--admin-muted); text-align:center; }.admin-table td strong { display:block; }.admin-table td small { display:block; margin-top:4px; color:var(--admin-muted); font-size:8px; }.admin-modal label input:disabled { opacity:.55; }
</style>
