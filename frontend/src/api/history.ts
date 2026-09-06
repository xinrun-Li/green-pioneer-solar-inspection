import { getJson } from './http'
import type { HistoryFilter, HistoryResponse } from '@/types/history'

export const historyApi = {
  getHistory(filters?: HistoryFilter): Promise<HistoryResponse> {
    const params = new URLSearchParams()
    if (filters?.date_from) params.set('date_from', filters.date_from)
    if (filters?.date_to) params.set('date_to', filters.date_to)
    if (filters?.classification) params.set('classification', filters.classification)
    if (filters?.station_area) params.set('station_area', filters.station_area)
    const qs = params.toString()
    return getJson<HistoryResponse>(`/inspections/history/${qs ? `?${qs}` : ''}`)
  },
}
