<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { mediaUrl } from '@/api/http'
import { getPublicPublication } from '@/api/publications'
import type { PublicPublication } from '@/types/publication'

const route = useRoute()
const publication = ref<PublicPublication>()
const error = ref('')
const loading = ref(true)
const previewFailed = ref(false)
const finishedPhotoFailed = ref(false)
let loadSequence = 0

const stats = computed(() => publication.value?.pattern.statistics)
const publishedAt = computed(() => {
  const value = publication.value?.publication.reviewed_at || publication.value?.publication.submitted_at
  if (!value) return ''
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '' : date.toLocaleDateString('zh-CN')
})

async function load(token: string) {
  const sequence = ++loadSequence
  loading.value = true
  error.value = ''
  publication.value = undefined
  previewFailed.value = false
  finishedPhotoFailed.value = false
  try {
    const result = await getPublicPublication(token)
    if (sequence === loadSequence) publication.value = result
  } catch (reason) {
    if (sequence === loadSequence) error.value = reason instanceof Error ? reason.message : '无法打开此作品'
  } finally {
    if (sequence === loadSequence) loading.value = false
  }
}

watch(
  () => String(route.params.token || ''),
  (token) => { if (token) void load(token) },
  { immediate: true },
)
</script>

<template>
  <main class="publication-page">
    <section v-if="loading" class="state card" aria-live="polite">正在载入作品…</section>
    <section v-else-if="error || !publication" class="state card">
      <span>!</span>
      <h1>作品不可用</h1>
      <p>{{ error || '作品尚未公开或已被撤回。' }}</p>
      <RouterLink class="button button--quiet" to="/gallery">返回作品社区</RouterLink>
    </section>

    <article v-else class="publication-detail">
      <header class="work-summary card">
        <RouterLink class="back-link" to="/gallery">← 返回作品社区</RouterLink>
        <p class="eyebrow">COMMUNITY PATTERN</p>
        <h1>{{ publication.publication.title }}</h1>
        <p class="description">{{ publication.publication.description || '一份经过平台审核的拼豆图纸作品。' }}</p>

        <div v-if="publication.publication.tags.length" class="tags">
          <span v-for="tag in publication.publication.tags" :key="tag">{{ tag }}</span>
        </div>

        <div class="author">
          <span>{{ publication.publication.author.display_name.slice(0, 1) || '创' }}</span>
          <div><b>{{ publication.publication.author.display_name }}</b><small>创作者{{ publishedAt ? ` · ${publishedAt} 发布` : '' }}</small></div>
        </div>

        <dl v-if="stats" class="work-stats">
          <div><dt>网格</dt><dd>{{ publication.pattern.grid_width }} × {{ publication.pattern.grid_height }}</dd></div>
          <div><dt>拼豆</dt><dd>{{ stats.total_beads.toLocaleString() }} 颗</dd></div>
          <div><dt>颜色</dt><dd>{{ stats.used_color_count }} 色</dd></div>
          <div><dt>成品尺寸</dt><dd>{{ stats.physical_width_mm }} × {{ stats.physical_height_mm }} mm</dd></div>
        </dl>

        <p class="review-note"><i>✓</i> 图纸已经平台审核，可按网格信息制作。</p>
      </header>

      <div class="work-media">
        <section class="pattern-preview card" aria-label="图纸预览">
          <div class="section-head"><div><span class="eyebrow">PATTERN PREVIEW</span><h2>图纸预览</h2></div><small>{{ publication.pattern.grid_width }} × {{ publication.pattern.grid_height }} 格</small></div>
          <figure>
            <img v-if="!previewFailed" :src="mediaUrl(publication.pattern.preview_url)" :alt="`${publication.publication.title} 拼豆图纸预览`" @error="previewFailed = true">
            <div v-else class="image-fallback"><span>图</span><b>图纸预览暂时无法显示</b><small>请刷新页面后重试</small></div>
          </figure>
        </section>

        <section v-if="publication.finished_photo_preview_url" class="finished-photo card">
          <div class="section-head"><div><span class="eyebrow">FINISHED WORK</span><h2>成品实拍</h2></div><small>由创作者上传</small></div>
          <figure>
            <img v-if="!finishedPhotoFailed" :src="mediaUrl(publication.finished_photo_preview_url)" :alt="`${publication.publication.title} 成品实拍`" loading="lazy" @error="finishedPhotoFailed = true">
            <div v-else class="image-fallback"><span>照</span><b>成品实拍暂时无法显示</b><small>请刷新页面后重试</small></div>
          </figure>
        </section>
      </div>

      <footer class="work-footer card">
        <div><b>喜欢这份作品？</b><span>浏览更多审核通过的图纸，寻找下一份拼豆灵感。</span></div>
        <RouterLink class="button" to="/gallery">继续浏览作品</RouterLink>
      </footer>
    </article>
  </main>
</template>

<style scoped>
.publication-page { width: min(1180px, calc(100% - 38px)); min-height: calc(100vh - 70px); margin: 0 auto; padding: clamp(28px, 5vw, 58px) 0 72px; }
.publication-detail { isolation: isolate; display: grid; grid-template-columns: minmax(280px, 350px) minmax(0, 1fr); gap: 18px; align-items: start; }
.work-summary { min-width: 0; overflow: hidden; padding: clamp(23px, 3vw, 34px); background: linear-gradient(145deg, #fff, #f8f6ff 58%, #eefaf5); }
.work-media { display: grid; min-width: 0; grid-template-columns: minmax(0, 1fr); gap: 18px; }
.back-link { display: inline-flex; margin-bottom: 28px; color: #756b8f; font-size: 10px; font-weight: 750; }
.eyebrow { margin: 0; color: #6d55d5; font-family: var(--font-mono); font-size: 9px; font-weight: 800; letter-spacing: .14em; }
.work-summary h1 { margin: 9px 0 10px; color: #202b46; font-family: Fraunces, Georgia, serif; font-size: clamp(29px, 4vw, 43px); letter-spacing: -1.7px; line-height: 1.08; overflow-wrap: anywhere; }
.description { margin: 0; color: #6e7890; font-size: 12px; line-height: 1.75; overflow-wrap: anywhere; }
.tags { display: flex; flex-wrap: wrap; gap: 5px; margin-top: 15px; }.tags span { border: 1px solid #e5e0f3; border-radius: 99px; padding: 4px 7px; color: #69618d; background: rgb(255 255 255 / 78%); font-size: 9px; }
.author { display: flex; align-items: center; gap: 9px; margin-top: 23px; padding-top: 17px; border-top: 1px solid #e8e4ef; }.author > span { display: grid; width: 34px; height: 34px; flex: 0 0 34px; place-items: center; border-radius: 11px; color: #fff; background: linear-gradient(135deg, #765ddd, #50a88b); font-size: 13px; font-weight: 850; }.author div { display: grid; min-width: 0; gap: 2px; }.author b { overflow: hidden; color: #35415c; font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }.author small { color: #8a93a5; font-size: 9px; }
.work-stats { display: grid; grid-template-columns: 1fr 1fr; gap: 7px; margin: 20px 0 0; }.work-stats div { min-width: 0; border: 1px solid #e7e3ef; border-radius: 10px; padding: 10px; background: rgb(255 255 255 / 72%); }.work-stats dt { color: #9299aa; font-size: 8px; }.work-stats dd { overflow: hidden; margin: 4px 0 0; color: #48536c; font-family: var(--font-mono); font-size: 10px; font-weight: 800; text-overflow: ellipsis; white-space: nowrap; }
.review-note { display: flex; align-items: flex-start; gap: 7px; margin: 17px 0 0; color: #558273; font-size: 9px; line-height: 1.55; }.review-note i { display: grid; width: 17px; height: 17px; flex: 0 0 17px; place-items: center; border-radius: 50%; color: #fff; background: #51a286; font-size: 9px; font-style: normal; }
.pattern-preview, .finished-photo { min-width: 0; overflow: hidden; }.section-head { display: flex; align-items: end; justify-content: space-between; gap: 12px; padding: 18px 21px; border-bottom: 1px solid #e7e4ee; background: #fff; }.section-head > div { display: grid; gap: 3px; }.section-head h2 { margin: 0; color: #34405a; font-size: 16px; }.section-head > small { flex: 0 0 auto; color: #818a9d; font-family: var(--font-mono); font-size: 9px; }
figure { display: flex; box-sizing: border-box; min-height: 420px; align-items: center; justify-content: center; margin: 0; padding: clamp(14px, 3vw, 28px); background: #f4f2ed; }figure img { display: block; width: auto; height: auto; max-width: 100%; max-height: min(72vh, 760px); object-fit: contain; border: 1px solid #ddd9e7; border-radius: 11px; background: #fff; box-shadow: 0 12px 30px rgb(35 42 70 / 13%); }
.pattern-preview figure { height: clamp(420px, 68vh, 760px); }
.pattern-preview figure img { max-height: 100%; image-rendering: pixelated; }
.finished-photo figure { min-height: 320px; background: linear-gradient(145deg, #f4fbf8, #f7f5ff); }.finished-photo figure img { width: auto; max-width: 100%; }
.image-fallback { display: grid; justify-items: center; gap: 5px; color: #838ca0; text-align: center; }.image-fallback > span { display: grid; width: 48px; height: 48px; place-items: center; border-radius: 15px; color: #745fce; background: #ebe7fb; font-size: 15px; font-weight: 800; }.image-fallback b { color: #566078; font-size: 12px; }.image-fallback small { font-size: 9px; }
.work-footer { grid-column: 1 / -1; display: flex; align-items: center; justify-content: space-between; gap: 20px; padding: 20px 22px; }.work-footer div { display: grid; gap: 3px; }.work-footer b { color: #39445d; font-size: 12px; }.work-footer span { color: #8991a3; font-size: 10px; }.work-footer .button { flex: 0 0 auto; }
.state { display: grid; width: min(520px, 100%); justify-items: center; gap: 9px; margin: clamp(55px, 12vh, 130px) auto 0; padding: 46px 28px; color: #727d92; text-align: center; }.state > span { display: grid; width: 42px; height: 42px; place-items: center; border-radius: 14px; color: #735add; background: #eeeaff; font-size: 18px; font-weight: 850; }.state h1, .state p { margin: 0; }.state h1 { color: #35405a; }.state p { font-size: 12px; }.state .button { margin-top: 7px; }
@media (max-width: 880px) { .publication-detail { grid-template-columns: minmax(0, 1fr); }.publication-detail > * { min-width: 0; }.work-footer { grid-column: auto; } }
@media (max-width: 560px) { .publication-page { width: min(100% - 24px, 1180px); padding-top: 18px; }.work-summary { padding: 22px 19px; }.back-link { margin-bottom: 22px; }.work-summary h1 { font-size: 31px; }.section-head { padding: 15px 16px; }figure { min-height: 280px; padding: 11px; }.pattern-preview figure { height: clamp(300px, 62vh, 520px); min-height: 0; }.finished-photo figure { min-height: 240px; }.work-footer { align-items: stretch; flex-direction: column; }.work-footer .button { justify-content: center; } }
</style>
