<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { X, Clock, AlertTriangle, Wrench } from 'lucide-vue-next'
import { getJson, requestJson } from '@/api/http'
import type { PanelDetail, PanelStatus } from '@/types/station'

const props = defineProps<{ panelId: number }>()
const emit = defineEmits<{ close: [] }>()

const detail = ref<PanelDetail | null>(null)
const loading = ref(true)
const error = ref('')
const manualStatus = ref<PanelStatus>('unknown')
const manualNote = ref('')
const manualSaving = ref(false)
const manualMessage = ref('')

const statusLabels: Record<PanelStatus, string> = {
  normal: '正常', cleaning: '需要清洗', repair: '需要维修',
  processing: '识别中', unknown: '未知',
}

async function loadDetail() {
  loading.value = true
  error.value = ''
  try {
    detail.value = await getJson<PanelDetail>(`/stations/panels/${props.panelId}`)
    manualStatus.value = detail.value.status === 'processing' ? 'unknown' : detail.value.status
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '加载组件详情失败'
  } finally {
    loading.value = false
  }
}

async function saveManualCheck() {
  manualSaving.value = true
  manualMessage.value = ''
  try {
    await requestJson(`/inspections/manual-check/`, {
      method: 'POST',
      body: JSON.stringify({ panel_id: props.panelId, status: manualStatus.value, note: manualNote.value }),
    })
    manualNote.value = ''
    manualMessage.value = '已记录本次手动检查'
    await loadDetail()
  } catch (reason) {
    manualMessage.value = reason instanceof Error ? reason.message : '保存手动检查失败'
  } finally {
    manualSaving.value = false
  }
}

onMounted(loadDetail)
</script>

<template>
  <div class="detail-overlay" @click.self="emit('close')">
    <div class="detail-card">
      <header>
        <div class="detail-header-left">
          <span class="detail-code">{{ detail?.full_code ?? '加载中…' }}</span>
          <span v-if="detail" class="status-badge" :class="`status-${detail.status}`">{{ statusLabels[detail.status] }}</span>
        </div>
        <button class="close-btn" @click="emit('close')"><X :size="18" /></button>
      </header>
      <div v-if="loading" class="loading">加载中…</div>
      <div v-else-if="error" class="error">{{ error }}</div>
      <template v-else-if="detail">
        <div class="detail-meta">
          <div class="meta-item"><label>位置</label><span>{{ detail.region_name }} / {{ detail.array_code }} / {{ detail.short_code }}</span></div>
          <div class="meta-item"><label>行列</label><span>第 {{ detail.row }} 行 · 第 {{ detail.column }} 列</span></div>
          <div class="meta-item"><label>最后识别</label><span>{{ detail.last_recognized_at ? new Date(detail.last_recognized_at).toLocaleString('zh-CN') : '尚未识别' }}</span></div>
        </div>
        <div class="detail-section manual-check-section">
          <h4><Clock :size="14" /> 手动检查</h4>
          <div class="manual-form">
            <select v-model="manualStatus" class="manual-select">
              <option value="normal">正常</option>
              <option value="cleaning">需要清洗</option>
              <option value="repair">需要维修</option>
              <option value="unknown">未知</option>
            </select>
            <input v-model="manualNote" class="manual-input" maxlength="120" placeholder="检查备注（可选）" />
            <button class="manual-btn" :disabled="manualSaving" @click="saveManualCheck">
              {{ manualSaving ? '保存中…' : '记录检查' }}
            </button>
          </div>
          <div v-if="manualMessage" class="manual-message">{{ manualMessage }}</div>
        </div>
        <div v-if="detail.events.length" class="detail-section">
          <h4><AlertTriangle :size="14" /> 异常事件</h4>
          <div v-for="evt in detail.events" :key="evt.id" class="event-row" :class="`event-${evt.status}`">
            <span class="event-icon"><Wrench v-if="evt.event_type === 'repair'" :size="12" /><AlertTriangle v-else :size="12" /></span>
            <div class="event-body">
              <div class="event-header">
                <span class="event-type">{{ evt.event_type === 'repair' ? '维修' : '清洗' }}</span>
                <span class="event-status">{{ evt.status === 'open' ? '进行中' : '已关闭' }}</span>
              </div>
              <div class="event-reason">{{ evt.reason }}</div>
              <div class="event-time">{{ new Date(evt.opened_at).toLocaleString('zh-CN') }}</div>
            </div>
          </div>
        </div>
        <div class="detail-section">
          <h4><Clock :size="14" /> 最近状态变更</h4>
          <div v-if="!detail.status_history.length" class="empty-hint">暂无状态变更记录</div>
          <div v-for="h in detail.status_history" :key="h.id" class="history-row">
            <span class="status-dot" :class="`status-${h.status}`"></span>
            <span :class="`status-label-${h.status}`">{{ statusLabels[h.status] }}</span>
            <span class="history-reason">{{ h.reason || '无备注' }}</span>
            <span class="history-time">{{ new Date(h.recorded_at).toLocaleString('zh-CN') }}</span>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.detail-overlay {
  position: fixed; inset: 0; z-index: 100;
  background: rgba(0,0,0,0.55);
  display: flex; align-items: center; justify-content: center;
}
.detail-card {
  background: #111A2E; border: 1px solid #1E2A45; border-radius: 8px;
  width: 480px; max-height: 80vh; overflow-y: auto;
  padding: 20px;
}
.detail-card header {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 16px;
}
.detail-header-left { display: flex; align-items: center; gap: 10px; }
.detail-code { font-size: 18px; font-weight: 600; color: #E2E8F0; }
.close-btn {
  background: none; border: none; color: #94A3B8; cursor: pointer;
  padding: 4px; border-radius: 4px;
}
.close-btn:hover { color: #E2E8F0; background: #1E2A45; }
.status-badge { font-size: 11px; padding: 2px 8px; border-radius: 4px; font-weight: 500; }
.status-normal { background: rgba(22,163,74,0.2); color: #22C55E; }
.status-cleaning { background: rgba(245,158,11,0.2); color: #F59E0B; }
.status-repair { background: rgba(239,68,68,0.2); color: #EF4444; }
.status-processing { background: rgba(59,130,246,0.2); color: #3B82F6; }
.status-unknown { background: rgba(100,116,139,0.2); color: #94A3B8; }
.loading, .error { padding: 20px; text-align: center; color: #94A3B8; }
.error { color: #EF4444; }
.detail-meta { display: flex; flex-direction: column; gap: 8px; margin-bottom: 16px; }
.meta-item { display: flex; gap: 8px; font-size: 13px; }
.meta-item label { color: #64748B; min-width: 64px; }
.meta-item span { color: #E2E8F0; }
.detail-section { margin-bottom: 16px; }
.manual-form { display: grid; grid-template-columns: 1fr 1.5fr auto; gap: 8px; }
.manual-select, .manual-input {
  min-height: 32px; padding: 0 8px; color: #E2E8F0; background: #0F172A;
  border: 1px solid #1E2A45; border-radius: 4px; font-size: 11px; outline: none;
}
.manual-btn {
  min-height: 32px; padding: 0 10px; color: #06170f; background: #39e58c;
  border: 0; border-radius: 4px; font-size: 11px; font-weight: 700; cursor: pointer;
}
.manual-btn:disabled { opacity: 0.55; cursor: not-allowed; }
.manual-message { margin-top: 7px; color: #39e58c; font-size: 11px; }
.detail-section h4 {
  display: flex; align-items: center; gap: 6px; font-size: 13px; font-weight: 500;
  color: #94A3B8; margin-bottom: 8px; padding-bottom: 6px; border-bottom: 1px solid #1E2A45;
}
.event-row { display: flex; gap: 8px; padding: 8px; border-radius: 4px; margin-bottom: 6px; background: #0F172A; }
.event-row.event-open { border-left: 2px solid #F59E0B; }
.event-row.event-closed { border-left: 2px solid #64748B; }
.event-icon { color: #F59E0B; margin-top: 2px; }
.event-body { flex: 1; }
.event-header { display: flex; gap: 8px; align-items: center; margin-bottom: 4px; }
.event-type { font-size: 12px; font-weight: 500; color: #E2E8F0; }
.event-status { font-size: 11px; color: #F59E0B; }
.event-row.event-closed .event-status { color: #64748B; }
.event-reason { font-size: 12px; color: #94A3B8; margin-bottom: 2px; }
.event-time { font-size: 11px; color: #64748B; }
.history-row { display: flex; align-items: center; gap: 8px; padding: 4px 0; font-size: 12px; }
.status-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.status-dot.status-normal { background: #22C55E; }
.status-dot.status-cleaning { background: #F59E0B; }
.status-dot.status-repair { background: #EF4444; }
.status-dot.status-processing { background: #3B82F6; }
.status-dot.status-unknown { background: #64748B; }
.status-label-normal { color: #22C55E; }
.status-label-cleaning { color: #F59E0B; }
.status-label-repair { color: #EF4444; }
.status-label-processing { color: #3B82F6; }
.status-label-unknown { color: #64748B; }
.history-reason { color: #94A3B8; flex: 1; }
.history-time { color: #64748B; white-space: nowrap; }
.empty-hint { color: #64748B; font-size: 12px; padding: 8px 0; text-align: center; }
</style>
