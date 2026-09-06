<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { ApiError, getJson, requestJson } from '@/api/http'
import AssistantPanel from '@/components/AssistantPanel.vue'
import type { DetectionClass, DetectionResult, RecognitionJob, UploadBatch, UploadedMedia } from '@/types/recognition'

const files = ref<File[]>([])
const note = ref('北区 A2 阵列，组件位置以本批次人工确认备注为准')
const batches = ref<UploadBatch[]>([])
const jobs = ref<RecognitionJob[]>([])
const selectedJob = ref<RecognitionJob | null>(null)
const classFilter = ref<DetectionClass | null>(null)
const working = ref(false)
const message = ref('')
const fileInput = ref<HTMLInputElement | null>(null)
const assistantWidth = ref(360)
const isResizingAssistant = ref(false)
const resizeStartX = ref(0)
const resizeStartWidth = ref(360)

const ASSISTANT_MIN_WIDTH = 280
const ASSISTANT_MAX_WIDTH = 560

const labels: Record<DetectionClass, string> = { normal: '正常', cleaning: '需要清洗', repair: '需要维修' }
const modelClassLabels: Record<string, string> = {
  Clean: '正常组件', Dust: '积尘', Bird: '鸟粪 / 鸟类遮挡', Electrical: '电气故障', Physical: '物理损伤', Snow: '积雪',
}
const pendingCount = computed(() => selectedJob.value?.detections.filter((item) => item.review_status === 'pending').length ?? 0)
const selectedBatch = computed(() => batches.value.find((batch) => batch.media.some((media) => media.id === selectedJob.value?.media.id)) ?? null)
const selectedBatchJobs = computed(() => {
  if (!selectedBatch.value) return selectedJob.value ? [selectedJob.value] : []
  const mediaIds = new Set(selectedBatch.value.media.map((media) => media.id))
  const related = jobs.value.filter((job) => mediaIds.has(job.media.id))
  return related.length ? related : selectedJob.value ? [selectedJob.value] : []
})
const previewMedia = computed(() => {
  const media = selectedBatch.value?.media.filter((item) => item.kind === 'image') ?? []
  if (!classFilter.value) return media
  const matchingMediaIds = new Set(selectedBatchJobs.value.filter((job) => job.detections.some((item) => item.effective_class === classFilter.value)).map((job) => job.media.id))
  return media.filter((item) => matchingMediaIds.has(item.id))
})
const counts = computed(() => {
  const result = { normal: 0, cleaning: 0, repair: 0 }
  selectedBatchJobs.value.forEach((job) => job.detections.forEach((item) => result[item.effective_class]++))
  return result
})

function jobStatusLabel(status: RecognitionJob['status']) {
  const labels: Record<RecognitionJob['status'], string> = {
    created: '准备检测', queued: '检测中', running: '检测中', review: '待人工复核', completed: '检测完成', failed: '检测失败',
  }
  return labels[status] ?? status
}

function detectionLabel(item: DetectionResult) {
  const detail = modelClassLabels[item.model_class_label || item.model_class] ?? labels[item.effective_class]
  return `${detail} · ${labels[item.effective_class]} ${Math.round(item.confidence * 100)}%`
}

function chooseFiles(event: Event) {
  appendFiles(Array.from((event.target as HTMLInputElement).files ?? []))
  ;(event.target as HTMLInputElement).value = ''
  message.value = ''
}

function appendFiles(incoming: File[]) {
  const merged = [...files.value]
  const known = new Set(merged.map((file) => `${file.name}:${file.size}:${file.lastModified}`))
  for (const file of incoming) {
    const key = `${file.name}:${file.size}:${file.lastModified}`
    if (!known.has(key)) {
      merged.push(file)
      known.add(key)
    }
  }
  files.value = merged
}

function startAssistantResize(event: PointerEvent) {
  isResizingAssistant.value = true
  resizeStartX.value = event.clientX
  resizeStartWidth.value = assistantWidth.value
  document.body.classList.add('resizing-columns')
  window.addEventListener('pointermove', resizeAssistant)
  window.addEventListener('pointerup', stopAssistantResize, { once: true })
}

function resizeAssistant(event: PointerEvent) {
  if (!isResizingAssistant.value) return
  const nextWidth = resizeStartWidth.value + (resizeStartX.value - event.clientX)
  assistantWidth.value = Math.min(ASSISTANT_MAX_WIDTH, Math.max(ASSISTANT_MIN_WIDTH, nextWidth))
  window.localStorage.setItem('green-pioneer-assistant-width', String(assistantWidth.value))
}

function stopAssistantResize() {
  isResizingAssistant.value = false
  document.body.classList.remove('resizing-columns')
  window.removeEventListener('pointermove', resizeAssistant)
}

function onDrop(event: DragEvent) {
  appendFiles(Array.from(event.dataTransfer?.files ?? []))
  message.value = ''
}

async function loadBatches(selectLatest = false) {
  const response = await getJson<{ results: UploadBatch[] }>('/upload-batches/')
  batches.value = response.results
  if (selectLatest && !selectedJob.value) {
    const jobId = response.results.flatMap((batch) => batch.media).find((media) => media.job_id)?.job_id
    if (jobId) await selectJob(jobId)
  }
}

async function selectJob(jobId: number) {
  const selected = await getJson<RecognitionJob>(`/recognition-jobs/${jobId}`)
  const currentBatchId = selectedBatch.value?.id
  const nextBatchId = batches.value.find((batch) => batch.media.some((media) => media.id === selected.media.id))?.id
  if (currentBatchId && nextBatchId && currentBatchId !== nextBatchId) classFilter.value = null
  selectedJob.value = selected
  upsertJob(selected)
  await loadSelectedBatchJobs(selected.media.id)
}

async function filterByClass(className: DetectionClass) {
  if (!counts.value[className]) return
  if (classFilter.value === className) {
    classFilter.value = null
    return
  }
  classFilter.value = className
  const firstMatch = selectedBatchJobs.value.find((job) => job.detections.some((item) => item.effective_class === className))
  if (firstMatch) await selectJob(firstMatch.id)
}

function upsertJob(job: RecognitionJob) {
  const index = jobs.value.findIndex((item) => item.id === job.id)
  if (index >= 0) jobs.value[index] = job
  else jobs.value.push(job)
}

async function loadSelectedBatchJobs(mediaId: number) {
  const batch = batches.value.find((item) => item.media.some((media) => media.id === mediaId))
  if (!batch) return
  const knownJobIds = new Set(jobs.value.map((job) => job.id))
  const missingJobIds = batch.media.map((media) => media.job_id).filter((id): id is number => id !== null && !knownJobIds.has(id))
  const loaded = await Promise.allSettled(missingJobIds.map((id) => getJson<RecognitionJob>(`/recognition-jobs/${id}`)))
  loaded.forEach((result) => { if (result.status === 'fulfilled') upsertJob(result.value) })
}

async function selectPreviewMedia(media: UploadedMedia) {
  if (media.job_id) {
    try {
      await selectJob(media.job_id)
    } catch (error) {
      message.value = error instanceof ApiError ? error.message : '识别结果加载失败'
    }
    return
  }
  selectedJob.value = {
    id: -media.id,
    status: 'completed',
    progress: 100,
    adapter: 'preview',
    model_version: null,
    model_version_id: null,
    is_demo_data: false,
    processed_frames: 0,
    total_frames: 1,
    retry_count: 0,
    error_message: '',
    media: { id: media.id, kind: media.kind, original_name: media.original_name, url: media.url, status: media.status },
    detections: [],
    created_at: '',
    completed_at: null,
  }
}

async function createAndRunJob(media: UploadedMedia) {
  const created = await requestJson<RecognitionJob>('/recognition-jobs/', {
    method: 'POST', body: JSON.stringify({ media_id: media.id }),
  })
  upsertJob(created)
  let completed = await requestJson<RecognitionJob>(`/recognition-jobs/${created.id}/run/`, { method: 'POST' })
  for (let attempt = 0; attempt < 120 && ['queued', 'running'].includes(completed.status); attempt += 1) {
    await new Promise((resolve) => window.setTimeout(resolve, 1500))
    completed = await getJson<RecognitionJob>(`/recognition-jobs/${created.id}`)
  }
  upsertJob(completed)
  if (!selectedJob.value) selectedJob.value = completed
}

async function submitBatch() {
  if (!files.value.length) {
    message.value = '请先选择至少一个图片或视频文件'
    return
  }
  working.value = true
  message.value = ''
  selectedJob.value = null
  jobs.value = []
  try {
    const batch = await requestJson<UploadBatch>('/upload-batches/', {
      method: 'POST', body: JSON.stringify({ region_note: note.value }),
    })
    const body = new FormData()
    files.value.forEach((file) => body.append('files', file))
    const uploaded = await requestJson<{ media: UploadedMedia[] }>(`/upload-batches/${batch.id}/media`, {
      method: 'POST', body,
    })
    let completedCount = 0
    let failedCount = 0
    for (const media of uploaded.media) {
      try {
        await createAndRunJob(media)
        completedCount += 1
      } catch {
        failedCount += 1
      }
    }
    files.value = []
    if (fileInput.value) fileInput.value.value = ''
    message.value = failedCount
      ? `批次 #${batch.id} 已完成 ${completedCount} 个文件，${failedCount} 个检测失败`
      : `批次 #${batch.id} 的 ${completedCount} 个文件检测完成`
    await loadBatches()
  } catch (error) {
    message.value = error instanceof ApiError ? error.message : '上传或模型检测失败'
  } finally {
    working.value = false
  }
}

async function review(item: DetectionResult, confirmedClass: DetectionClass) {
  if (!selectedJob.value) return
  await requestJson(`/detections/${item.id}/review`, {
    method: 'POST', body: JSON.stringify({ confirmed_class: confirmedClass, note: '控制台人工复核' }),
  })
  await selectJob(selectedJob.value.id)
  await loadBatches()
}

onMounted(() => {
  const savedWidth = Number(window.localStorage.getItem('green-pioneer-assistant-width'))
  if (Number.isFinite(savedWidth)) assistantWidth.value = Math.min(ASSISTANT_MAX_WIDTH, Math.max(ASSISTANT_MIN_WIDTH, savedWidth))
  loadBatches(true)
})

onBeforeUnmount(() => {
  stopAssistantResize()
})
</script>

<template>
  <section class="recognition-page feature-layout">
    <div class="recognition-body">
      <div class="recognition-main">
      <article v-if="!selectedJob" class="upload-console">
        <button class="drop-zone" type="button" @click="fileInput?.click()" @dragover.prevent @drop.prevent="onDrop">
          <span class="drop-code">MEDIA INPUT</span><strong>{{ files.length ? `已选择 ${files.length} 个文件` : '拖放或选择巡检图片与视频' }}</strong>
          <small>JPG / PNG / WEBP · MP4 / MOV · 每批最多一个视频</small>
        </button>
        <input ref="fileInput" class="hidden-input" type="file" multiple accept="image/jpeg,image/png,image/webp,video/mp4,video/quicktime" @change="chooseFiles" />
        <div v-if="files.length" class="selected-files">
          <span v-for="file in files" :key="`${file.name}-${file.size}`"><b>{{ file.type.startsWith('video') ? 'VIDEO' : 'IMAGE' }}</b>{{ file.name }}<small>{{ (file.size / 1024 / 1024).toFixed(2) }} MB</small></span>
        </div>
        <label class="note-field"><span>区域与组件备注</span><textarea v-model="note" rows="3"></textarea><small>位置来自任务、备注或人工确认，不通过普通画面猜测。</small></label>
        <p v-if="message" class="console-message">{{ message }}</p>
        <button class="run-button" :disabled="working" @click="submitBatch">{{ working ? '正在上传并检测…' : '上传并开始检测' }}</button>
      </article>

      <article v-else class="result-console">
        <div class="result-toolbar">
          <div><span>{{ selectedJob.media.kind === 'video' ? '巡检视频' : '巡检图片' }}</span><strong>{{ selectedJob.media.original_name }}</strong><small class="model-version">模型 {{ selectedJob.model_version ?? '待绑定' }}</small></div>
          <div class="toolbar-actions"><span :class="`job-state state-${selectedJob.status}`">{{ selectedJob.status === 'review' ? `待复核 ${pendingCount}` : jobStatusLabel(selectedJob.status) }}</span><button @click="selectedJob = null">上传新批次</button></div>
        </div>
        <div class="result-body">
          <div class="media-stage">
            <img v-if="selectedJob.media.kind === 'image'" :src="selectedJob.media.url" alt="上传的巡检图片" />
            <video v-else :src="selectedJob.media.url" controls></video>
            <div v-for="item in selectedJob.detections" :key="item.id" class="detection-box" :class="[`box-${item.effective_class}`, { pending: item.review_status === 'pending' }]" :style="{ left: `${item.bbox.x * 100}%`, top: `${item.bbox.y * 100}%`, width: `${item.bbox.width * 100}%`, height: `${item.bbox.height * 100}%` }">
              <span>{{ detectionLabel(item) }}</span>
            </div>
          </div>
          <aside class="result-summary">
            <span class="summary-caption">当前批次识别摘要</span><h3>三分类结果</h3>
            <div class="count-grid"><button :class="{ active: classFilter === 'normal' }" :disabled="!counts.normal" @click="filterByClass('normal')"><span>正常</span><b>{{ counts.normal }}</b></button><button :class="{ active: classFilter === 'cleaning' }" :disabled="!counts.cleaning" @click="filterByClass('cleaning')"><span>清洗</span><b>{{ counts.cleaning }}</b></button><button :class="{ active: classFilter === 'repair' }" :disabled="!counts.repair" @click="filterByClass('repair')"><span>维修</span><b>{{ counts.repair }}</b></button></div>
            <div class="result-preview">
              <div class="result-preview-head"><span>本批次图片预览</span><small>{{ previewMedia.length }} 张</small></div>
              <div class="result-preview-scroll">
                <button v-for="media in previewMedia" :key="media.id" class="result-preview-item" :class="{ active: selectedJob.media.id === media.id }" @click.prevent="selectPreviewMedia(media)">
                  <span class="result-preview-image"><img :src="media.url" :alt="media.original_name" /><template v-if="selectedJob.media.id === media.id"><i v-for="item in selectedJob.detections" :key="`preview-${item.id}`" class="preview-detection-box" :style="{ left: `${item.bbox.x * 100}%`, top: `${item.bbox.y * 100}%`, width: `${item.bbox.width * 100}%`, height: `${item.bbox.height * 100}%` }"></i></template></span>
                </button>
                <p v-if="!previewMedia.length" class="result-preview-empty">暂无同批次图片</p>
              </div>
            </div>
            <div class="detection-list">
              <div v-for="item in selectedJob.detections" :key="item.id" class="detection-row">
                <i :class="`status-${item.effective_class}`"></i><div><b>#{{ item.sequence }} {{ modelClassLabels[item.model_class_label || item.model_class] ?? labels[item.effective_class] }}</b><span>{{ labels[item.effective_class] }} · {{ Math.round(item.confidence * 100) }}% · {{ item.reason || '未发现补充异常' }}</span></div>
                <div v-if="item.review_status === 'pending'" class="review-actions"><button v-for="(label, key) in labels" :key="key" @click="review(item, key)">{{ label }}</button></div><em v-else>已确认</em>
              </div>
            </div>
          </aside>
        </div>
      </article>

    </div>

    <aside class="recent-batches">
      <div class="recent-heading"><span>RECENT BATCHES</span><h3>最近批次</h3></div>
      <p v-if="!batches.length">暂无上传记录</p>
      <article v-for="batch in batches" :key="batch.id">
        <header><b>#{{ batch.id }}</b><span>{{ new Date(batch.created_at).toLocaleString('zh-CN') }}</span></header>
        <p>{{ batch.region_note || '未填写区域备注' }}</p>
        <button v-for="media in batch.media" :key="media.id" :disabled="!media.job_id" @click="media.job_id && selectJob(media.job_id)"><span>{{ media.kind === 'video' ? 'VIDEO' : 'IMAGE' }}</span><b>{{ media.original_name }}</b><em>{{ media.status }}</em></button>
      </article>
    </aside>
    </div>

    <div
      class="assistant-resizer"
      :class="{ active: isResizingAssistant }"
      role="separator"
      aria-label="调整智能助手宽度"
      aria-orientation="vertical"
      tabindex="0"
      @pointerdown.prevent="startAssistantResize"
    >
      <span></span>
    </div>
    <AssistantPanel :width="assistantWidth" />
  </section>
</template>

<style scoped>
.feature-layout {
  display: flex;
  align-items: stretch;
  gap: 14px;
  padding: 14px;
  overflow: hidden;
}
.assistant-resizer {
  position: relative;
  z-index: 2;
  width: 8px;
  flex: 0 0 8px;
  margin: 0 -7px;
  cursor: col-resize;
  touch-action: none;
}
.assistant-resizer::before {
  content: '';
  position: absolute;
  top: 0;
  bottom: 0;
  left: 3px;
  width: 2px;
  background: #1b362a;
  transition: background 0.15s ease, box-shadow 0.15s ease;
}
.assistant-resizer span {
  position: absolute;
  top: 50%;
  left: 1px;
  width: 6px;
  height: 42px;
  transform: translateY(-50%);
  border-radius: 4px;
  background: #2f6449;
  opacity: 0;
  transition: opacity 0.15s ease;
}
.assistant-resizer:hover::before,
.assistant-resizer.active::before {
  background: #45d98b;
  box-shadow: 0 0 10px #45d98b66;
}
.assistant-resizer:hover span,
.assistant-resizer.active span {
  opacity: 1;
}
.recognition-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}
.recognition-body .recognition-main {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.result-preview {
  flex: 0 0 auto;
  min-height: 0;
  display: flex;
  flex-direction: column;
  margin: 14px 0;
  padding-top: 12px;
  border-top: 1px solid #1b3c2c;
}
.result-preview-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
  color: #b7cfc0;
  font-size: 10px;
}
.result-preview-head small {
  color: #6f9180;
  font: 9px ui-monospace, monospace;
}
.result-preview-scroll {
  flex: 0 1 auto;
  min-height: 0;
  height: auto;
  max-height: min(420px, calc(100vh - 470px));
  overflow-y: auto;
  scrollbar-gutter: stable;
  display: grid;
  grid-template-columns: 1fr;
  align-content: start;
  grid-auto-rows: max-content;
  gap: 6px;
  padding-right: 3px;
}
.result-preview-item {
  display: block;
  min-width: 0;
  align-self: start;
  width: 100%;
  padding: 4px;
  color: #abc4b4;
  background: #081a12;
  border: 1px solid #1b3c2c;
  text-align: left;
  cursor: pointer;
}
.result-preview-item:hover,
.result-preview-item.active {
  color: #dceae2;
  border-color: #39e58c;
  background: #0d2a1d;
}
.result-preview-item img {
  width: 100%;
  height: auto;
  max-height: 180px;
  display: block;
  object-fit: cover;
  background: #030a07;
}
.result-preview-item span {
  display: block;
}
.result-preview-image {
  position: relative;
  display: block !important;
  overflow: hidden;
  line-height: 0;
}
.preview-detection-box {
  position: absolute;
  display: block !important;
  border: 2px solid #39e58c;
  pointer-events: none;
}
.result-preview-empty {
  margin: 0;
  padding: 18px 0;
  color: #6f9180;
  font-size: 9px;
  text-align: center;
}
.result-body {
  align-items: stretch;
  flex: 1 1 auto;
  min-height: 0;
  overflow: hidden;
}
.result-summary {
  height: 100%;
  min-height: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.result-console {
  height: calc(100vh - 144px);
  min-height: 540px;
  display: flex;
  flex-direction: column;
}
.media-stage {
  min-height: 0;
}
.media-stage img,
.media-stage video {
  min-height: 0;
}
</style>
