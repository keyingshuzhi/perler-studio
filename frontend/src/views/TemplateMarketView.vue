<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { favoritePublication, listFavoritePublicationTokens, listFavoritePublicationsPage, listPublications, remixPublication, unfavoritePublication } from '@/api/publications'
import { mediaUrl } from '@/api/http'
import InfiniteScrollTrigger from '@/components/common/InfiniteScrollTrigger.vue'
import { useAppStore } from '@/stores/app'
import type { PublicationSummary } from '@/types/publication'

const app = useAppStore()
const router = useRouter()
const query = ref('')
const publicItems = ref<PublicationSummary[]>([])
const favoriteItems = ref<PublicationSummary[]>([])
const favoriteTokens = ref(new Set<string>())
const total = ref(0)
const page = ref(1)
const loading = ref(false)
const favoriteTotal = ref(0)
const favoritePage = ref(1)
const favoriteLoading = ref(false)
const workingToken = ref('')
const favoritesOnly = ref(false)
const hasMore = computed(() => favoritesOnly.value ? favoriteItems.value.length < favoriteTotal.value : publicItems.value.length < total.value)
const currentLoading = computed(() => favoritesOnly.value ? favoriteLoading.value : loading.value)
const items = computed(() => favoritesOnly.value ? favoriteItems.value : publicItems.value)

async function load(reset = false) {
  if (loading.value) return
  const targetPage = reset ? 1 : page.value + 1
  loading.value = true
  try {
    const result = await listPublications(query.value.trim(), targetPage)
    total.value = result.total
    page.value = targetPage
    publicItems.value = reset ? result.items : [...publicItems.value, ...result.items]
  } catch (error) { app.showError(error) } finally { loading.value = false }
}
async function loadFavorites(reset = false) {
  if (favoriteLoading.value) return
  const targetPage = reset ? 1 : favoritePage.value + 1
  favoriteLoading.value = true
  try {
    const result = await listFavoritePublicationsPage(targetPage, 12, query.value.trim())
    favoriteTotal.value = result.total
    favoritePage.value = targetPage
    favoriteItems.value = reset ? result.items : [...favoriteItems.value, ...result.items]
  } catch (error) { app.showError(error) } finally { favoriteLoading.value = false }
}
async function loadFavoriteTokens() {
  try { favoriteTokens.value = new Set((await listFavoritePublicationTokens()).items) } catch (error) { app.showError(error) }
}
async function toggleFavorite(item: PublicationSummary) {
  workingToken.value = item.public_token
  try {
    if (favoriteTokens.value.has(item.public_token)) {
      await unfavoritePublication(item.public_token)
      favoriteTokens.value.delete(item.public_token)
      favoriteItems.value = favoriteItems.value.filter((entry) => entry.public_token !== item.public_token)
      favoriteTotal.value = Math.max(0, favoriteTotal.value - 1)
    } else {
      await favoritePublication(item.public_token)
      favoriteTokens.value.add(item.public_token)
      favoriteItems.value = [item, ...favoriteItems.value]
      favoriteTotal.value += 1
    }
    favoriteTokens.value = new Set(favoriteTokens.value)
    await loadFavorites(true)
  } catch (error) { app.showError(error) } finally { workingToken.value = '' }
}
async function remix(item: PublicationSummary) {
  workingToken.value = item.public_token
  try {
    const result = await remixPublication(item.public_token)
    app.showNotice('已创建可编辑副本，现在可以替换颜色与细节')
    await router.push(`/editor/${result.project.id}`)
  } catch (error) { app.showError(error) } finally { workingToken.value = '' }
}
function switchCollection(onlyFavorites: boolean) {
  favoritesOnly.value = onlyFavorites
  void (onlyFavorites ? loadFavorites(true) : load(true))
}
function search() { void (favoritesOnly.value ? loadFavorites(true) : load(true)) }
function loadNext() { void (favoritesOnly.value ? loadFavorites() : load()) }

onMounted(async () => {
  await Promise.all([load(true), loadFavorites(true), loadFavoriteTokens()])
})
</script>

<template>
  <main class="market-page">
    <header class="market-hero"><div><p class="eyebrow">EDITABLE TEMPLATE MARKET</p><h1>把灵感变成<br><em>你的作品。</em></h1><p>所有模板都来自已审核的社区图纸。收藏常用灵感，一键创建独立可编辑副本，再把颜色、构图和细节做成自己的版本。</p></div><div class="hero-actions"><RouterLink class="button button--quiet" to="/create">从内置模板创作</RouterLink><RouterLink class="button button--quiet" to="/gallery">浏览作品社区</RouterLink></div></header>
    <section class="market-toolbar card"><label class="search"><span>⌕</span><input v-model="query" maxlength="120" type="search" placeholder="搜索模板、创作者或主题标签" @keyup.enter="search"></label><div class="collection"><button type="button" :class="{ active: !favoritesOnly }" @click="switchCollection(false)">全部模板</button><button type="button" :class="{ active: favoritesOnly }" @click="switchCollection(true)">★ 我的收藏 {{ favoriteTotal }}</button></div></section>
    <section class="market-meta"><span>{{ favoritesOnly ? `已收藏 ${favoriteTotal} 个模板` : `可再创作模板 ${total} 个` }}</span><span>向下滚动将自动加载更多模板</span></section>
    <section v-if="items.length" class="market-grid"><article v-for="item in items" :key="item.id" class="template-card card"><figure><div class="template-card__preview"><img :src="mediaUrl(item.preview_url)" :alt="`${item.title} 图纸预览`"></div><img v-if="item.finished_photo_preview_url" class="physical-thumb" :src="mediaUrl(item.finished_photo_preview_url)" alt="作品成品实拍"><figcaption>{{ item.grid_width }} × {{ item.grid_height }} 格</figcaption></figure><div class="template-card__body"><p class="creator">{{ item.author.display_name }} · {{ new Date(item.reviewed_at || item.submitted_at).toLocaleDateString() }}</p><h2>{{ item.title }}</h2><p>{{ item.description || '一份可以继续延展的社区拼豆模板。' }}</p><div class="tags"><span v-for="tag in item.tags" :key="tag">{{ tag }}</span><span v-if="item.finished_photo_preview_url" class="physical">实拍案例</span></div><div class="card-actions"><button class="favorite" type="button" :class="{ active: favoriteTokens.has(item.public_token) }" :disabled="workingToken === item.public_token" @click="toggleFavorite(item)">{{ favoriteTokens.has(item.public_token) ? '★ 已收藏' : '☆ 收藏' }}</button><button class="button" type="button" :disabled="workingToken === item.public_token" @click="remix(item)">{{ workingToken === item.public_token ? '创建中…' : '基于此模板再创作 →' }}</button></div></div></article></section>
    <section v-else-if="!currentLoading" class="empty card"><span>✦</span><h2>{{ favoritesOnly ? '还没有收藏模板' : '没有匹配的社区模板' }}</h2><p>{{ favoritesOnly ? '在模板卡片上点击收藏，常用灵感会保存在这里。' : '可以换一个关键词，或先从内置模板开始创作。' }}</p><RouterLink class="button button--quiet" to="/create">前往创作工作室</RouterLink></section>
    <InfiniteScrollTrigger v-if="items.length" :has-more="hasMore" :loading="currentLoading" end-text="模板已全部加载" @load="loadNext" />
  </main>
</template>

<style scoped>
.market-page { width: min(1200px, calc(100% - 38px)); margin: 0 auto; padding: clamp(40px, 7vw, 80px) 0 82px; }.market-hero { display: flex; align-items: end; justify-content: space-between; gap: 30px; }.eyebrow { margin: 0; color: #735ae3; font-family: var(--font-mono); font-size: 10px; font-weight: 800; letter-spacing: .14em; }.market-hero h1 { margin: 9px 0; color: #1d2844; font-family: Fraunces, Georgia, serif; font-size: clamp(38px, 6vw, 67px); letter-spacing: -2.8px; line-height: .98; }.market-hero h1 em { color: #5d9f89; font-style: normal; }.market-hero p:last-child { max-width: 590px; margin: 17px 0 0; color: #718097; font-size: 14px; line-height: 1.7; }.hero-actions { display: flex; flex: 0 0 auto; flex-wrap: wrap; justify-content: end; gap: 7px; }.market-toolbar { display: grid; grid-template-columns: minmax(230px, 1fr) auto; gap: 10px; align-items: center; margin-top: 34px; padding: 11px; }.search { display: flex; align-items: center; gap: 7px; border: 1px solid #dfdce8; border-radius: 9px; padding: 0 10px; color: #7661d0; }.search input { width: 100%; min-height: 36px; border: 0; outline: 0; color: #3c4760; background: transparent; font: inherit; font-size: 11px; }.collection { display: flex; gap: 5px; }.collection button, .favorite { border: 1px solid #e1ddec; border-radius: 8px; padding: 8px 9px; background: #fff; color: #6f7890; font-size: 10px; font-weight: 800; white-space: nowrap; }.collection button.active, .favorite.active { border-color: #d6c8f7; color: #5b45c4; background: #f4f1ff; }.market-meta { display: flex; justify-content: space-between; gap: 12px; margin: 19px 0 14px; color: #7d879b; font-family: var(--font-mono); font-size: 10px; }.market-meta span:last-child { color: #4f9b86; }.market-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; }.template-card { overflow: hidden; }.template-card figure { position: relative; display: grid; height: 214px; place-items: center; margin: 0; overflow: hidden; background: repeating-conic-gradient(#edf0f5 0 25%, #fff 0 50%) 50% / 18px 18px; }.template-card figure > img:first-child { width: 100%; height: 100%; object-fit: contain; }.physical-thumb { position: absolute; right: 10px; bottom: 10px; width: 58px; height: 58px; border: 2px solid #fff; border-radius: 11px; object-fit: cover; box-shadow: 0 5px 13px rgb(27 34 64 / 22%); }.template-card figcaption { position: absolute; top: 9px; left: 9px; border-radius: 7px; padding: 4px 6px; color: #5c6680; background: rgb(255 255 255 / 90%); font-family: var(--font-mono); font-size: 9px; }.template-card__body { display: grid; gap: 7px; padding: 16px; }.creator { margin: 0; color: #7863d4; font-family: var(--font-mono); font-size: 9px; }.template-card h2 { overflow: hidden; margin: 0; color: #28334e; font-size: 17px; text-overflow: ellipsis; white-space: nowrap; }.template-card__body > p:not(.creator) { display: -webkit-box; min-height: 34px; margin: 0; overflow: hidden; color: #758096; font-size: 11px; line-height: 1.55; -webkit-box-orient: vertical; -webkit-line-clamp: 2; }.tags { display: flex; min-height: 20px; flex-wrap: wrap; gap: 4px; }.tags span { border-radius: 99px; padding: 3px 6px; color: #6f6992; background: #f1eff8; font-size: 8px; }.tags .physical { color: #35836a; background: #eaf8f1; }.card-actions { display: grid; grid-template-columns: auto 1fr; gap: 6px; align-items: center; margin-top: 2px; }.card-actions .button { min-height: 34px; padding: 6px; font-size: 10px; }.empty { display: grid; justify-items: center; gap: 8px; padding: 70px 20px; text-align: center; }.empty > span { color: #6650d3; font-size: 27px; }.empty h2, .empty p { margin: 0; }.empty h2 { color: #33405a; font-size: 20px; }.empty p { color: #7b869a; font-size: 12px; }.load-more { display: flex; justify-content: center; margin-top: 24px; }@media (max-width: 850px) { .market-hero { align-items: start; flex-direction: column; }.hero-actions { justify-content: start; }.market-grid { grid-template-columns: repeat(2, 1fr); } }@media (max-width: 590px) { .market-page { width: min(100% - 28px, 1200px); }.market-toolbar { grid-template-columns: 1fr; }.collection button { flex: 1; }.market-grid { grid-template-columns: 1fr; }.market-meta { align-items: start; flex-direction: column; } }
.template-card figure { display: block; box-sizing: border-box; height: 270px; padding: 15px; background: #f4f2ed; }
.template-card__preview { display: flex; width: 100%; height: 100%; min-width: 0; min-height: 0; align-items: center; justify-content: center; overflow: hidden; }
.template-card__preview img { display: block; width: auto; height: auto; max-width: 100%; max-height: 100%; object-fit: contain; object-position: center; image-rendering: pixelated; }
@media (max-width: 590px) { .template-card figure { height: 290px; } }
</style>
