<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Play, Pause, Check, X, RotateCcw, SkipForward, ArrowLeft, MapPin, Clock, AlertTriangle,
} from 'lucide-vue-next'
import { getJson, requestJson } from '@/api/http'
import type { InspectionTaskDetail, WaypointItem, TaskStatus } from '@/types/task'
import { taskStatusLabels, taskStatusColors, waypointStatusLabels, waypointStatusColors } from '@/types/task'

const route = useRoute()
const router = useRouter()
const taskId = Number(route.params.taskId)
const task = ref<InspectionTaskDetail | null>(null)
const loading = ref(true)
const error = ref('')
const actionLoading = ref(false)

async function fetchTask() {
  loading.value = true
  try {
    task.value = await getJson<InspectionTaskDetail>(`/inspections/${taskId}/`)
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '加载任务详情失败'
  } finally {
    loading.value = false
  }
}

async function doAction(action: string) {
  actionLoading.value = true
  try {
    await requestJson(`/inspections/${taskId}/${action}/`, { method: 'POST' })
    await fetchTask()
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '操作失败'
  } finally {
    actionLoading.value = false
  }
}

async function doSimulate() {
  actionLoading.value = true
  try {
    await requestJson(`/inspections/${taskId}/simulate/`, { method: 'POST' })
    await fetchTask()
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '模拟执行失败'
  } finally {
    actionLoading.value = false
  }
}

async function skipWaypoint(waypointId: number) {
  actionLoading.value = true
  try {
    await requestJson(`/inspections/${taskId}/waypoints/${waypointId}/skip/`, {
      method: 'POST',
      body: JSON.stringify({ reason: '手动跳过' }),
    })
    await fetchTask()
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '跳过失败'
  } finally {
    actionLoading.value = false
  }
}

const statusColor = computed(() => {
  if (!task.value) return '#64748B'
  return taskStatusColors[task.value.status]
})

const allowedActions = computed(() => {
  if (!task.value) return []
  const s = task.value.status
  const actions: { label: string; key: string; icon: string }[] = []
  if (s === 'draft') actions.push({ label: '确认任务', key: 'confirm', icon: 'Check' })
  if (s === 'confirmed') actions.push({ label: '开始执行', key: 'start', icon: 'Play' })
  if (s === 'running') actions.push({ label: '暂停', key: 'pause', icon: 'Pause' })
  if (s === 'paused') actions.push({ label: '恢复', key: 'resume', icon: 'RotateCcw' })
  if (s === 'paused') actions.push({ label: '继续模拟', key: 'simulate', icon: 'Play' })
  if (s === 'draft' || s === 'paused') actions.push({ label: '取消任务', key: 'cancel', icon: 'X' })
  return actions
})

const waypointGroups = computed(() => {
  if (!task.value) return []
  const groups: { region: string; array: string; waypoints: WaypointItem[] }[] = []
  const map = new Map<string, WaypointItem[]>()
  for (const wp of task.value.waypoints) {
    const key = `${wp.region_name} / ${wp.array_code}`
    if (!map.has(key)) map.set(key, [])
    map.get(key)!.push(wp)
  }
  for (const [key, wps] of map) {
    const parts = key.split(' / ')
    groups.push({ region: parts[0], array: parts[1], waypoints: wps.sort((a, b) => a.order - b.order) })
  }
  return groups.sort((a, b) => a.region.localeCompare(b.region) || a.array.localeCompare(b.array))
})

const progressPercent = computed(() => {
  if (!task.value || task.value.total_waypoints === 0) return 0
  return Math.round(task.value.visited_waypoints / task.value.total_waypoints * 100)
})

onMounted(fetchTask)
</script>

<template>
  <section class="workspace detail-page">
    <div v-if="loading" class="loading-state">正在加载任务详情…</div>
    <div v-else-if="error" class="error-state">{{ error }}</div>
    <template v-else-if="task">
      <!-- 导航返回 -->
      <button class="back-button" @click="router.push('/tasks')">
        <ArrowLeft :size="16" /> 返回任务列表
      </button>

      <!-- 任务头部 -->
      <div class="detail-heading">
        <div class="heading-left">
          <span class="eyebrow">INSPECTION TASK / {{ task.station_code }}</span>
          <h2>{{ task.title }}</h2>
          <div class="heading-meta">
            <span class="task-badge" :style="{ background: statusColor + '22', color: statusColor, borderColor: statusColor }">
              {{ taskStatusLabels[task.status] }}
            </span>
            <span class="meta-item"><MapPin :size="12" /> {{ task.station_name }}</span>
            <span class="meta-item"><Clock :size="12" /> {{ new Date(task.created_at).toLocaleString('zh-CN') }}</span>
          </div>
        </div>
        <div class="heading-actions">
          <button
            v-for="act in allowedActions"
            :key="act.key"
            class="action-btn"
            :disabled="actionLoading"
            @click="act.key === 'simulate' ? doSimulate() : doAction(act.key)"
          >
            <Play v-if="act.key === 'start' || act.key === 'simulate'" :size="14" />
            <Pause v-else-if="act.key === 'pause'" :size="14" />
            <Check v-else-if="act.key === 'confirm'" :size="14" />
            <RotateCcw v-else-if="act.key === 'resume'" :size="14" />
            <X v-else :size="14" />
            {{ act.label }}
          </button>
        </div>
      </div>

      <!-- 描述 -->
      <p v-if="task.description" class="description">{{ task.description }}</p>

      <!-- 进度概览 -->
      <div class="progress-section">
        <div class="progress-card">
          <div class="progress-header">
            <span>巡检进度</span>
            <b>{{ progressPercent }}%</b>
          </div>
          <div class="progress-bar">
            <div class="progress-fill" :style="{ width: progressPercent + '%', background: statusColor }"></div>
          </div>
          <div class="progress-metrics">
            <div><span>总航点</span><b>{{ task.total_waypoints }}</b></div>
            <div><span>已巡检</span><b>{{ task.visited_waypoints }}</b></div>
            <div><span>覆盖率</span><b>{{ task.coverage }}%</b></div>
          </div>
        </div>
        <div class="info-card">
          <div class="info-row"><label>创建人</label><span>{{ task.created_by_name }}</span></div>
          <div class="info-row"><label>确认人</label><span>{{ task.confirmed_by_name || '—' }}</span></div>
          <div class="info-row"><label>确认时间</label><span>{{ task.confirmed_at ? new Date(task.confirmed_at).toLocaleString('zh-CN') : '—' }}</span></div>
          <div class="info-row"><label>开始时间</label><span>{{ task.started_at ? new Date(task.started_at).toLocaleString('zh-CN') : '—' }}</span></div>
          <div class="info-row"><label>完成时间</label><span>{{ task.completed_at ? new Date(task.completed_at).toLocaleString('zh-CN') : '—' }}</span></div>
        </div>
      </div>

      <!-- 航点网格 -->
      <div class="waypoint-section">
        <h3 class="section-title">巡检路线 · 航点 <small>{{ task.waypoints.length }} 个</small></h3>
        <div v-if="!waypointGroups.length" class="empty-hint">暂无航点</div>
        <div v-for="group in waypointGroups" :key="group.region + group.array" class="array-block">
          <h4 class="array-title">{{ group.region }} / {{ group.array }} 阵列</h4>
          <div class="waypoint-grid">
            <div
              v-for="wp in group.waypoints"
              :key="wp.id"
              :class="['waypoint-cell', `status-${wp.status}`]"
              :title="`${wp.panel_full_code} · ${waypointStatusLabels[wp.status]}${wp.notes ? ' · ' + wp.notes : ''}`"
            >
              <span class="wp-order">{{ wp.order }}</span>
              <span class="wp-code">{{ wp.panel_short_code }}</span>
              <span class="wp-status-dot" :style="{ background: waypointStatusColors[wp.status] }"></span>
              <button
                v-if="wp.status === 'pending' && task.status === 'running'"
                class="wp-skip"
                title="跳过"
                @click="skipWaypoint(wp.id)"
              ><SkipForward :size="10" /></button>
            </div>
          </div>
        </div>
      </div>

      <!-- 事件时间线 -->
      <div class="event-section">
        <h3 class="section-title">任务事件 <small>{{ task.events.length }} 条</small></h3>
        <div v-if="!task.events.length" class="empty-hint">暂无事件记录</div>
        <div class="timeline">
          <div v-for="evt in task.events" :key="evt.id" class="timeline-item">
            <div class="timeline-dot" :class="[`dot-${evt.event_type}`]"></div>
            <div class="timeline-body">
              <div class="timeline-header">
                <span class="timeline-type">{{ evt.description || evt.event_type }}</span>
                <span class="timeline-time">{{ new Date(evt.created_at).toLocaleString('zh-CN') }}</span>
              </div>
              <span v-if="evt.created_by_name" class="timeline-actor">{{ evt.created_by_name }}</span>
            </div>
          </div>
        </div>
      </div>
    </template>
  </section>
</template>

<style scoped>
.detail-page { max-width: 1200px; }
.back-button {
  display: flex; align-items: center; gap: 6px; margin-bottom: 16px;
  padding: 6px 12px; color: #94A3B8; background: transparent;
  border: 1px solid #1E2A45; border-radius: 4px; font-size: 12px; cursor: pointer;
}
.back-button:hover { color: #E2E8F0; border-color: #3B82F6; }
.loading-state, .error-state {
  min-height: 400px; display: grid; place-items: center;
  color: #94A3B8; font-size: 13px;
}
.error-state { color: #EF4444; }
.detail-heading {
  display: flex; justify-content: space-between; align-items: flex-start;
  padding-bottom: 20px; border-bottom: 1px solid #1E2A45; margin-bottom: 16px;
  gap: 20px;
}
.heading-left h2 { margin: 8px 0 10px; font-size: 27px; }
.heading-meta { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; }
.meta-item { display: flex; align-items: center; gap: 4px; color: #64748B; font-size: 12px; }
.task-badge { padding: 2px 10px; border-radius: 4px; font-size: 11px; font-weight: 500; border: 1px solid; }
.heading-actions { display: flex; gap: 8px; flex-shrink: 0; }
.action-btn {
  display: flex; align-items: center; gap: 5px; min-height: 36px;
  padding: 0 14px; color: #E2E8F0; background: #0F172A;
  border: 1px solid #1E2A45; border-radius: 4px; font-size: 12px; cursor: pointer;
}
.action-btn:hover { color: #22C55E; border-color: #22C55E; }
.action-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.description { color: #94A3B8; font-size: 13px; margin-bottom: 20px; line-height: 1.6; }

.progress-section { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 24px; }
.progress-card, .info-card {
  padding: 18px; background: #0F172A; border: 1px solid #1E2A45; border-radius: 6px;
}
.progress-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.progress-header span { color: #94A3B8; font-size: 12px; }
.progress-header b { font-size: 22px; font-family: ui-monospace, monospace; }
.progress-bar { height: 6px; background: #1E2A45; border-radius: 3px; overflow: hidden; margin-bottom: 12px; }
.progress-fill { height: 100%; border-radius: 3px; transition: width 0.5s ease; }
.progress-metrics { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
.progress-metrics div { display: grid; gap: 2px; }
.progress-metrics span { color: #64748B; font-size: 9px; }
.progress-metrics b { font-size: 14px; font-family: ui-monospace, monospace; color: #E2E8F0; }
.info-row { display: flex; justify-content: space-between; padding: 6px 0; font-size: 12px; }
.info-row label { color: #64748B; }
.info-row span { color: #E2E8F0; }

.section-title { font-size: 15px; font-weight: 500; margin-bottom: 14px; color: #E2E8F0; }
.section-title small { color: #64748B; font-weight: 400; }
.waypoint-section { margin-bottom: 24px; }
.array-block { margin-bottom: 16px; }
.array-title { font-size: 13px; font-weight: 500; color: #94A3B8; margin-bottom: 8px; }
.waypoint-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); gap: 6px; }
.waypoint-cell {
  display: grid; grid-template-columns: auto 1fr auto; gap: 4px; align-items: center;
  padding: 6px 8px; background: #0F172A; border: 1px solid #1E2A45; border-radius: 3px;
  font-size: 10px; position: relative;
}
.waypoint-cell.status-visited { border-color: #22C55E44; }
.waypoint-cell.status-skipped { border-color: #F59E0B44; }
.waypoint-cell.status-failed { border-color: #EF444444; }
.wp-order { color: #64748B; font-family: ui-monospace, monospace; }
.wp-code { color: #E2E8F0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.wp-status-dot { width: 6px; height: 6px; border-radius: 50%; }
.wp-skip {
  position: absolute; right: 2px; top: 2px; padding: 2px;
  background: transparent; border: none; color: #F59E0B; cursor: pointer;
  opacity: 0; transition: opacity 0.15s;
}
.waypoint-cell:hover .wp-skip { opacity: 1; }

.event-section { margin-bottom: 24px; }
.timeline { position: relative; padding-left: 20px; }
.timeline::before {
  content: ''; position: absolute; left: 7px; top: 0; bottom: 0;
  width: 1px; background: #1E2A45;
}
.timeline-item { display: flex; gap: 10px; padding-bottom: 14px; position: relative; }
.timeline-dot {
  position: absolute; left: -16px; top: 4px;
  width: 10px; height: 10px; border-radius: 50%; background: #64748B;
  z-index: 1;
}
.dot-created, .dot-completed { background: #22C55E; }
.dot-started, .dot-resumed { background: #3B82F6; }
.dot-paused, .dot-cancelled, .dot-failed, .dot-media_missing { background: #F59E0B; }
.dot-waypoint_visited { background: #22C55E; }
.dot-waypoint_skipped { background: #F59E0B; }
.timeline-body { flex: 1; }
.timeline-header { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; }
.timeline-type { color: #E2E8F0; font-size: 12px; }
.timeline-time { color: #64748B; font-size: 10px; white-space: nowrap; }
.timeline-actor { color: #64748B; font-size: 10px; }
.empty-hint { color: #64748B; font-size: 12px; padding: 20px; text-align: center; }
</style>