export type JobStatus = 'created' | 'queued' | 'running' | 'review' | 'completed' | 'failed'
export type DetectionClass = 'normal' | 'cleaning' | 'repair'

export interface DetectionResult {
  id: number
  sequence: number
  bbox: { x: number; y: number; width: number; height: number }
  original_class: DetectionClass
  model_class: string
  model_class_label: string
  effective_class: DetectionClass
  confidence: number
  reason: string
  review_status: 'pending' | 'confirmed'
  is_demo_data: boolean
}

export interface RecognitionJob {
  id: number
  status: JobStatus
  progress: number
  adapter: string
  model_version: string | null
  model_version_id: number | null
  is_demo_data: boolean
  processed_frames: number
  total_frames: number
  retry_count: number
  error_message: string
  media: { id: number; kind: 'image' | 'video'; original_name: string; url: string; status: string }
  detections: DetectionResult[]
  created_at: string
  completed_at: string | null
}

export interface UploadedMedia {
  id: number
  kind: 'image' | 'video'
  original_name: string
  mime_type: string
  size_bytes: number
  status: string
  url: string
  job_id: number | null
}

export interface UploadBatch {
  id: number
  region_note: string
  status: string
  created_at: string
  media: UploadedMedia[]
}
