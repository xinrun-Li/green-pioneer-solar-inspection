export interface AgentConversation {
  id: number
  message: string
  response: string
  intent: string
  intent_display: string
  slots: Record<string, unknown>
  draft_action: Record<string, unknown> | null
  status: 'pending' | 'drafted' | 'confirmed' | 'rejected' | 'failed'
  status_display: string
  confidence: number
  source: 'local' | 'cloud'
  source_display: string
  error_message: string
  created_at: string
  updated_at: string
}

export interface MessageRequest {
  message: string
}

export interface ConfirmActionRequest {
  conversation_id: number
  action: 'confirm' | 'reject' | 'retry'
}

export interface AssistantStatus {
  provider: 'DeepSeek'
  model: string
  configured: boolean
}

export const INTENT_LABELS: Record<string, string> = {
  check_status: '查询状态',
  check_stats: '查看统计',
  create_report: '生成报告',
  start_inspection: '开始巡检',
  retry_job: '重试识别',
  check_events: '查看异常',
  check_panel: '查询组件',
  help: '帮助',
  feedback: '反馈',
  query_anomaly: '查询异常',
  query_task: '查询任务',
  query_stats: '查询统计',
  create_task: '创建任务',
  start_task: '开始任务',
  pause_task: '暂停任务',
  navigate: '跳转页面',
  generate_report: '生成报告',
  export_data: '导出数据',
  chat: '智能对话',
  unknown: '未知意图',
}

export const INTENT_COLORS: Record<string, string> = {
  check_status: '#3B82F6',
  check_stats: '#8B5CF6',
  create_report: '#16A34A',
  start_inspection: '#F59E0B',
  retry_job: '#EF4444',
  check_events: '#EC4899',
  check_panel: '#06B6D4',
  help: '#64748B',
  feedback: '#F97316',
  query_anomaly: '#EC4899',
  query_task: '#3B82F6',
  query_stats: '#8B5CF6',
  create_task: '#F59E0B',
  start_task: '#16A34A',
  pause_task: '#F97316',
  navigate: '#06B6D4',
  generate_report: '#16A34A',
  export_data: '#64748B',
  chat: '#168B58',
  unknown: '#64748B',
}
