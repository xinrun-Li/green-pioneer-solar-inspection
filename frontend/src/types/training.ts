export type AnnotationStatus = 'pending' | 'annotating' | 'annotated' | 'rejected'
export type ModelStatus = 'candidate' | 'active' | 'retired' | 'failed'

export interface DatasetAnnotation {
  id: number
  asset_id: number
  class_name: 'normal' | 'cleaning' | 'repair'
  bbox: { x: number; y: number; width: number; height: number }
  source: string
  operator: number
}

export interface DatasetAsset {
  id: number
  original_name: string
  media_type: string
  size_bytes: number
  annotation_status: AnnotationStatus
  source_type: string
  is_hard_sample: boolean
  url: string
  annotations: DatasetAnnotation[]
  created_at: string
}

export interface DatasetVersion {
  id: number
  name: string
  version: string
  status: 'draft' | 'frozen' | 'archived'
  asset_ids: number[]
  train_count: number
  validation_count: number
  test_count: number
  class_config: Array<{ name: string; display_name: string }>
}

export interface ModelVersion {
  id: number
  name: string
  version: string
  model_type: 'mock' | 'yolo'
  model_path: string
  dataset_version_id: number | null
  metrics: Record<string, number | number[]>
  class_config: string[]
  status: ModelStatus
  is_active: boolean
  created_at: string
  activated_at: string | null
}

export interface TrainingRun {
  id: number
  dataset_version_id: number
  base_model_version_id: number | null
  output_model_version_id: number | null
  status: 'created' | 'queued' | 'running' | 'completed' | 'failed' | 'cancelled'
  epochs: number
  image_size: number
  batch_size: number
  device: string
  progress: number
  metrics: Record<string, number | number[]>
  error_message: string
  created_at: string
}
