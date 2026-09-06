export type TaskStatus = 'draft' | 'confirmed' | 'running' | 'paused' | 'completed' | 'failed' | 'cancelled'
export type WaypointStatus = 'pending' | 'visited' | 'skipped' | 'failed'
export type InspectionEventType =
  'created' | 'confirmed' | 'started' | 'paused' | 'resumed' | 'cancelled' | 'failed' | 'completed' |
  'waypoint_visited' | 'waypoint_skipped' | 'media_uploaded' | 'media_missing'

export interface WaypointItem {
  id: number
  task_id: number
  panel_id: number
  panel_full_code: string
  panel_short_code: string
  region_name: string
  array_code: string
  row: number
  column: number
  order: number
  status: WaypointStatus
  visited_at: string | null
  uploaded_media_id: number | null
  notes: string
  created_at: string
}

export interface InspectionEventItem {
  id: number
  task_id: number
  event_type: InspectionEventType
  description: string
  created_by_name: string
  created_at: string
}

export interface InspectionTaskSummary {
  id: number
  title: string
  station_id: number
  station_name: string
  status: TaskStatus
  total_waypoints: number
  visited_waypoints: number
  coverage: number
  created_by_name: string
  confirmed_at: string | null
  started_at: string | null
  completed_at: string | null
  created_at: string
  updated_at: string
}

export interface InspectionTaskDetail extends InspectionTaskSummary {
  description: string
  station_code: string
  progress: number
  waypoints: WaypointItem[]
  events: InspectionEventItem[]
  confirmed_by_name: string
}

export const taskStatusLabels: Record<TaskStatus, string> = {
  draft: '草稿', confirmed: '已确认', running: '执行中', paused: '已暂停',
  completed: '已完成', failed: '失败', cancelled: '已取消',
}

export const taskStatusColors: Record<TaskStatus, string> = {
  draft: '#64748B', confirmed: '#3B82F6', running: '#22C55E', paused: '#F59E0B',
  completed: '#16A34A', failed: '#EF4444', cancelled: '#64748B',
}

export const waypointStatusLabels: Record<WaypointStatus, string> = {
  pending: '待巡检', visited: '已巡检', skipped: '已跳过', failed: '失败',
}

export const waypointStatusColors: Record<WaypointStatus, string> = {
  pending: '#64748B', visited: '#22C55E', skipped: '#F59E0B', failed: '#EF4444',
}