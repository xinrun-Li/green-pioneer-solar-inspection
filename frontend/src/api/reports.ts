import { getJson, requestJson } from './http'
import type { Report, ReportCreateRequest } from '@/types/reports'

export const reportsApi = {
  list(): Promise<Report[]> {
    return getJson<{ results: Report[] }>('/reports/').then((r) => r.results)
  },
  detail(id: number): Promise<Report> {
    return getJson<Report>(`/reports/${id}/`)
  },
  create(data: ReportCreateRequest): Promise<Report> {
    return requestJson<Report>('/reports/', { method: 'POST', body: JSON.stringify(data) })
  },
  download(id: number): Promise<Blob> {
    return requestJson<Blob>(`/reports/${id}/download/`, { method: 'GET' })
  },
  retry(id: number): Promise<Report> {
    return requestJson<Report>(`/reports/${id}/retry/`, { method: 'POST' })
  },
}