export type PanelStatus = 'normal' | 'cleaning' | 'repair' | 'processing' | 'unknown'

export interface PanelMapItem {
  id: number
  full_code: string
  short_code: string
  row: number
  column: number
  status: PanelStatus
  last_recognized_at: string | null
}

export interface ArrayMapItem {
  id: number
  code: string
  rows: number
  columns: number
  panels: PanelMapItem[]
}

export interface RegionMapItem {
  id: number
  name: string
  direction: string
  arrays: ArrayMapItem[]
}

export interface StationMap {
  id: number
  code: string
  name: string
  panel_count: number
  summary: Record<PanelStatus, number>
  regions: RegionMapItem[]
}

export interface StatusHistoryItem {
  id: number
  status: PanelStatus
  reason: string
  recorded_at: string
  source: string
}

export interface AbnormalEventItem {
  id: number
  event_type: string
  status: 'open' | 'closed'
  reason: string
  opened_at: string
  closed_at: string | null
  closed_note: string
}

export interface PanelDetail {
  id: number
  full_code: string
  short_code: string
  row: number
  column: number
  status: PanelStatus
  last_recognized_at: string | null
  array_code: string
  region_name: string
  station_name: string
  status_history: StatusHistoryItem[]
  events: AbnormalEventItem[]
}

export interface WaypointPos {
  row: number
  column: number
  panel_id: number
}

