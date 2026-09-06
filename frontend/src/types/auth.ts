export type ReviewStatus = 'pending' | 'approved' | 'rejected' | 'disabled'

export interface CurrentUser {
  id: number
  username: string
  display_name: string
  review_status: ReviewStatus
  station: { id: number; name: string } | null
  is_admin: boolean
  is_account_manager?: boolean
  is_superuser?: boolean
  rejection_reason?: string
}

export interface MeResponse {
  authenticated: boolean
  user?: CurrentUser
  csrf_token: string
}

export interface AccountNotification {
  id: number
  kind: 'approved' | 'rejected' | 'status'
  title: string
  content: string
  is_read: boolean
  created_at: string
}
