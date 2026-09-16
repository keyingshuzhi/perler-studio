<script setup lang="ts">
import { onMounted } from 'vue'

import AppHeader from '@/components/common/AppHeader.vue'
import { useAppStore } from '@/stores/app'
import { useAuthStore } from '@/stores/auth'

const app = useAppStore()
const auth = useAuthStore()

onMounted(() => { void auth.restore() })
</script>

<template>
  <AppHeader />
  <RouterView />
  <aside v-if="app.notice" class="toast toast--notice" role="status">{{ app.notice }}</aside>
  <aside v-if="app.error" class="toast toast--error" role="alert"><span>{{ app.error }}</span><button aria-label="关闭错误提示" @click="app.clearError">×</button></aside>
</template>

<style scoped>
.toast { position: fixed; z-index: 20; right: 22px; bottom: 22px; display: flex; max-width: min(420px, calc(100vw - 40px)); align-items: center; gap: 16px; padding: 13px 15px; border: 1px solid rgb(255 255 255 / 20%); border-radius: 14px; box-shadow: 0 18px 40px rgb(21 28 48 / 24%); color: #fff; font-size: 13px; font-weight: 700; animation: enter .24s ease-out; }.toast--notice { background: #1f806d; }.toast--error { background: #c64f58; }.toast button { border: 0; background: transparent; color: inherit; font-size: 22px; line-height: 1; } @keyframes enter { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
</style>
