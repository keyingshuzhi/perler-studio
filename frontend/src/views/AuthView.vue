<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const mode = ref<'login' | 'register'>(route.query.mode === 'register' ? 'register' : 'login')
const account = ref('')
const password = ref('')
const displayName = ref('')
const error = ref('')
const nextPath = computed(() => typeof route.query.next === 'string' && route.query.next.startsWith('/') ? route.query.next : '/projects')

async function submit() {
  error.value = ''
  try {
    if (mode.value === 'login') await auth.signIn({ account: account.value, password: password.value })
    else await auth.signUp({ email: account.value, password: password.value, display_name: displayName.value })
    await router.replace(nextPath.value)
  } catch (reason) { error.value = reason instanceof Error ? reason.message : '暂时无法完成登录，请稍后重试' }
}
</script>

<template>
  <main class="auth-page">
    <section class="auth-card card">
      <aside class="auth-card__intro">
        <p class="eyebrow">PERLER STUDIO</p>
        <div class="intro-mark" aria-hidden="true"><i></i><i></i><i></i><i></i></div>
        <h1>{{ mode === 'login' ? '回到你的创作台。' : '创建你的创作空间。' }}</h1>
        <p>{{ mode === 'login' ? '继续编辑图纸、管理色卡与材料，所有作品都安全保存在你的账户中。' : '用一个账户保存图纸、色卡、库存、版本和发布作品。' }}</p>
        <ul><li>自动识别账户权限</li><li>项目与素材独立保存</li><li>修改密码即时保护账户</li></ul>
      </aside>
      <div class="auth-card__form">
        <div class="auth-tabs" role="tablist" aria-label="账户操作"><button type="button" :class="{ active: mode === 'login' }" @click="mode = 'login'; error = ''">登录</button><button type="button" :class="{ active: mode === 'register' }" @click="mode = 'register'; error = ''">注册</button></div>
        <div class="form-heading"><span>{{ mode === 'login' ? '欢迎回来' : '开始创作' }}</span><p>{{ mode === 'login' ? '请输入账号或注册邮箱，系统会自动识别管理员权限。' : '注册的是创作者账户；管理员权限由平台统一管理。' }}</p></div>
        <form @submit.prevent="submit">
          <label v-if="mode === 'register'" class="field">显示名称<input v-model.trim="displayName" required maxlength="80" autocomplete="name" placeholder="例如：小林的拼豆工坊"></label>
          <label class="field">{{ mode === 'login' ? '账号或邮箱' : '邮箱' }}<input v-model.trim="account" required :type="mode === 'login' ? 'text' : 'email'" :autocomplete="mode === 'login' ? 'username' : 'email'" :placeholder="mode === 'login' ? '例如：admin 或 you@example.com' : 'you@example.com'"></label>
          <label class="field">密码<input v-model="password" required type="password" :minlength="mode === 'login' ? 1 : 8" maxlength="128" :autocomplete="mode === 'login' ? 'current-password' : 'new-password'" :placeholder="mode === 'login' ? '输入密码' : '至少 8 位'"></label>
          <p v-if="mode === 'login'" class="account-note"><span>✓</span> 无需选择身份，登录后将自动进入对应工作空间。</p>
          <p v-else class="password-note">建议使用 12 位以上、包含字母与数字的独立密码。</p>
          <p v-if="error" class="form-error" role="alert">{{ error }}</p>
          <button class="button submit" :disabled="auth.loading">{{ auth.loading ? '正在处理…' : mode === 'login' ? '登录并继续 →' : '创建账户并继续 →' }}</button>
        </form>
        <p class="privacy">继续即表示你同意仅将内容用于个人创作与项目协作。公开部署前可在此接入隐私政策与服务条款。</p>
      </div>
    </section>
  </main>
</template>

<style scoped>
.auth-page { display: grid; min-height: calc(100vh - 70px); place-items: center; padding: 42px 18px; background: radial-gradient(circle at 12% 13%, #dfdaff, transparent 28%), radial-gradient(circle at 88% 88%, #d9f4eb, transparent 24%), linear-gradient(135deg, #f9faff, #eff4fa); }.auth-card { display: grid; width: min(860px, 100%); grid-template-columns: minmax(270px, .94fr) minmax(360px, 1.06fr); overflow: hidden; padding: 0; box-shadow: 0 24px 65px rgb(45 50 87 / 14%); }.auth-card__intro { position: relative; overflow: hidden; padding: clamp(30px, 5vw, 52px); background: linear-gradient(145deg, #222d51, #463487 68%, #5a47a7); color: #fff; }.auth-card__intro::after { position: absolute; right: -72px; bottom: -90px; width: 230px; height: 230px; border: 1px solid rgb(255 255 255 / 12%); border-radius: 50%; content: ''; box-shadow: 0 0 0 34px rgb(255 255 255 / 4%), 0 0 0 69px rgb(255 255 255 / 3%); }.eyebrow { margin: 0; color: #a9e4d1; font-family: var(--font-mono); font-size: 10px; font-weight: 800; letter-spacing: .15em; }.intro-mark { display: grid; width: 62px; grid-template-columns: repeat(2, 1fr); gap: 7px; margin: 31px 0 24px; }.intro-mark i { display: block; aspect-ratio: 1; border: 1px solid rgb(255 255 255 / 34%); border-radius: 9px; background: linear-gradient(145deg, #9c8cff, #6bdac0); box-shadow: inset 0 1px 1px rgb(255 255 255 / 38%); }.intro-mark i:nth-child(2) { background: linear-gradient(145deg, #ffcf73, #ed968a); }.intro-mark i:nth-child(3) { background: linear-gradient(145deg, #77d6c0, #71a9e9); }.intro-mark i:nth-child(4) { background: linear-gradient(145deg, #c5b5ff, #9175e8); }.auth-card h1 { position: relative; z-index: 1; margin: 0 0 11px; font-family: Fraunces, Georgia, serif; font-size: clamp(31px, 4vw, 46px); line-height: 1.06; letter-spacing: -1.8px; }.auth-card__intro > p:not(.eyebrow) { position: relative; z-index: 1; max-width: 330px; margin: 0; color: #d6dcf0; font-size: 13px; line-height: 1.75; }.auth-card__intro ul { position: relative; z-index: 1; display: grid; gap: 9px; margin: 30px 0 0; padding: 0; list-style: none; color: #cbd5ef; font-size: 11px; }.auth-card__intro li::before { display: inline-grid; width: 16px; height: 16px; place-items: center; margin-right: 7px; border-radius: 50%; color: #59cfb4; background: rgb(94 207 180 / 13%); content: '✓'; font-size: 9px; font-weight: 800; }.auth-card__form { display: flex; min-width: 0; flex-direction: column; background: rgb(255 255 255 / 94%); }.auth-tabs { display: grid; grid-template-columns: 1fr 1fr; margin: 20px 30px 0; padding: 4px; border-radius: 10px; background: #f3f1f9; }.auth-tabs button { border: 0; border-radius: 7px; padding: 9px; background: transparent; color: #7b8497; font: inherit; font-size: 12px; font-weight: 800; cursor: pointer; }.auth-tabs button.active { color: #493a9d; background: #fff; box-shadow: 0 2px 8px rgb(42 38 80 / 10%); }.form-heading { padding: 27px 31px 4px; }.form-heading span { color: #29334d; font-size: 19px; font-weight: 850; letter-spacing: -.4px; }.form-heading p { margin: 7px 0 0; color: #8590a4; font-size: 11px; line-height: 1.6; }.auth-card form { display: grid; gap: 14px; padding: 18px 31px 12px; }.field { display: grid; gap: 7px; color: #505a70; font-size: 11px; font-weight: 800; }.field input { min-height: 44px; border: 1px solid #dedbe8; border-radius: 10px; padding: 0 12px; background: #fff; color: #2e3853; font: inherit; font-size: 13px; transition: border-color .18s ease, box-shadow .18s ease; }.field input:focus { outline: 0; border-color: #836de2; box-shadow: 0 0 0 3px rgb(111 85 222 / 14%); }.password-note, .privacy { margin: -4px 0 0; color: #8a93a7; font-size: 10px; line-height: 1.55; }.account-note { display: flex; align-items: center; gap: 6px; margin: -2px 0 0; color: #657087; font-size: 10px; line-height: 1.5; }.account-note span { display: grid; width: 16px; height: 16px; flex: 0 0 16px; place-items: center; border-radius: 50%; color: #328d6e; background: #e9f8f1; font-size: 9px; font-weight: 800; }.form-error { margin: -2px 0 0; border-radius: 9px; padding: 9px 10px; background: #fff0f1; color: #af4b57; font-size: 11px; line-height: 1.45; }.submit { width: 100%; min-height: 44px; justify-content: center; margin-top: 3px; }.privacy { margin-top: auto; padding: 9px 31px 24px; font-size: 9px; }@media (max-width: 720px) { .auth-page { align-items: start; padding-top: 24px; }.auth-card { grid-template-columns: 1fr; width: min(480px, 100%); }.auth-card__intro { padding: 28px 30px 25px; }.intro-mark, .auth-card__intro ul { display: none; }.auth-card__intro > p:not(.eyebrow) { max-width: none; }.auth-card__intro::after { width: 150px; height: 150px; right: -54px; bottom: -72px; }.auth-tabs { margin-top: 18px; } }
</style>
