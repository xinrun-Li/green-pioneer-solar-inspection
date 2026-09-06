<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Download, RotateCcw, Trash2, X, FileText, FileSpreadsheet, File } from 'lucide-vue-next'
import { getJson } from '@/api/http'
import { reportsApi } from '@/api/reports'
import type { Report } from '@/types/reports'
import type { InspectionTaskSummary } from '@/types/task'
import { REPORT_TYPE_LABELS, REPORT_STATUS_LABELS, REPORT_STATUS_COLORS } from '@/types/reports'

const reports = ref<Report[]>([])
const completedTasks = ref<InspectionTaskSummary[]>([])
const error = ref('')
const loading = ref(false)
const showCreate = ref(false)
const selectedType = ref<'web' | 'excel' | 'pdf'>('web')
const creating = ref(false)
const selectedTaskId = ref<number | null>(null)

const typeColors: Record<string, string> = {
  web: '#3B82F6',
  excel: '#22C55E',
  pdf: '#F59E0B',
}

const typeIcons: Record<string, any> = {
  web: FileText,
  excel: FileSpreadsheet,
  pdf: File,
}

async function fetchReports() {
  loading.value = true
  error.value = ''
  try {
    reports.value = await reportsApi.list()
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '加载报告列表失败'
  } finally {
    loading.value = false
  }
}

async function fetchCompletedTasks() {
  try {
    const response = await getJson<{ results: InspectionTaskSummary[] }>('/inspections/?status=completed')
    completedTasks.value = response.results
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '加载巡检结果失败'
  }
}

async function doCreate() {
  if (!selectedTaskId.value) {
    error.value = '请先选择一个已完成的巡检结果'
    return
  }
  creating.value = true
  try {
    await reportsApi.create({ report_type: selectedType.value, inspection_task_id: selectedTaskId.value })
    showCreate.value = false
    await fetchReports()
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '创建报告失败'
  } finally {
    creating.value = false
  }
}

async function doRetry(id: number) {
  try {
    await reportsApi.retry(id)
    await fetchReports()
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '重试失败'
  }
}

async function doDownload(report: Report) {
  if (report.status !== 'ready' || !report.file) return
  try {
    const blob = await reportsApi.download(report.id)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = report.file!.split('/').pop() || `report-${report.id}`
    a.click()
    URL.revokeObjectURL(url)
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '下载失败'
  }
}

function typeColor(type: string): string {
  return typeColors[type] ?? '#94A3B8'
}

function statusColor(status: string): string {
  return REPORT_STATUS_COLORS[status] ?? '#94A3B8'
}

onMounted(async () => {
  await Promise.all([fetchReports(), fetchCompletedTasks()])
})
</script>

<template>
  <section class="workspace">
    <div class="page-heading">
      <div>
        <span class="eyebrow">REPORTS / CENTER</span>
        <h2>报告中心</h2>
        <p>查看和管理系统生成的各类报告</p>
      </div>
      <button class="primary-button" @click="showCreate = true">
        <FileText :size="16" /> 生成报告
      </button>
    </div>

    <div v-if="error" class="error-banner">{{ error }}</div>

    <div v-if="loading && !reports.length" class="empty-state">
      <p>加载中…</p>
    </div>

    <div v-else-if="reports.length === 0 && !error" class="empty-state">
      <div class="empty-icon">▤</div>
      <p>暂无报告</p>
      <button class="primary-button" @click="showCreate = true">
        <FileText :size="16" /> 生成第一份报告
      </button>
    </div>

    <div v-else class="report-grid">
      <article v-for="report in reports" :key="report.id" class="report-card">
        <header>
          <div class="report-type-row">
            <span class="type-badge" :style="{ background: typeColor(report.report_type) + '22', color: typeColor(report.report_type), borderColor: typeColor(report.report_type) }">
              <component :is="typeIcons[report.report_type] || FileText" :size="12" />
              {{ REPORT_TYPE_LABELS[report.report_type] || report.report_type }}
            </span>
            <span class="status-badge" :style="{ background: statusColor(report.status) + '22', color: statusColor(report.status), borderColor: statusColor(report.status) }">
              {{ REPORT_STATUS_LABELS[report.status] || report.status }}
            </span>
          </div>
        </header>
          <div class="report-meta">
          <div class="meta-row task-meta-row">
            <span class="meta-label">巡检结果</span>
            <span class="meta-value">{{ report.inspection_task_title || '未关联具体任务' }}</span>
          </div>
          <div class="meta-row">
            <span class="meta-label">创建者</span>
            <span class="meta-value">{{ report.created_by }}</span>
          </div>
          <div class="meta-row">
            <span class="meta-label">生成时间</span>
            <span class="meta-value">{{ new Date(report.created_at).toLocaleString('zh-CN') }}</span>
          </div>
        </div>

        <!-- 进度条（生成中） -->
        <div v-if="report.status === 'generating'" class="progress-bar">
          <div class="progress-fill" :style="{ width: `${report.progress}%` }"></div>
          <span class="progress-text">{{ report.progress }}%</span>
        </div>

        <!-- 错误信息 -->
        <div v-if="report.status === 'failed' && report.error_message" class="report-error">
          {{ report.error_message }}
        </div>

        <div class="report-actions">
          <button
            v-if="report.status === 'ready' && report.file"
            class="action-btn"
            title="下载"
            @click="doDownload(report)"
          >
            <Download :size="13" /> 下载
          </button>
          <button
            v-if="report.status === 'failed'"
            class="action-btn"
            title="重试"
            @click="doRetry(report.id)"
          >
            <RotateCcw :size="13" /> 重试
          </button>
        </div>
      </article>
    </div>

    <!-- 创建报告弹窗 -->
    <Teleport to="body">
      <div v-if="showCreate" class="modal-overlay" @click.self="showCreate = false">
        <div class="modal-card">
          <header>
            <h3>生成新报告</h3>
            <button class="close-btn" @click="showCreate = false"><X :size="18" /></button>
          </header>
          <div class="modal-body">
            <label class="form-field">
              <span>选择巡检结果</span>
              <select v-model="selectedTaskId">
                <option :value="null" disabled>请选择已完成的巡检任务</option>
                <option v-for="task in completedTasks" :key="task.id" :value="task.id">
                  #{{ task.id }} · {{ task.title }} · 覆盖率 {{ task.coverage }}%
                </option>
              </select>
              <small v-if="!completedTasks.length" class="field-hint">暂无已完成巡检任务，请先在任务中心完成一次巡检。</small>
            </label>
            <label class="form-field">
              <span>选择报告类型</span>
              <div class="type-selector">
                <button
                  v-for="type in (['web', 'excel', 'pdf'] as const)"
                  :key="type"
                  :class="['type-option', { active: selectedType === type }]"
                  :style="selectedType === type ? { borderColor: typeColors[type], color: typeColors[type] } : {}"
                  @click="selectedType = type"
                >
                  <component :is="typeIcons[type]" :size="18" />
                  <span>{{ REPORT_TYPE_LABELS[type] }}</span>
                </button>
              </div>
            </label>
          </div>
          <footer>
            <button class="ghost-button" @click="showCreate = false">取消</button>
            <button class="primary-button" :disabled="creating || !selectedTaskId" @click="doCreate">
              {{ creating ? '生成中…' : '开始生成' }}
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

.report-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 14px; }
.report-card {
  padding: 18px; background: #111A2E; border: 1px solid #1E2A45;
  border-radius: 6px; transition: all 0.15s;
}
.report-card:hover { border-color: #3B82F6; background: #0F172A; }
.report-card header { height: auto; background: transparent; padding: 0 0 12px; border-bottom: 1px solid #1E2A45; }
.report-type-row { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.type-badge, .status-badge {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 2px 8px; border-radius: 4px; font-size: 10px; font-weight: 500; border: 1px solid; white-space: nowrap;
}
.report-meta { padding: 12px 0; display: grid; gap: 6px; }
.meta-row { display: flex; justify-content: space-between; align-items: center; }
.meta-label { color: #64748B; font-size: 11px; }
.meta-value { color: #E2E8F0; font-size: 11px; }

.progress-bar {
  position: relative; height: 6px; background: #1E2A45; border-radius: 3px;
  margin: 8px 0; overflow: hidden;
}
.progress-fill {
  height: 100%; background: #3B82F6; border-radius: 3px; transition: width 0.5s;
}
.progress-text {
  position: absolute; right: 0; top: -16px; font-size: 10px; color: #3B82F6;
}

.report-error {
  padding: 6px 10px; margin: 8px 0; color: #EF4444;
  background: rgba(239,68,68,0.1); border: 1px solid rgba(239,68,68,0.3);
  border-radius: 4px; font-size: 11px;
}

.report-actions {
  display: flex; gap: 6px; padding-top: 10px; border-top: 1px solid #1E2A45;
}
.action-btn {
  display: flex; align-items: center; gap: 4px; min-height: 28px;
  padding: 0 10px; color: #94A3B8; background: #0F172A;
  border: 1px solid #1E2A45; border-radius: 3px; font-size: 10px; cursor: pointer;
}
.action-btn:hover { color: #E2E8F0; border-color: #3B82F6; }

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
.form-field select { width: 100%; min-height: 38px; padding: 0 10px; color: #E2E8F0; background: #0F172A; border: 1px solid #1E2A45; border-radius: 4px; }
.field-hint { color: #F59E0B; font-size: 11px; line-height: 1.5; }
.task-meta-row { padding-bottom: 6px; border-bottom: 1px solid #1E2A45; }
.type-selector { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; }
.type-option {
  display: flex; flex-direction: column; align-items: center; gap: 6px;
  padding: 16px 8px; color: #94A3B8; background: #0F172A;
  border: 1px solid #1E2A45; border-radius: 6px; cursor: pointer; font-size: 12px;
}
.type-option:hover { color: #E2E8F0; border-color: #64748B; }
.type-option.active { background: rgba(59,130,246,0.08); }
.modal-card footer {
  display: flex; justify-content: flex-end; gap: 8px;
  padding: 14px 20px; border-top: 1px solid #1E2A45;
}
</style>
