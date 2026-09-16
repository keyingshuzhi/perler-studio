<script setup lang="ts">
import { reactive, ref } from 'vue'

import { exportCsv, exportPdf, exportPng, exportProject, exportSvg } from '@/api/exports'
import { mediaUrl } from '@/api/http'
import type { ExportKind } from '@/types/export'

const props = defineProps<{ projectId?: string; patternId?: string }>()
const emit = defineEmits<{ notice: [message: string]; error: [error: unknown] }>()
const kind = ref<ExportKind>('png')
const running = ref(false)
const formats: ExportKind[] = ['png', 'pdf', 'guide', 'svg', 'csv', 'project']
const settings = reactive({
  cell_size_px: 32,
  show_grid: true,
  show_coordinates: true,
  show_symbols: true,
  symbol_mode: 'short_code' as 'color_code' | 'short_code' | 'none',
  include_legend: true,
  paper_size: 'A4' as 'A4' | 'A3',
  orientation: 'landscape' as 'portrait' | 'landscape',
  mode: 'multipage' as 'single' | 'multipage',
  include_statistics: true,
  overlap_cells: 1,
  margin_mm: 10,
  assembly_board_width: 29,
  assembly_board_height: 29,
  assembly_overlap: 0,
})

async function submit() {
  running.value = true
  try {
    const target = props.projectId ? { project_id: props.projectId } : { pattern_id: props.patternId }
    const record = kind.value === 'png'
      ? await exportPng({ ...target, cell_size_px: settings.cell_size_px, show_grid: settings.show_grid, show_coordinates: settings.show_coordinates, show_symbols: settings.show_symbols, symbol_mode: settings.symbol_mode, background: 'white', include_legend: settings.include_legend })
      : kind.value === 'pdf' || kind.value === 'guide'
        ? await exportPdf({ ...target, paper_size: settings.paper_size, orientation: settings.orientation, mode: kind.value === 'guide' ? 'guide' : settings.mode, show_grid: settings.show_grid, show_coordinates: settings.show_coordinates, show_symbols: settings.show_symbols, symbol_mode: settings.symbol_mode, include_legend: settings.include_legend, include_statistics: settings.include_statistics, overlap_cells: settings.overlap_cells, margin_mm: settings.margin_mm, assembly_board_width: settings.assembly_board_width, assembly_board_height: settings.assembly_board_height, assembly_overlap: settings.assembly_overlap })
        : kind.value === 'svg'
          ? await exportSvg({ ...target, cell_size_px: settings.cell_size_px, show_grid: settings.show_grid, show_coordinates: settings.show_coordinates, show_symbols: settings.show_symbols, symbol_mode: settings.symbol_mode, background: 'white', include_legend: settings.include_legend })
          : kind.value === 'csv'
            ? await exportCsv({ ...target, include_waste: true })
            : await exportProject(target)
    if (record.file_url) window.open(mediaUrl(record.file_url), '_blank', 'noopener')
    emit('notice', '导出文件已生成')
  } catch (error) {
    emit('error', error)
  } finally {
    running.value = false
  }
}
</script>

<template>
  <section class="export card">
    <div class="export__head"><div><span class="eyebrow">交付中心</span><strong>导出图纸</strong></div><span class="tag">最新已保存版本</span></div>
    <div class="formats" role="tablist">
      <button v-for="item in formats" :key="item" :class="{ active: kind === item }" @click="kind = item">{{ item.toUpperCase() }}</button>
    </div>
    <template v-if="kind === 'png' || kind === 'svg'">
      <label class="field">单元格像素 <input v-model.number="settings.cell_size_px" type="number" min="8" max="256"><small>8–256 px</small></label>
      <p v-if="kind === 'svg'" class="hint">SVG 为可无限缩放的矢量图，适合印刷、激光雕刻和专业排版。</p>
    </template>
    <template v-if="kind === 'pdf' || kind === 'guide'">
      <div class="two-fields">
        <label class="field">纸张 <select v-model="settings.paper_size"><option>A4</option><option>A3</option></select></label>
        <label class="field">方向 <select v-model="settings.orientation"><option value="landscape">横向</option><option value="portrait">纵向</option></select></label>
      </div>
      <template v-if="kind === 'pdf'"><label class="field">分页 <select v-model="settings.mode"><option value="multipage">自动多页</option><option value="single">单页</option></select></label></template>
      <template v-else><p class="hint">制作说明书包含封面、材料、底板布局、安装顺序与带坐标的分页图纸。</p><div class="two-fields"><label class="field">底板宽度 <input v-model.number="settings.assembly_board_width" type="number" min="4" max="120"></label><label class="field">底板高度 <input v-model.number="settings.assembly_board_height" type="number" min="4" max="120"></label></div><label class="field">拼接重叠格 <input v-model.number="settings.assembly_overlap" type="number" min="0" max="12"></label></template>
    </template>
    <div v-if="kind === 'png' || kind === 'pdf' || kind === 'guide' || kind === 'svg'" class="checks">
      <label><input v-model="settings.show_grid" type="checkbox"> 网格</label>
      <label><input v-model="settings.show_coordinates" type="checkbox"> 坐标</label>
      <label><input v-model="settings.show_symbols" type="checkbox"> 色号</label>
      <label><input v-model="settings.include_legend" type="checkbox"> 图例</label>
    </div>
    <label v-if="kind === 'png' || kind === 'pdf' || kind === 'guide' || kind === 'svg'" class="field">格内标识 <select v-model="settings.symbol_mode"><option value="short_code">简写色号（推荐）</option><option value="color_code">完整色号</option></select></label>
    <button class="button" :disabled="running" @click="submit">{{ running ? '正在生成…' : kind === 'guide' ? '导出制作说明书' : `导出 ${kind.toUpperCase()}` }}</button>
  </section>
</template>

<style scoped>
.export { display: grid; gap: 17px; padding: 23px; border: 1px solid #e6e1fa; background: linear-gradient(145deg, #fff 0%, #fbfaff 100%); }.export__head { display: flex; align-items: start; justify-content: space-between; gap: 10px; }.export__head > div { display: grid; gap: 3px; }.export__head strong { color: #17213a; font-size: 20px; }.eyebrow { color: #7457e8; font-size: 10px; font-weight: 800; letter-spacing: .14em; }.tag { border: 1px solid #dcefdc; border-radius: 99px; padding: 5px 8px; color: #2d7959; background: #f2fbf5; font-size: 10px; white-space: nowrap; }
.formats { display: grid; grid-template-columns: repeat(6, 1fr); gap: 3px; padding: 4px; border: 1px solid #e9e6f3; border-radius: 11px; background: #f4f2fa; }.formats button { border: 0; border-radius: 8px; padding: 8px 3px; background: transparent; color: #77728d; font-family: var(--font-mono); font-size: 10px; font-weight: 700; transition: background .18s, color .18s, box-shadow .18s; }.formats button:hover { color: #4638a1; }.formats button.active { background: #fff; color: #4c37bd; box-shadow: 0 2px 7px rgb(48 39 101 / 12%); }
.field { display: grid; gap: 6px; color: #424b69; font-size: 12px; font-weight: 700; }.field input, .field select { width: 100%; border: 1px solid #dedbea; border-radius: 9px; padding: 9px; color: #28324d; background: #fff; font-weight: 500; }.field small { margin-top: -3px; color: #8b86a2; font-family: var(--font-mono); font-size: 10px; font-weight: 400; }.two-fields { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }.checks { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; padding: 12px; border-radius: 10px; background: #f7f6fb; color: #555d78; font-size: 12px; }.checks label { display: flex; align-items: center; gap: 6px; cursor: pointer; }.checks input { accent-color: #6950dd; }.hint { margin: -8px 0 0; border-left: 3px solid #a58fff; padding: 6px 9px; color: #67617f; background: #f7f5ff; font-size: 12px; line-height: 1.5; }.export > .button { min-height: 43px; margin-top: 1px; border-radius: 10px; background: linear-gradient(135deg, #5d42d0, #8e70ee); box-shadow: 0 8px 17px rgb(88 61 202 / 24%); }.export > .button:hover { transform: translateY(-1px); box-shadow: 0 11px 21px rgb(88 61 202 / 30%); }
</style>
