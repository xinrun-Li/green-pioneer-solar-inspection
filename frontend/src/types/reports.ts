export interface Report {
  id: number
  report_type: 'web' | 'excel' | 'pdf'
  report_type_label: string
  status: 'generating' | 'ready' | 'failed'
  status_label: string
  parameters: Record<string, any>
  filters: Record<string, any>
  snapshot_data: Record<string, any>
  file: string | null
  error_message: string
  progress: number
  created_by: string
  inspection_task_id: number | null
  inspection_task_title: string
  created_at: string
  updated_at: string
}

export interface ReportCreateRequest {
  report_type: 'web' | 'excel' | 'pdf'
  inspection_task_id: number
  parameters?: Record<string, any>
  filters?: Record<string, any>
}

export const REPORT_TYPE_LABELS: Record<string, string> = {
  web: '网页报告',
  excel: 'Excel 报告',
  pdf: 'PDF 报告',
}

export const REPORT_STATUS_LABELS: Record<string, string> = {
  generating: '生成中',
  ready: '已完成',
  failed: '生成失败',
}

export const REPORT_STATUS_COLORS: Record<string, string> = {
  generating: '#3B82F6',
  ready: '#16A34A',
  failed: '#EF4444',
}
