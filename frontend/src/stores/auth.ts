import { defineStore } from 'pinia'
import { ref } from 'vue'
import { requestJson } from '@/api/http'
import type { CurrentUser, MeResponse } from '@/types/auth'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<CurrentUser | null>(null)
  const checked = ref(false)

  async function loadCurrentUser() {
    try {
      const response = await requestJson<MeResponse>('/auth/me')
      user.value = response.authenticated ? response.user ?? null : null
    } catch {
      user.value = null
    } finally {
      checked.value = true
    }
  }

  async function login(username: string, password: string, remember: boolean) {
    const response = await requestJson<{ user: CurrentUser }>('/auth/login', {
      method: 'POST', body: JSON.stringify({ username, password, remember }),
    })
    user.value = response.user
  }

  async function logout() {
    await requestJson('/auth/logout', { method: 'POST' })
    user.value = null
  }

  return { user, checked, loadCurrentUser, login, logout }
})
