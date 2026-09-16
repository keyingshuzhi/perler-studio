<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'

import type { PatternPreview } from '@/types/bead'
import type { PaletteColor } from '@/types/palette'

const props = defineProps<{
  sourceUrl: string
  sourceWidth: number
  sourceHeight: number
  preview?: PatternPreview
  colors: PaletteColor[]
  loading?: boolean
  focusX: number
  focusY: number
  subjectCrop: boolean
  activeIndex: number | null
  showHeatmap: boolean
}>()

const emit = defineEmits<{
  focus: [point: { x: number; y: number }]
  select: [index: number]
  updateHeatmap: [visible: boolean]
}>()

const patternCanvas = ref<HTMLCanvasElement>()
const sourceFrame = ref<HTMLElement>()
const colorByCode = computed(() => new Map(props.colors.map((color) => [color.code, color.hex])))
const qualityBasisLabel = computed(() => {
  const basis = props.preview?.diagnostics.quality_basis
  if (basis === 'measured_lab') return '实体 LAB'
  if (basis === 'mixed_lab') return '混合校准'
  if (basis === 'screen_rgb') return '屏幕参考'
  return '—'
})
const qualityBasisTitle = computed(() => {
  const basis = props.preview?.diagnostics.quality_basis
  if (basis === 'measured_lab') return '所有已评估格均使用 D65/2° 实体测量 LAB'
  if (basis === 'mixed_lab') return '有实测值的色号使用实体 LAB，其余色号回退到屏幕 RGB'
  if (basis === 'screen_rgb') return '当前色卡没有实体测量值，色差仅基于屏幕参考 RGB'
  return '当前没有可评估的参考格'
})
const targetAdvice = computed(() => {
  const report = props.preview?.color_report
  if (!report || report.target_met !== false) return ''
  if (report.oracle_target_reachable === false) {
    return `全色卡理论 P95 下界为 ${report.oracle_p95_delta_e_00 ?? '—'}，当前目标超出该色卡色域。`
  }
  return `理论目标可达；当前距离全色卡下界仍有 ${report.p95_oracle_gap ?? '—'} ΔE00，可继续增加色数或优化重点区域。`
})
const activeCell = computed(() => {
  if (!props.preview || props.activeIndex === null) return null
  const { grid_width: width, cells, diagnostics } = props.preview
  const index = props.activeIndex
  if (index < 0 || index >= cells.length) return null
  return {
    row: Math.floor(index / width) + 1,
    column: index % width + 1,
    color: cells[index],
    delta: (diagnostics.cell_delta_e_00_tenths[index] || 0) / 10,
  }
})
const focusMarkerStyle = computed(() => ({ left: `${props.focusX * 100}%`, top: `${props.focusY * 100}%` }))

function mixHex(hex: string, delta: number) {
  const normalized = hex.replace('#', '')
  const values = [0, 2, 4].map((offset) => Number.parseInt(normalized.slice(offset, offset + 2), 16))
  const intensity = Math.min(0.72, Math.max(0, delta / 18) * 0.72)
  const heated = values.map((value, index) => Math.round(value * (1 - intensity) + [238, 76, 76][index] * intensity))
  return `rgb(${heated.join(' ')})`
}

function drawPattern() {
  const canvas = patternCanvas.value
  const preview = props.preview
  if (!canvas || !preview) return
  const { grid_width: width, grid_height: height, cells, diagnostics } = preview
  canvas.width = width
  canvas.height = height
  const context = canvas.getContext('2d')
  if (!context) return
  context.imageSmoothingEnabled = false
  context.fillStyle = '#f3f5f9'
  context.fillRect(0, 0, width, height)
  for (let index = 0; index < cells.length; index += 1) {
    const code = cells[index]
    if (!code) continue
    const delta = (diagnostics.cell_delta_e_00_tenths[index] || 0) / 10
    context.fillStyle = props.showHeatmap ? mixHex(colorByCode.value.get(code) || '#ccd2de', delta) : colorByCode.value.get(code) || '#ccd2de'
    context.fillRect(index % width, Math.floor(index / width), 1, 1)
  }
  if (props.activeIndex !== null && props.activeIndex >= 0 && props.activeIndex < cells.length) {
    context.lineWidth = Math.max(1 / Math.max(width, height), 0.35)
    context.strokeStyle = '#172033'
    context.strokeRect(props.activeIndex % width, Math.floor(props.activeIndex / width), 1, 1)
    context.strokeStyle = '#ffffff'
    context.lineWidth /= 2
    context.strokeRect(props.activeIndex % width + context.lineWidth, Math.floor(props.activeIndex / width) + context.lineWidth, 1 - context.lineWidth * 2, 1 - context.lineWidth * 2)
  }
}

function chooseCell(event: PointerEvent) {
  const canvas = patternCanvas.value
  const preview = props.preview
  if (!canvas || !preview) return
  const rect = canvas.getBoundingClientRect()
  const column = Math.min(preview.grid_width - 1, Math.max(0, Math.floor((event.clientX - rect.left) / rect.width * preview.grid_width)))
  const row = Math.min(preview.grid_height - 1, Math.max(0, Math.floor((event.clientY - rect.top) / rect.height * preview.grid_height)))
  emit('select', row * preview.grid_width + column)
}

function chooseFocus(event: PointerEvent) {
  const frame = sourceFrame.value
  if (!frame || !props.sourceWidth || !props.sourceHeight) return
  const rect = frame.getBoundingClientRect()
  const sourceRatio = props.sourceWidth / props.sourceHeight
  const frameRatio = rect.width / rect.height
  const displayWidth = sourceRatio >= frameRatio ? rect.width : rect.height * sourceRatio
  const displayHeight = sourceRatio >= frameRatio ? rect.width / sourceRatio : rect.height
  const offsetX = (rect.width - displayWidth) / 2
  const offsetY = (rect.height - displayHeight) / 2
  const x = (event.clientX - rect.left - offsetX) / displayWidth
  const y = (event.clientY - rect.top - offsetY) / displayHeight
  if (x < 0 || x > 1 || y < 0 || y > 1) return
  emit('focus', { x: Number(x.toFixed(3)), y: Number(y.toFixed(3)) })
}

watch(
  () => [props.preview, props.colors, props.activeIndex, props.showHeatmap],
  async () => { await nextTick(); drawPattern() },
  { deep: true },
)
</script>

<template>
  <section class="conversion-preview card" aria-label="转换效果预览">
    <header class="preview-head">
      <div><p class="eyebrow">LIVE CONVERSION</p><h2>原图与图纸实时对比</h2><p>点击原图设定主体焦点；点击图纸查看单格色差。</p></div>
      <label class="heat-switch"><input :checked="showHeatmap" type="checkbox" @change="emit('updateHeatmap', ($event.target as HTMLInputElement).checked)"><span />色差热力图</label>
    </header>

    <div class="comparison-grid">
      <button ref="sourceFrame" class="source-frame" type="button" aria-label="点击原图设定主体焦点" @pointerdown="chooseFocus">
        <img :src="sourceUrl" alt="转换原图">
        <span class="source-tag">原图 · 点击定位焦点</span>
        <i class="focus-marker" :class="{ 'focus-marker--crop': subjectCrop }" :style="focusMarkerStyle" />
      </button>
      <div class="pattern-frame" :class="{ loading }">
        <canvas v-if="preview" ref="patternCanvas" class="pattern-canvas" :style="{ aspectRatio: `${preview.grid_width} / ${preview.grid_height}` }" aria-label="拼豆图纸预览" @pointerdown="chooseCell" />
        <div v-else class="preview-placeholder">{{ loading ? '正在计算转换预览…' : '调整图纸参数后显示实时预览' }}</div>
        <span class="source-tag">{{ showHeatmap ? '图纸 · 色差热力图' : '图纸 · 实物配色' }}</span>
      </div>
    </div>

    <div v-if="preview" class="diagnostic-bar">
      <dl><div><dt>平均 ΔE00</dt><dd>{{ preview.diagnostics.average_delta_e_00 }}</dd></div><div><dt>95% ΔE00</dt><dd :class="{ 'quality-miss': preview.color_report.target_met === false }">{{ preview.diagnostics.p95_delta_e_00 }}<small v-if="preview.color_report.target_p95_delta_e_00"> / ≤ {{ preview.color_report.target_p95_delta_e_00 }}</small></dd></div><div v-if="preview.color_report.oracle_p95_delta_e_00 != null"><dt>全色卡下界</dt><dd>{{ preview.color_report.oracle_p95_delta_e_00 }}<small v-if="preview.color_report.p95_oracle_gap != null"> / 差 {{ preview.color_report.p95_oracle_gap }}</small></dd></div><div><dt>最大 ΔE00</dt><dd>{{ preview.diagnostics.maximum_delta_e_00 }}</dd></div><div><dt>成品用色</dt><dd>{{ preview.statistics.used_color_count }}</dd></div><div :title="qualityBasisTitle"><dt>色差依据</dt><dd>{{ qualityBasisLabel }}<small v-if="preview.diagnostics.quality_basis === 'mixed_lab'"> / {{ preview.diagnostics.measured_evaluated_percent }}%</small></dd></div><div v-if="preview.color_report.cleanup_adjusted_cell_count"><dt>区域去杂</dt><dd>{{ preview.color_report.cleanup_adjusted_cell_count }} 格<small> / {{ preview.color_report.cleanup_adjusted_percent }}%</small></dd></div><div v-if="preview.color_report.structure_aware_enabled"><dt>重点结构</dt><dd>{{ preview.color_report.structure_protected_cell_count }} 格<small v-if="preview.color_report.structure_protected_p95_delta_e_00 != null"> / P95 {{ preview.color_report.structure_protected_p95_delta_e_00 }}</small></dd></div></dl>
      <p v-if="activeCell" class="cell-inspector">格 {{ activeCell.column }}, {{ activeCell.row }} · {{ activeCell.color || '空格' }} · ΔE00 {{ activeCell.delta.toFixed(1) }}</p>
      <p v-else-if="preview.color_report.target_met === false" class="cell-inspector cell-inspector--warning">{{ targetAdvice }}</p>
      <p v-else class="cell-inspector">{{ showHeatmap ? '颜色越偏红，表示该格与原图色差越大。' : '点击图纸可检查色号与色差。' }}</p>
    </div>
  </section>
</template>

<style scoped>
.conversion-preview { display: grid; gap: 17px; margin-top: 22px; padding: 22px; }.preview-head { display: flex; align-items: start; justify-content: space-between; gap: 16px; }.preview-head h2 { margin: 7px 0 4px; font-size: 17px; }.preview-head p:last-child { margin: 0; color: #778196; font-size: 11px; }.heat-switch { display: flex; flex: 0 0 auto; align-items: center; gap: 7px; padding: 7px 9px; border: 1px solid #dfdbea; border-radius: 9px; background: #faf9ff; color: #6255b2; font-size: 10px; font-weight: 800; white-space: nowrap; }.heat-switch input { position: absolute; opacity: 0; }.heat-switch span { position: relative; width: 25px; height: 14px; border-radius: 99px; background: #c8c6d6; transition: background .2s; }.heat-switch span::after { position: absolute; top: 2px; left: 2px; width: 10px; height: 10px; border-radius: 50%; background: #fff; box-shadow: 0 1px 3px rgb(20 25 50 / 22%); content: ''; transition: transform .2s; }.heat-switch input:checked + span { background: #7760df; }.heat-switch input:checked + span::after { transform: translateX(11px); }.comparison-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }.source-frame, .pattern-frame { position: relative; display: grid; min-width: 0; min-height: 235px; overflow: hidden; place-items: center; border: 1px solid #e0e2eb; border-radius: 13px; background: repeating-conic-gradient(#eef0f5 0 25%, #fff 0 50%) 50% / 18px 18px; }.source-frame { padding: 0; }.source-frame img { display: block; width: 100%; height: 100%; object-fit: contain; }.source-frame:hover { border-color: #9889e9; }.source-tag { position: absolute; top: 9px; left: 9px; padding: 4px 7px; border: 1px solid rgb(255 255 255 / 70%); border-radius: 99px; background: rgb(23 32 51 / 78%); color: #fff; font-family: var(--font-mono); font-size: 9px; font-weight: 700; pointer-events: none; }.focus-marker { position: absolute; width: 23px; height: 23px; border: 2px solid #fff; border-radius: 50%; box-shadow: 0 0 0 2px #6854e8, 0 2px 8px rgb(30 35 70 / 32%); pointer-events: none; transform: translate(-50%, -50%); }.focus-marker::before, .focus-marker::after { position: absolute; top: 50%; left: 50%; background: #6854e8; content: ''; transform: translate(-50%, -50%); }.focus-marker::before { width: 1px; height: 31px; }.focus-marker::after { width: 31px; height: 1px; }.focus-marker--crop { width: 34px; height: 34px; border-style: dashed; }.pattern-frame.loading { opacity: .72; }.pattern-canvas { display: block; width: 100%; height: 100%; object-fit: contain; image-rendering: pixelated; cursor: crosshair; }.preview-placeholder { max-width: 180px; color: #7e8798; font-size: 11px; line-height: 1.6; text-align: center; }.diagnostic-bar { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 12px; align-items: center; padding: 11px 12px; border: 1px solid #e8e6ef; border-radius: 11px; background: #fbfcff; }.diagnostic-bar dl { display: grid; grid-template-columns: repeat(auto-fit, minmax(82px, 1fr)); gap: 9px; padding: 0; margin: 0; }.diagnostic-bar dt { color: #8b93a3; font-size: 9px; font-weight: 700; }.diagnostic-bar dd { margin: 2px 0 0; color: #33405a; font-family: var(--font-mono); font-size: 13px; font-weight: 700; }.diagnostic-bar dd small { font-size: 8px; }.diagnostic-bar .quality-miss, .cell-inspector--warning { color: #b55a45; }.cell-inspector { max-width: 260px; margin: 0; color: #6a5cbb; font-size: 10px; line-height: 1.5; text-align: right; }
@media (max-width: 720px) { .preview-head { display: grid; }.heat-switch { justify-self: start; }.comparison-grid { grid-template-columns: 1fr; }.source-frame, .pattern-frame { min-height: 210px; }.diagnostic-bar { grid-template-columns: 1fr; }.diagnostic-bar dl { grid-template-columns: repeat(2, minmax(0, 1fr)); }.cell-inspector { max-width: none; text-align: left; } }
</style>
