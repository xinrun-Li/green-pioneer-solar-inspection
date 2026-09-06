<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Plus, Play, Check, X, RotateCcw, RefreshCw } from 'lucide-vue-next'
import { getJson, requestJson } from '@/api/http'
import type { InspectionTaskSummary, TaskStatus } from '@/types/task'
import { taskStatusLabels, taskStatusColors } from '@/types/task'
import type { StationMap } from '@/types/station'

const router = useRouter()
const tasks = ref<InspectionTaskSummary[]>([])
const stations = ref<StationMap | null>(null)
const showCreate = ref(false)
const createTitle = ref('')
const createStationId = ref<number | null>(null)
const creating = ref(false)
const error = ref('')
const actionLoading = ref<Record<number, boolean>>({})

const allowedActions = (status: TaskStatus) => {
  const actions: { label: string; key: string; icon: string }[] = []
  if (status === 'draft') actions.push({ label: '确认', key: 'confirm', icon: 'Check' })
  if (status === 'confirmed') actions.push({ label: '开始', key: 'start', icon: 'Play' })
  if (status === 'running') actions.push({ label: '暂停', key: 'pause', icon: 'X' })
  if (status === 'paused') actions.push({ label: '恢复', key: 'resume', icon: 'RotateCcw' })
  if (status === 'draft' || status === 'paused') actions.push({ label: '取消', key: 'cancel', icon: 'X' })
  return actions
}

async function fetchTasks() {
  try {
    tasks.value = (await getJson<{ count: number; results: InspectionTaskSummary[] }>('/inspections/')).results
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '加载任务列表失败'
  }
}

async function fetchStations() {
  try {
    stations.value = await getJson<StationMap>('/stations/current/map')
  } catch (reason) {
    // 静默失败，建任务时再提示
    console.error('加载电站列表失败', reason)
  }
}

async function doAction(taskId: number, action: string) {
  actionLoading.value[taskId] = true
  try {
    await requestJson(`/inspections/${taskId}/${action}/`, { method: 'POST' })
    await fetchTasks()
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '操作失败'
  } finally {
    actionLoading.value[taskId] = false
  }
}

async function doCreate() {
  if (!createTitle.value.trim() || !createStationId.value) return
  creating.value = true
  try {
    await requestJson('/inspections/create/', {
      method: 'POST',
      body: JSON.stringify({ title: createTitle.value, station_id: createStationId.value }),
    })
    showCreate.value = false
    createTitle.value = ''
    createStationId.value = null
    await fetchTasks()
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '创建失败'
  } finally {
    creating.value = false
  }
}

function statusColor(status: TaskStatus): string {
  return taskStatusColors[status]
}

onMounted(() => {
  fetchTasks()
  fetchStations()
})
</script>

<template>
  <section class="workspace">
    <div class="page-heading">
      <div>
        <span class="eyebrow">INSPECTIONS / TASK CENTER</span>
        <h2>巡检任务</h2>
        <p>管理电站巡检任务，创建 S 形路线并执行模拟巡检</p>
      </div>
      <button class="primary-button" @click="showCreate = true">
        <Plus :size="16" /> 新建任务
      </button>
    </div>

    <div v-if="error" class="error-banner">{{ error }}</div>

    <div v-if="tasks.length === 0 && !error" class="empty-state">
      <div class="empty-icon">◇</div>
      <p>暂无巡检任务</p>
      <button class="primary-button" @click="showCreate = true">
        <Plus :size="16" /> 创建第一个任务
      </button>
    </div>

    <div v-else class="task-grid">
      <article v-for="task in tasks" :key="task.id" class="task-card" @click="router.push(`/tasks/${task.id}`)">
        <header>
          <div class="task-title-row">
            <h3>{{ task.title }}</h3>
            <span class="task-badge" :style="{ background: statusColor(task.status) + '22', color: statusColor(task.status), borderColor: statusColor(task.status) }">
              {{ taskStatusLabels[task.status] }}
            </span>
          </div>
          <span class="task-station">{{ task.station_name }}</span>
        </header>
        <div class="task-metrics">
          <div class="metric">
            <span>航点</span>
            <b>{{ task.visited_waypoints }}/{{ task.total_waypoints }}</b>
          </div>
          <div class="metric">
            <span>覆盖率</span>
            <b>{{ task.coverage }}%</b>
          </div>
          <div class="metric">
            <span>创建人</span>
            <b>{{ task.created_by_name }}</b>
          </div>
        </div>
        <div class="task-footer">
          <div class="task-time">{{ new Date(task.created_at).toLocaleString('zh-CN') }}</div>
          <div class="task-actions" @click.stop>
            <button
              v-for="act in allowedActions(task.status)"
              :key="act.key"
              class="action-btn"
              :disabled="actionLoading[task.id]"
              @click="doAction(task.id, act.key)"
            >
              <Check v-if="act.key === 'confirm'" :size="12" />
              <Play v-else-if="act.key === 'start'" :size="12" />
              <RotateCcw v-else-if="act.key === 'resume'" :size="12" />
              <X v-else :size="12" />
              {{ act.label }}
            </button>
          </div>
        </div>
      </article>
    </div>

    <!-- 创建任务弹窗 -->
    <Teleport to="body">
      <div v-if="showCreate" class="modal-overlay" @click.self="showCreate = false">
        <div class="modal-card">
          <header>
            <h3>新建巡检任务</h3>
            <button class="close-btn" @click="showCreate = false"><X :size="18" /></button>
          </header>
          <div class="modal-body">
            <label class="form-field">
              <span>任务标题</span>
              <input v-model="createTitle" type="text" placeholder="输入任务名称" />
            </label>
            <label class="form-field">
              <span>目标电站</span>
              <select v-model="createStationId">
                <option :value="null" disabled>选择电站</option>
                <option v-if="stations" :value="stations.id">{{ stations.name }}</option>
              </select>
            </label>
          </div>
          <footer>
            <button class="ghost-button" @click="showCreate = false">取消</button>
            <button class="primary-button" :disabled="!createTitle.trim() || !createStationId || creating" @click="doCreate">
              {{ creating ? '创建中…' : '创建并生成路线' }}
            </button>
          </footer>
        </div>
      </div>
    </Teleport>
  </section>
</template>

<style scoped>
.page-heading {
  display: flex; align-items: flex-end; justify-content: space-between;
  padding-bottom: 20px; border-bottom: 1px solid #1E2A45; margin-bottom: 20px;
}
.page-heading h2 { margin: 8px 0 5px; font-size: 27px; }
.page-heading p { margin: 0; color: #789084; font-size: 12px; }
.primary-button {
  display: flex; align-items: center; gap: 6px; min-height: 38px;
  padding: 0 16px; color: #06170f; background: #39e58c; border: 0;
  border-radius: 4px; font-size: 12px; font-weight: 700; cursor: pointer;
}
.primary-button:hover { background: #63eea5; }
.primary-button:disabled { opacity: 0.55; cursor: not-allowed; }
.ghost-button {
  min-height: 38px; padding: 0 16px; color: #94A3B8;
  background: transparent; border: 1px solid #1E2A45; border-radius: 4px;
  font-size: 12px; cursor: pointer;
}
.ghost-button:hover { color: #E2E8F0; border-color: #3B82F6; }
.error-banner {
  padding: 10px 14px; margin-bottom: 16px; color: #EF4444;
  background: rgba(239,68,68,0.1); border: 1px solid rgba(239,68,68,0.3);
  border-radius: 4px; font-size: 12px;
}
.empty-state {
  display: grid; place-items: center; padding: 60px; text-align: center;
}
.empty-icon { font-size: 36px; color: #64748B; margin-bottom: 12px; }
.empty-state p { color: #94A3B8; font-size: 13px; margin-bottom: 16px; }
.task-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; }
.task-card {
  padding: 18px; background: #0F172A; border: 1px solid #1E2A45;
  border-radius: 6px; cursor: pointer; transition: all 0.15s;
}
.task-card:hover { border-color: #3B82F6; background: #111A2E; }
.task-card header { height: auto; background: transparent; padding: 0 0 12px; border-bottom: 1px solid #1E2A45; }
.task-title-row { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.task-title-row h3 { margin: 0; font-size: 15px; font-weight: 500; color: #E2E8F0; }
.task-badge { padding: 2px 8px; border-radius: 4px; font-size: 10px; font-weight: 500; border: 1px solid; white-space: nowrap; }
.task-station { display: block; margin-top: 6px; color: #64748B; font-size: 11px; }
.task-metrics { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; padding: 12px 0; }
.metric { display: grid; gap: 2px; }
.metric span { color: #64748B; font-size: 9px; }
.metric b { font-size: 13px; color: #E2E8F0; font-family: ui-monospace, monospace; }
.task-footer { display: flex; align-items: center; justify-content: space-between; padding-top: 10px; border-top: 1px solid #1E2A45; }
.task-time { color: #64748B; font-size: 10px; }
.task-actions { display: flex; gap: 4px; }
.action-btn {
  display: flex; align-items: center; gap: 3px; min-height: 26px;
  padding: 0 8px; color: #94A3B8; background: #0F172A;
  border: 1px solid #1E2A45; border-radius: 3px; font-size: 10px; cursor: pointer;
}
.action-btn:hover { color: #E2E8F0; border-color: #3B82F6; }
.action-btn:disabled { opacity: 0.5; cursor: not-allowed; }

/* Modal */
.modal-overlay {
  position: fixed; inset: 0; z-index: 100;
  background: rgba(0,0,0,0.55);
  display: flex; align-items: center; justify-content: center;
}
.modal-card {
  background: #111A2E; border: 1px solid #1E2A45; border-radius: 8px;
  width: 440px; padding: 0;
}
.modal-card header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 18px 20px; border-bottom: 1px solid #1E2A45;
  height: auto; background: transparent;
}
.modal-card header h3 { margin: 0; font-size: 16px; }
.close-btn {
  background: none; border: none; color: #94A3B8; cursor: pointer;
  padding: 4px; border-radius: 4px;
}
.close-btn:hover { color: #E2E8F0; background: #1E2A45; }
.modal-body { padding: 20px; display: grid; gap: 16px; }
.form-field { display: grid; gap: 6px; }
.form-field span { color: #94A3B8; font-size: 12px; }
.form-field input, .form-field select {
  width: 100%; height: 40px; padding: 0 12px; color: #E2E8F0;
  background: #0F172A; border: 1px solid #1E2A45; border-radius: 4px;
  outline: none; font-size: 13px;
}
.form-field input:focus, .form-field select:focus { border-color: #3B82F6; }
.modal-card footer {
  display: flex; justify-content: flex-end; gap: 8px;
  padding: 14px 20px; border-top: 1px solid #1E2A45;
}
</style>