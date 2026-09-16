<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { listPublications } from '@/api/publications'
import { mediaUrl } from '@/api/http'
import { useAppStore } from '@/stores/app'
import type { PublicationSummary } from '@/types/publication'

const app = useAppStore()
const search = ref('')
const items = ref<PublicationSummary[]>([])
const total = ref(0)
const page = ref(1)
const loading = ref(false)
const hasMore = computed(() => items.value.length < total.value)

async function load(reset = false) {
  if (loading.value) return
  if (reset) { page.value = 1; items.value = [] }
  loading.value = true
  try {
    const result = await listPublications(search.value.trim(), page.value)
    total.value = result.total
    items.value.push(...result.items)
  } catch (error) { app.showError(error) } finally { loading.value = false }
}

async function loadMore() { page.value += 1; await load() }

onMounted(() => { void load(true) })
</script>

<template>
  <main class="gallery-page">
    <header class="gallery-hero"><div><p class="eyebrow">COMMUNITY GALLERY</p><h1>发现可制作的<br><em>拼豆灵感。</em></h1><p>这里展示的是经平台审核的创作者图纸。喜欢一个作品，就从它的网格、颜色和细节开始研究。</p></div><form class="search card" @submit.prevent="load(true)"><label for="gallery-search">搜索作品或创作者</label><div><input id="gallery-search" v-model="search" maxlength="120" placeholder="例如：猫咪、挂件、像素风…"><button type="submit" :disabled="loading">搜索</button></div></form></header>
    <section class="gallery-meta"><span>{{ total ? `已收录 ${total} 份审核作品` : '作品库正在等待第一份公开作品' }}</span><span>仅展示审核通过的图纸</span></section>
    <section v-if="items.length" class="gallery-grid"><RouterLink v-for="item in items" :key="item.id" class="gallery-card card" :to="`/p/${item.public_token}`"><figure><div class="gallery-card__preview"><img :src="mediaUrl(item.preview_url)" :alt="`${item.title} 图纸预览`"></div><img v-if="item.finished_photo_preview_url" class="physical-thumb" :src="mediaUrl(item.finished_photo_preview_url)" alt="作品成品实拍"><figcaption>{{ item.grid_width }} × {{ item.grid_height }}</figcaption></figure><div class="gallery-card__body"><p class="creator">{{ item.author.display_name }} · {{ new Date(item.reviewed_at || item.submitted_at).toLocaleDateString() }}</p><h2>{{ item.title }}</h2><p class="description">{{ item.description || '一份经平台审核的拼豆创作。' }}</p><div class="tags"><span v-for="tag in item.tags" :key="tag">{{ tag }}</span><span v-if="item.finished_photo_preview_url" class="physical">实拍案例</span></div><div class="stats"><span>{{ item.statistics.total_beads.toLocaleString() }} 颗</span><span>{{ item.statistics.used_color_count }} 色</span><b>查看图纸 →</b></div></div></RouterLink></section>
    <section v-else-if="!loading" class="empty card"><span>✦</span><h2>{{ search ? '没有匹配的作品' : '第一份公开图纸即将出现' }}</h2><p>{{ search ? '试试更简短的关键词，或搜索创作者名称。' : '创作者提交图纸并通过审核后，会在这里展示。' }}</p><button v-if="search" class="button button--quiet" type="button" @click="search = ''; load(true)">清除搜索</button></section>
    <div v-if="hasMore" class="load-more"><button class="button button--quiet" type="button" :disabled="loading" @click="loadMore">{{ loading ? '载入中…' : '加载更多作品' }}</button></div>
    <p v-else-if="loading" class="loading">正在载入作品…</p>
  </main>
</template>

<style scoped>
.gallery-page { width: min(1200px, calc(100% - 38px)); margin: 0 auto; padding: clamp(39px, 7vw, 82px) 0 82px; }.gallery-hero { display: grid; grid-template-columns: 1.25fr .75fr; gap: clamp(30px, 7vw, 92px); align-items: end; }.eyebrow { margin: 0; color: #735ae3; font-family: var(--font-mono); font-size: 10px; font-weight: 800; letter-spacing: .14em; }.gallery-hero h1 { margin: 9px 0; color: #1d2844; font-family: Fraunces, Georgia, serif; font-size: clamp(38px, 6vw, 67px); letter-spacing: -2.8px; line-height: .98; }.gallery-hero h1 em { color: #6751d7; font-style: normal; }.gallery-hero > div > p:last-child { max-width: 570px; margin: 17px 0 0; color: #718097; font-size: 14px; line-height: 1.7; }.search { display: grid; gap: 8px; padding: 16px; background: rgb(255 255 255 / 78%); }.search label { color: #68728a; font-size: 11px; font-weight: 800; }.search > div { display: flex; gap: 6px; }.search input { min-width: 0; flex: 1; border: 1px solid #dfdce8; border-radius: 9px; padding: 10px; color: #3c4760; background: #fbfaff; font: inherit; font-size: 11px; }.search button { border: 0; border-radius: 8px; padding: 0 12px; color: #fff; background: #6550cc; font: inherit; font-size: 11px; font-weight: 800; }.gallery-meta { display: flex; justify-content: space-between; gap: 12px; margin: 42px 0 16px; color: #7d879b; font-family: var(--font-mono); font-size: 10px; }.gallery-meta span:last-child { color: #4f9b86; }.gallery-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; }.gallery-card { overflow: hidden; transition: border-color .2s ease, box-shadow .2s ease, transform .2s ease; }.gallery-card:hover { border-color: #cfc7f7; box-shadow: var(--shadow-md); transform: translateY(-4px); }.gallery-card figure { position: relative; box-sizing: border-box; height: 270px; margin: 0; overflow: hidden; padding: 15px; background: #f4f2ed; }.gallery-card__preview { display: flex; width: 100%; height: 100%; min-width: 0; min-height: 0; align-items: center; justify-content: center; overflow: hidden; }.gallery-card__preview img { display: block; width: auto; height: auto; max-width: 100%; max-height: 100%; object-fit: contain; object-position: center; image-rendering: pixelated; transition: filter .25s ease; }.gallery-card:hover .gallery-card__preview img { filter: saturate(1.04); }.physical-thumb { position: absolute; right: 10px; bottom: 10px; width: 54px; height: 54px; border: 2px solid #fff; border-radius: 10px; object-fit: cover; box-shadow: 0 4px 11px rgb(23 31 57 / 22%); }.gallery-card figcaption { position: absolute; right: 9px; top: 9px; border: 1px solid rgb(255 255 255 / 55%); border-radius: 7px; padding: 4px 6px; color: #5c6680; background: rgb(255 255 255 / 92%); font-family: var(--font-mono); font-size: 9px; }.gallery-card__body { padding: 17px; }.creator { margin: 0; color: #7863d4; font-family: var(--font-mono); font-size: 9px; }.gallery-card h2 { overflow: hidden; margin: 7px 0 5px; color: #28334e; font-size: 17px; text-overflow: ellipsis; white-space: nowrap; }.description { display: -webkit-box; min-height: 36px; margin: 0; overflow: hidden; color: #758096; font-size: 11px; line-height: 1.6; -webkit-box-orient: vertical; -webkit-line-clamp: 2; }.tags { display: flex; min-height: 20px; flex-wrap: wrap; gap: 4px; margin-top: 8px; }.tags span { border-radius: 99px; padding: 3px 6px; color: #706b91; background: #f1eff8; font-size: 8px; }.tags .physical { color: #35836a; background: #eaf8f1; }.stats { display: flex; align-items: center; gap: 7px; margin-top: 9px; color: #8790a3; font-family: var(--font-mono); font-size: 9px; }.stats b { margin-left: auto; color: #604bc0; font-family: inherit; font-weight: 800; }.empty { display: grid; justify-items: center; gap: 7px; padding: 70px 20px; color: #7b869a; text-align: center; }.empty span { color: #6650d3; font-size: 27px; }.empty h2, .empty p { margin: 0; }.empty h2 { color: #33405a; font-size: 20px; }.empty p { font-size: 12px; }.empty .button { margin-top: 8px; }.load-more, .loading { display: flex; justify-content: center; margin-top: 24px; }.loading { color: #8d96a8; font-family: var(--font-mono); font-size: 11px; }@media (max-width: 850px) { .gallery-hero { grid-template-columns: 1fr; }.gallery-grid { grid-template-columns: repeat(2, 1fr); } }@media (max-width: 560px) { .gallery-page { width: min(100% - 28px, 1200px); }.gallery-grid { grid-template-columns: 1fr; }.gallery-card figure { height: 290px; }.gallery-meta { align-items: start; flex-direction: column; margin-top: 28px; } }
</style>
