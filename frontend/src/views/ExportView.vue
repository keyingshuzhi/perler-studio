<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import ExportPanel from '@/components/export-panel/ExportPanel.vue'
import { useAppStore } from '@/stores/app'
import { useProjectStore } from '@/stores/project'

const route = useRoute()
const app = useAppStore()
const projects = useProjectStore()
const loading = ref(true)

onMounted(async () => {
  try {
    await projects.load(String(route.params.projectId))
  } catch (error) {
    app.showError(error)
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <main class="export-page">
    <template v-if="!loading && projects.current">
      <header class="export-page__hero">
        <p class="eyebrow">DELIVER YOUR PATTERN</p>
        <h1>导出 {{ projects.current.name }}</h1>
        <p>选择适合交付场景的文件格式。导出始终使用最后一次保存的图纸版本。</p>
      </header>
      <div class="export-layout">
        <ExportPanel :project-id="projects.current.id" @notice="app.showNotice" @error="app.showError" />
        <aside class="card delivery-guide">
          <div class="guide__head"><span>✦</span><div><p>FORMAT GUIDE</p><h2>交付建议</h2></div></div>
          <ol><li><b>PNG</b><span>屏幕查看与局部打印</span></li><li><b>PDF</b><span>分页打印，保留网格与色号</span></li><li><b>GUIDE</b><span>制作说明书：材料、底板、坐标与装配</span></li><li><b>SVG</b><span>无限缩放，适合印刷与设计软件</span></li><li><b>CSV</b><span>色号统计与建议损耗</span></li><li><b>JSON</b><span>工程文件备份与迁移</span></li></ol>
          <RouterLink class="button button--quiet" :to="`/editor/${projects.current.id}`">返回编辑器</RouterLink>
        </aside>
      </div>
    </template>
    <p v-else class="loading">正在加载项目…</p>
  </main>
</template>

<style scoped>
.export-page { max-width: 1010px; margin: 0 auto; padding: 58px 28px 72px; }.eyebrow { margin: 0; color: #7258e7; font-family: var(--font-mono); font-size: 11px; font-weight: 800; letter-spacing: .13em; }.export-page h1 { overflow: hidden; margin: 8px 0 11px; color: #17213a; font-size: clamp(34px, 5vw, 51px); letter-spacing: -.05em; text-overflow: ellipsis; white-space: nowrap; }.export-page__hero > p:last-child { max-width: 620px; color: #69728d; line-height: 1.65; }.export-layout { display: grid; grid-template-columns: minmax(330px, 1fr) 286px; gap: 20px; margin-top: 35px; align-items: start; }.delivery-guide { display: grid; gap: 18px; padding: 20px; border: 1px solid #e4e0f2; background: #fff; }.guide__head { display: flex; align-items: center; gap: 10px; }.guide__head > span { display: grid; width: 34px; height: 34px; place-items: center; border-radius: 10px; color: #fff; background: linear-gradient(135deg, #7054e5, #a98cf8); box-shadow: 0 6px 13px rgb(85 59 187 / 23%); }.guide__head p { margin: 0 0 2px; color: #7965d5; font-family: var(--font-mono); font-size: 9px; font-weight: 800; letter-spacing: .11em; }.delivery-guide h2 { margin: 0; color: #202a44; font-size: 18px; }.delivery-guide ol { display: grid; gap: 9px; margin: 0; padding: 0; list-style: none; }.delivery-guide li { display: grid; grid-template-columns: 40px 1fr; gap: 7px; align-items: baseline; border-bottom: 1px solid #f0eef5; padding-bottom: 9px; font-size: 11px; }.delivery-guide li:last-child { border-bottom: 0; padding-bottom: 0; }.delivery-guide b { color: #6249ce; font-family: var(--font-mono); font-size: 10px; }.delivery-guide li span { color: #6f7790; line-height: 1.45; }.delivery-guide .button { width: 100%; margin-top: 1px; text-align: center; }.loading { padding: 80px; color: #7b8196; text-align: center; } @media (max-width: 700px) { .export-page { padding: 38px 18px 55px; }.export-layout { grid-template-columns: 1fr; }.export-page h1 { white-space: normal; } }
</style>
