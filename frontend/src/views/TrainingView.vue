<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { ApiError, getJson, requestJson } from '@/api/http'
import type { DatasetAnnotation, DatasetAsset, DatasetVersion, ModelVersion, TrainingRun } from '@/types/training'

type AssetTab = 'pending' | 'annotated' | 'rejected'
type ClassName = 'normal' | 'cleaning' | 'repair'

const classLabels: Record<ClassName, string> = { repair: '需要维修', cleaning: '需要清洗', normal: '正常' }
const classColors: Record<ClassName, string> = { repair: '#ff625b', cleaning: '#f3bd4b', normal: '#39e58c' }
const sourceLabels: Record<string, string> = {
  uploaded: '直接上传', low_confidence: '低置信度', manual_correction: '人工修正',
  manual_unrecognized: '人工标记无法识别', inference_failed: '识别失败',
}
const statusLabels: Record<AssetTab, string> = { pending: '待标注', annotated: '已标注', rejected: '无效样本' }

const assets = ref<DatasetAsset[]>([])
const assetCounts = ref<Record<AssetTab, number>>({ pending: 0, annotated: 0, rejected: 0 })
const versions = ref<DatasetVersion[]>([])
const models = ref<ModelVersion[]>([])
const runs = ref<TrainingRun[]>([])
const selectedAsset = ref<DatasetAsset | null>(null)
const selectedAnnotationId = ref<number | null>(null)
const pendingBox = ref<{ x: number; y: number; width: number; height: number } | null>(null)
const tab = ref<AssetTab>('pending')
const sourceFilter = ref('')
const search = ref('')
const loading = ref(false)
const loadingMore = ref(false)
const nextOffset = ref<number | null>(0)
const message = ref('')
const fileInput = ref<HTMLInputElement | null>(null)
const annotationViewport = ref<HTMLElement | null>(null)
const annotationStage = ref<HTMLElement | null>(null)
const workspace = ref<HTMLElement | null>(null)
const imageDimensions = ref({ width: 16, height: 9 })
const zoom = ref(1)
const pan = ref({ x: 0, y: 0 })
const fullscreen = ref(false)
const activeClass = ref<ClassName>('repair')
const trainingConfig = ref({ epochs: 50, image_size: 1024, batch_size: 16, device: 'cuda' })
const showTrainingConfig = ref(false)
const datasetName = ref('光伏巡检数据集')
const datasetVersion = ref(`v${new Date().toISOString().slice(0, 10).replace(/-/g, '')}`)
const busy = ref(false)
const dirty = ref(false)

let drawStart: { x: number; y: number } | null = null
let dragMode: 'draw' | 'move' | 'resize' | 'pan' | null = null
let dragAnnotationId: number | null = null
let dragOffset = { x: 0, y: 0 }
let panStart = { x: 0, y: 0 }
let panOrigin = { x: 0, y: 0 }
let pointerCaptureTarget: HTMLElement | null = null

const currentModel = computed(() => models.value.find((model) => model.is_active) ?? null)
const frozenVersion = computed(() => versions.value.find((version) => version.status === 'frozen') ?? null)
const selectedIndex = computed(() => selectedAsset.value ? assets.value.findIndex((asset) => asset.id === selectedAsset.value?.id) : -1)
const totalAssetCount = computed(() => Object.values(assetCounts.value).reduce((total, count) => total + (Number.isFinite(count) ? count : 0), 0))
const stageStyle = computed(() => ({
  aspectRatio: `${imageDimensions.value.width} / ${imageDimensions.value.height}`,
  transform: `translate(${pan.value.x}px, ${pan.value.y}px) scale(${zoom.value})`,
}))
const selectedAnnotation = computed(() => selectedAsset.value?.annotations.find((item) => item.id === selectedAnnotationId.value) ?? null)
const visibleAnnotations = computed(() => selectedAsset.value?.annotations ?? [])
const latestRun = computed(() => runs.value[0] ?? null)
const metricSource = computed(() => latestRun.value?.metrics ?? currentModel.value?.metrics ?? {})
const lossCurve = computed(() => {
  const curve = metricSource.value.loss_curve
  return Array.isArray(curve) ? curve : []
})

function metricValue(key: string) {
  const value = metricSource.value[key]
  return typeof value === 'number' ? value.toFixed(3) : '—'
}

function notify(text: string) {
  message.value = text
  window.setTimeout(() => { if (message.value === text) message.value = '' }, 2600)
}

function queryString(offset = 0) {
  const params = new URLSearchParams({ status: tab.value, offset: String(offset), limit: '24' })
  if (sourceFilter.value) params.set('source', sourceFilter.value)
  if (search.value.trim()) params.set('search', search.value.trim())
  return params.toString()
}

async function loadCounts() {
  const values = await Promise.all((Object.keys(statusLabels) as AssetTab[]).map(async (status) => {
    const payload = await getJson<{ count: number }>(`/dataset-assets/?status=${status}&limit=1`)
    return [status, Number.isFinite(payload.count) ? payload.count : 0] as const
  }))
  assetCounts.value = Object.fromEntries(values) as Record<AssetTab, number>
}

async function loadAssets(reset = true) {
  if (reset) {
    loading.value = true
    assets.value = []
    nextOffset.value = 0
    selectedAsset.value = null
  } else {
    loadingMore.value = true
  }
  try {
    const offset = nextOffset.value ?? 0
    const payload = await getJson<{ results: DatasetAsset[]; next_offset: number | null }>(`/dataset-assets/?${queryString(offset)}`)
    assets.value = reset ? payload.results : [...assets.value, ...payload.results]
    nextOffset.value = payload.next_offset
    if (!selectedAsset.value && assets.value.length) selectAsset(assets.value[0])
  } catch (error) {
    notify(error instanceof Error ? error.message : '样本队列加载失败')
  } finally {
    loading.value = false
    loadingMore.value = false
  }
}

async function loadAll() {
  try {
    await Promise.all([
      loadAssets(), loadCounts(),
      getJson<{ results: DatasetVersion[] }>('/dataset-versions/').then((payload) => { versions.value = payload.results }),
      getJson<{ results: ModelVersion[] }>('/model-versions/').then((payload) => { models.value = payload.results }),
      getJson<{ results: TrainingRun[] }>('/training-runs/').then((payload) => { runs.value = payload.results }),
    ])
  } catch (error) {
    notify(error instanceof Error ? error.message : '训练接口暂时无法连接')
  }
}

async function loadMore() {
  if (nextOffset.value !== null && !loadingMore.value) await loadAssets(false)
}

function onQueueScroll(event: Event) {
  const element = event.target as HTMLElement
  if (element.scrollTop + element.clientHeight >= element.scrollHeight - 80) loadMore()
}

async function selectAsset(asset: DatasetAsset) {
  if (dirty.value) await flushChanges()
  selectedAsset.value = asset
  selectedAnnotationId.value = null
  pendingBox.value = null
  zoom.value = 1
  pan.value = { x: 0, y: 0 }
}

function onImageLoad(event: Event) {
  const image = event.target as HTMLImageElement
  imageDimensions.value = { width: image.naturalWidth || 16, height: image.naturalHeight || 9 }
}

function pointFromEvent(event: PointerEvent) {
  const rect = annotationStage.value?.getBoundingClientRect()
  if (!rect) return { x: 0, y: 0 }
  return {
    x: Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width)),
    y: Math.max(0, Math.min(1, (event.clientY - rect.top) / rect.height)),
  }
}

function annotationAt(point: { x: number; y: number }) {
  return [...visibleAnnotations.value].reverse().find((annotation) => point.x >= annotation.bbox.x && point.x <= annotation.bbox.x + annotation.bbox.width && point.y >= annotation.bbox.y && point.y <= annotation.bbox.y + annotation.bbox.height)
}

function beginStagePointer(event: PointerEvent) {
  if (pendingBox.value) return
  capturePointer(event)
  const point = pointFromEvent(event)
  const hit = annotationAt(point)
  if (hit) {
    selectedAnnotationId.value = hit.id
    beginAnnotationDrag(event, hit)
    return
  }
  if (event.shiftKey || zoom.value > 1) {
    dragMode = 'pan'
    panStart = { x: event.clientX, y: event.clientY }
    panOrigin = { ...pan.value }
    return
  }
  dragMode = 'draw'
  drawStart = point
}

function beginAnnotationDrag(event: PointerEvent, annotation: DatasetAnnotation) {
  capturePointer(event)
  const point = pointFromEvent(event)
  const nearResizeHandle = point.x > annotation.bbox.x + annotation.bbox.width - 0.035 && point.y > annotation.bbox.y + annotation.bbox.height - 0.035
  dragMode = nearResizeHandle ? 'resize' : 'move'
  dragAnnotationId = annotation.id
  dragOffset = { x: point.x - annotation.bbox.x, y: point.y - annotation.bbox.y }
}

function movePointer(event: PointerEvent) {
  if (!dragMode) return
  if (dragMode === 'pan') {
    pan.value = { x: panOrigin.x + event.clientX - panStart.x, y: panOrigin.y + event.clientY - panStart.y }
    return
  }
  const point = pointFromEvent(event)
  if (dragMode === 'draw' && drawStart) {
    pendingBox.value = { x: Math.min(drawStart.x, point.x), y: Math.min(drawStart.y, point.y), width: Math.abs(point.x - drawStart.x), height: Math.abs(point.y - drawStart.y) }
    return
  }
  const annotation = selectedAsset.value?.annotations.find((item) => item.id === dragAnnotationId)
  if (!annotation) return
  if (dragMode === 'move') {
    annotation.bbox.x = Math.max(0, Math.min(1 - annotation.bbox.width, point.x - dragOffset.x))
    annotation.bbox.y = Math.max(0, Math.min(1 - annotation.bbox.height, point.y - dragOffset.y))
  } else {
    annotation.bbox.width = Math.max(0.01, Math.min(1 - annotation.bbox.x, point.x - annotation.bbox.x))
    annotation.bbox.height = Math.max(0.01, Math.min(1 - annotation.bbox.y, point.y - annotation.bbox.y))
  }
  dirty.value = true
}

function capturePointer(event: PointerEvent) {
  const target = event.currentTarget
  if (!(target instanceof HTMLElement)) return
  try {
    target.setPointerCapture(event.pointerId)
    pointerCaptureTarget = target
  } catch {
    // Pointer capture is not available in a few embedded WebView implementations.
  }
}

function releasePointer(event?: PointerEvent) {
  if (pointerCaptureTarget && event) {
    try {
      if (pointerCaptureTarget.hasPointerCapture(event.pointerId)) pointerCaptureTarget.releasePointerCapture(event.pointerId)
    } catch {
      // The pointer may already have been released by the browser.
    }
  }
  pointerCaptureTarget = null
}

async function endPointer(event?: PointerEvent) {
  if (dragMode === 'draw' && pendingBox.value && pendingBox.value.width > 0.015 && pendingBox.value.height > 0.015) {
    activeClass.value = 'repair'
  } else if (dragMode && dragMode !== 'draw' && dirty.value) {
    await flushChanges()
  }
  releasePointer(event)
  drawStart = null
  dragMode = null
  dragAnnotationId = null
}

async function chooseClass(className: ClassName) {
  activeClass.value = className
  if (pendingBox.value && selectedAsset.value) {
    busy.value = true
    try {
      await requestJson(`/dataset-assets/${selectedAsset.value.id}/annotations/`, {
        method: 'POST', body: JSON.stringify({ class_name: className, bbox: pendingBox.value, source: 'manual' }),
      })
      await refreshAsset(selectedAsset.value.id)
      pendingBox.value = null
      notify(`已保存${classLabels[className]}标注`)
    } catch (error) { notify(error instanceof ApiError ? error.message : '标注保存失败') }
    finally { busy.value = false }
  } else if (selectedAnnotation.value) {
    await updateAnnotation(selectedAnnotation.value, className)
  }
}

async function updateAnnotation(annotation: DatasetAnnotation, className = annotation.class_name) {
  if (!selectedAsset.value) return
  try {
    const updated = await requestJson<DatasetAnnotation>(`/annotations/${annotation.id}/`, {
      method: 'PATCH', body: JSON.stringify({ class_name: className, bbox: annotation.bbox }),
    })
    const index = selectedAsset.value.annotations.findIndex((item) => item.id === updated.id)
    if (index >= 0) selectedAsset.value.annotations[index] = updated
    selectedAnnotationId.value = updated.id
    dirty.value = false
  } catch (error) { notify(error instanceof ApiError ? error.message : '标注修改失败') }
}

async function deleteSelectedAnnotation() {
  if (!selectedAnnotation.value) return
  try {
    await requestJson(`/annotations/${selectedAnnotation.value.id}/`, { method: 'DELETE' })
    if (selectedAsset.value) await refreshAsset(selectedAsset.value.id)
    selectedAnnotationId.value = null
    notify('检测框已删除')
  } catch (error) { notify(error instanceof ApiError ? error.message : '检测框删除失败') }
}

async function flushChanges() {
  if (selectedAnnotation.value && dirty.value) await updateAnnotation(selectedAnnotation.value)
}

async function refreshAsset(id: number) {
  const asset = await getJson<DatasetAsset>(`/dataset-assets/${id}/`)
  const index = assets.value.findIndex((item) => item.id === id)
  if (index >= 0) assets.value[index] = asset
  selectedAsset.value = asset
  dirty.value = false
  await loadCounts()
}

async function markInvalid() {
  if (!selectedAsset.value) return
  try {
    const asset = await requestJson<DatasetAsset>(`/dataset-assets/${selectedAsset.value.id}/reject/`, { method: 'POST' })
    assets.value = assets.value.filter((item) => item.id !== asset.id)
    selectedAsset.value = null
    selectedAnnotationId.value = null
    await loadCounts()
    notify('已记录为非光伏图片 / 无效样本')
  } catch (error) { notify(error instanceof ApiError ? error.message : '无效样本保存失败') }
}

async function navigate(step: number) {
  await flushChanges()
  let index = selectedIndex.value + step
  if (index < 0) index = 0
  if (index >= assets.value.length && nextOffset.value !== null) {
    await loadMore()
    index = Math.min(selectedIndex.value + step, assets.value.length - 1)
  }
  if (assets.value[index]) await selectAsset(assets.value[index])
}

async function uploadSamples(event: Event) {
  const files = Array.from((event.target as HTMLInputElement).files ?? [])
  if (!files.length) return
  busy.value = true
  try {
    const results = await Promise.allSettled(files.map(async (file) => {
      const body = new FormData()
      body.append('file', file)
      body.append('source_type', 'uploaded')
      return requestJson('/dataset-assets/', { method: 'POST', body })
    }))
    const uploadedCount = results.filter((result) => result.status === 'fulfilled').length
    const failedCount = results.length - uploadedCount
    await loadAssets()
    await loadCounts()
    if (failedCount) notify(`${uploadedCount} 个素材已上传，${failedCount} 个文件上传失败或已存在`)
    else notify(`${uploadedCount} 个素材已进入待标注队列`)
  } catch (error) { notify(error instanceof ApiError ? error.message : '样本上传失败') }
  finally { busy.value = false; if (fileInput.value) fileInput.value.value = '' }
}

async function applyFilters() { await loadAssets() }

async function createDatasetVersion() {
  busy.value = true
  try {
    const version = await requestJson<DatasetVersion>('/dataset-versions/', { method: 'POST', body: JSON.stringify({ name: datasetName.value, version: datasetVersion.value }) })
    versions.value.unshift(version)
    notify(`已创建数据集 ${version.version}，默认纳入全部已标注样本`)
  } catch (error) { notify(error instanceof ApiError ? error.message : '数据集版本创建失败') }
  finally { busy.value = false }
}

async function freezeVersion(version: DatasetVersion) {
  try {
    const frozen = await requestJson<DatasetVersion>(`/dataset-versions/${version.id}/freeze/`, { method: 'POST' })
    versions.value = versions.value.map((item) => item.id === frozen.id ? frozen : item)
    notify('数据集已按 7:2:1 冻结')
  } catch (error) { notify(error instanceof ApiError ? error.message : '数据集冻结失败') }
}

async function startTraining() {
  if (!frozenVersion.value) { notify('请先创建并冻结一个数据集版本'); return }
  busy.value = true
  try {
    const run = await requestJson<TrainingRun>('/training-runs/', { method: 'POST', body: JSON.stringify({ dataset_version_id: frozenVersion.value.id, ...trainingConfig.value }) })
    runs.value.unshift(run)
    showTrainingConfig.value = false
    notify('离线演示训练已完成；正式模型请在 YOLO Worker 中训练')
  } catch (error) { notify(error instanceof ApiError ? error.message : '训练任务创建失败') }
  finally { busy.value = false }
}

async function switchModel(model: ModelVersion) {
  if (!window.confirm(`确认切换到模型 ${model.version}？`)) return
  try {
    const endpoint = model.status === 'retired' ? 'rollback' : 'activate'
    const activated = await requestJson<ModelVersion>(`/model-versions/${model.id}/${endpoint}/`, { method: 'POST' })
    models.value = models.value.map((item) => item.id === activated.id ? activated : { ...item, is_active: false, status: 'retired' })
    notify(`当前模型已切换为 ${activated.version}`)
  } catch (error) { notify(error instanceof ApiError ? error.message : '模型切换失败') }
}

async function toggleFullscreen() {
  try {
    if (!document.fullscreenElement) await workspace.value?.requestFullscreen?.()
    else await document.exitFullscreen()
  } catch { fullscreen.value = !fullscreen.value }
}

function onFullscreenChange() { fullscreen.value = Boolean(document.fullscreenElement) }
function onWheel(event: WheelEvent) {
  event.preventDefault()
  zoom.value = Math.max(0.6, Math.min(3, zoom.value + (event.deltaY > 0 ? -0.1 : 0.1)))
}
function resetViewport() { zoom.value = 1; pan.value = { x: 0, y: 0 } }
function onKeydown(event: KeyboardEvent) {
  if ((event.target as HTMLElement)?.tagName === 'INPUT') return
  if (event.key === 'Delete' || event.key === 'Backspace') { event.preventDefault(); deleteSelectedAnnotation() }
  if (event.key === 'Escape' && pendingBox.value) { pendingBox.value = null; drawStart = null; dragMode = null; releasePointer(); return }
  if (event.key === 'Escape' && document.fullscreenElement) document.exitFullscreen()
}

onMounted(() => {
  window.addEventListener('keydown', onKeydown)
  document.addEventListener('fullscreenchange', onFullscreenChange)
  loadAll()
})
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeydown)
  document.removeEventListener('fullscreenchange', onFullscreenChange)
})
</script>

<template>
  <section ref="workspace" class="model-lab" :class="{ 'is-fullscreen': fullscreen }" tabindex="0">
    <header class="lab-heading">
      <div><span class="eyebrow">DATASET / ANNOTATION WORKBENCH</span><h2>模型训练</h2><p>处理识别失败和困难样本，完成标注后创建数据集并启动 YOLO 训练。</p></div>
      <div class="lab-heading-actions"><span class="current-model">当前模型：<b>{{ currentModel?.version ?? 'mock-v1' }}</b></span><label class="submit-button upload-button">上传图片 / 视频<input ref="fileInput" type="file" multiple accept="image/jpeg,image/png,image/webp,video/mp4,video/quicktime" @change="uploadSamples" /></label></div>
    </header>
    <div v-if="message" class="console-message">{{ message }}</div>

    <div class="annotation-layout">
      <aside class="sample-rail panel">
        <div class="rail-head"><div><span class="eyebrow">SAMPLE POOL</span><h3>样本池</h3></div><b>{{ totalAssetCount }} ASSETS</b></div>
        <div class="sample-tabs"><button v-for="(label, key) in statusLabels" :key="key" :class="{ active: tab === key }" @click="tab = key; applyFilters()">{{ label }} <b>{{ assetCounts[key] }}</b></button></div>
        <div class="sample-filters"><input v-model="search" placeholder="搜索文件名" @keyup.enter="applyFilters" /><select v-model="sourceFilter" @change="applyFilters"><option value="">全部来源</option><option value="inference_failed">识别失败</option><option value="manual_unrecognized">人工标记无法识别</option><option value="uploaded">直接上传</option></select></div>
        <div class="asset-scroll" @scroll="onQueueScroll">
          <button v-for="asset in assets" :key="asset.id" class="asset-card" :class="{ active: selectedAsset?.id === asset.id }" @click="selectAsset(asset)">
            <span class="asset-thumb"><img v-if="asset.media_type.startsWith('image')" :src="asset.url" :alt="asset.original_name" /><i v-else>VIDEO</i></span>
            <span class="asset-meta"><strong>{{ asset.original_name }}</strong><small>{{ new Date(asset.created_at).toLocaleString('zh-CN', { hour12: false }) }}</small><small>{{ sourceLabels[asset.source_type] ?? asset.source_type }} · {{ asset.annotations.length ? `${asset.annotations.length} 个框` : '待处理' }}</small></span>
            <span class="asset-confidence">{{ asset.source_type === 'inference_failed' ? '—' : '低置信' }}</span>
          </button>
          <p v-if="loading" class="empty-state">正在加载样本…</p><p v-else-if="!assets.length" class="empty-state">当前分组暂无样本</p><p v-if="loadingMore" class="empty-state">正在加载更多…</p>
        </div>
      </aside>

      <section class="annotation-workspace panel">
        <div class="workspace-head"><div><span class="eyebrow">IMAGE ANNOTATION</span><h3>{{ selectedAsset?.original_name ?? '请选择待标注图片' }}</h3></div><div class="workspace-tools"><span v-if="selectedAsset">{{ selectedAsset.annotations.length }} 个检测框</span><button @click="resetViewport">重置视图</button><button @click="toggleFullscreen">全屏标注</button></div></div>
        <div ref="annotationViewport" class="annotation-viewport" @wheel="onWheel" @pointermove="movePointer" @pointerup="endPointer" @pointercancel="endPointer">
          <div v-if="selectedAsset" ref="annotationStage" class="annotation-stage" :style="stageStyle" @pointerdown="beginStagePointer">
            <img :src="selectedAsset.url" :alt="selectedAsset.original_name" @load="onImageLoad" />
            <div v-for="annotation in selectedAsset.annotations" :key="annotation.id" class="annotation-box" :class="{ selected: selectedAnnotationId === annotation.id }" :style="{ ...{ left: `${annotation.bbox.x * 100}%`, top: `${annotation.bbox.y * 100}%`, width: `${annotation.bbox.width * 100}%`, height: `${annotation.bbox.height * 100}%` }, '--box-color': classColors[annotation.class_name] }" @pointerdown.stop="beginAnnotationDrag($event, annotation)" @click.stop="selectedAnnotationId = annotation.id">
              <b>{{ classLabels[annotation.class_name] }}</b><i v-if="selectedAnnotationId === annotation.id" class="resize-handle"></i>
            </div>
            <div v-if="pendingBox" class="annotation-box draft" :style="{ left: `${pendingBox.x * 100}%`, top: `${pendingBox.y * 100}%`, width: `${pendingBox.width * 100}%`, height: `${pendingBox.height * 100}%` }"></div>
            <div v-if="pendingBox" class="class-popover"><span>标注类别</span><button v-for="(label, key) in classLabels" :key="key" :style="{ '--class-color': classColors[key] }" @pointerdown.stop @click.stop="chooseClass(key)"><i></i>{{ label }}</button></div>
          </div>
          <div v-else class="canvas-empty"><span>选择左侧样本开始标注</span><small>支持预标注框、多框绘制和全屏查看</small></div>
        </div>
        <div class="workspace-help"><span>滚轮缩放</span><span>拖拽平移</span><span>拖动边角调整大小</span><span>Delete 删除选中框</span></div>
      </section>

      <aside class="label-panel panel">
        <div class="label-head"><div><span class="eyebrow">CLASSIFICATION</span><h3>分类标注</h3></div><span>{{ selectedAnnotation ? `框 ${selectedAnnotation.id}` : '新建检测框' }}</span></div>
        <div class="class-actions"><button v-for="(label, key) in classLabels" :key="key" :class="{ selected: activeClass === key || selectedAnnotation?.class_name === key }" :style="{ '--class-color': classColors[key] }" @click="chooseClass(key)"><i></i><span>{{ label }}</span><small>{{ key.toUpperCase() }}</small></button></div>
        <div class="box-list-head"><strong>当前图片检测框</strong><span>{{ visibleAnnotations.length }}</span></div>
        <div class="box-list"><button v-for="(annotation, index) in visibleAnnotations" :key="annotation.id" :class="{ active: selectedAnnotationId === annotation.id }" @click="selectedAnnotationId = annotation.id"><b :style="{ color: classColors[annotation.class_name] }">{{ String(index + 1).padStart(2, '0') }}</b><span><strong>{{ classLabels[annotation.class_name] }}</strong><small>{{ annotation.source === 'auto' ? '预标注' : annotation.source === 'corrected' ? '人工修正' : '人工标注' }}</small></span><em>{{ Math.round((annotation.bbox.width * annotation.bbox.height) * 100) }}%</em></button><p v-if="!visibleAnnotations.length" class="empty-state">在中间图片上拖拽绘制检测框</p></div>
        <button class="invalid-button" :disabled="!selectedAsset || tab === 'rejected'" @click="markInvalid">标记为非光伏图片 / 无效样本</button>
      </aside>
    </div>

    <section class="lifecycle-grid">
      <article class="lifecycle-panel panel"><div class="lifecycle-title"><div><span class="eyebrow">DATASET VERSION</span><h3>数据集版本</h3></div><span>7 : 2 : 1 自动划分</span></div><div class="dataset-form"><input v-model="datasetName" placeholder="数据集名称" /><input v-model="datasetVersion" placeholder="版本号" /><button class="submit-button" :disabled="busy" @click="createDatasetVersion">创建版本</button></div><div class="dataset-summary"><span><b>{{ assetCounts.annotated }}</b> 已标注样本</span><span><b>70%</b> 训练</span><span><b>20%</b> 验证</span><span><b>10%</b> 测试</span></div><div v-for="version in versions.slice(0, 3)" :key="version.id" class="history-row"><span><strong>{{ version.version }}</strong><small>{{ version.name }} · {{ version.train_count }}/{{ version.validation_count }}/{{ version.test_count }}</small></span><em>{{ version.status === 'frozen' ? '已冻结' : '草稿' }}</em><button v-if="version.status === 'draft'" @click="freezeVersion(version)">冻结版本</button></div></article>
      <article class="lifecycle-panel panel"><div class="lifecycle-title"><div><span class="eyebrow">MODEL LIFECYCLE</span><h3>模型版本与训练</h3></div><span>AUTO SWITCH</span></div><div class="model-current"><span>当前模型</span><strong>{{ currentModel?.version ?? 'mock-v1' }}</strong><em>ACTIVE</em></div><div class="metric-grid"><div><span>Precision</span><b>{{ metricValue('precision') }}</b></div><div><span>Recall</span><b>{{ metricValue('recall') }}</b></div><div><span>mAP50</span><b>{{ metricValue('map50') }}</b></div><div><span>mAP50-95</span><b>{{ metricValue('map50_95') }}</b></div></div><div class="loss-panel"><div><span>训练损失曲线</span><small v-if="!lossCurve.length">训练完成后生成</small></div><div v-if="lossCurve.length" class="loss-bars"><i v-for="(point, index) in lossCurve" :key="index" :style="{ height: `${Math.max(8, Math.min(100, 100 - Number(point) * 100))}%` }"></i></div><div v-else class="loss-placeholder"><i v-for="index in 12" :key="index" :style="{ height: `${20 + (index % 4) * 8}%` }"></i></div></div><div class="model-history"><div v-for="model in models.slice(0, 4)" :key="model.id" class="history-row"><span><strong>{{ model.version }}</strong><small>{{ model.model_type.toUpperCase() }} · {{ new Date(model.created_at).toLocaleDateString('zh-CN') }}</small></span><em :class="{ active: model.is_active }">{{ model.is_active ? '当前使用' : model.status === 'retired' ? '历史模型' : '候选' }}</em><button v-if="!model.is_active && (model.status === 'candidate' || model.status === 'retired')" @click="switchModel(model)">{{ model.status === 'retired' ? '回滚' : '切换' }}</button></div></div><div class="run-summary"><strong>训练任务</strong><span v-if="runs.length">{{ runs[0].status }} · {{ runs[0].progress }}%</span><span v-else>尚未创建训练任务</span><button class="submit-button" :disabled="!frozenVersion" @click="showTrainingConfig = true">启动 YOLO 训练</button></div></article>
    </section>

    <footer class="lab-actionbar"><div><span>当前样本</span><strong>{{ selectedIndex >= 0 ? `${selectedIndex + 1} / ${assets.length}` : '—' }}</strong><small v-if="selectedAsset">{{ selectedAsset.annotations.length ? '已保存标注' : '尚未标注' }}</small></div><div class="navigation-actions"><button :disabled="selectedIndex <= 0" @click="navigate(-1)">← 上一张</button><button :disabled="selectedIndex < 0" @click="navigate(1)">下一张 →</button></div><div class="primary-actions"><button class="secondary-action" :disabled="!frozenVersion" @click="showTrainingConfig = true">创建数据集后训练</button><button class="primary-action" :disabled="!frozenVersion" @click="startTraining">启动训练</button></div></footer>

    <div v-if="showTrainingConfig" class="training-modal-backdrop"><section class="training-modal"><div class="modal-head"><div><span class="eyebrow">YOLO11 / CLOUD TRAINING</span><h3>启动训练任务</h3></div><button @click="showTrainingConfig = false">×</button></div><p>数据集：{{ frozenVersion?.version }} · 训练云端：24GB GPU</p><label>基础模型<select><option>YOLO11n · 预训练模型</option></select></label><label>训练轮数 <strong>{{ trainingConfig.epochs }} 轮</strong><input v-model.number="trainingConfig.epochs" type="range" min="20" max="100" step="10" /></label><div class="modal-pair"><label>图片尺寸<select v-model.number="trainingConfig.image_size"><option :value="1024">1024</option><option :value="1280">1280</option><option :value="768">768</option></select></label><label>批次大小<select v-model.number="trainingConfig.batch_size"><option :value="16">16</option><option :value="8">8</option><option :value="32">32</option></select></label></div><label>运行设备<select v-model="trainingConfig.device"><option value="cuda">CUDA · 24GB GPU</option><option value="auto">自动选择</option></select></label><div class="slice-note"><i></i><span><strong>高分辨率自动切片</strong><small>系统将自动去除相似帧并切片训练，无需手动设置区域。</small></span></div><div class="modal-actions"><button class="secondary-action" @click="showTrainingConfig = false">取消</button><button class="primary-action" :disabled="busy" @click="startTraining">创建训练任务</button></div></section></div>
  </section>
</template>

<style scoped>
.model-lab { --lab-bg: #06130e; --lab-panel: #091a13; --lab-panel-deep: #07150f; --lab-line: #1b3c2c; --lab-muted: #729184; --lab-text: #dceae2; --lab-green: #39e58c; --lab-amber: #f3bd4b; --lab-red: #ff625b; max-width: 100%; padding: 30px 30px 110px; color: var(--lab-text); background: radial-gradient(circle at 82% 8%, #0d3524 0, transparent 30%), var(--lab-bg); }
.model-lab:focus { outline: none; }.lab-heading { display: flex; align-items: flex-end; justify-content: space-between; gap: 22px; padding-bottom: 22px; border-bottom: 1px solid var(--lab-line); }.lab-heading h2 { margin: 8px 0 5px; font-size: 30px; letter-spacing: -.04em; }.lab-heading p { margin: 0; color: var(--lab-muted); font-size: 12px; }.lab-heading-actions { display: flex; align-items: center; gap: 18px; }.current-model { color: var(--lab-muted); font: 10px ui-monospace, monospace; }.current-model b { color: var(--lab-green); }.upload-button { position: relative; min-width: 145px; cursor: pointer; text-align: center; }.upload-button input { position: absolute; inset: 0; opacity: 0; cursor: pointer; }.console-message { margin: 12px 0; padding: 10px 12px; color: var(--lab-green); border: 1px solid var(--lab-line); background: #0b2117; font-size: 11px; }
.annotation-layout { display: grid; grid-template-columns: 282px minmax(420px, 1fr) 274px; gap: 14px; margin-top: 16px; min-height: 560px; }.panel { border: 1px solid var(--lab-line); background: rgba(7, 21, 15, .92); }.sample-rail, .label-panel, .annotation-workspace { min-height: 0; }.sample-rail { display: flex; flex-direction: column; }.rail-head, .workspace-head, .label-head, .lifecycle-title { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; padding: 16px 16px 13px; border-bottom: 1px solid var(--lab-line); }.rail-head h3, .workspace-head h3, .label-head h3, .lifecycle-title h3 { margin: 5px 0 0; font-size: 16px; }.rail-head > b, .label-head > span, .lifecycle-title > span { color: #6c8b7c; font: 9px ui-monospace, monospace; }.sample-tabs { display: grid; grid-template-columns: repeat(3, 1fr); padding: 9px 10px 0; gap: 5px; }.sample-tabs button { padding: 8px 4px; color: var(--lab-muted); background: transparent; border: 1px solid transparent; font-size: 10px; cursor: pointer; }.sample-tabs button b { display: block; margin-top: 4px; color: #9db8a9; font: 10px ui-monospace, monospace; }.sample-tabs button.active { color: var(--lab-green); border-color: var(--lab-line); background: #0b2318; }.sample-tabs button.active b { color: var(--lab-green); }.sample-filters { display: grid; gap: 6px; padding: 10px; border-bottom: 1px solid var(--lab-line); }.sample-filters input, .sample-filters select, .dataset-form input, .training-modal select { min-height: 31px; padding: 0 8px; color: var(--lab-text); background: var(--lab-panel-deep); border: 1px solid #245039; border-radius: 3px; font-size: 10px; }.asset-scroll { flex: 1; min-height: 360px; max-height: 560px; overflow: auto; padding: 7px; }.asset-card { width: 100%; display: grid; grid-template-columns: 43px minmax(0, 1fr) auto; align-items: center; gap: 8px; padding: 8px 6px; color: var(--lab-text); background: transparent; border: 1px solid transparent; text-align: left; cursor: pointer; }.asset-card:hover, .asset-card.active { background: #0d2a1d; border-color: #2a6344; }.asset-thumb { width: 43px; height: 36px; display: grid; place-items: center; overflow: hidden; background: #10271c; color: var(--lab-green); font: 8px ui-monospace, monospace; }.asset-thumb img { width: 100%; height: 100%; object-fit: cover; }.asset-meta { min-width: 0; display: grid; gap: 3px; }.asset-meta strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 10px; }.asset-meta small { color: var(--lab-muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 8px; }.asset-confidence { color: var(--lab-amber); font: 8px ui-monospace, monospace; }.empty-state { padding: 20px 8px; color: #668274; font-size: 10px; text-align: center; }
.annotation-workspace { display: flex; flex-direction: column; overflow: hidden; }.workspace-head { align-items: center; }.workspace-tools { display: flex; align-items: center; gap: 7px; }.workspace-tools span { color: var(--lab-green); font: 9px ui-monospace, monospace; }.workspace-tools button, .history-row button { min-height: 28px; padding: 0 9px; color: #a7c0b2; background: transparent; border: 1px solid #234c38; font-size: 9px; cursor: pointer; }.workspace-tools button:hover, .history-row button:hover { color: var(--lab-green); border-color: var(--lab-green); }.annotation-viewport { position: relative; flex: 1; min-height: 400px; display: grid; place-items: center; overflow: hidden; background: #030a07; background-image: linear-gradient(#0c2118 1px, transparent 1px), linear-gradient(90deg, #0c2118 1px, transparent 1px); background-size: 28px 28px; cursor: crosshair; }.annotation-stage { position: relative; width: min(94%, 900px); transform-origin: center; transition: transform .12s ease; user-select: none; }.annotation-stage > img { display: block; width: 100%; height: 100%; object-fit: fill; pointer-events: none; }.annotation-box { position: absolute; min-width: 5px; min-height: 5px; border: 2px solid var(--box-color); box-shadow: 0 0 0 1px rgba(0,0,0,.6); cursor: move; }.annotation-box b { position: absolute; top: -18px; left: -2px; padding: 2px 5px; color: #06130e; background: var(--box-color); font-size: 8px; white-space: nowrap; }.annotation-box.selected { z-index: 3; filter: brightness(1.2); }.resize-handle { position: absolute; right: -5px; bottom: -5px; width: 9px; height: 9px; border: 2px solid var(--box-color); background: #06130e; cursor: nwse-resize; }.annotation-box.draft { border: 2px dashed var(--lab-green); pointer-events: none; }.class-popover { position: absolute; left: 50%; top: 10px; z-index: 8; display: grid; min-width: 150px; padding: 8px; background: #0c2418; border: 1px solid #3a7352; box-shadow: 0 14px 30px rgba(0,0,0,.35); transform: translateX(-50%); }.class-popover > span { margin: 0 0 6px; color: #8eaa9a; font-size: 9px; }.class-popover button { display: flex; align-items: center; gap: 7px; padding: 7px 6px; color: var(--lab-text); background: transparent; border: 0; text-align: left; font-size: 10px; cursor: pointer; }.class-popover button:hover { background: #133421; }.class-popover button i, .class-actions button i { width: 8px; height: 8px; border-radius: 50%; background: var(--class-color); }.canvas-empty { display: grid; gap: 8px; color: #819b8d; font-size: 12px; text-align: center; }.canvas-empty small { color: #526e60; font: 9px ui-monospace, monospace; }.workspace-help { display: flex; gap: 18px; padding: 9px 14px; color: #6b8979; border-top: 1px solid var(--lab-line); font: 9px ui-monospace, monospace; }
.label-panel { display: flex; flex-direction: column; }.class-actions { display: grid; gap: 7px; padding: 14px; border-bottom: 1px solid var(--lab-line); }.class-actions button { display: grid; grid-template-columns: 10px 1fr auto; align-items: center; gap: 8px; min-height: 42px; padding: 0 10px; color: #9bb5a6; background: #091b12; border: 1px solid #1d412f; text-align: left; cursor: pointer; }.class-actions button.selected { color: var(--lab-text); border-color: var(--class-color); background: color-mix(in srgb, var(--class-color) 12%, #091b12); }.class-actions button small { color: var(--class-color); font: 8px ui-monospace, monospace; }.box-list-head { display: flex; justify-content: space-between; padding: 14px 14px 8px; color: #b4cabe; font-size: 10px; }.box-list-head span { color: var(--lab-green); font: 10px ui-monospace, monospace; }.box-list { flex: 1; overflow: auto; padding: 0 8px; }.box-list button { width: 100%; display: grid; grid-template-columns: 27px 1fr auto; align-items: center; gap: 6px; padding: 9px 6px; color: #aac0b2; background: transparent; border: 1px solid transparent; text-align: left; cursor: pointer; }.box-list button:hover, .box-list button.active { background: #0d2a1d; border-color: #244f38; }.box-list button > b { font: 10px ui-monospace, monospace; }.box-list button span { display: grid; gap: 3px; }.box-list button span strong { font-size: 10px; }.box-list button span small { color: #668375; font-size: 8px; }.box-list button em { color: #708d7c; font: 8px ui-monospace, monospace; font-style: normal; }.invalid-button { margin: 12px; min-height: 36px; color: var(--lab-red); background: transparent; border: 1px solid #9a3d39; font-size: 10px; cursor: pointer; }.invalid-button:disabled { opacity: .4; cursor: not-allowed; }
.lifecycle-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-top: 14px; }.lifecycle-panel { min-height: 230px; }.dataset-form { display: grid; grid-template-columns: 1fr 1fr auto; gap: 6px; padding: 13px 14px 8px; }.dataset-form .submit-button { min-height: 31px; padding: 0 12px; font-size: 10px; }.dataset-summary { display: flex; gap: 14px; padding: 8px 14px 12px; color: var(--lab-muted); font-size: 9px; }.dataset-summary b { color: var(--lab-green); font: 11px ui-monospace, monospace; }.history-row { display: flex; align-items: center; gap: 10px; margin: 5px 14px; padding: 9px 10px; background: #091a12; border: 1px solid #1a3c2c; }.history-row > span { min-width: 0; display: grid; gap: 3px; }.history-row strong { font-size: 10px; }.history-row small { color: var(--lab-muted); font-size: 8px; }.history-row em { margin-left: auto; color: var(--lab-amber); font: 8px ui-monospace, monospace; font-style: normal; }.history-row em.active { color: var(--lab-green); }.history-row button { white-space: nowrap; }.model-current { display: grid; grid-template-columns: auto 1fr auto; align-items: center; gap: 10px; margin: 13px 14px 8px; padding: 11px; background: #0c2a1d; border: 1px solid #286143; }.model-current span { color: var(--lab-muted); font-size: 9px; }.model-current strong { color: var(--lab-green); font: 12px ui-monospace, monospace; }.model-current em { color: var(--lab-green); font: 8px ui-monospace, monospace; font-style: normal; }.model-history { max-height: 136px; overflow: auto; }.run-summary { display: flex; align-items: center; gap: 10px; margin: 14px; padding-top: 12px; border-top: 1px solid var(--lab-line); }.run-summary strong { font-size: 10px; }.run-summary span { color: var(--lab-muted); font-size: 9px; }.run-summary .submit-button { margin-left: auto; min-height: 30px; padding: 0 10px; font-size: 9px; }
.metric-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 5px; margin: 0 14px 8px; }.metric-grid div { padding: 7px 6px; background: #091a12; border: 1px solid #183b2b; }.metric-grid span { display: block; color: var(--lab-muted); font: 8px ui-monospace, monospace; }.metric-grid b { display: block; margin-top: 4px; color: var(--lab-green); font: 11px ui-monospace, monospace; }.loss-panel { margin: 0 14px 8px; padding: 8px; border: 1px solid #183b2b; background: #07150f; }.loss-panel > div:first-child { display: flex; justify-content: space-between; color: #9ab4a5; font-size: 9px; }.loss-panel small { color: #638172; font: 8px ui-monospace, monospace; }.loss-bars, .loss-placeholder { height: 32px; display: flex; align-items: flex-end; gap: 3px; margin-top: 6px; }.loss-bars i, .loss-placeholder i { flex: 1; min-height: 3px; background: var(--lab-green); opacity: .82; }.loss-placeholder i { background: #295d43; opacity: .45; }
.lab-actionbar { position: sticky; bottom: 0; z-index: 20; display: grid; grid-template-columns: 1fr auto 1fr; align-items: center; gap: 16px; margin: 14px -30px -110px; padding: 12px 30px; background: rgba(5, 17, 12, .96); border-top: 1px solid #2a5d42; box-shadow: 0 -12px 30px rgba(0,0,0,.25); }.lab-actionbar > div:first-child { display: flex; align-items: baseline; gap: 9px; }.lab-actionbar span, .lab-actionbar small { color: var(--lab-muted); font-size: 9px; }.lab-actionbar strong { color: var(--lab-green); font: 12px ui-monospace, monospace; }.lab-actionbar small { color: #7f9d8d; }.navigation-actions, .primary-actions { display: flex; gap: 7px; }.navigation-actions button, .secondary-action, .primary-action { min-height: 36px; padding: 0 14px; color: #a8c0b1; background: transparent; border: 1px solid #2b6043; font-size: 10px; cursor: pointer; }.navigation-actions button:hover, .secondary-action:hover { color: var(--lab-green); border-color: var(--lab-green); }.primary-actions { justify-content: flex-end; }.primary-action { color: #06130e; background: var(--lab-green); border-color: var(--lab-green); }.secondary-action:disabled, .primary-action:disabled, .navigation-actions button:disabled { opacity: .35; cursor: not-allowed; }.training-modal-backdrop { position: fixed; inset: 0; z-index: 50; display: grid; place-items: center; padding: 20px; background: rgba(0,0,0,.65); }.training-modal { width: min(480px, 100%); padding: 22px; background: #0a1e14; border: 1px solid #367653; box-shadow: 0 24px 80px rgba(0,0,0,.45); }.modal-head { display: flex; justify-content: space-between; }.modal-head h3 { margin: 7px 0 18px; font-size: 20px; }.modal-head button { color: #8aa998; background: transparent; border: 0; font-size: 24px; cursor: pointer; }.training-modal > p { margin: 0 0 18px; color: var(--lab-muted); font: 10px ui-monospace, monospace; }.training-modal label { display: grid; gap: 7px; margin: 13px 0; color: #a6beae; font-size: 10px; }.training-modal label strong { color: var(--lab-green); font: 10px ui-monospace, monospace; }.training-modal input[type=range] { accent-color: var(--lab-green); }.modal-pair { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }.slice-note { display: flex; gap: 9px; margin: 18px 0; padding: 11px; color: #b7cfbd; background: #0d291b; border: 1px solid #27583d; }.slice-note > i { width: 7px; height: 7px; margin-top: 3px; border-radius: 50%; background: var(--lab-green); box-shadow: 0 0 12px var(--lab-green); }.slice-note span { display: grid; gap: 5px; }.slice-note small { color: var(--lab-muted); font-size: 9px; }.modal-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 18px; }
.model-lab.is-fullscreen { position: fixed; inset: 0; z-index: 100; overflow: auto; padding: 22px 30px 100px; background: var(--lab-bg); }.model-lab:fullscreen { overflow: auto; background: var(--lab-bg); }.model-lab:fullscreen .annotation-layout { min-height: calc(100vh - 180px); }.model-lab:fullscreen .annotation-viewport { min-height: 620px; }
@media (max-width: 1280px) { .model-lab { padding-left: 20px; padding-right: 20px; }.annotation-layout { grid-template-columns: 250px minmax(360px, 1fr) 240px; }.lab-actionbar { margin-left: -20px; margin-right: -20px; padding-left: 20px; padding-right: 20px; } }
</style>
