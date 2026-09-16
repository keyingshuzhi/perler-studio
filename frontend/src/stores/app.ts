import { defineStore } from 'pinia'

export const useAppStore = defineStore('app', {
  state: () => ({
    error: '' as string,
    notice: '' as string,
  }),
  actions: {
    showError(error: unknown) {
      this.error = error instanceof Error ? error.message : '发生未知错误'
    },
    showNotice(message: string) {
      this.notice = message
      window.setTimeout(() => {
        if (this.notice === message) this.notice = ''
      }, 3_500)
    },
    clearError() {
      this.error = ''
    },
  },
})
