export type OperatorRole = 'admin' | 'reviewer' | 'inspector' | 'viewer'
export type OperatorStatus = 'pending' | 'approved' | 'rejected' | 'disabled'

export interface OperatorRecord {
  id: number
  user_id: number
  username: string
  display_name: string
  phone: string
  role: OperatorRole
  role_display?: string
  review_status: OperatorStatus
  rejection_reason: string
  station: { id: number; name: string } | null
  reviewed_by: { id: number; username: string; display_name: string } | null
  reviewed_at: string | null
  created_at: string
  updated_at: string
  is_active: boolean
}

export interface AuditLogRecord {
  id: number
  action_type: string
  action_label?: string
  reason: string
  operator: { id: number; username: string; display_name: string } | null
  target_user: { id: number; username: string; display_name: string } | null
  created_at: string
}

export const operatorRoleLabels: Record<OperatorRole, string> = {
  admin: '管理员', reviewer: '审核员', inspector: '巡检员', viewer: '查看员',
}

export const operatorStatusLabels: Record<OperatorStatus, string> = {
  pending: '待审核', approved: '正常', rejected: '已驳回', disabled: '已停用',
}
