<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ChevronDown, ChevronUp, Calendar } from 'lucide-vue-next'
import { historyApi } from '@/api/history'
import type { HistoryRecord, HistoryStats, HistoryFilter } from '@/types/history'

const stats = ref<HistoryStats | null>(null)
const events = ref<HistoryRecord[]>([])
const error = ref('')
const loading = ref(false)
const timeRange = ref<'7d' | '30d' | 'custom'>('7d')
const customFrom = ref('')
const customTo = ref('')
const currentPage = ref(1)
const pageSize = 10
const expandedEvent = ref<number | null>(null)

const paginatedEvents = computed(() => {
  const start = (currentPage.value - 1) * pageSize
  return events.value.slice(start, start + pageSize)
})

const totalPages = computed(() => Math.max(1, Math.ceil(events.value.length / pageSize)))

function buildFilters(): HistoryFilter {
  const now = new Date()
  const filters: HistoryFilter = {}
  if (timeRange.value === '7d') {
    const from = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000)
    filters.date_from = from.toISOString().split('T')[0]
    filters.date_to = now.toISOString().split('T')[0]
  } else if (timeRange.value === '30d') {
    const from = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000)
    filters.date_from = from.toISOString().split('T')[0]
    filters.date_to = now.toISOString().split('T')[0]
  } else {
    if (customFrom.value) filters.date_from = customFrom.value
    if (customTo.value) filters.date_to = customTo.value
  }
  return filters
}

async function fetchData() {
  loading.value = true
  error.value = ''
  const filters = buildFilters()
  try {
    const response = await historyApi.getHistory(filters)
    stats.value = response.stats
    events.value = response.results ?? []
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '加载历史数据失败'
  } finally {
    loading.value = false
  }
}

function toggleEvent(id: number) {
  expandedEvent.value = expandedEvent.value === id ? null : id
}

function prevPage() {
  if (currentPage.value > 1) currentPage.value--
}

function nextPage() {
  if (currentPage.value < totalPages.value) currentPage.value++
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleString('zh-CN')
}

onMounted(fetchData)
</script>

<template>
  <section class="workspace">
    <div class="page-heading">
      <div>
        <span class="eyebrow">HISTORY / DATA</span>
        <h2>历史数据</h2>
        <p>查看历史趋势和数据分析</p>
      </div>
      <div class="time-filter">
        <button
          :class="['filter-btn', { active: timeRange === '7d' }]"
          @click="timeRange = '7d'; currentPage = 1; fetchData()"
        >
          7天
        </button>
        <button
          :class="['filter-btn', { active: timeRange === '30d' }]"
          @click="timeRange = '30d'; currentPage = 1; fetchData()"
        >
          30天
        </button>
        <button
          :class="['filter-btn', { active: timeRange === 'custom' }]"
          @click="timeRange = 'custom'"
        >
          <Calendar :size="12" /> 自定义
        </button>
        <div v-if="timeRange === 'custom'" class="custom-date-range">
          <input v-model="customFrom" type="date" class="date-input" />
          <span>至</span>
          <input v-model="customTo" type="date" class="date-input" />
          <button class="query-btn" @click="currentPage = 1; fetchData()">查询</button>
        </div>
      </div>
    </div>

    <div v-if="error" class="error-banner">{{ error }}</div>

    <div v-if="loading && !stats" class="empty-state">
      <p>加载中…</p>
    </div>

    <template v-else-if="stats">
      <!-- 概览统计卡片 -->
      <div class="stats-grid">
        <article class="stat-card">
          <span class="stat-label">历史记录数</span>
          <strong class="stat-value">{{ stats.total_records }}</strong>
        </article>
        <article class="stat-card">
          <span class="stat-label">巡检任务</span>
          <strong class="stat-value">{{ stats.task_records }}</strong>
        </article>
        <article class="stat-card">
          <span class="stat-label">手动检查</span>
          <strong class="stat-value">{{ stats.manual_records }}</strong>
        </article>
        <article class="stat-card">
          <span class="stat-label">人工复核</span>
          <strong class="stat-value">{{ stats.review_records }}</strong>
        </article>
      </div>

      <!-- 三分类柱状图 (CSS) -->
      <div class="chart-section">
        <h3 class="section-title">三分类结果</h3>
        <div class="bar-chart">
          <div class="bar-item">
            <span class="bar-label">正常</span>
            <div class="bar-track">
              <div
                class="bar-fill bar-normal"
                :style="{ width: `${stats.total_records > 0 ? (stats.classification_counts.normal / stats.total_records * 100) : 0}%` }"
              ></div>
            </div>
            <span class="bar-count">{{ stats.classification_counts.normal }}</span>
          </div>
          <div class="bar-item">
            <span class="bar-label">需要清洗</span>
            <div class="bar-track">
              <div
                class="bar-fill bar-cleaning"
                :style="{ width: `${stats.total_records > 0 ? (stats.classification_counts.needs_cleaning / stats.total_records * 100) : 0}%` }"
              ></div>
            </div>
            <span class="bar-count">{{ stats.classification_counts.needs_cleaning }}</span>
          </div>
          <div class="bar-item">
            <span class="bar-label">需要维修</span>
            <div class="bar-track">
              <div
                class="bar-fill bar-repair"
                :style="{ width: `${stats.total_records > 0 ? (stats.classification_counts.needs_repair / stats.total_records * 100) : 0}%` }"
              ></div>
            </div>
            <span class="bar-count">{{ stats.classification_counts.needs_repair }}</span>
          </div>
        </div>
      </div>

      <!-- 异常事件列表 -->
      <div class="event-section">
        <h3 class="section-title">巡检与手动检查记录（最近 200 条）</h3>
        <div v-if="events.length === 0" class="empty-state" style="padding: 30px">
            <p>暂无巡检或手动检查记录</p>
        </div>
        <div v-else class="event-list">
          <div v-for="event in paginatedEvents" :key="event.id" class="event-item">
            <div class="event-header" @click="toggleEvent(event.id)">
              <div class="event-info">
                <span class="event-type-badge">{{ event.source_label }}</span>
                <span class="event-desc">{{ event.summary || '无备注' }}</span>
              </div>
              <div class="event-meta">
                <span class="event-time">{{ formatDate(event.recorded_at) }}</span>
                <component :is="expandedEvent === event.id ? ChevronUp : ChevronDown" :size="14" />
              </div>
            </div>
            <div v-if="expandedEvent === event.id" class="event-detail">
              <div class="detail-row">
                <span class="detail-label">记录 ID</span>
                <span class="detail-value">{{ event.id }}</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">操作人员</span>
                <span class="detail-value">{{ event.operator_name || '-' }}</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">检查来源</span>
                <span class="detail-value">{{ event.source_label || '-' }}</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">检查结果</span>
                <span class="detail-value">{{ event.status_label || '-' }} · {{ event.summary || '-' }}</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">巡检任务</span>
                <span class="detail-value">{{ event.task_title || '-' }}</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">组件</span>
                <span class="detail-value">{{ event.panel_full_code || '-' }}</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">记录时间</span>
                <span class="detail-value">{{ formatDate(event.recorded_at) }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 分页 -->
        <div v-if="events.length > pageSize" class="pagination">
          <button :disabled="currentPage === 1" @click="prevPage">上一页</button>
          <span>{{ currentPage }} / {{ totalPages }}</span>
          <button :disabled="currentPage === totalPages" @click="nextPage">下一页</button>
        </div>
      </div>
    </template>
  </section>
</template>

<style scoped>
.page-heading {
  display: flex; align-items: flex-end; justify-content: space-between;
  padding-bottom: 20px; border-bottom: 1px solid #1E2A45; margin-bottom: 20px;
  flex-wrap: wrap; gap: 12px;
}
.page-heading h2 { margin: 8px 0 5px; font-size: 27px; }
.page-heading p { margin: 0; color: #789084; font-size: 12px; }
.time-filter {
  display: flex; align-items: center; gap: 6px; flex-wrap: wrap;
}
.filter-btn {
  display: flex; align-items: center; gap: 4px; min-height: 30px;
  padding: 0 10px; color: #94A3B8; background: #0F172A;
  border: 1px solid #1E2A45; border-radius: 4px; font-size: 11px; cursor: pointer;
}
.filter-btn:hover { color: #E2E8F0; border-color: #3B82F6; }
.filter-btn.active { color: #3B82F6; border-color: #3B82F6; background: rgba(59,130,246,0.08); }
.custom-date-range {
  display: flex; align-items: center; gap: 6px;
}
.date-input {
  height: 30px; padding: 0 8px; color: #E2E8F0; background: #0F172A;
  border: 1px solid #1E2A45; border-radius: 4px; font-size: 11px; outline: none;
}
.date-input:focus { border-color: #3B82F6; }
.query-btn {
  min-height: 30px; padding: 0 10px; color: #06170f; background: #39e58c;
  border: 0; border-radius: 4px; font-size: 11px; font-weight: 700; cursor: pointer;
}
.query-btn:hover { background: #63eea5; }

.error-banner {
  padding: 10px 14px; margin-bottom: 16px; color: #EF4444;
  background: rgba(239,68,68,0.1); border: 1px solid rgba(239,68,68,0.3);
  border-radius: 4px; font-size: 12px;
}
.empty-state {
  display: grid; place-items: center; padding: 60px; text-align: center;
}
.empty-state p { color: #94A3B8; font-size: 13px; margin-bottom: 16px; }

.stats-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 20px; }
.stat-card {
  padding: 18px; background: #111A2E; border: 1px solid #1E2A45;
  border-radius: 6px; display: grid; gap: 6px;
}
.stat-label { color: #64748B; font-size: 11px; }
.stat-value { font-size: 24px; color: #E2E8F0; font-family: ui-monospace, monospace; }
.stat-value.warn { color: #F59E0B; }

.section-title { margin: 0 0 14px; font-size: 15px; font-weight: 500; color: #E2E8F0; }

.chart-section { margin-bottom: 24px; padding: 18px; background: #111A2E; border: 1px solid #1E2A45; border-radius: 6px; }

.bar-chart { display: grid; gap: 12px; }
.bar-item { display: flex; align-items: center; gap: 10px; }
.bar-label { width: 80px; font-size: 11px; color: #94A3B8; flex-shrink: 0; }
.bar-track { flex: 1; height: 20px; background: #0F172A; border-radius: 4px; overflow: hidden; }
.bar-fill { height: 100%; border-radius: 4px; transition: width 0.6s; }
.bar-normal { background: #22C55E; }
.bar-cleaning { background: #F59E0B; }
.bar-repair { background: #EF4444; }
.bar-count { width: 40px; text-align: right; font-size: 12px; color: #E2E8F0; font-family: ui-monospace, monospace; }

.event-section { padding: 18px; background: #111A2E; border: 1px solid #1E2A45; border-radius: 6px; }
.event-list { display: grid; gap: 4px; }
.event-item { border: 1px solid #1E2A45; border-radius: 4px; overflow: hidden; }
.event-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 10px 14px; cursor: pointer; background: #0F172A;
  transition: background 0.15s;
}
.event-header:hover { background: #111A2E; }
.event-info { display: flex; align-items: center; gap: 8px; flex: 1; }
.event-type-badge {
  padding: 1px 6px; border-radius: 3px; font-size: 10px; background: rgba(59,130,246,0.15);
  color: #3B82F6; border: 1px solid rgba(59,130,246,0.3); white-space: nowrap;
}
.event-desc { font-size: 12px; color: #E2E8F0; }
.event-meta { display: flex; align-items: center; gap: 8px; }
.event-time { color: #64748B; font-size: 10px; }
.event-detail {
  padding: 12px 14px; border-top: 1px solid #1E2A45; display: grid; gap: 8px;
}
.detail-row { display: flex; gap: 10px; }
.detail-label { color: #64748B; font-size: 11px; width: 70px; flex-shrink: 0; }
.detail-value { color: #E2E8F0; font-size: 11px; }

.pagination {
  display: flex; align-items: center; justify-content: center; gap: 12px;
  padding-top: 14px; margin-top: 10px; border-top: 1px solid #1E2A45;
}
.pagination button {
  min-height: 28px; padding: 0 10px; color: #94A3B8; background: #0F172A;
  border: 1px solid #1E2A45; border-radius: 3px; font-size: 11px; cursor: pointer;
}
.pagination button:hover:not(:disabled) { color: #E2E8F0; border-color: #3B82F6; }
.pagination button:disabled { opacity: 0.4; cursor: not-allowed; }
.pagination span { color: #94A3B8; font-size: 11px; }
</style>
