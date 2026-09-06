export interface HistoryStats {
  total_records: number
  task_records: number
  manual_records: number
  review_records: number
  classification_counts: {
    normal: number
    needs_cleaning: number
    needs_repair: number
  }
  abnormal_events: {
    open: number
    closed: number
  }
}

export interface HistoryRecord {
  id: number
  source: 'task' | 'manual' | 'review'
  source_label: string
  status: string
  status_label: string
  summary: string
  details: Record<string, unknown>
  task_id: number | null
  task_title: string
  panel_id: number | null
  panel_full_code: string
  region_name: string
  array_code: string
  operator_name: string
  recorded_at: string
}

export interface HistoryResponse {
  count: number
  stats: HistoryStats
  results: HistoryRecord[]
}

export interface HistoryFilter {
  date_from?: string
  date_to?: string
  classification?: string
  station_area?: string
}
