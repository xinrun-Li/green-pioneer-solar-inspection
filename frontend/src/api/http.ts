const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api/v1'

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string) {
    super(message)
  }
}

function csrfToken(): string {
  return document.cookie.split('; ').find((item) => item.startsWith('csrftoken='))?.split('=')[1] ?? ''
}

export async function requestJson<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers)
  if (options.body && !(options.body instanceof FormData) && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
  const token = csrfToken()
  if (token) headers.set('X-CSRFToken', decodeURIComponent(token))
  const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers, credentials: 'include' })
  if (!response.ok) {
    const payload = await response.json().catch(() => ({})) as { code?: string; message?: string; detail?: string }
    throw new ApiError(response.status, payload.code ?? 'request_failed', payload.message ?? payload.detail ?? `请求失败：${response.status}`)
  }
  return response.json() as Promise<T>
}

export const getJson = <T>(path: string) => requestJson<T>(path)
