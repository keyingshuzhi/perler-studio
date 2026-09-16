<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { exportPdf } from '@/api/exports'
import { mediaUrl } from '@/api/http'
import { getProductionPlan } from '@/api/patterns'
import { getPegboardTemplates } from '@/api/presets'
import type { PegboardTemplate, ProductionPlan, ProductionStrategy } from '@/types/design'
import type { ProductionGuideProgress } from '@/types/project'

const props = defineProps<{ patternId: string; projectId: string; progress?: ProductionGuideProgress }>()
const emit = defineEmits<{ updateProgress: [progress: ProductionGuideProgress]; notice: [message: string]; error: [error: unknown] }>()

const templates = ref<PegboardTemplate[]>([])
const templateId = ref('midi-square-29')
const overlap = ref(0)
const strategy = ref<ProductionStrategy>('color')
const beadsPerHour = ref(360)
const plan = ref<ProductionPlan>()
const loading = ref(false)
const exporting = ref(false)
const error = ref('')
const activeBoardId = ref('')
const activeSection = ref<'assembly' | 'progress' | 'materials'>('assembly')
const boardMapViewport = ref<HTMLElement>()
const completedSteps = ref<string[]>([])
const animating = ref(false)
let animationTimer: number | undefined
let reloadTimer: number | undefined
let loadSequence = 0

const selectedBoard = computed(() => plan.value?.assembly.boards.find((board) => board.id === activeBoardId.value) || plan.value?.assembly.boards[0])
const completedSet = computed(() => new Set(completedSteps.value))
const completedCount = computed(() => plan.value?.make_steps.filter((step) => completedSet.value.has(step.id)).length || 0)
const progressPercent = computed(() => plan.value?.make_steps.length ? Math.round(completedCount.value / plan.value.make_steps.length * 100) : 0)
const completedBeads = computed(() => plan.value?.make_steps.filter((step) => completedSet.value.has(step.id)).reduce((sum, step) => sum + step.bead_count, 0) || 0)
const selectedTemplate = computed(() => templates.value.find((template) => template.id === templateId.value))
const selectedBoardIndex = computed(() => plan.value?.assembly.boards.findIndex((board) => board.id === selectedBoard.value?.id) ?? -1)
const boardMapStyle = computed(() => {
  const columns = Math.max(1, plan.value?.assembly.board_columns || 1)
  return {
    gridTemplateColumns: `repeat(${columns}, minmax(52px, 1fr))`,
    minWidth: `${columns * 56}px`,
  }
})
const pegLayoutStyle = computed(() => selectedTemplate.value ? {
  '--board-columns': String(selectedTemplate.value.board_width),
  '--board-rows': String(selectedTemplate.value.board_height),
} : {})

function stopAnimation() {
  if (animationTimer) window.clearInterval(animationTimer)
  animationTimer = undefined
  animating.value = false
}

async function load() {
  const sequence = ++loadSequence
  loading.value = true
  error.value = ''
  try {
    const result = await getProductionPlan(props.patternId, {
      board_template_id: templateId.value,
      overlap: overlap.value,
      strategy: strategy.value,
      beads_per_hour: beadsPerHour.value,
    })
    if (sequence !== loadSequence) return
    plan.value = result
    if (!result.assembly.boards.some((board) => board.id === activeBoardId.value)) activeBoardId.value = result.assembly.boards[0]?.id || ''
  } catch (reason) {
    if (sequence === loadSequence) error.value = reason instanceof Error ? reason.message : '无法生成制作计划'
  } finally {
    if (sequence === loadSequence) loading.value = false
  }
}

function scheduleLoad() {
  if (reloadTimer) window.clearTimeout(reloadTimer)
  reloadTimer = window.setTimeout(() => { reloadTimer = undefined; void load() }, 220)
}

function moveBoard(offset: number) {
  const boards = plan.value?.assembly.boards || []
  if (!boards.length) return
  const next = Math.max(0, Math.min(boards.length - 1, selectedBoardIndex.value + offset))
  activeBoardId.value = boards[next].id
}

function persistProgress() {
  emit('updateProgress', { version: 1, completed_step_ids: completedSteps.value })
}

function toggleStep(id: string) {
  completedSteps.value = completedSet.value.has(id)
    ? completedSteps.value.filter((item) => item !== id)
    : [...completedSteps.value, id]
  persistProgress()
}

function playInstallation() {
  if (!plan.value?.assembly.installation_steps.length) return
  stopAnimation()
  const steps = plan.value.assembly.installation_steps
  let index = Math.max(0, steps.findIndex((step) => step.board_id === activeBoardId.value))
  activeBoardId.value = steps[index].board_id || ''
  animating.value = true
  animationTimer = window.setInterval(() => {
    index += 1
    if (index >= steps.length) { stopAnimation(); return }
    activeBoardId.value = steps[index].board_id || ''
  }, 900)
}

async function exportGuide() {
  exporting.value = true
  try {
    const template = selectedTemplate.value
    if (!template) return
    const record = await exportPdf({
      project_id: props.projectId,
      paper_size: 'A4',
      orientation: 'landscape',
      mode: 'guide',
      show_grid: true,
      show_coordinates: true,
      show_symbols: true,
      symbol_mode: 'short_code',
      include_legend: true,
      include_statistics: true,
      overlap_cells: 1,
      margin_mm: 10,
      assembly_board_width: template.board_width,
      assembly_board_height: template.board_height,
      assembly_overlap: overlap.value,
    })
    if (record.file_url) window.open(mediaUrl(record.file_url), '_blank', 'noopener')
    emit('notice', '制作说明书已生成')
  } catch (reason) {
    emit('error', reason)
  } finally {
    exporting.value = false
  }
}

onMounted(async () => {
  try {
    templates.value = await getPegboardTemplates()
    if (!templates.value.some((template) => template.id === templateId.value)) templateId.value = templates.value[0]?.id || ''
  } catch (reason) { error.value = reason instanceof Error ? reason.message : '无法读取底板模板' }
  await load()
})
watch([templateId, overlap, strategy, beadsPerHour, () => props.patternId], () => { stopAnimation(); scheduleLoad() })
watch(activeBoardId, async () => {
  await nextTick()
  boardMapViewport.value?.querySelector<HTMLElement>('[aria-current="true"]')?.scrollIntoView({ block: 'nearest', inline: 'nearest' })
})
watch(() => props.progress, (progress) => { completedSteps.value = progress?.completed_step_ids || [] }, { immediate: true, deep: true })
onBeforeUnmount(() => {
  stopAnimation()
  if (reloadTimer) window.clearTimeout(reloadTimer)
  loadSequence += 1
})
</script>

<template>
  <section class="production-guide">
    <header class="guide-head">
      <div><span class="eyebrow">MAKE PLAN</span><strong>制作指导</strong></div>
      <button type="button" :disabled="exporting || loading" @click="exportGuide">{{ exporting ? '正在生成…' : '导出说明书' }}</button>
    </header>
    <details class="guide-settings">
      <summary><span>制作参数</span><small>{{ selectedTemplate?.name_zh || '请选择底板' }} · 重叠 {{ overlap }} 格</small></summary>
      <div class="guide-controls"><label>底板模板<select v-model="templateId"><option v-for="template in templates" :key="template.id" :value="template.id">{{ template.name_zh }}</option></select></label><label>重叠格<input v-model.number="overlap" type="number" min="0" max="12"></label><label>制作顺序<select v-model="strategy"><option value="color">按颜色</option><option value="region">按分区</option><option value="rows">按行</option><option value="columns">按列</option></select></label><label>每小时颗数<input v-model.number="beadsPerHour" type="number" min="30" max="3000" step="30"></label></div>
      <p v-if="selectedTemplate" class="template-note">{{ selectedTemplate.usable_holes.toLocaleString() }} 孔 · {{ selectedTemplate.description }}</p>
    </details>
    <p v-if="loading" class="muted" aria-live="polite">正在更新底板、材料与步骤…</p><p v-if="error" class="error">{{ error }}</p>
    <template v-if="plan">
      <div class="plan-summary"><div><b>{{ plan.assembly.board_count }}</b><span>块底板</span></div><div><b>{{ Math.ceil(plan.estimated_minutes / 60) || 0 }}</b><span>小时估时</span></div><div><b>{{ plan.make_steps.length }}</b><span>制作步骤</span></div><div><b>{{ plan.materials.coverage_percent === null ? '—' : `${plan.materials.coverage_percent}%` }}</b><span>库存覆盖</span></div></div>
      <nav class="guide-sections" aria-label="制作指导内容">
        <button type="button" :class="{ active: activeSection === 'assembly' }" @click="activeSection = 'assembly'"><span>底板拼接</span><b>{{ plan.assembly.board_count }}</b></button>
        <button type="button" :class="{ active: activeSection === 'progress' }" @click="activeSection = 'progress'"><span>制作步骤</span><b>{{ plan.make_steps.length }}</b></button>
        <button type="button" :class="{ active: activeSection === 'materials' }" @click="activeSection = 'materials'"><span>材料缺口</span><b>{{ plan.materials.shortages.length }}</b></button>
      </nav>
      <section v-if="activeSection === 'assembly'" class="assembly-section guide-section">
        <div class="section-head"><div><b>底板布局与拼接</b><small>底板保持可读尺寸，数量多时可横向和纵向滚动。</small></div><button type="button" :class="{ playing: animating }" @click="animating ? stopAnimation() : playInstallation">{{ animating ? '停止演示' : '播放拼接' }}</button></div>
        <div class="board-navigation"><label><span>定位底板</span><select v-model="activeBoardId"><option v-for="board in plan.assembly.boards" :key="board.id" :value="board.id">{{ board.id }} · {{ board.bead_count }} 颗</option></select></label><small>{{ selectedBoardIndex + 1 }} / {{ plan.assembly.board_count }}</small><div><button type="button" :disabled="selectedBoardIndex <= 0" @click="moveBoard(-1)">←</button><button type="button" :disabled="selectedBoardIndex >= plan.assembly.boards.length - 1" @click="moveBoard(1)">→</button></div></div>
        <div ref="boardMapViewport" class="board-map-viewport" tabindex="0" aria-label="底板布局，可滚动查看"><div class="board-map" :style="boardMapStyle"><button v-for="board in plan.assembly.boards" :key="board.id" type="button" :class="{ active: selectedBoard?.id === board.id }" :aria-current="selectedBoard?.id === board.id" :title="`行 ${board.row_range[0]}–${board.row_range[1]}，列 ${board.column_range[0]}–${board.column_range[1]}`" @click="activeBoardId = board.id"><b>{{ board.id }}</b><small>{{ board.bead_count }} 颗</small></button></div></div>
        <div v-if="selectedBoard && selectedTemplate" class="board-detail"><div class="peg-layout" :style="pegLayoutStyle"><span>{{ selectedBoard.id }}</span></div><div><b>{{ selectedBoard.id }} · {{ selectedBoard.bead_count }} 颗</b><p>原图坐标：行 {{ selectedBoard.row_range[0] }}–{{ selectedBoard.row_range[1] }}，列 {{ selectedBoard.column_range[0] }}–{{ selectedBoard.column_range[1] }}</p><p>{{ selectedBoard.used_color_count }} 色 · 右接 {{ selectedBoard.join_right || '无' }} · 下接 {{ selectedBoard.join_bottom || '无' }}</p><div class="board-colors"><span v-for="([code, count]) in Object.entries(selectedBoard.color_counts).slice(0, 8)" :key="code">{{ code }} {{ count }}</span><span v-if="Object.keys(selectedBoard.color_counts).length > 8">+{{ Object.keys(selectedBoard.color_counts).length - 8 }} 色</span></div></div></div>
      </section>
      <section v-else-if="activeSection === 'progress'" class="progress-section guide-section"><div class="section-head"><div><b>制作进度</b><small>{{ completedCount }} / {{ plan.make_steps.length }} 步 · 已完成 {{ completedBeads.toLocaleString() }} 颗</small></div><strong>{{ progressPercent }}%</strong></div><progress :value="progressPercent" max="100" /><ol><li v-for="step in plan.make_steps" :key="step.id" :class="{ done: completedSet.has(step.id) }"><label><input type="checkbox" :checked="completedSet.has(step.id)" @change="toggleStep(step.id)"><span><b>{{ step.ordinal }}. {{ step.title }}</b><small>{{ step.instruction }}</small></span></label><em>{{ step.bead_count }} 颗 · {{ step.estimated_minutes || 0 }} 分</em></li></ol></section>
      <section v-else class="material-section guide-section"><div class="section-head"><div><b>缺色提醒</b><small v-if="plan.materials.tracked">库存覆盖 {{ plan.materials.coverage_percent }}%</small><small v-else>尚未录入库存，暂不计算缺色。</small></div></div><ul v-if="plan.materials.shortages.length"><li v-for="item in plan.materials.shortages" :key="item.color_code"><b>{{ item.color_code }}</b><span>需 {{ item.required_quantity }} · 有 {{ item.available_quantity }}</span><em>缺 {{ item.shortage_quantity }}</em></li></ul><p v-else class="stocked">{{ plan.materials.tracked ? '库存数量足够，可开始制作。' : '在图纸设置中录入库存后，系统会自动提醒缺色。' }}</p></section>
    </template>
  </section>
</template>

<style scoped>
.production-guide { display: grid; gap: 11px; padding: 18px; border-top: 1px solid #e7e4ef; background: #fcfbff; }.guide-head, .section-head { display: flex; align-items: end; justify-content: space-between; gap: 9px; }.guide-head > div, .section-head > div { display: grid; gap: 3px; }.eyebrow { color: #7359e6; font-size: 9px; font-weight: 800; letter-spacing: .13em; }.guide-head strong { color: #1d2742; font-size: 15px; }.guide-head button, .section-head button { border: 1px solid #ded8f3; border-radius: 7px; padding: 5px 7px; background: #f5f2ff; color: #5b4ab4; font-size: 9px; font-weight: 800; }.section-head button.playing { border-color: #c9ebdd; background: #edfbf4; color: #258060; }.guide-controls { display: grid; grid-template-columns: 1fr 62px; gap: 7px; }.guide-controls label { display: grid; gap: 3px; color: #788197; font-size: 9px; font-weight: 800; }.guide-controls label:nth-child(3), .guide-controls label:nth-child(4) { grid-column: span 1; }.guide-controls select, .guide-controls input { width: 100%; min-height: 29px; border: 1px solid #e1deeb; border-radius: 7px; padding: 4px 6px; color: #4b5570; background: #fff; font-family: var(--font-mono); font-size: 9px; }.template-note, .muted, .error { margin: 0; color: #778196; font-size: 9px; line-height: 1.5; }.error { color: #bd5160; }.plan-summary { display: grid; grid-template-columns: repeat(4, 1fr); gap: 5px; }.plan-summary div { display: grid; gap: 2px; padding: 7px 4px; border: 1px solid #e9e6f1; border-radius: 8px; background: #fff; text-align: center; }.plan-summary b { color: #4c3cad; font-family: var(--font-mono); font-size: 13px; }.plan-summary span { color: #8c94a5; font-size: 8px; }.assembly-section, .progress-section, .material-section { display: grid; gap: 8px; border-top: 1px solid #ece9f2; padding-top: 11px; }.section-head b { color: #3d475f; font-size: 11px; }.section-head small { color: #8490a3; font-size: 8px; line-height: 1.4; }.board-map { display: grid; gap: 4px; border: 1px solid #e5e1f1; border-radius: 9px; padding: 6px; background: #f5f3fb; }.board-map button { display: grid; min-width: 0; aspect-ratio: 1.22; place-items: center; border: 1px solid #cfc5f1; border-radius: 5px; background: linear-gradient(145deg, #fff, #f4f0ff); color: #5947b4; }.board-map button.active { border-color: #42b388; background: linear-gradient(145deg, #f1fcf7, #e1f7ed); color: #28795c; box-shadow: 0 0 0 2px rgb(66 179 136 / 18%); }.board-map b { font-family: var(--font-mono); font-size: 9px; }.board-map small { font-size: 7px; }.board-detail { display: grid; grid-template-columns: 72px 1fr; gap: 9px; align-items: center; padding: 8px; border: 1px solid #e7e4ef; border-radius: 9px; background: #fff; }.peg-layout { position: relative; aspect-ratio: 1; overflow: hidden; border: 1px solid #cfc7e9; border-radius: 6px; background-color: #eeeaff; background-image: radial-gradient(circle, #a99fe0 20%, transparent 23%); background-size: calc(100% / var(--board-columns)) calc(100% / var(--board-rows)); }.peg-layout span { position: absolute; inset: 0; display: grid; place-items: center; color: #4f3db2; font-family: var(--font-mono); font-size: 12px; font-weight: 800; text-shadow: 0 1px #fff; }.board-detail b { color: #49536c; font-size: 10px; }.board-detail p { margin: 3px 0; color: #7c8498; font-size: 8px; line-height: 1.45; }.board-colors { display: flex; flex-wrap: wrap; gap: 3px; }.board-colors span { border-radius: 99px; padding: 2px 4px; background: #f3f1f9; color: #69728a; font-family: var(--font-mono); font-size: 7px; }.progress-section strong { color: #36a47b; font-family: var(--font-mono); font-size: 12px; }.progress-section progress { width: 100%; height: 6px; overflow: hidden; border: 0; border-radius: 99px; background: #e9edf0; }.progress-section progress::-webkit-progress-bar { background: #e9edf0; }.progress-section progress::-webkit-progress-value { border-radius: 99px; background: linear-gradient(90deg, #42b78a, #83daba); }.progress-section ol, .material-section ul { display: grid; gap: 4px; max-height: 245px; overflow: auto; margin: 0; padding: 0; list-style: none; }.progress-section li { display: grid; grid-template-columns: 1fr auto; gap: 6px; align-items: center; border-bottom: 1px solid #f0eef5; padding: 4px 0; }.progress-section li.done { opacity: .55; }.progress-section label { display: flex; gap: 6px; align-items: start; cursor: pointer; }.progress-section input { margin-top: 2px; accent-color: #3eaf83; }.progress-section label span { display: grid; gap: 2px; }.progress-section label b { color: #566077; font-size: 9px; }.progress-section label small { color: #8891a3; font-size: 8px; line-height: 1.4; }.progress-section em, .material-section em { color: #7667ba; font-family: var(--font-mono); font-size: 8px; font-style: normal; white-space: nowrap; }.material-section li { display: grid; grid-template-columns: 45px 1fr auto; gap: 6px; align-items: center; color: #768095; font-size: 8px; }.material-section li b { color: #4a536b; font-family: var(--font-mono); }.material-section li em { color: #bd5d64; }.stocked { margin: 0; color: #338465; font-size: 9px; }
@media (max-width: 600px) { .plan-summary { grid-template-columns: repeat(2, 1fr); }.guide-controls { grid-template-columns: 1fr 1fr; }.guide-controls label:first-child { grid-column: 1 / -1; }.board-detail { grid-template-columns: 62px 1fr; } }
</style>

<style scoped>
/* Keep dense production data navigable inside the editor inspector. */
.production-guide { min-width: 0; }
.guide-settings { overflow: hidden; border: 1px solid #e4e0ee; border-radius: 9px; background: #fff; }
.guide-settings summary { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 8px 9px; color: #5446a0; background: #f8f6ff; font-size: 9px; font-weight: 800; cursor: pointer; list-style: none; }
.guide-settings summary::-webkit-details-marker { display: none; }
.guide-settings summary::before { color: #8170d6; content: '▸'; transition: transform .16s ease; }
.guide-settings[open] summary::before { transform: rotate(90deg); }
.guide-settings summary span { margin-right: auto; }
.guide-settings summary small { overflow: hidden; color: #8b93a6; font-weight: 600; text-overflow: ellipsis; white-space: nowrap; }
.guide-settings .guide-controls { padding: 9px 9px 0; }
.guide-settings .template-note { padding: 7px 9px 9px; }
.guide-sections { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 4px; padding: 4px; border: 1px solid #e5e1ef; border-radius: 10px; background: #f4f2f9; }
.guide-sections button { display: flex; min-width: 0; align-items: center; justify-content: center; gap: 5px; border: 1px solid transparent; border-radius: 7px; padding: 7px 5px; color: #777f93; background: transparent; font-size: 9px; font-weight: 800; }
.guide-sections button span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.guide-sections button b { display: grid; min-width: 17px; height: 17px; place-items: center; border-radius: 99px; color: #71679b; background: #e8e5f0; font-family: var(--font-mono); font-size: 7px; }
.guide-sections button.active { border-color: #d6cdf8; color: #513dac; background: #fff; box-shadow: 0 3px 9px rgb(55 42 120 / 8%); }
.guide-sections button.active b { color: #fff; background: #6e55d5; }
.guide-section { min-width: 0; border-top: 0; padding-top: 2px; }
.board-navigation { display: grid; grid-template-columns: minmax(0, 1fr) auto auto; gap: 7px; align-items: end; }
.board-navigation label { display: grid; min-width: 0; gap: 3px; color: #798298; font-size: 8px; font-weight: 800; }
.board-navigation select { width: 100%; min-width: 0; min-height: 29px; border: 1px solid #dfdbea; border-radius: 7px; padding: 4px 6px; color: #4a5570; background: #fff; font-family: var(--font-mono); font-size: 9px; }
.board-navigation > small { min-width: 38px; padding-bottom: 7px; color: #8991a4; font-family: var(--font-mono); font-size: 8px; text-align: center; }
.board-navigation > div { display: flex; gap: 3px; padding-bottom: 1px; }
.board-navigation button { width: 29px; height: 29px; border: 1px solid #dfdaee; border-radius: 7px; color: #5f50ae; background: #f7f5ff; font-weight: 800; }
.board-navigation button:disabled { cursor: not-allowed; opacity: .38; }
.board-map-viewport { max-width: 100%; max-height: clamp(190px, 32vh, 320px); overflow: auto; border: 1px solid #ded9eb; border-radius: 10px; padding: 7px; background: #f3f1f8; overscroll-behavior: contain; scrollbar-color: #bdb4df #eeecf4; }
.board-map-viewport:focus { border-color: #8c79e2; outline: 3px solid rgb(108 84 216 / 10%); }
.board-map { width: 100%; gap: 5px; border: 0; border-radius: 0; padding: 0; background: transparent; }
.board-map button { min-height: 48px; aspect-ratio: auto; padding: 5px; cursor: pointer; }
.board-map button:hover { border-color: #8e7bdc; }
.board-map button.active { position: relative; z-index: 1; }
.board-detail { grid-template-columns: 82px minmax(0, 1fr); align-items: start; }
.board-detail > div:last-child { min-width: 0; }
.board-colors { max-height: 44px; overflow: auto; }
.progress-section ol, .material-section ul { max-height: min(420px, 48vh); padding-right: 3px; overscroll-behavior: contain; }
.progress-section li { grid-template-columns: minmax(0, 1fr) auto; }
.progress-section label span { min-width: 0; }
.progress-section label small { overflow-wrap: anywhere; }
@media (max-width: 600px) {
  .board-map-viewport { max-height: 260px; }
  .board-detail { grid-template-columns: 68px minmax(0, 1fr); }
  .guide-sections button { flex-direction: column; gap: 2px; }
  .guide-sections button b { height: 15px; min-width: 15px; }
}
</style>
