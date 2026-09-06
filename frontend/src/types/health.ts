export interface ServiceState {
  status: 'ok' | 'unavailable' | 'not_configured'
  detail?: string
}

export interface HealthResponse {
  status: 'ok' | 'degraded'
  service: string
  version: string
  services: Record<string, ServiceState>
}

