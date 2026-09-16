<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const title = computed(() => (route.meta.title as string | undefined) || 'Perler Studio')

async function signOut() {
  await auth.signOut()
  await router.push('/')
}
</script>

<template>
  <header class="header">
    <RouterLink class="brand" to="/"><span class="brand__mark"><i /><i /><i /><i /></span><span>Perler <em>Studio</em></span></RouterLink>
    <div class="title"><span class="title__dot" />{{ title }}</div>
    <nav aria-label="主导航">
      <RouterLink to="/convert">新建图纸</RouterLink>
      <RouterLink to="/templates">模板</RouterLink>
      <RouterLink to="/projects">项目</RouterLink>
      <RouterLink to="/gallery">社区</RouterLink>
      <template v-if="auth.isAuthenticated"><RouterLink v-if="auth.isAdmin" class="admin-link" to="/admin">管理</RouterLink><RouterLink class="account" to="/account" :title="auth.user?.email">{{ auth.user?.display_name }}</RouterLink><button class="sign-out" type="button" @click="signOut">退出</button></template>
      <RouterLink v-else class="sign-in" to="/auth">登录</RouterLink>
    </nav>
  </header>
</template>

<style scoped>
.header { position: sticky; z-index: 10; top: 0; display: flex; height: 70px; align-items: center; gap: 28px; padding: 0 clamp(18px, 4vw, 56px); border-bottom: 1px solid rgb(255 255 255 / 9%); background: rgb(19 27 45 / 94%); box-shadow: 0 7px 28px rgb(19 27 45 / 13%); backdrop-filter: blur(18px); }
.brand { display: inline-flex; align-items: center; gap: 10px; color: #fff; font-family: Fraunces, Georgia, serif; font-size: 20px; font-weight: 700; letter-spacing: -.7px; }.brand em { color: #a99cff; font-style: normal; }
.brand__mark { display: grid; grid-template-columns: repeat(2, 7px); gap: 3px; padding: 6px; border-radius: 10px; background: linear-gradient(135deg, #826ff6, #4ccab0); box-shadow: 0 5px 14px rgb(123 104 241 / 35%); }.brand__mark i { width: 7px; height: 7px; border-radius: 3px; background: rgb(255 255 255 / 95%); }.brand__mark i:nth-child(2) { opacity: .68; }.brand__mark i:nth-child(3) { opacity: .45; }
.title { display: flex; flex: 1; align-items: center; gap: 8px; color: #b4bdcf; font-size: 12px; font-weight: 700; }.title__dot { width: 6px; height: 6px; border-radius: 50%; background: #62d8b8; box-shadow: 0 0 0 4px rgb(98 216 184 / 12%); }
nav { display: flex; align-items: center; gap: 5px; font-size: 12px; font-weight: 800; } nav a, .sign-out { padding: 8px 11px; border-radius: 9px; color: #bdc6d7; transition: background .18s ease, color .18s ease; } nav a:hover, nav a.router-link-active, .sign-out:hover { background: rgb(255 255 255 / 10%); color: #fff; }.admin-link { color: #ffd78a; }.account { max-width: 110px; overflow: hidden; padding: 0 3px 0 7px; color: #a9e4d1; font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }.sign-out { border: 0; background: transparent; font: inherit; cursor: pointer; }.sign-in { border: 1px solid rgb(169 156 255 / 38%); color: #fff; }
@media (max-width: 680px) { .header { height: 64px; gap: 12px; padding: 0 15px; }.title { display: none; }.brand { font-size: 17px; }.brand__mark { grid-template-columns: repeat(2, 6px); gap: 2px; }.brand__mark i { width: 6px; height: 6px; } nav { gap: 1px; } nav a, .sign-out { padding: 7px 7px; } .account { max-width: 70px; } } @media (max-width: 470px) { nav a:nth-of-type(1), nav a:nth-of-type(2) { display: none; } }
</style>
