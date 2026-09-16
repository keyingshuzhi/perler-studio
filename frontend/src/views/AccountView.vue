<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { deletePublication, listFavoritePublicationsPage, listMyPublicationsPage, resumePublication, unfavoritePublication, withdrawPublication } from '@/api/publications'
import InfiniteScrollTrigger from '@/components/common/InfiniteScrollTrigger.vue'
import { useAppStore } from '@/stores/app'
import { useAuthStore } from '@/stores/auth'
import type { Publication, PublicationSummary } from '@/types/publication'

const router = useRouter()
const app = useAppStore()
const auth = useAuthStore()
const displayName = ref(auth.user?.display_name || '')
const currentPassword = ref('')
const nextPassword = ref('')
const confirmPassword = ref('')
const savingProfile = ref(false)
const savingPassword = ref(false)
const publications = ref<Publication[]>([])
const favorites = ref<PublicationSummary[]>([])
const publicationLoading = ref(false)
const favoriteLoading = ref(false)
const publicationPage = ref(1)
const favoritePage = ref(1)
const publicationTotal = ref(0)
const favoriteTotal = ref(0)
const approvedTotal = ref(0)
const rejectedTotal = ref(0)
const workingPublicationId = ref('')
const communityTab = ref<'publications' | 'favorites'>('publications')
const settingsTab = ref<'profile' | 'security'>('profile')

const activePublications = computed(() => publications.value)
const communityLoading = computed(() => communityTab.value === 'publications' ? publicationLoading.value : favoriteLoading.value)
const hasMoreCommunity = computed(() => communityTab.value === 'publications' ? publications.value.length < publicationTotal.value : favorites.value.length < favoriteTotal.value)
const avatarLetter = computed(() => (auth.user?.display_name || '?').slice(0, 1).toUpperCase())
const joinedAt = computed(() => auth.user ? new Date(auth.user.created_at).toLocaleDateString('zh-CN') : '—')

function publicationStatus(status: Publication['status']) {
  return ({ pending: '审核中', approved: '已公开', rejected: '需修改', withdrawn: '仅自己可见' }[status])
}

function formatDate(value: string) {
  return new Date(value).toLocaleDateString('zh-CN', { year: 'numeric', month: 'short', day: 'numeric' })
}

watch(() => auth.user?.display_name, (value) => { displayName.value = value || '' })

async function saveProfile() {
  if (!displayName.value.trim()) { app.showError('请输入显示名称'); return }
  savingProfile.value = true
  try {
    await auth.updateProfile(displayName.value.trim())
    app.showNotice('个人资料已更新')
  } catch (error) { app.showError(error) } finally { savingProfile.value = false }
}

async function savePassword() {
  if (nextPassword.value.length < 8) { app.showError('新密码至少需要 8 位'); return }
  if (nextPassword.value !== confirmPassword.value) { app.showError('两次输入的新密码不一致'); return }
  savingPassword.value = true
  try {
    await auth.changePassword(currentPassword.value, nextPassword.value)
    app.showNotice('密码已更新，请使用新密码重新登录')
    await router.replace({ path: '/auth', query: { next: '/account' } })
  } catch (error) { app.showError(error) } finally { savingPassword.value = false }
}

async function loadMyPublications(reset = false) {
  if (publicationLoading.value) return
  const targetPage = reset ? 1 : publicationPage.value + 1
  publicationLoading.value = true
  try {
    const result = await listMyPublicationsPage(targetPage, 12)
    publicationPage.value = targetPage
    publicationTotal.value = result.total
    approvedTotal.value = result.status_counts.approved || 0
    rejectedTotal.value = result.status_counts.rejected || 0
    publications.value = reset ? result.items : [...publications.value, ...result.items]
  } catch (error) { app.showError(error) } finally { publicationLoading.value = false }
}

async function loadFavorites(reset = false) {
  if (favoriteLoading.value) return
  const targetPage = reset ? 1 : favoritePage.value + 1
  favoriteLoading.value = true
  try {
    const result = await listFavoritePublicationsPage(targetPage, 12)
    favoritePage.value = targetPage
    favoriteTotal.value = result.total
    favorites.value = reset ? result.items : [...favorites.value, ...result.items]
  } catch (error) { app.showError(error) } finally { favoriteLoading.value = false }
}

async function loadCommunity() {
  await Promise.all([loadMyPublications(true), loadFavorites(true)])
}

function loadMoreCommunity() {
  void (communityTab.value === 'publications' ? loadMyPublications() : loadFavorites())
}

async function withdrawWork(publication: Publication) {
  const action = publication.status === 'pending' ? '撤回审核申请' : '下架公开作品'
  if (!window.confirm(`确定${action}吗？作品会立即变为仅自己可见。`)) return
  workingPublicationId.value = publication.id
  try {
    await withdrawPublication(publication.id)
    await loadMyPublications(true)
    app.showNotice(publication.status === 'pending' ? '已撤回审核申请' : '作品已下架，社区链接已失效')
  } catch (error) { app.showError(error) } finally { workingPublicationId.value = '' }
}

async function deleteWork(publication: Publication) {
  const visibilityWarning = publication.status === 'approved' ? '公开页面会立即失效，' : ''
  if (!window.confirm(`永久删除“${publication.title}”？${visibilityWarning}该发布记录和审核信息将无法恢复，但原项目不会被删除。`)) return
  workingPublicationId.value = publication.id
  try {
    await deletePublication(publication.id)
    await loadMyPublications(true)
    app.showNotice('社区作品已永久删除，原项目仍可继续编辑')
  } catch (error) { app.showError(error) } finally { workingPublicationId.value = '' }
}

async function continueEditing(publication: Publication) {
  workingPublicationId.value = publication.id
  try {
    const project = await resumePublication(publication.id)
    await router.push(`/editor/${project.id}`)
  } catch (error) { app.showError(error) } finally { workingPublicationId.value = '' }
}

async function removeFavorite(publication: PublicationSummary) {
  workingPublicationId.value = publication.id
  try {
    await unfavoritePublication(publication.public_token)
    await loadFavorites(true)
    app.showNotice('已取消收藏')
  } catch (error) { app.showError(error) } finally { workingPublicationId.value = '' }
}

onMounted(() => { void loadCommunity() })
</script>

<template>
  <main class="account-page">
    <header class="page-header">
      <div>
        <p class="eyebrow">CREATOR WORKSPACE</p>
        <h1>个人中心</h1>
        <p class="page-description">集中管理你的创作者资料、社区作品与灵感收藏。</p>
      </div>
      <RouterLink class="project-entry" to="/projects"><span>进入我的图纸</span><i aria-hidden="true">→</i></RouterLink>
    </header>

    <section class="account-summary card">
      <div class="summary-identity">
        <div class="avatar" aria-hidden="true">{{ avatarLetter }}</div>
        <div class="identity-copy">
          <div class="identity-heading">
            <h2>{{ auth.user?.display_name || '创作者' }}</h2>
            <span class="role-badge" :class="{ admin: auth.isAdmin }">{{ auth.isAdmin ? '管理员' : '创作者' }}</span>
          </div>
          <p>{{ auth.user?.email }}</p>
          <small>加入平台于 {{ joinedAt }}</small>
        </div>
      </div>

      <dl class="summary-stats">
        <div><dt>发布记录</dt><dd>{{ publicationTotal }}</dd></div>
        <div><dt>公开作品</dt><dd>{{ approvedTotal }}</dd></div>
        <div><dt>灵感收藏</dt><dd>{{ favoriteTotal }}</dd></div>
      </dl>

      <nav class="summary-links" aria-label="个人中心快捷入口">
        <RouterLink to="/projects"><span>我的图纸</span><i>项目与版本</i><b>→</b></RouterLink>
        <RouterLink to="/gallery"><span>灵感社区</span><i>发现与收藏</i><b>→</b></RouterLink>
        <RouterLink v-if="auth.isAdmin" to="/admin"><span>平台管理</span><i>审核与用户</i><b>→</b></RouterLink>
      </nav>
    </section>

    <div class="dashboard-grid">
      <section class="community-panel card">
        <div class="section-header">
          <div>
            <p class="section-kicker">COMMUNITY ASSETS</p>
            <h2>作品与收藏</h2>
            <p>查看发布状态、处理审核反馈，也可以随时返回编辑器继续完善。</p>
          </div>
          <button class="refresh-button" type="button" :disabled="communityLoading" @click="loadCommunity">
            <span :class="{ spinning: communityLoading }" aria-hidden="true">↻</span>{{ communityLoading ? '正在同步' : '同步数据' }}
          </button>
        </div>

        <nav class="asset-tabs" aria-label="社区资产分类">
          <button type="button" :class="{ active: communityTab === 'publications' }" :aria-pressed="communityTab === 'publications'" @click="communityTab = 'publications'">我的发布 <b>{{ publicationTotal }}</b></button>
          <button type="button" :class="{ active: communityTab === 'favorites' }" :aria-pressed="communityTab === 'favorites'" @click="communityTab = 'favorites'">我的收藏 <b>{{ favoriteTotal }}</b></button>
        </nav>

        <div v-if="communityTab === 'publications' && activePublications.length" class="asset-list">
          <article v-for="publication in activePublications" :key="publication.id" class="asset-row">
            <div class="asset-content">
              <div class="asset-meta"><span class="status-badge" :class="publication.status">{{ publicationStatus(publication.status) }}</span><time :datetime="publication.submitted_at">提交于 {{ formatDate(publication.submitted_at) }}</time></div>
              <h3>{{ publication.title }}</h3>
              <p v-if="publication.review_note" class="review-note"><strong>{{ publication.status === 'rejected' ? '审核反馈' : '状态说明' }}</strong>{{ publication.review_note }}</p>
              <p v-else class="asset-description">{{ publication.description || '暂未填写作品说明。' }}</p>
              <div class="asset-tags"><span v-for="tag in publication.tags.slice(0, 4)" :key="tag"># {{ tag }}</span><span v-if="!publication.tags.length">未设置标签</span></div>
            </div>
            <div class="asset-actions">
              <a v-if="publication.status === 'approved'" :href="`/p/${publication.public_token}`" target="_blank" rel="noopener">查看公开页</a>
              <button class="primary-action" type="button" :disabled="workingPublicationId === publication.id" @click="continueEditing(publication)">{{ workingPublicationId === publication.id ? '正在打开…' : publication.status === 'rejected' || publication.status === 'withdrawn' ? '重新编辑' : '继续编辑' }}</button>
              <button v-if="publication.status === 'approved' || publication.status === 'pending'" class="danger-action" type="button" :disabled="workingPublicationId === publication.id" @click="withdrawWork(publication)">{{ workingPublicationId === publication.id ? '处理中…' : publication.status === 'pending' ? '撤回审核' : '下架作品' }}</button>
              <button class="delete-action" type="button" :disabled="workingPublicationId === publication.id" @click="deleteWork(publication)">{{ workingPublicationId === publication.id ? '处理中…' : '删除作品' }}</button>
            </div>
          </article>
        </div>

        <div v-else-if="communityTab === 'favorites' && favorites.length" class="asset-list">
          <article v-for="publication in favorites" :key="publication.id" class="asset-row">
            <div class="asset-content">
              <div class="asset-meta"><span class="status-badge favorite">已收藏</span><span>{{ publication.grid_width }} × {{ publication.grid_height }} 格</span></div>
              <h3>{{ publication.title }}</h3>
              <p class="asset-description">由 {{ publication.author.display_name }} 发布</p>
              <div class="asset-tags"><span v-for="tag in publication.tags.slice(0, 4)" :key="tag"># {{ tag }}</span><span v-if="!publication.tags.length">社区拼豆作品</span></div>
            </div>
            <div class="asset-actions">
              <a :href="`/p/${publication.public_token}`" target="_blank" rel="noopener">查看作品</a>
              <button class="danger-action" type="button" :disabled="workingPublicationId === publication.id" @click="removeFavorite(publication)">{{ workingPublicationId === publication.id ? '处理中…' : '取消收藏' }}</button>
            </div>
          </article>
        </div>

        <div v-else class="empty-state">
          <div class="empty-icon" aria-hidden="true">{{ communityTab === 'publications' ? '稿' : '藏' }}</div>
          <h3>{{ communityTab === 'publications' ? '还没有社区发布记录' : '还没有收藏作品' }}</h3>
          <p>{{ communityTab === 'publications' ? '完成图纸后，可在编辑器中选择公开发布或仅自己可见。' : '前往灵感社区收藏喜欢的作品，建立自己的创作参考库。' }}</p>
          <RouterLink :to="communityTab === 'publications' ? '/projects' : '/gallery'">{{ communityTab === 'publications' ? '管理我的图纸' : '浏览灵感社区' }} →</RouterLink>
        </div>
        <InfiniteScrollTrigger v-if="communityTab === 'publications' ? activePublications.length : favorites.length" :has-more="hasMoreCommunity" :loading="communityLoading" end-text="内容已全部加载" @load="loadMoreCommunity" />
      </section>

      <aside class="settings-panel card">
        <div class="settings-heading">
          <p class="section-kicker">ACCOUNT SETTINGS</p>
          <h2>账户设置</h2>
          <p>资料和安全设置分区展示，减少页面滚动与干扰。</p>
        </div>

        <nav class="settings-tabs" aria-label="账户设置分类">
          <button type="button" :class="{ active: settingsTab === 'profile' }" @click="settingsTab = 'profile'">个人资料</button>
          <button type="button" :class="{ active: settingsTab === 'security' }" @click="settingsTab = 'security'">登录安全</button>
        </nav>

        <form v-if="settingsTab === 'profile'" class="settings-form" @submit.prevent="saveProfile">
          <div class="form-intro"><h3>创作者资料</h3><p>显示名称将用于社区署名和作品交付。</p></div>
          <label class="form-field"><span>显示名称</span><input v-model.trim="displayName" required maxlength="80" autocomplete="name"></label>
          <div class="readonly-field"><span>登录邮箱</span><strong>{{ auth.user?.email }}</strong><small>邮箱暂不支持自行修改</small></div>
          <button class="save-button" :disabled="savingProfile">{{ savingProfile ? '正在保存…' : '保存个人资料' }}</button>
        </form>

        <form v-else class="settings-form" @submit.prevent="savePassword">
          <div class="form-intro"><h3>修改登录密码</h3><p>更新后所有已登录设备都会安全退出。</p></div>
          <p v-if="auth.isAdmin" class="admin-note">其他用户的密码请前往“平台管理”重置。</p>
          <label class="form-field"><span>当前密码</span><input v-model="currentPassword" required type="password" autocomplete="current-password"></label>
          <label class="form-field"><span>新密码</span><input v-model="nextPassword" required minlength="8" maxlength="128" type="password" autocomplete="new-password" placeholder="至少 8 位字符"></label>
          <label class="form-field"><span>确认新密码</span><input v-model="confirmPassword" required minlength="8" maxlength="128" type="password" autocomplete="new-password"></label>
          <button class="save-button" :disabled="savingPassword">{{ savingPassword ? '正在更新…' : '更新登录密码' }}</button>
        </form>

        <div v-if="rejectedTotal" class="attention-card"><span>{{ rejectedTotal }}</span><p><strong>个作品需要修改</strong>查看左侧审核反馈后重新编辑并提交。</p></div>
      </aside>
    </div>
  </main>
</template>

<style scoped>
.account-page { width: min(1240px, calc(100% - 48px)); margin: 0 auto; padding: clamp(42px, 6vw, 76px) 0 88px; }
.page-header { display: flex; align-items: end; justify-content: space-between; gap: 28px; }
.eyebrow, .section-kicker { margin: 0; color: #7159d9; font-family: var(--font-mono); font-size: 11px; font-weight: 800; letter-spacing: .14em; }
.page-header h1 { margin: 8px 0 7px; color: #1e2944; font-family: Fraunces, Georgia, serif; font-size: clamp(42px, 5vw, 60px); letter-spacing: -2.5px; line-height: 1; }
.page-description { margin: 0; color: #6d7890; font-size: 15px; line-height: 1.7; }
.project-entry { display: inline-flex; min-height: 46px; align-items: center; gap: 20px; border-radius: 13px; padding: 0 18px; color: #fff; background: linear-gradient(135deg, #6049ca, #7b62e4); font-size: 13px; font-weight: 800; text-decoration: none; box-shadow: 0 12px 28px rgb(91 70 190 / 20%); transition: transform .18s ease, box-shadow .18s ease; }
.project-entry:hover { transform: translateY(-2px); box-shadow: 0 16px 32px rgb(91 70 190 / 26%); }
.project-entry i { font-size: 18px; font-style: normal; }

.account-summary { display: grid; grid-template-columns: minmax(280px, 1fr) auto minmax(260px, .72fr); align-items: center; gap: 26px; margin-top: 32px; overflow: hidden; padding: 24px; background: radial-gradient(circle at 92% 0%, rgb(96 208 179 / 13%), transparent 31%), radial-gradient(circle at 8% 100%, rgb(128 102 232 / 10%), transparent 34%), #fff; box-shadow: 0 14px 38px rgb(40 47 80 / 8%); }
.summary-identity { display: flex; min-width: 0; align-items: center; gap: 16px; }
.avatar { display: grid; width: 66px; height: 66px; flex: 0 0 66px; place-items: center; border: 3px solid #fff; border-radius: 21px; color: #fff; background: linear-gradient(140deg, #7c65e7, #55c9ad); font-family: Fraunces, Georgia, serif; font-size: 30px; box-shadow: 0 10px 24px rgb(86 73 169 / 23%); }
.identity-copy { min-width: 0; }
.identity-heading { display: flex; align-items: center; gap: 9px; }
.identity-heading h2 { overflow: hidden; margin: 0; color: #28334d; font-size: 19px; text-overflow: ellipsis; white-space: nowrap; }
.role-badge { flex: 0 0 auto; border: 1px solid #ccefe4; border-radius: 999px; padding: 4px 8px; color: #2d8069; background: #ecf9f4; font-size: 11px; font-weight: 800; }
.role-badge.admin { border-color: #eee0ae; color: #8a681a; background: #fff8df; }
.identity-copy p { overflow: hidden; margin: 5px 0 4px; color: #647088; font-size: 13px; text-overflow: ellipsis; white-space: nowrap; }
.identity-copy small { color: #949cad; font-size: 11px; }
.summary-stats { display: grid; grid-template-columns: repeat(3, minmax(80px, 1fr)); margin: 0; border-right: 1px solid #e9e6f0; border-left: 1px solid #e9e6f0; }
.summary-stats div { display: grid; gap: 3px; padding: 4px 18px; text-align: center; }
.summary-stats dt { color: #8b94a6; font-size: 11px; white-space: nowrap; }
.summary-stats dd { grid-row: 1; margin: 0; color: #2e3851; font-family: Fraunces, Georgia, serif; font-size: 25px; font-weight: 700; line-height: 1; }
.summary-links { display: grid; grid-template-columns: repeat(2, minmax(110px, 1fr)); gap: 8px; }
.summary-links a { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 3px 10px; border: 1px solid #e7e3ef; border-radius: 11px; padding: 10px 11px; color: #435069; background: rgb(255 255 255 / 72%); text-decoration: none; transition: border-color .16s ease, background .16s ease, transform .16s ease; }
.summary-links a:hover { border-color: #cec6ed; background: #f8f6ff; transform: translateY(-1px); }
.summary-links span { font-size: 12px; font-weight: 800; }
.summary-links i { grid-column: 1; color: #9299aa; font-size: 10px; font-style: normal; }
.summary-links b { grid-column: 2; grid-row: 1 / 3; align-self: center; color: #725ad5; font-size: 14px; }

.dashboard-grid { display: grid; grid-template-columns: minmax(0, 1fr) 350px; align-items: start; gap: 18px; margin-top: 18px; }
.community-panel, .settings-panel { min-width: 0; padding: 25px; }
.section-header { display: flex; align-items: start; justify-content: space-between; gap: 20px; }
.section-header h2, .settings-heading h2 { margin: 5px 0 4px; color: #28334d; font-size: 20px; letter-spacing: -.3px; }
.section-header > div > p:last-child, .settings-heading > p:last-child { max-width: 560px; margin: 0; color: #7c8699; font-size: 12px; line-height: 1.6; }
.refresh-button { display: inline-flex; min-height: 36px; flex: 0 0 auto; align-items: center; gap: 7px; border: 1px solid #ded9ed; border-radius: 10px; padding: 0 11px; color: #5d4db1; background: #faf9ff; font-size: 11px; font-weight: 800; }
.refresh-button:disabled { cursor: wait; opacity: .65; }
.spinning { display: inline-block; animation: spin .75s linear infinite; }
.asset-tabs, .settings-tabs { display: flex; gap: 5px; border-radius: 12px; padding: 4px; background: #f3f1f7; }
.asset-tabs { width: fit-content; margin-top: 20px; }
.asset-tabs button, .settings-tabs button { border: 0; border-radius: 9px; color: #798297; background: transparent; font-size: 12px; font-weight: 800; transition: color .16s ease, background .16s ease, box-shadow .16s ease; }
.asset-tabs button { min-height: 34px; padding: 0 13px; }
.asset-tabs button.active, .settings-tabs button.active { color: #5743b7; background: #fff; box-shadow: 0 3px 10px rgb(45 36 90 / 9%); }
.asset-tabs b { display: inline-grid; min-width: 20px; height: 20px; margin-left: 5px; place-items: center; border-radius: 10px; padding: 0 5px; color: #726a90; background: #e9e6f0; font-size: 10px; }
.asset-tabs button.active b { color: #fff; background: #725bd7; }
.asset-list { display: grid; gap: 11px; margin-top: 16px; }
.asset-row { display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: center; gap: 18px; border: 1px solid #e7e4ed; border-radius: 14px; padding: 17px 18px; background: linear-gradient(135deg, #fff, #fdfcff); transition: border-color .18s ease, box-shadow .18s ease, transform .18s ease; }
.asset-row:hover { border-color: #d4cdef; transform: translateY(-1px); box-shadow: 0 10px 24px rgb(45 37 85 / 8%); }
.asset-content { min-width: 0; }
.asset-meta { display: flex; align-items: center; gap: 9px; color: #98a0af; font-size: 10px; }
.status-badge { border-radius: 999px; padding: 4px 8px; font-size: 10px; font-weight: 800; }
.status-badge.pending { color: #92611e; background: #fff3dc; }
.status-badge.approved { color: #2f7b62; background: #e9f8f1; }
.status-badge.rejected { color: #aa4e5a; background: #fff0f2; }
.status-badge.withdrawn { color: #657087; background: #eef1f5; }
.status-badge.favorite { color: #8b681e; background: #fff7df; }
.asset-row h3 { overflow: hidden; margin: 8px 0 5px; color: #36415a; font-size: 15px; text-overflow: ellipsis; white-space: nowrap; }
.asset-description, .review-note { margin: 0; color: #7a8498; font-size: 12px; line-height: 1.55; }
.review-note { max-width: 680px; border-left: 3px solid #e4a1a9; padding-left: 9px; color: #8f4b54; }
.review-note strong { margin-right: 5px; font-size: 11px; }
.asset-tags { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 9px; }
.asset-tags span { border-radius: 999px; padding: 4px 7px; color: #756d91; background: #f1eff6; font-size: 10px; }
.asset-actions { display: flex; max-width: 100%; flex: 0 0 auto; flex-wrap: nowrap; justify-content: flex-end; gap: 7px; overflow-x: auto; scrollbar-width: thin; }
.asset-actions a, .asset-actions button { display: inline-flex; min-height: 34px; align-items: center; justify-content: center; border: 1px solid #e2deeb; border-radius: 9px; padding: 0 10px; color: #59647b; background: #fff; font-size: 11px; font-weight: 800; text-decoration: none; white-space: nowrap; }
.asset-actions .primary-action { border-color: #e1dcf8; color: #5a46b6; background: #f3f0ff; }
.asset-actions .danger-action { border-color: transparent; color: #ac535d; background: #fff1f2; }
.asset-actions .delete-action { border-color: #efd7da; color: #a33f4b; background: #fff; }
.asset-actions button:disabled { cursor: wait; opacity: .58; }

.empty-state { display: grid; justify-items: center; gap: 8px; margin-top: 16px; border: 1px dashed #ddd8e8; border-radius: 15px; padding: 42px 24px; color: #818a9c; background: #fdfcff; text-align: center; }
.empty-icon { display: grid; width: 48px; height: 48px; place-items: center; border-radius: 15px; color: #634fc2; background: #eeeaff; font-size: 15px; font-weight: 900; }
.empty-state h3 { margin: 4px 0 0; color: #414c64; font-size: 15px; }
.empty-state p { max-width: 470px; margin: 0; font-size: 12px; line-height: 1.6; }
.empty-state a { margin-top: 3px; color: #5b47b5; font-size: 12px; font-weight: 800; text-decoration: none; }

.settings-panel { position: sticky; top: 82px; }
.settings-tabs { display: grid; grid-template-columns: 1fr 1fr; margin-top: 19px; }
.settings-tabs button { min-height: 36px; }
.settings-form { display: grid; gap: 14px; margin-top: 19px; }
.form-intro { border-bottom: 1px solid #ebe8f0; padding-bottom: 14px; }
.form-intro h3 { margin: 0 0 4px; color: #3a455e; font-size: 15px; }
.form-intro p { margin: 0; color: #858ea0; font-size: 11px; line-height: 1.55; }
.form-field { display: grid; gap: 7px; color: #606b81; font-size: 12px; font-weight: 700; }
.form-field input { width: 100%; min-height: 43px; box-sizing: border-box; border: 1px solid #ddd9e6; border-radius: 10px; padding: 0 12px; color: #303b54; outline: none; background: #fff; font: inherit; font-weight: 500; transition: border-color .16s ease, box-shadow .16s ease; }
.form-field input:focus { border-color: #8873e0; box-shadow: 0 0 0 3px rgb(116 89 217 / 12%); }
.readonly-field { display: grid; gap: 4px; border: 1px solid #e9e5ef; border-radius: 11px; padding: 12px; background: #faf9fc; }
.readonly-field span { color: #8a93a4; font-size: 10px; }
.readonly-field strong { overflow: hidden; color: #555f75; font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
.readonly-field small { color: #a0a6b2; font-size: 10px; }
.save-button { min-height: 43px; border: 0; border-radius: 11px; color: #fff; background: #273552; font-size: 12px; font-weight: 800; box-shadow: 0 8px 18px rgb(39 53 82 / 15%); }
.save-button:hover:not(:disabled) { background: #344466; }
.save-button:disabled { cursor: wait; opacity: .6; }
.admin-note { margin: 0; border-left: 3px solid #8f79e3; padding: 9px 10px; color: #64569d; background: #f6f3ff; font-size: 11px; line-height: 1.5; }
.attention-card { display: grid; grid-template-columns: auto 1fr; align-items: center; gap: 11px; margin-top: 18px; border: 1px solid #f0d5d9; border-radius: 12px; padding: 11px; background: #fff7f8; }
.attention-card > span { display: grid; width: 34px; height: 34px; place-items: center; border-radius: 10px; color: #a34e59; background: #ffe6e9; font-size: 14px; font-weight: 900; }
.attention-card p { margin: 0; color: #8a6066; font-size: 10px; line-height: 1.5; }
.attention-card strong { display: block; color: #8f4650; font-size: 11px; }

@keyframes spin { to { transform: rotate(360deg); } }
@media (max-width: 1080px) {
  .account-summary { grid-template-columns: minmax(280px, 1fr) auto; }
  .summary-links { grid-column: 1 / -1; grid-template-columns: repeat(3, minmax(0, 1fr)); }
}
@media (max-width: 900px) {
  .dashboard-grid { grid-template-columns: 1fr; }
  .settings-panel { position: static; }
  .account-summary { grid-template-columns: 1fr; }
  .summary-stats { border: 0; border-top: 1px solid #e9e6f0; border-bottom: 1px solid #e9e6f0; padding: 15px 0; }
  .settings-form { max-width: 560px; }
}
@media (max-width: 680px) {
  .account-page { width: min(100% - 28px, 1240px); padding: 32px 0 64px; }
  .page-header { align-items: stretch; flex-direction: column; }
  .page-header h1 { font-size: 43px; }
  .project-entry { justify-content: space-between; }
  .account-summary, .community-panel, .settings-panel { padding: 19px; }
  .summary-links { grid-template-columns: 1fr; }
  .section-header { align-items: stretch; flex-direction: column; }
  .refresh-button { align-self: start; }
  .asset-row { grid-template-columns: 1fr; }
  .asset-actions { width: 100%; max-width: none; justify-content: flex-start; border-top: 1px solid #ece9f1; padding: 12px 0 3px; }
}
@media (max-width: 420px) {
  .account-page { width: min(100% - 20px, 1240px); }
  .summary-identity { align-items: flex-start; }
  .avatar { width: 56px; height: 56px; flex-basis: 56px; border-radius: 18px; font-size: 26px; }
  .identity-heading { align-items: flex-start; flex-direction: column; gap: 5px; }
  .summary-stats div { padding: 4px 8px; }
  .summary-stats dt { font-size: 10px; }
  .asset-tabs { width: 100%; }
  .asset-tabs button { flex: 1; }
  .asset-actions a, .asset-actions button { flex: 0 0 auto; }
}
</style>
