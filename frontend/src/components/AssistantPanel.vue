<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { Check, ChevronDown, ChevronLeft, ChevronRight, Loader2, Send, Sparkles, X } from 'lucide-vue-next'
import { assistantApi } from '@/api/assistant'
import { ApiError } from '@/api/http'
import { INTENT_COLORS, INTENT_LABELS } from '@/types/assistant'
import type { AgentConversation, AssistantStatus } from '@/types/assistant'

const props = defineProps<{ width?: number }>()
const messages = ref<AgentConversation[]>([])
const inputText = ref('')
const loading = ref(false)
const collapsed = ref(false)
const messagesRef = ref<HTMLElement | null>(null)
const errorText = ref('')
const assistantStatus = ref<AssistantStatus | null>(null)
const welcomePrompts = ['查看最近的识别结果', '查询北区有哪些异常组件', '创建一次北区巡检任务', '生成今日巡检摘要']
const showWelcome = computed(() => messages.value.length === 0 && !loading.value)
const serviceText = computed(() => {
  if (!assistantStatus.value) return '正在检查服务'
  return assistantStatus.value.configured ? `${assistantStatus.value.model} 已配置` : 'DeepSeek API 待配置'
})

function intentLabel(msg: AgentConversation): string { return msg.intent_display || INTENT_LABELS[msg.intent] || INTENT_LABELS.unknown || msg.intent }
function intentColor(msg: AgentConversation): string { return INTENT_COLORS[msg.intent] || INTENT_COLORS.unknown }
function sourceText(msg: AgentConversation): string { return msg.source === 'cloud' ? 'DeepSeek' : '本地数据' }
type DraftAction = { action_type?: string; target?: string; payload?: Record<string, unknown> }
type DraftFact = { label: string; value: string }

function draftAction(msg: AgentConversation): DraftAction {
  return (msg.draft_action ?? {}) as DraftAction
}

function isConfirmableDraft(msg: AgentConversation): boolean {
  return msg.status === 'drafted' && ['create', 'update', 'export'].includes(draftAction(msg).action_type ?? '')
}

function payloadText(msg: AgentConversation, key: string): string {
  const value = draftAction(msg).payload?.[key]
  return typeof value === 'string' || typeof value === 'number' ? String(value) : ''
}

function draftActionLabel(msg: AgentConversation): string {
  const action = draftAction(msg)
  if (action.action_type === 'create') return '创建'
  if (action.action_type === 'update') return payloadText(msg, 'action') === 'pause' ? '暂停任务' : '启动任务'
  if (action.action_type === 'export') return action.target === '巡检报告' ? '生成报告' : '导出数据'
  return '需要确认'
}

function draftTitle(msg: AgentConversation): string {
  const action = draftAction(msg)
  if (action.action_type === 'create') return '创建巡检任务'
  if (action.action_type === 'update') return payloadText(msg, 'action') === 'pause' ? '暂停巡检任务' : '启动巡检任务'
  if (action.action_type === 'export') return action.target === '巡检报告' ? '生成巡检分析报告' : '导出巡检数据'
  return '确认下一步操作'
}

function draftSummary(msg: AgentConversation): string {
  const action = draftAction(msg)
  if (action.action_type === 'create') {
    const station = payloadText(msg, 'station_name') || '当前电站'
    const scope = [payloadText(msg, 'region'), payloadText(msg, 'array_code')].filter(Boolean).join(' · ')
    return `将在「${station}」${scope ? `的${scope}` : '全站'}创建一项巡检任务。`
  }
  if (action.action_type === 'update') {
    const title = payloadText(msg, 'title') || action.target || '这项巡检任务'
    const verb = payloadText(msg, 'action') === 'pause' ? '暂停' : '启动'
    return `确认后将${verb}「${title}」。`
  }
  if (action.target === '巡检报告') {
    const task = payloadText(msg, 'task_title')
    return `确认后将生成${task ? `「${task}」的` : ''}巡检分析报告。`
  }
  return `确认后将导出「${action.target || '巡检数据'}」。`
}

function statusLabel(status: string): string {
  return ({ draft: '草稿', confirmed: '已确认', running: '执行中', paused: '已暂停', completed: '已完成', review: '待复核' } as Record<string, string>)[status] ?? status
}

function draftFacts(msg: AgentConversation): DraftFact[] {
  const action = draftAction(msg)
  const facts: DraftFact[] = []
  if (action.action_type === 'create') {
    const title = payloadText(msg, 'title')
    const station = payloadText(msg, 'station_name')
    const scope = [payloadText(msg, 'region'), payloadText(msg, 'array_code')].filter(Boolean).join(' · ')
    if (title) facts.push({ label: '任务名称', value: title })
    if (station) facts.push({ label: '目标电站', value: station })
    if (scope) facts.push({ label: '巡检范围', value: scope })
  } else if (action.action_type === 'update') {
    const currentStatus = payloadText(msg, 'current_status')
    if (currentStatus) facts.push({ label: '当前状态', value: statusLabel(currentStatus) })
  } else if (action.action_type === 'export') {
    const format = payloadText(msg, 'format')
    const period = payloadText(msg, 'period')
    if (format) facts.push({ label: '文件格式', value: format })
    if (period) facts.push({ label: '时间范围', value: period })
  }
  return facts
}
function formatTime(value: string): string {
  const d = new Date(value)
  return Number.isNaN(d.getTime()) ? '' : `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}
async function scrollToBottom() { await nextTick(); if (messagesRef.value) messagesRef.value.scrollTop = messagesRef.value.scrollHeight }
async function upsertMessage(msg: AgentConversation) {
  const index = messages.value.findIndex((item) => item.id === msg.id)
  if (index >= 0) messages.value[index] = msg
  else messages.value.push(msg)
  await scrollToBottom()
}
async function sendMessage() {
  const text = inputText.value.trim()
  if (!text || loading.value) return
  inputText.value = ''
  errorText.value = ''
  loading.value = true
  try {
    await upsertMessage(await assistantApi.sendMessage({ message: text }))
  } catch (error) {
    inputText.value = text
    errorText.value = error instanceof ApiError ? error.message : '发送失败，请检查网络或后端服务。'
  }
  finally { loading.value = false }
}
function sendWelcomePrompt(prompt: string) { inputText.value = prompt; sendMessage() }
async function confirmDraft(msg: AgentConversation) {
  if (!msg.draft_action) return
  loading.value = true
  try { await upsertMessage(await assistantApi.confirmAction({ conversation_id: msg.id, action: 'confirm' })) }
  finally { loading.value = false }
}
async function rejectDraft(msg: AgentConversation) {
  if (!msg.draft_action) return
  loading.value = true
  try { await upsertMessage(await assistantApi.rejectAction({ conversation_id: msg.id, action: 'reject' })) }
  finally { loading.value = false }
}
onMounted(async () => {
  try { messages.value = await assistantApi.getHistory() } catch { messages.value = [] }
  try { assistantStatus.value = await assistantApi.getStatus() } catch { assistantStatus.value = null }
  await scrollToBottom()
})
</script>

<template>
  <div v-if="!collapsed" class="assistant-panel" :style="props.width ? { width: `${props.width}px` } : undefined">
    <div class="panel-header">
      <div class="assistant-identity">
        <span class="assistant-mark"><Sparkles :size="15" /></span>
        <div><span class="title">绿能助手</span><small :class="{ missing: assistantStatus && !assistantStatus.configured }"><i></i> {{ serviceText }}</small></div>
      </div>
      <button class="collapse-btn" type="button" aria-label="收起智能助手" @click="collapsed = true"><ChevronRight :size="18" /></button>
    </div>

    <div ref="messagesRef" class="messages-list">
      <div v-if="showWelcome" class="welcome-state">
        <div class="welcome-mark"><Sparkles :size="22" /></div>
        <p class="welcome-eyebrow">DEEPSEEK AI ASSISTANT</p>
        <h2>你好，我是绿能助手</h2>
        <p class="welcome-copy">我可以帮你查询巡检数据、分析组件异常，或生成需要人工确认的巡检任务。</p>
        <div class="welcome-prompts">
          <button v-for="prompt in welcomePrompts" :key="prompt" type="button" @click="sendWelcomePrompt(prompt)">{{ prompt }}<ChevronRight :size="14" /></button>
        </div>
      </div>

      <template v-for="msg in messages" :key="msg.id">
        <div class="message-item from-user">
          <div class="message-content"><div class="message-bubble"><p class="message-text">{{ msg.message }}</p><div class="message-meta"><span>{{ formatTime(msg.created_at) }}</span></div></div></div>
        </div>
        <div class="message-item from-assistant" :class="{ 'has-error': msg.status === 'failed' }">
          <span class="message-avatar"><Sparkles :size="12" /></span>
          <div class="message-content">
            <div class="message-bubble">
              <p class="message-text">{{ msg.response }}</p>
              <div class="message-meta"><span v-if="msg.intent" class="intent-tag" :style="{ background: intentColor(msg), color: '#fff' }">{{ intentLabel(msg) }}</span><span>{{ sourceText(msg) }}</span><span>{{ formatTime(msg.created_at) }}</span></div>
            </div>
            <div v-if="isConfirmableDraft(msg)" class="draft-card">
              <div class="draft-head"><span>需要你确认</span><small>{{ draftActionLabel(msg) }}</small></div>
              <strong class="draft-title">{{ draftTitle(msg) }}</strong>
              <p class="draft-summary">{{ draftSummary(msg) }}</p>
              <dl v-if="draftFacts(msg).length" class="draft-facts">
                <div v-for="fact in draftFacts(msg)" :key="fact.label"><dt>{{ fact.label }}</dt><dd>{{ fact.value }}</dd></div>
              </dl>
              <details class="draft-details">
                <summary><span>查看操作详情</span><ChevronDown :size="13" /></summary>
                <pre class="draft-body">{{ JSON.stringify(msg.draft_action, null, 2) }}</pre>
              </details>
              <div class="draft-actions"><button class="confirm-btn" type="button" :disabled="loading" @click="confirmDraft(msg)"><Check :size="14" />确认执行</button><button class="reject-btn" type="button" :disabled="loading" @click="rejectDraft(msg)"><X :size="14" />暂不执行</button></div>
            </div>
          </div>
        </div>
      </template>

      <div v-if="loading" class="loading-spinner"><span class="message-avatar"><Sparkles :size="12" /></span><Loader2 class="spin" :size="17" /><span>正在思考…</span></div>
    </div>

    <div class="input-area">
      <p v-if="errorText" class="input-error">{{ errorText }}</p>
      <textarea v-model="inputText" class="assistant-input" rows="1" placeholder="向绿能助手提问…" :disabled="loading" @keydown.enter.exact.prevent="sendMessage"></textarea>
      <div class="input-footer"><span>Enter 发送 · Shift + Enter 换行</span><button class="send-btn" type="button" aria-label="发送消息" :disabled="loading || !inputText.trim()" @click="sendMessage"><Send :size="16" /></button></div>
    </div>
  </div>

  <button v-else class="expand-button" type="button" aria-label="展开智能助手" @click="collapsed = false"><ChevronLeft :size="18" /><span>助手</span></button>
</template>

<style scoped>
.assistant-panel { width: 360px; height: calc(100vh - 104px); min-height: 0; display: flex; flex-direction: column; flex-shrink: 0; min-width: 0; color: #dcebe4; background: #07150f; border: 1px solid #1e3b2f; border-radius: 4px; overflow: hidden; }
.panel-header { min-height: 58px; display: flex; align-items: center; justify-content: space-between; padding: 0 14px; background: #0b2118; border-bottom: 1px solid #204033; }
.assistant-identity { display: flex; align-items: center; gap: 9px; }.assistant-identity > div { display: grid; gap: 3px; }.assistant-mark, .welcome-mark, .message-avatar { display: grid; place-items: center; color: #06170f; background: #45dc8d; border-radius: 50%; }.assistant-mark { width: 28px; height: 28px; }.title { font-size: 13px; font-weight: 650; }.assistant-identity small { color: #668074; font-size: 9px; }.assistant-identity small i { display: inline-block; width: 5px; height: 5px; margin-right: 4px; border-radius: 50%; background: #45dc8d; }
.collapse-btn { display: grid; place-items: center; width: 28px; height: 28px; color: #789084; background: transparent; border: 0; border-radius: 4px; cursor: pointer; }.collapse-btn:hover { color: #eaf7f0; background: #163326; }
.messages-list { flex: 1 1 auto; height: 0; min-height: 0; overflow-y: scroll; overflow-x: hidden; padding: 18px 14px; display: flex; flex-direction: column; gap: 14px; scrollbar-width: thin; scrollbar-color: #2f6449 #07150f; }
.welcome-state { padding: 22px 5px 8px; text-align: center; }.welcome-mark { width: 44px; height: 44px; margin: 0 auto 14px; box-shadow: 0 0 0 7px #45dc8d12; }.welcome-eyebrow { margin: 0 0 8px; color: #48dd90; font: 8px ui-monospace, monospace; letter-spacing: .14em; }.welcome-state h2 { margin: 0 0 9px; color: #eaf7f0; font-size: 18px; font-weight: 600; }.welcome-copy { margin: 0 auto 20px; max-width: 270px; color: #789084; font-size: 11px; line-height: 1.7; }
.welcome-prompts { display: grid; gap: 7px; text-align: left; }.welcome-prompts button { min-height: 35px; display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 0 10px; color: #a9bdb3; background: #0b1e16; border: 1px solid #1e3b2f; border-radius: 3px; font-size: 10px; cursor: pointer; }.welcome-prompts button:hover { color: #eaf7f0; background: #123024; border-color: #397257; }.welcome-prompts svg { color: #45dc8d; }
.message-item { display: flex; align-items: flex-start; gap: 8px; }.message-item.from-user { justify-content: flex-end; }.message-content { min-width: 0; max-width: calc(100% - 28px); }.message-bubble { padding: 10px 11px; border-radius: 4px; font-size: 11px; line-height: 1.6; }.from-user .message-bubble { color: #06170f; background: #45dc8d; }.from-assistant .message-bubble { color: #dcebe4; background: #10251c; border: 1px solid #1f4333; }.message-text { margin: 0 0 6px; white-space: pre-wrap; word-break: break-word; }.message-meta { display: flex; align-items: center; gap: 6px; color: #688277; font-size: 8px; }.from-user .message-meta { color: #1d6746; }.intent-tag { padding: 1px 5px; border-radius: 2px; font-weight: 600; }
.message-avatar { flex: 0 0 22px; width: 22px; height: 22px; margin-top: 2px; }.draft-card { width: 100%; margin-top: 7px; padding: 11px; background: #0b2118; border: 1px solid #52764f; border-radius: 4px; box-shadow: inset 3px 0 0 #d49a34; }.draft-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; font-size: 10px; font-weight: 600; }.draft-head span { color: #e7b34e; }.draft-head small { color: #789084; font-weight: 400; }.draft-title { display: block; margin-top: 8px; color: #edf8f1; font-size: 12px; line-height: 1.4; }.draft-summary { margin: 5px 0 10px; color: #a9c3b4; font-size: 10px; line-height: 1.55; }.draft-facts { display: grid; gap: 5px; margin: 0 0 10px; padding: 8px 9px; background: #07150f; border: 1px solid #1e3b2f; border-radius: 3px; }.draft-facts div { display: flex; align-items: baseline; justify-content: space-between; gap: 10px; }.draft-facts dt { flex: 0 0 auto; color: #6f8d7e; font-size: 9px; }.draft-facts dd { min-width: 0; margin: 0; color: #d7e9dd; font-size: 9px; text-align: right; overflow-wrap: anywhere; }.draft-details { margin-bottom: 10px; border-top: 1px solid #1e3b2f; }.draft-details summary { display: flex; align-items: center; justify-content: space-between; padding-top: 8px; color: #789084; font-size: 9px; cursor: pointer; list-style: none; }.draft-details summary::-webkit-details-marker { display: none; }.draft-details summary:hover { color: #cde4d5; }.draft-body { margin: 8px 0 0; padding: 8px; max-height: 150px; overflow: auto; color: #9eb4aa; background: #07150f; border: 1px solid #1e3b2f; border-radius: 3px; font-size: 9px; line-height: 1.5; white-space: pre-wrap; word-break: break-word; }.draft-actions { display: flex; gap: 7px; }.draft-actions button { flex: 1; min-height: 34px; display: inline-flex; align-items: center; justify-content: center; gap: 5px; border: 0; border-radius: 3px; font-size: 10px; font-weight: 600; cursor: pointer; }.confirm-btn { color: #06170f; background: #45dc8d; }.confirm-btn:hover:not(:disabled) { background: #63eea5; }.reject-btn { color: #dcebe4; background: #274337; }.reject-btn:hover:not(:disabled) { background: #345947; }.draft-actions button:disabled { opacity: .5; cursor: not-allowed; }
.loading-spinner { display: flex; align-items: center; gap: 7px; color: #789084; font-size: 10px; }.loading-spinner .message-avatar { margin-right: 1px; }.spin { animation: spin .9s linear infinite; } @keyframes spin { to { transform: rotate(360deg); } }
.input-area { padding: 10px; background: #0b2118; border-top: 1px solid #204033; }.assistant-input { width: 100%; min-height: 38px; max-height: 100px; resize: none; padding: 10px 11px; color: #dcebe4; background: #07150f; border: 1px solid #244536; border-radius: 3px; outline: none; font: 11px/1.5 inherit; }.assistant-input:focus { border-color: #45dc8d; }.assistant-input::placeholder { color: #5f786c; }.input-footer { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-top: 7px; color: #5f786c; font-size: 8px; }.send-btn { display: grid; place-items: center; width: 30px; height: 27px; color: #06170f; background: #45dc8d; border: 0; border-radius: 3px; cursor: pointer; }.send-btn:hover:not(:disabled) { background: #63eea5; }.send-btn:disabled { opacity: .4; cursor: not-allowed; }
.expand-button { display: flex; flex-direction: column; align-items: center; gap: 4px; width: 44px; height: 100%; flex-shrink: 0; padding-top: 18px; color: #7c8ba0; background: #07150f; border: 1px solid #1e3b2f; border-radius: 4px; cursor: pointer; }.expand-button:hover { color: #eaf7f0; background: #123024; }.expand-button span { writing-mode: vertical-rl; font-size: 11px; letter-spacing: .1em; }
.assistant-identity small.missing { color: #b88b38; }
.assistant-identity small.missing i { background: #d49a34; }
.message-item.has-error .message-bubble { color: #e9c98d; border-color: #735724; background: #261e0c; }
.input-error { margin: 0 0 7px; color: #e7b34e; font-size: 9px; line-height: 1.5; }
</style>
