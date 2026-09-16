import { defineStore } from 'pinia'

import { changeCurrentPassword, getCurrentUser, login, logout, register, updateCurrentUser } from '@/api/auth'
import type { Session, User } from '@/types/auth'
import { AUTH_TOKEN_STORAGE_KEY } from '@/utils/auth-token'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: null as User | null,
    expiresAt: '',
    initialized: false,
    loading: false,
  }),
  getters: {
    isAuthenticated: (state) => Boolean(state.user && window.localStorage.getItem(AUTH_TOKEN_STORAGE_KEY)),
    isAdmin: (state) => state.user?.role === 'admin',
  },
  actions: {
    applySession(session: Session) {
      window.localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, session.access_token)
      this.user = session.user
      this.expiresAt = session.expires_at
      this.initialized = true
    },
    clear() {
      window.localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY)
      this.user = null
      this.expiresAt = ''
      this.initialized = true
    },
    async restore() {
      if (this.initialized) return
      const token = window.localStorage.getItem(AUTH_TOKEN_STORAGE_KEY)
      if (!token) { this.initialized = true; return }
      this.loading = true
      try { this.user = await getCurrentUser() } catch { this.clear() } finally { this.loading = false; this.initialized = true }
    },
    async signIn(payload: { account: string; password: string }) {
      this.loading = true
      try { this.applySession(await login(payload)) } finally { this.loading = false }
    },
    async signUp(payload: { email: string; password: string; display_name: string }) {
      this.loading = true
      try { this.applySession(await register(payload)) } finally { this.loading = false }
    },
    async updateProfile(displayName: string) {
      this.loading = true
      try { this.user = await updateCurrentUser(displayName) } finally { this.loading = false }
    },
    async changePassword(currentPassword: string, newPassword: string) {
      this.loading = true
      try { await changeCurrentPassword(currentPassword, newPassword); this.clear() } finally { this.loading = false }
    },
    async signOut() {
      try { if (window.localStorage.getItem(AUTH_TOKEN_STORAGE_KEY)) await logout() } catch { /* A stale session is safe to clear locally. */ }
      this.clear()
    },
  },
})
