<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import {
  createAdminUser,
  deleteAdminUser,
  getAdminPublication,
  listAdminPublicationsPage,
  listAdminUsers,
  resetAdminUserPassword,
  reviewPublication,
  updateAdminUser,
  withdrawAdminPublication,
} from '@/api/admin'
import { mediaUrl } from '@/api/http'
import PublicationReviewDialog from '@/components/admin/PublicationReviewDialog.vue'
import InfiniteScrollTrigger from '@/components/common/InfiniteScrollTrigger.vue'
import { useAppStore } from '@/stores/app'
import { useAuthStore } from '@/stores/auth'
import type { AdminUser } from '@/types/auth'
import type { AdminPublicationDetail, AdminPublicationSummary, PublicationReviewCheck } from '@/types/publication'

const app = useAppStore()
const auth = useAuthStore()
const activeTab = ref<'users' | 'review' | 'community'>('users')
const query = ref('')
const users = ref<AdminUser[]>([])
const totalUsers = ref(0)
const userPage = ref(1)
const userLoading = ref(false)
const pendingPublications = ref<AdminPublicationSummary[]>([])
const approvedPublications = ref<AdminPublicationSummary[]>([])
const pendingPage = ref(1)
const approvedPage = ref(1)
const pendingTotal = ref(0)
const approvedTotal = ref(0)
const pendingLibraryTotal = ref(0)
const approvedLibraryTotal = ref(0)
const pendingPublicationQueryDraft = ref('')
const approvedPublicationQueryDraft = ref('')
const pendingPublicationQuery = ref('')
const approvedPublicationQuery = ref('')
const pendingLoading = ref(false)
const approvedLoading = ref(false)
const loading = ref(false)
const workingId = ref('')
const selectedPublicationId = ref('')
const publicationDetail = ref<AdminPublicationDetail>()
const detailLoading = ref(false)
const detailError = ref('')
const reviewError = ref('')
const showCreate = ref(false)
const createForm = reactive({ display_name: '', email: '', password: '', role: 'user' as 'user' | 'admin', is_active: true })

const publications = computed(() => activeTab.value === 'community' ? approvedPublications.value : pendingPublications.value)
const pendingCount = computed(() => pendingLibraryTotal.value)
const approvedCount = computed(() => approvedLibraryTotal.value)
const currentPublicationTotal = computed(() => activeTab.value === 'community' ? approvedTotal.value : pendingTotal.value)
const currentPublicationLoading = computed(() => activeTab.value === 'community' ? approvedLoading.value : pendingLoading.value)
const currentPublicationQuery = computed(() => activeTab.value === 'community' ? approvedPublicationQuery.value : pendingPublicationQuery.value)
const publicationQueryDraft = computed({
  get: () => activeTab.value === 'community' ? approvedPublicationQueryDraft.value : pendingPublicationQueryDraft.value,
  set: (value: string) => {
    if (activeTab.value === 'community') approvedPublicationQueryDraft.value = value
    else pendingPublicationQueryDraft.value = value
  },
})
const hasPublicationSearch = computed(() => Boolean(publicationQueryDraft.value.trim() || currentPublicationQuery.value))
const hasMoreUsers = computed(() => users.value.length < totalUsers.value)
const hasMorePublications = computed(() => publications.value.length < currentPublicationTotal.value)

async function loadUsers(reset = true) {
  if (userLoading.value) return
  const targetPage = reset ? 1 : userPage.value + 1
  userLoading.value = true
  try {
    const result = await listAdminUsers(query.value.trim(), targetPage, 30)
    userPage.value = targetPage
    users.value = reset ? result.items : [...users.value, ...result.items]
    totalUsers.value = result.total
  } catch (error) { app.showError(error) } finally { userLoading.value = false }
}

async function loadPublicationPage(status: 'pending' | 'approved', reset = false) {
  const isPending = status === 'pending'
  const loadingRef = isPending ? pendingLoading : approvedLoading
  if (loadingRef.value) return
  const currentPage = isPending ? pendingPage.value : approvedPage.value
  const targetPage = reset ? 1 : currentPage + 1
  const publicationQuery = isPending ? pendingPublicationQuery.value : approvedPublicationQuery.value
  loadingRef.value = true
  try {
    const result = await listAdminPublicationsPage(status, publicationQuery, targetPage, 20)
    if (isPending) {
      pendingPage.value = targetPage
      pendingTotal.value = result.total
      pendingLibraryTotal.value = result.library_total ?? result.total
      pendingPublications.value = reset ? result.items : [...pendingPublications.value, ...result.items]
    } else {
      approvedPage.value = targetPage
      approvedTotal.value = result.total
      approvedLibraryTotal.value = result.library_total ?? result.total
      approvedPublications.value = reset ? result.items : [...approvedPublications.value, ...result.items]
    }
  } catch (error) { app.showError(error) } finally { loadingRef.value = false }
}

async function loadPublications() {
  await Promise.all([loadPublicationPage('pending', true), loadPublicationPage('approved', true)])
}

async function refresh() {
  loading.value = true
  try { await Promise.all([loadUsers(true), loadPublications()]) } finally { loading.value = false }
}

function loadMorePublications() {
  void loadPublicationPage(activeTab.value === 'community' ? 'approved' : 'pending')
}

async function searchPublications() {
  if (currentPublicationLoading.value) return
  const isCommunity = activeTab.value === 'community'
  const normalized = publicationQueryDraft.value.trim()
  if (isCommunity) {
    approvedPublicationQueryDraft.value = normalized
    approvedPublicationQuery.value = normalized
  } else {
    pendingPublicationQueryDraft.value = normalized
    pendingPublicationQuery.value = normalized
  }
  await loadPublicationPage(isCommunity ? 'approved' : 'pending', true)
}

async function clearPublicationSearch() {
  if (currentPublicationLoading.value) return
  const isCommunity = activeTab.value === 'community'
  if (isCommunity) {
    approvedPublicationQueryDraft.value = ''
    approvedPublicationQuery.value = ''
  } else {
    pendingPublicationQueryDraft.value = ''
    pendingPublicationQuery.value = ''
  }
  await loadPublicationPage(isCommunity ? 'approved' : 'pending', true)
}

async function createUser() {
  workingId.value = 'create'
  try {
    await createAdminUser({ ...createForm })
    Object.assign(createForm, { display_name: '', email: '', password: '', role: 'user', is_active: true })
    showCreate.value = false
    await loadUsers(true)
    app.showNotice('已创建用户账号')
  } catch (error) { app.showError(error) } finally { workingId.value = '' }
}

async function updateUser(user: AdminUser, changes: Partial<Pick<AdminUser, 'role' | 'is_active'>>) {
  workingId.value = user.id
  try {
    const updated = await updateAdminUser(user.id, changes)
    users.value = users.value.map((item) => item.id === updated.id ? updated : item)
    app.showNotice('用户设置已更新')
  } catch (error) { app.showError(error); await loadUsers(true) } finally { workingId.value = '' }
}

async function editUser(user: AdminUser) {
  const displayName = window.prompt('显示名称：', user.display_name)
  if (displayName === null) return
  const email = window.prompt('登录邮箱：', user.email)
  if (email === null) return
  if (!displayName.trim() || !email.trim()) { app.showError('显示名称和邮箱不能为空'); return }
  workingId.value = user.id
  try {
    const updated = await updateAdminUser(user.id, { display_name: displayName.trim(), email: email.trim() })
    users.value = users.value.map((item) => item.id === updated.id ? updated : item)
    app.showNotice('用户资料已更新')
  } catch (error) { app.showError(error) } finally { workingId.value = '' }
}

async function resetPassword(user: AdminUser) {
  const password = window.prompt(`为「${user.display_name}」设置新密码（至少 8 位）：`)
  if (!password) return
  if (password.length < 8) { app.showError('密码至少需要 8 位'); return }
  workingId.value = user.id
  try { await resetAdminUserPassword(user.id, password); app.showNotice('密码已重置，该用户需重新登录') } catch (error) { app.showError(error) } finally { workingId.value = '' }
}

async function removeUser(user: AdminUser) {
  if (!window.confirm(`删除「${user.display_name}」的账号？该操作会立即注销其所有设备，并保留作品审计记录。`)) return
  workingId.value = user.id
  try { await deleteAdminUser(user.id); await loadUsers(true); app.showNotice('用户已删除并注销') } catch (error) { app.showError(error) } finally { workingId.value = '' }
}

let detailRequestSequence = 0

async function loadPublicationDetail() {
  const publicationId = selectedPublicationId.value
  if (!publicationId || detailLoading.value) return
  const sequence = ++detailRequestSequence
  detailLoading.value = true
  detailError.value = ''
  reviewError.value = ''
  publicationDetail.value = undefined
  try {
    const result = await getAdminPublication(publicationId)
    if (sequence === detailRequestSequence && selectedPublicationId.value === publicationId) publicationDetail.value = result
  } catch (error) {
    if (sequence === detailRequestSequence) detailError.value = error instanceof Error ? error.message : '无法载入作品审核详情'
  } finally {
    if (sequence === detailRequestSequence) detailLoading.value = false
  }
}

function openPublication(publication: AdminPublicationSummary) {
  selectedPublicationId.value = publication.id
  void loadPublicationDetail()
}

function closePublication(force = false) {
  if (!force && workingId.value === selectedPublicationId.value) return
  detailRequestSequence += 1
  selectedPublicationId.value = ''
  publicationDetail.value = undefined
  detailError.value = ''
  reviewError.value = ''
  detailLoading.value = false
}

async function reviewDetail(decision: 'approved' | 'rejected', note: string | undefined, checks: PublicationReviewCheck[]) {
  const publication = publicationDetail.value?.publication
  if (!publication) return
  reviewError.value = ''
  workingId.value = publication.id
  try {
    await reviewPublication(publication.id, decision, note, checks)
    closePublication(true)
    await loadPublicationPage('pending', true)
    if (decision === 'approved') await loadPublicationPage('approved', true)
    app.showNotice(decision === 'approved' ? '作品已通过审核并公开' : '作品已驳回，创作者可修改后重新提交')
  } catch (error) {
    reviewError.value = error instanceof Error ? error.message : '审核提交失败，请重试'
    app.showError(error)
  } finally { workingId.value = '' }
}

async function takeDown(publication: AdminPublicationSummary) {
  const note = window.prompt(`删除并下架「${publication.title}」的原因（必填，将告知创作者）：`)
  if (note === null) return
  if (!note.trim()) { app.showError('请填写删除原因'); return }
  if (!window.confirm('删除并下架后，社区页面与公开链接会立即失效，创作者将收到原因说明。确定继续吗？')) return
  workingId.value = publication.id
  try {
    await withdrawAdminPublication(publication.id, note.trim())
    await loadPublicationPage('approved', true)
    app.showNotice('作品已删除并下架，创作者可在个人中心查看原因')
  } catch (error) { app.showError(error) } finally { workingId.value = '' }
}

onMounted(() => { void refresh() })
</script>

<template>
  <main class="admin-page">
    <section class="admin-hero">
      <div><p class="eyebrow">PLATFORM CONTROL</p><h1>平台管理</h1><p>管理账户访问、审核发布申请，并维护已公开的社区作品。</p></div>
      <button class="refresh" type="button" :disabled="loading" @click="refresh">{{ loading ? '同步中…' : '刷新数据' }}</button>
    </section>

    <section class="admin-shell card">
      <nav class="tabs" aria-label="管理功能"><button :class="{ active: activeTab === 'users' }" type="button" @click="activeTab = 'users'">用户管理 <b>{{ totalUsers }}</b></button><button :class="{ active: activeTab === 'review' }" type="button" @click="activeTab = 'review'">作品审核 <b>{{ pendingCount }}</b></button><button :class="{ active: activeTab === 'community' }" type="button" @click="activeTab = 'community'">社区作品管理 <b>{{ approvedCount }}</b></button></nav>

      <template v-if="activeTab === 'users'">
        <div class="toolbar"><label class="search"><span>⌕</span><input v-model="query" type="search" placeholder="搜索名称或邮箱" @keyup.enter="loadUsers(true)"></label><button class="button button--quiet" type="button" @click="loadUsers(true)">搜索</button><button class="button" type="button" @click="showCreate = !showCreate">{{ showCreate ? '收起' : '+ 新建用户' }}</button></div>
        <form v-if="showCreate" class="create-form" @submit.prevent="createUser"><input v-model.trim="createForm.display_name" required maxlength="80" placeholder="显示名称"><input v-model.trim="createForm.email" required type="email" maxlength="254" placeholder="邮箱"><input v-model="createForm.password" required minlength="8" type="password" placeholder="初始密码（至少 8 位）"><select v-model="createForm.role"><option value="user">普通用户</option><option value="admin">管理员</option></select><button class="button" :disabled="workingId === 'create'">{{ workingId === 'create' ? '创建中…' : '创建账号' }}</button></form>
        <div class="table-wrap"><table><thead><tr><th>用户</th><th>角色</th><th>状态</th><th>注册时间</th><th>操作</th></tr></thead><tbody><tr v-for="user in users" :key="user.id" :class="{ deleted: user.deleted_at }"><td><strong>{{ user.display_name }}</strong><small>{{ user.email }}</small></td><td><select :value="user.role" :disabled="Boolean(user.deleted_at) || workingId === user.id" @change="updateUser(user, { role: ($event.target as HTMLSelectElement).value as 'user' | 'admin' })"><option value="user">普通用户</option><option value="admin">管理员</option></select></td><td><button class="status" :class="{ on: user.is_active, off: !user.is_active }" type="button" :disabled="Boolean(user.deleted_at) || workingId === user.id" @click="updateUser(user, { is_active: !user.is_active })">{{ user.deleted_at ? '已删除' : user.is_active ? '已启用' : '已停用' }}</button></td><td><time>{{ new Date(user.created_at).toLocaleDateString() }}</time></td><td class="actions"><button type="button" :disabled="Boolean(user.deleted_at) || workingId === user.id" @click="editUser(user)">编辑资料</button><button type="button" :disabled="Boolean(user.deleted_at) || workingId === user.id" @click="resetPassword(user)">重置密码</button><button class="danger" type="button" :disabled="Boolean(user.deleted_at) || user.id === auth.user?.id || workingId === user.id" @click="removeUser(user)">删除</button></td></tr><tr v-if="!users.length"><td colspan="5" class="empty">没有找到用户</td></tr></tbody></table></div>
        <InfiniteScrollTrigger v-if="users.length" :has-more="hasMoreUsers" :loading="userLoading" end-text="用户已全部加载" @load="loadUsers(false)" />
      </template>

      <template v-else>
        <div class="review-intro">
          <div>
            <span class="eyebrow">{{ activeTab === 'review' ? 'PENDING REVIEW' : 'COMMUNITY WORK MANAGEMENT' }}</span>
            <h2>{{ activeTab === 'review' ? '待审核发布' : '社区作品管理' }}</h2>
            <p>{{ activeTab === 'review' ? '审核通过后才会生成可公开访问的作品页面；驳回理由将回传给创作者。' : '管理已公开的社区作品。删除并下架时必须填写原因，创作者会在个人中心看到说明。' }}</p>
          </div>
          <span class="count">{{ currentPublicationTotal }}</span>
        </div>
        <form class="publication-search" role="search" @submit.prevent="searchPublications">
          <label class="search">
            <span aria-hidden="true">⌕</span>
            <input
              v-model="publicationQueryDraft"
              type="search"
              maxlength="120"
              :aria-label="activeTab === 'review' ? '检索待审核作品' : '检索社区作品'"
              placeholder="搜索标题、简介、标签、作者或资源 ID"
            >
          </label>
          <span v-if="currentPublicationQuery" class="publication-search__result" aria-live="polite">{{ currentPublicationTotal }} 条匹配结果</span>
          <button class="button" type="submit" :disabled="currentPublicationLoading">{{ currentPublicationLoading ? '检索中…' : '检索' }}</button>
          <button v-if="hasPublicationSearch" class="button button--quiet" type="button" :disabled="currentPublicationLoading" @click="clearPublicationSearch">清除</button>
        </form>
        <div v-if="publications.length" class="publication-list">
          <article v-for="publication in publications" :key="publication.id" class="publication">
            <div class="review-media">
              <button v-if="publication.preview_url" class="review-thumbnail review-thumbnail--pattern" type="button" :aria-label="`查看${publication.title}完整图纸`" @click="openPublication(publication)"><img :src="mediaUrl(publication.preview_url)" :alt="`${publication.title}图纸预览`"><span>图纸</span></button>
              <button v-else class="review-thumbnail review-thumbnail--missing" type="button" @click="openPublication(publication)"><span>!</span><small>图纸不可用</small></button>
              <button v-if="publication.finished_photo_preview_url" class="review-thumbnail review-thumbnail--photo" type="button" :aria-label="`查看${publication.title}成品实拍`" @click="openPublication(publication)"><img :src="mediaUrl(publication.finished_photo_preview_url)" alt="作品成品实拍"><span>实拍</span></button>
            </div>
            <div class="publication-copy">
              <p class="publication__meta">{{ publication.author.display_name }} · {{ new Date(publication.submitted_at).toLocaleString() }}</p>
              <h3>{{ publication.title }}</h3>
              <p>{{ publication.description || '创作者未填写作品说明。' }}</p>
              <div class="review-tags"><span v-for="tag in publication.tags" :key="tag">{{ tag }}</span></div>
              <small><template v-if="publication.grid_width && publication.grid_height">{{ publication.grid_width }} × {{ publication.grid_height }} 格 · {{ (publication.total_beads ?? 0).toLocaleString() }} 颗 · {{ publication.used_color_count ?? 0 }} 色 · </template>图纸 {{ publication.pattern_id.slice(-8) }}</small>
              <span class="review-readiness" :class="{ blocked: !publication.review_ready }">{{ activeTab === 'community' ? publication.review_ready ? '已通过合规审核，记录可追溯' : '已公开，但当前图纸资源异常' : publication.review_ready ? '材料可用，待人工合规审核' : '存在图纸阻断问题' }}</span>
            </div>
            <div v-if="activeTab === 'review'" class="review-actions">
              <button class="button" :disabled="workingId === publication.id" @click="openPublication(publication)">查看详情并审核</button>
            </div>
            <div v-else class="review-actions">
              <button class="button button--quiet" type="button" @click="openPublication(publication)">审核详情</button>
              <a class="button button--quiet" :href="`/p/${publication.public_token}`" target="_blank" rel="noopener">查看作品</a>
              <button class="button button--danger" :disabled="workingId === publication.id" @click="takeDown(publication)">{{ workingId === publication.id ? '删除中…' : '删除并下架' }}</button>
            </div>
          </article>
        </div>
        <div v-else class="review-empty">
          <span>{{ currentPublicationQuery ? '⌕' : activeTab === 'review' ? '✓' : '○' }}</span>
          <h2>{{ currentPublicationQuery ? '没有找到匹配作品' : activeTab === 'review' ? '审核队列为空' : '暂无已公开作品' }}</h2>
          <p>{{ currentPublicationQuery ? `没有与“${currentPublicationQuery}”相关的作品，请更换关键词后重试。` : activeTab === 'review' ? '新的用户发布申请会出现在这里。' : '审核通过的作品会出现在这里，供管理员进行删除下架管理。' }}</p>
        </div>
        <InfiniteScrollTrigger v-if="publications.length" :has-more="hasMorePublications" :loading="currentPublicationLoading" end-text="作品已全部加载" @load="loadMorePublications" />
      </template>
    </section>
    <PublicationReviewDialog
      v-if="selectedPublicationId"
      :detail="publicationDetail"
      :loading="detailLoading"
      :load-error="detailError"
      :submit-error="reviewError"
      :working="workingId === selectedPublicationId"
      :review-mode="activeTab === 'review'"
      @close="closePublication"
      @retry="loadPublicationDetail"
      @decide="reviewDetail"
    />
  </main>
</template>

<style scoped>
.admin-page { width: min(1240px, calc(100% - 38px)); margin: 0 auto; padding: clamp(35px, 6vw, 72px) 0 80px; }.admin-hero { display: flex; align-items: end; justify-content: space-between; gap: 20px; margin-bottom: 26px; }.eyebrow { margin: 0; color: #7860e8; font-family: var(--font-mono); font-size: 10px; font-weight: 800; letter-spacing: .14em; }.admin-hero h1 { margin: 7px 0; color: #1c2743; font-family: Fraunces, Georgia, serif; font-size: clamp(37px, 6vw, 59px); letter-spacing: -2.4px; }.admin-hero p:not(.eyebrow) { max-width: 570px; margin: 0; color: #718099; font-size: 14px; line-height: 1.65; }.refresh { border: 1px solid #ded9ee; border-radius: 10px; padding: 10px 13px; color: #6150bd; background: #fff; font: inherit; font-size: 12px; font-weight: 800; white-space: nowrap; }.admin-shell { overflow: hidden; }.tabs { display: flex; gap: 3px; border-bottom: 1px solid #e8e5f1; padding: 10px 14px 0; background: #fbfaff; }.tabs button { border: 0; border-bottom: 2px solid transparent; padding: 12px 13px 10px; color: #788297; background: transparent; font: inherit; font-size: 12px; font-weight: 800; cursor: pointer; }.tabs button.active { border-color: #7059df; color: #44358a; }.tabs b { display: inline-grid; min-width: 18px; place-items: center; margin-left: 5px; border-radius: 9px; padding: 1px 5px; color: #fff; background: #7059df; font-size: 9px; }.toolbar { display: flex; align-items: center; gap: 8px; padding: 18px; }.search { display: flex; flex: 1; align-items: center; gap: 6px; border: 1px solid #dedbe8; border-radius: 9px; padding: 0 10px; color: #8d95a7; }.search input { width: 100%; border: 0; outline: 0; padding: 10px 0; color: #38425c; background: transparent; font: inherit; font-size: 12px; }.create-form { display: grid; grid-template-columns: 1fr 1.3fr 1.2fr .75fr auto; gap: 7px; margin: 0 18px 18px; border: 1px solid #ddd6fa; border-radius: 12px; padding: 12px; background: #faf9ff; }.create-form input, .create-form select, table select { min-width: 0; border: 1px solid #ddd9e9; border-radius: 7px; padding: 8px; color: #404960; background: #fff; font: inherit; font-size: 11px; }.button { border: 1px solid #5f4cbf; border-radius: 8px; padding: 9px 12px; color: #fff; background: #5f4cbf; font: inherit; font-size: 11px; font-weight: 800; cursor: pointer; }.button--quiet { border-color: #ded9ee; color: #6253ae; background: #f8f6ff; }.button--danger { border-color: #bd5661; background: #bd5661; }.button:disabled, button:disabled { cursor: not-allowed; opacity: .52; }.table-wrap { overflow-x: auto; border-top: 1px solid #ebe8f2; } table { width: 100%; min-width: 780px; border-collapse: collapse; } th { padding: 11px 18px; color: #8991a4; background: #fcfbfe; font-family: var(--font-mono); font-size: 9px; letter-spacing: .08em; text-align: left; text-transform: uppercase; } td { border-top: 1px solid #efedf4; padding: 14px 18px; color: #657087; font-size: 11px; } td strong, td small { display: block; } td strong { color: #2b3651; font-size: 12px; } td small { margin-top: 3px; color: #99a0b0; font-family: var(--font-mono); font-size: 9px; } td time { color: #8b94a6; font-family: var(--font-mono); font-size: 10px; }.deleted { opacity: .58; }.status { border: 0; border-radius: 999px; padding: 5px 8px; font: inherit; font-size: 10px; font-weight: 800; }.status.on { color: #267a60; background: #ecfaf3; }.status.off { color: #a26445; background: #fff4eb; }.actions { white-space: nowrap; }.actions button { border: 0; padding: 4px 7px; color: #58647e; background: transparent; font: inherit; font-size: 10px; font-weight: 800; }.actions .danger { color: #bd5661; }.empty { padding: 34px; color: #9199ab; text-align: center; }.publication-scopes { display: flex; gap: 6px; padding: 16px 24px 0; }.publication-scopes button { border: 1px solid #e2deee; border-radius: 8px; padding: 7px 9px; color: #737d92; background: #fbfaff; font-size: 10px; font-weight: 800; }.publication-scopes button.active { border-color: #cfc5f7; color: #5744bd; background: #f1efff; }.publication-scopes b { min-width: 16px; margin-left: 4px; padding: 1px 4px; color: inherit; background: transparent; font-size: 9px; }.review-intro { display: flex; align-items: center; justify-content: space-between; padding: 21px 24px 20px; }.review-intro h2 { margin: 5px 0; color: #24304a; font-size: 21px; }.review-intro p { margin: 0; color: #7c869c; font-size: 12px; }.count { display: grid; min-width: 45px; height: 45px; place-items: center; border-radius: 14px; color: #5e49c2; background: #f0edff; font-family: var(--font-mono); font-size: 16px; font-weight: 800; }.publication-list { display: grid; border-top: 1px solid #ebe8f2; }.publication { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 22px 24px; border-bottom: 1px solid #ebe8f2; }.review-photo { width: 76px; height: 76px; flex: 0 0 auto; border: 1px solid #e1ddea; border-radius: 11px; object-fit: cover; }.publication__meta { margin: 0; color: #8170cf; font-family: var(--font-mono); font-size: 9px; }.publication h3 { margin: 5px 0 6px; color: #28344e; font-size: 16px; }.publication p:not(.publication__meta) { max-width: 650px; margin: 0; color: #737e94; font-size: 12px; line-height: 1.55; }.review-tags { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 7px; }.review-tags span { border-radius: 99px; padding: 3px 6px; color: #6d6891; background: #f1eff8; font-size: 8px; }.publication small { display: block; margin-top: 8px; color: #a0a6b4; font-family: var(--font-mono); font-size: 9px; }.review-actions { display: flex; flex-shrink: 0; gap: 7px; }.review-actions a { text-decoration: none; }.review-empty { display: grid; justify-items: center; gap: 5px; padding: 70px 25px; border-top: 1px solid #ebe8f2; color: #7a859b; text-align: center; }.review-empty span { display: grid; width: 40px; height: 40px; place-items: center; border-radius: 50%; color: #38a37d; background: #eafaf2; font-size: 20px; }.review-empty h2, .review-empty p { margin: 0; }.review-empty h2 { color: #35405a; font-size: 18px; }.review-empty p { font-size: 12px; }@media (max-width: 820px) { .admin-page { width: min(100% - 26px, 1240px); }.admin-hero { align-items: start; flex-direction: column; }.create-form { grid-template-columns: 1fr 1fr; }.publication { align-items: start; flex-direction: column; }.toolbar { flex-wrap: wrap; }.search { flex-basis: 100%; } }@media (max-width: 520px) { .create-form { grid-template-columns: 1fr; }.toolbar .button { flex: 1; }.review-photo { width: 100%; height: 160px; }.publication-scopes { padding-inline: 15px; } }
.publication { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; }.review-media { display: flex; align-items: center; gap: 7px; }.review-thumbnail { position: relative; display: grid; width: 94px; height: 94px; flex: 0 0 auto; overflow: hidden; border: 1px solid #e1ddea; border-radius: 12px; padding: 6px; background: #f5f4f8; cursor: zoom-in; place-items: center; }.review-thumbnail img { display: block; max-width: 100%; max-height: 100%; object-fit: contain; }.review-thumbnail span { position: absolute; right: 5px; bottom: 5px; border-radius: 999px; padding: 2px 5px; color: #fff; background: rgb(37 43 62 / 75%); font-size: 7px; font-weight: 800; }.review-thumbnail--pattern img { image-rendering: pixelated; }.review-thumbnail--photo { width: 64px; }.review-thumbnail--missing { gap: 4px; border-style: dashed; color: #a24a55; background: #fff5f6; cursor: pointer; }.review-thumbnail--missing > span { position: static; display: grid; width: 25px; height: 25px; border-radius: 50%; padding: 0; color: #a24a55; background: #f8dfe2; font-size: 13px; place-items: center; }.review-thumbnail--missing small { margin: 0; color: #a24a55; font-family: inherit; font-size: 8px; }.publication-copy { min-width: 0; }.review-readiness { display: inline-flex; margin-top: 8px; border-radius: 999px; padding: 4px 7px; color: #2c8064; background: #eaf8f2; font-size: 8px; font-weight: 800; }.review-readiness.blocked { color: #a44c57; background: #fff0f2; }.review-actions { flex-wrap: wrap; justify-content: flex-end; }.review-actions button { white-space: nowrap; }@media (max-width: 920px) { .publication { grid-template-columns: auto minmax(0, 1fr); }.review-actions { grid-column: 1 / -1; justify-content: flex-start; padding-left: 0; } }@media (max-width: 620px) { .publication { display: grid; grid-template-columns: 1fr; }.review-media { width: 100%; }.review-thumbnail { width: min(68vw, 240px); height: 160px; }.review-thumbnail--photo { width: 88px; }.review-actions { display: grid; width: 100%; grid-template-columns: 1fr; }.review-actions .button { text-align: center; } }
.publication-search { display: flex; align-items: center; gap: 8px; padding: 0 24px 20px; }.publication-search .search { min-width: 220px; }.publication-search__result { flex: 0 0 auto; color: #777f93; font-family: var(--font-mono); font-size: 9px; white-space: nowrap; }@media (max-width: 620px) { .publication-search { flex-wrap: wrap; padding-inline: 15px; }.publication-search .search { flex-basis: 100%; }.publication-search__result { margin-right: auto; }.publication-search .button { flex: 1; } }
</style>
