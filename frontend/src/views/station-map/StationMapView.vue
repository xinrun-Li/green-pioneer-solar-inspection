<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Filter, X } from 'lucide-vue-next'
import { getJson } from '@/api/http'
import type { PanelStatus, StationMap, RegionMapItem, ArrayMapItem, WaypointPos } from '@/types/station'
import StationMapDetail from '@/components/StationMapDetail.vue'

const station = ref<StationMap | null>(null)
const selectedRegionId = ref<number | null>(null)
const statusFilter = ref<PanelStatus | 'all'>('all')
const detailPanelId = ref<number | null>(null)
const showSRoute = ref(true)
const error = ref('')

const labels: Record<PanelStatus, string> = {
  normal: '正常', cleaning: '需要清洗', repair: '需要维修', processing: '识别中', unknown: '未知',
}

const selectedRegion = computed<RegionMapItem | null>(() =>
  station.value?.regions.find((r) => r.id === selectedRegionId.value) ?? station.value?.regions[0] ?? null
)

const filteredArrays = computed<ArrayMapItem[]>(() => {
  if (!selectedRegion.value) return []
  let arrays = selectedRegion.value.arrays
  if (statusFilter.value !== 'all') {
    arrays = arrays.map((a) => ({
      ...a,
      panels: a.panels.filter((p) => p.status === statusFilter.value),
    })).filter((a) => a.panels.length > 0)
  }
  return arrays
})

function generateSRoute(panels: ArrayMapItem['panels']): WaypointPos[] {
  if (!panels.length) return []
  const sorted = [...panels].sort((a, b) => {
    if (a.row !== b.row) return a.row - b.row
    return a.row % 2 === 1 ? a.column - b.column : b.column - a.column
  })
  return sorted.map((p) => ({ row: p.row, column: p.column, panel_id: p.id }))
}

onMounted(async () => {
  try {
    station.value = await getJson<StationMap>('/stations/current/map')
    selectedRegionId.value = station.value.regions[0]?.id ?? null
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '地图数据加载失败'
  }
})
</script>

<template>
  <section class="workspace map-workspace">
    <div v-if="error" class="panel error">{{ error }}</div>
    <template v-else-if="station">
      <div class="map-heading">
        <div>
          <span class="eyebrow">{{ station.code }} / ASSET MAP</span>
          <h2>{{ station.name }}</h2>
          <p>{{ station.regions.length }} 个区域 · {{ station.regions.reduce((s, r) => s + r.arrays.length, 0) }} 个阵列 · {{ station.panel_count }} 块组件</p>
        </div>
        <div class="map-summary">
          <div v-for="(label, status) in labels" :key="status">
            <i :class="`status-${status}`"></i><span>{{ label }}</span><b>{{ station.summary[status] }}</b>
          </div>
        </div>
      </div>
      <div class="filter-bar">
        <div class="filter-group">
          <Filter :size="14" />
          <button
            v-for="opt in (['all', ...Object.keys(labels)] as (PanelStatus | 'all')[])"
            :key="opt"
            :class="['filter-btn', { active: statusFilter === opt }]"
            @click="statusFilter = opt"
          >{{ opt === 'all' ? '全部' : labels[opt as PanelStatus] }}</button>
        </div>
        <label class="sroute-toggle">
          <input type="checkbox" v-model="showSRoute" />
          <span>S 形航线</span>
        </label>
      </div>
      <div class="region-tabs" role="tablist">
        <button
          v-for="region in station.regions"
          :key="region.id"
          :class="{ active: selectedRegion?.id === region.id }"
          @click="selectedRegionId = region.id"
        >{{ region.name }}<small>{{ region.arrays.length }} 个阵列</small></button>
      </div>
      <div v-if="filteredArrays.length" class="array-grid">
        <article v-for="array in filteredArrays" :key="array.id" class="array-card">
          <header>
            <div><span>{{ selectedRegion!.name }}</span><h3>{{ array.code }} 阵列</h3></div>
            <small>{{ array.rows }} × {{ array.columns }}</small>
          </header>
          <div class="panel-grid-wrapper">
            <div class="panel-grid" :style="{ gridTemplateColumns: `repeat(${array.columns}, 1fr)` }">
              <button
                v-for="panel in array.panels"
                :key="panel.id"
                :class="['solar-panel', `status-${panel.status}`, { 's-route-point': showSRoute }]"
                :title="`${panel.full_code} · ${labels[panel.status]}`"
                @click="detailPanelId = panel.id"
              ><span>{{ panel.short_code.split('-')[1] }}</span></button>
            </div>
            <svg v-if="showSRoute && array.panels.length > 1" class="sroute-svg" :viewBox="`0 0 ${array.columns * 100} ${array.rows * 100}`" preserveAspectRatio="none">
              <polyline
                :points="generateSRoute(array.panels).map((wp) => `${(wp.column - 0.5) * 100},${(wp.row - 0.5) * 100}`).join(' ')"
                fill="none" stroke="#3B82F6" stroke-width="1.5" stroke-dasharray="6,4" stroke-linecap="round" stroke-linejoin="round"
              />
              <circle
                v-for="(wp, idx) in generateSRoute(array.panels)"
                :key="wp.panel_id"
                :cx="(wp.column - 0.5) * 100"
                :cy="(wp.row - 0.5) * 100"
                :r="idx === 0 ? 4 : 2.5"
                :fill="idx === 0 ? '#22C55E' : '#3B82F6'"
              />
            </svg>
          </div>
        </article>
      </div>
      <div v-else class="empty-hint">当前筛选项无匹配组件</div>
    </template>
    <div v-else class="loading-state">正在读取电站资产…</div>
    <Teleport to="body">
      <StationMapDetail v-if="detailPanelId" :panel-id="detailPanelId" @close="detailPanelId = null" />
    </Teleport>
  </section>
</template>

<style scoped>
.filter-bar {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 10px; gap: 12px;
}
.filter-group {
  display: flex; align-items: center; gap: 6px; color: #94A3B8;
  font-size: 12px;
}
.filter-btn {
  background: #0F172A; border: 1px solid #1E2A45; color: #94A3B8;
  padding: 3px 10px; border-radius: 4px; font-size: 12px; cursor: pointer;
  transition: all 0.15s;
}
.filter-btn:hover { border-color: #3B82F6; color: #E2E8F0; }
.filter-btn.active { background: rgba(59,130,246,0.15); border-color: #3B82F6; color: #60A5FA; }
.sroute-toggle {
  display: flex; align-items: center; gap: 6px; font-size: 12px; color: #94A3B8; cursor: pointer;
}
.sroute-toggle input { accent-color: #3B82F6; }
.panel-grid-wrapper {
  position: relative;
}
.sroute-svg {
  position: absolute; inset: 0; width: 100%; height: 100%;
  pointer-events: none;
}
.s-route-point { cursor: pointer; }
.empty-hint {
  text-align: center; padding: 40px; color: #64748B; font-size: 13px;
}
</style>