<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'

import BeadCanvas from '@/components/bead-editor/BeadCanvas.vue'
import BeadStatusBar from '@/components/bead-editor/BeadStatusBar.vue'
import BeadToolbar from '@/components/bead-editor/BeadToolbar.vue'
import CostQuotePanel from '@/components/bead-editor/CostQuotePanel.vue'
import LayerPanel from '@/components/bead-editor/LayerPanel.vue'
import ProductionGuidePanel from '@/components/bead-editor/ProductionGuidePanel.vue'
import ProjectLifecyclePanel from '@/components/bead-editor/ProjectLifecyclePanel.vue'
import SelectionPanel from '@/components/bead-editor/SelectionPanel.vue'
import ColorReportPanel from '@/components/color-palette/ColorReportPanel.vue'
import PalettePanel from '@/components/color-palette/PalettePanel.vue'
import { getImage } from '@/api/images'
import { mediaUrl } from '@/api/http'
import { useAppStore } from '@/stores/app'
import { useEditorStore } from '@/stores/editor'
import { usePaletteStore } from '@/stores/palette'
import { useProjectStore } from '@/stores/project'
import { minimumEditorSymbolZoom } from '@/utils/grid'
import { liveStatistics } from '@/utils/statistics'
import type { CellValue } from '@/types/bead'
import type { CostQuoteSettings, ImageInfo, ProductionGuideProgress } from '@/types/project'

const route = useRoute()
const router = useRouter()
const app = useAppStore()
const editor = useEditorStore()
const palettes = usePaletteStore()
const projects = useProjectStore()
const coordinate = ref('')
const loading = ref(true)
const referenceImage = ref<ImageInfo>()
const versionRefreshKey = ref(0)
const sidebarOpen = ref(true)
type SidebarTab = 'palette' | 'selection' | 'layers' | 'materials' | 'guide' | 'project' | 'quote'
const sidebarItems: Array<{ id: SidebarTab; label: string; hint: string; glyph: string }> = [
  { id: 'palette', label: '色卡', hint: '选色与用量', glyph: '色' },
  { id: 'selection', label: '选区', hint: '选择与变换', glyph: '选' },
  { id: 'layers', label: '图层', hint: '参考与草稿', glyph: '层' },
  { id: 'materials', label: '材料', hint: '用量与色差', glyph: '料' },
  { id: 'guide', label: '制作', hint: '分板与步骤', glyph: '制' },
  { id: 'project', label: '项目', hint: '版本与发布', glyph: '项' },
  { id: 'quote', label: '报价', hint: '成本与工时', glyph: '价' },
]
const sidebarTab = ref<SidebarTab>('palette')
const workspaceDirty = ref(false)
const manualSaving = ref(false)
const savedWorkspaceSignature = ref('')
const lastObservedWorkspaceSignature = ref('')
let workspaceReady = false
let workspaceEditVersion = 0
const pendingProductionProgress = ref<ProductionGuideProgress>()
const pendingQuote = ref<CostQuoteSettings>()

const pattern = computed(() => editor.pattern)
const workspaceSignature = computed(() => pattern.value ? JSON.stringify(editor.workspaceSettings()) : '')
const hasUnsavedChanges = computed(() => editor.dirty || workspaceDirty.value)
const saving = computed(() => editor.saving || manualSaving.value)
const canOpenPatternSettings = computed(() => Boolean(pattern.value?.image_id) && pattern.value?.settings.source_kind !== 'design')
const toolLabel = computed(() => ({ brush: '绘制', eraser: '擦除', fill: '填充', eyedropper: '取色', select: '选择' }[editor.tool]))
const selectedColor = computed(() => palettes.current?.colors.find((color) => color.code === palettes.currentColorCode))
const activeSidebarItem = computed(() => sidebarItems.find((item) => item.id === sidebarTab.value) || sidebarItems[0])
const referenceUrl = computed(() => referenceImage.value ? mediaUrl(referenceImage.value.preview_url) : undefined)
const focusedCode = computed<CellValue>(() => {
  const index = editor.selectedIndices[0]
  return index === undefined ? null : editor.cellValue(index)
})
const selectionLocked = computed(() => editor.selectionCount > 0 && editor.selectedIndices.every((index) => editor.isLocked(index)))
const statistics = computed(() => {
  if (!pattern.value) return null
  return liveStatistics(pattern.value.cells, pattern.value.grid_width, pattern.value.grid_height, palettes.current?.colors || [], pattern.value.statistics.bead_size_mm, pattern.value.statistics.waste_rate)
})
const productionProgress = computed<ProductionGuideProgress | undefined>(() => {
  if (pendingProductionProgress.value) return pendingProductionProgress.value
  const value = projects.current?.editor_settings.production_guide
  if (!value || typeof value !== 'object') return undefined
  const progress = value as Partial<ProductionGuideProgress>
  return progress.version === 1 && Array.isArray(progress.completed_step_ids)
    ? { version: 1, completed_step_ids: progress.completed_step_ids.filter((id): id is string => typeof id === 'string') }
    : undefined
})
const quoteSettings = computed(() => pendingQuote.value || projects.current?.editor_settings.cost_quote)
const symbolZoomTarget = computed(() => {
  if (!pattern.value || editor.symbolMode === 'none') return null
  const minimumZoom = minimumEditorSymbolZoom(pattern.value.grid_width, pattern.value.grid_height, editor.symbolMode)
  if (editor.zoom + .001 >= minimumZoom) return null
  return Math.min(2.5, Math.ceil(minimumZoom * 10 - .001) / 10)
})
const symbolZoomTitle = computed(() => {
  if (symbolZoomTarget.value === null) return ''
  const label = editor.symbolMode === 'color_code' ? '完整色号' : '短色号'
  return `当前格子过小，放大至 ${Math.round(symbolZoomTarget.value * 100)}% 显示${label}`
})

async function load() {
  loading.value = true
  workspaceReady = false
  try {
    const project = await projects.load(String(route.params.projectId))
    if (!project.pattern_id) throw new Error('该项目还没有关联图纸')
    await editor.load(project.pattern_id)
    await palettes.ensure(editor.pattern!.palette_id)
    editor.hydrateWorkspace(project.editor_settings)
    if (editor.pattern!.image_id) {
      const source = await getImage(editor.pattern!.image_id)
      referenceImage.value = source.parent_image_id ? await getImage(source.parent_image_id) : source
    } else referenceImage.value = undefined
    await nextTick()
    savedWorkspaceSignature.value = workspaceSignature.value
    lastObservedWorkspaceSignature.value = workspaceSignature.value
    workspaceDirty.value = false
    pendingProductionProgress.value = undefined
    pendingQuote.value = undefined
    workspaceReady = true
  } catch (error) {
    app.showError(error)
  } finally {
    loading.value = false
  }
}

function interact(index: number, erase: boolean) {
  if (!pattern.value) return
  const code = pattern.value.cells[index]
  if (editor.tool === 'eyedropper') {
    if (code) palettes.select(code)
    editor.tool = 'brush'
    return
  }
  const next = erase || editor.tool === 'eraser' ? null : palettes.currentColorCode
  if (editor.tool === 'fill') editor.fill(index, next || null)
  else editor.paint(index, next || null)
}

function zoomForSymbols() {
  if (symbolZoomTarget.value !== null) editor.zoom = symbolZoomTarget.value
}

async function save(showNotice = true) {
  if (manualSaving.value) return
  if (!hasUnsavedChanges.value) {
    if (showNotice) app.showNotice('当前没有未保存的变更')
    return
  }
  manualSaving.value = true
  try {
    await editor.save()
    await saveWorkspace()
    if (showNotice) app.showNotice('图纸已保存')
  } catch (error) {
    app.showError(error)
  } finally {
    manualSaving.value = false
  }
}

async function saveWorkspace() {
  if (!workspaceDirty.value || !projects.current) return
  const targetEditVersion = workspaceEditVersion
  const targetWorkspaceSignature = workspaceSignature.value
  const productionProgress = pendingProductionProgress.value
  const costQuote = pendingQuote.value
  const editorSettings = {
    ...projects.current.editor_settings,
    professional_editor: editor.workspaceSettings(),
    ...(productionProgress ? { production_guide: productionProgress } : {}),
    ...(costQuote ? { cost_quote: costQuote } : {}),
  }
  try {
    await projects.saveEditorSettings(editorSettings)
    if (workspaceEditVersion === targetEditVersion) {
      savedWorkspaceSignature.value = targetWorkspaceSignature
      lastObservedWorkspaceSignature.value = targetWorkspaceSignature
      pendingProductionProgress.value = undefined
      pendingQuote.value = undefined
      workspaceDirty.value = false
    }
  } catch (error) {
    workspaceDirty.value = true
    throw error
  }
}

async function returnToSettings() {
  if (!canOpenPatternSettings.value) return
  await router.push({ path: '/convert', query: { project: String(route.params.projectId) } })
}

async function reloadAfterRestore() {
  try {
    const project = await projects.load(String(route.params.projectId))
    if (!project.pattern_id) return
    await editor.load(project.pattern_id)
    await palettes.ensure(editor.pattern!.palette_id)
    editor.hydrateWorkspace(project.editor_settings)
    await nextTick()
    savedWorkspaceSignature.value = workspaceSignature.value
    lastObservedWorkspaceSignature.value = workspaceSignature.value
    workspaceDirty.value = false
    pendingProductionProgress.value = undefined
    pendingQuote.value = undefined
    workspaceReady = true
    app.showNotice('已恢复图纸版本')
  } catch (error) { app.showError(error) }
}

function updateHover({ row, column, index }: { row: number; column: number; index: number }) {
  const code = editor.cellValue(index)
  const count = code ? statistics.value?.colors.find((item) => item.color_code === code)?.count || 0 : 0
  coordinate.value = `第 ${row + 1} 行 · 第 ${column + 1} 列 · ${code || '透明格'}${code ? ` · 共 ${count.toLocaleString()} 颗` : ''}`
}

function smartSelect(mode: 'color' | 'region' | 'similar') {
  const index = editor.selectedIndices[0]
  if (index === undefined) return
  if (mode === 'similar') {
    editor.selectSimilarColor(index, new Map((palettes.current?.colors || []).map((color) => [color.code, color.hex])))
  } else editor.selectByColor(index, mode === 'region')
}

function clearSelectedCells() {
  editor.apply(editor.selectedIndices.map((index) => ({ index, before: null, after: null })), '清除选区')
}

function applyDraft() {
  editor.applyDraftToFinished()
  app.showNotice('草稿已应用到成品层')
}

function updateProductionProgress(progress: ProductionGuideProgress) {
  pendingProductionProgress.value = progress
  workspaceEditVersion += 1
  workspaceDirty.value = true
}

function updateCostQuote(quote: CostQuoteSettings) {
  pendingQuote.value = quote
  workspaceEditVersion += 1
  workspaceDirty.value = true
}

function warnBeforeUnload(event: BeforeUnloadEvent) {
  if (!hasUnsavedChanges.value) return
  event.preventDefault()
  event.returnValue = ''
}

function shortcuts(event: KeyboardEvent) {
  const key = event.key.toLowerCase()
  if ((event.metaKey || event.ctrlKey) && key === 's') { event.preventDefault(); void save(); return }
  if (event.target instanceof HTMLInputElement || event.target instanceof HTMLSelectElement || event.target instanceof HTMLTextAreaElement) return
  if ((event.metaKey || event.ctrlKey) && key === 'z') { event.preventDefault(); event.shiftKey ? editor.redo() : editor.undo(); return }
  if ((event.metaKey || event.ctrlKey) && key === 'y') { event.preventDefault(); editor.redo(); return }
  if ((event.metaKey || event.ctrlKey) && key === 'c') { event.preventDefault(); editor.copySelection(); return }
  if ((event.metaKey || event.ctrlKey) && key === 'v') { event.preventDefault(); editor.pasteSelection(); return }
  if (event.altKey && key === 'arrowleft') { event.preventDefault(); editor.transformSelection('move-left'); return }
  if (event.altKey && key === 'arrowright') { event.preventDefault(); editor.transformSelection('move-right'); return }
  if (event.altKey && key === 'arrowup') { event.preventDefault(); editor.transformSelection('move-up'); return }
  if (event.altKey && key === 'arrowdown') { event.preventDefault(); editor.transformSelection('move-down'); return }
  if (key === 'escape') { editor.clearSelection(); return }
  if (key === 'backspace' || key === 'delete') { event.preventDefault(); clearSelectedCells(); return }
  if (key === 'b') editor.tool = 'brush'
  if (key === 'e') editor.tool = 'eraser'
  if (key === 'i') editor.tool = 'eyedropper'
  if (key === 'f') editor.tool = 'fill'
  if (key === 'v') editor.tool = 'select'
}

onMounted(() => {
  void load()
  window.addEventListener('keydown', shortcuts)
  window.addEventListener('beforeunload', warnBeforeUnload)
})
watch(
  () => editor.workspaceVersion,
  () => {
    if (!workspaceReady || loading.value) return
    const nextSignature = workspaceSignature.value
    if (nextSignature === lastObservedWorkspaceSignature.value) return
    lastObservedWorkspaceSignature.value = nextSignature
    workspaceEditVersion += 1
    workspaceDirty.value = nextSignature !== savedWorkspaceSignature.value
      || Boolean(pendingProductionProgress.value)
      || Boolean(pendingQuote.value)
  },
)
onBeforeRouteLeave(() => (
  !hasUnsavedChanges.value
  || window.confirm('还有未保存的编辑内容，离开后这些修改会丢失。确定离开吗？')
))
onBeforeUnmount(() => {
  window.removeEventListener('keydown', shortcuts)
  window.removeEventListener('beforeunload', warnBeforeUnload)
})
</script>

<template>
  <main v-if="!loading && pattern && statistics" class="editor-page">
    <section class="editor-shell card">
      <BeadToolbar :tool="editor.tool" :can-undo="editor.canUndo" :can-redo="editor.canRedo" :can-edit-settings="canOpenPatternSettings" :dirty="hasUnsavedChanges" :saving="saving" @tool="editor.tool = $event" @undo="editor.undo" @redo="editor.redo" @save="save" @settings="returnToSettings" />
      <div class="editor-main" :class="{ 'editor-main--sidebar-closed': !sidebarOpen, 'editor-main--guide': sidebarOpen && sidebarTab === 'guide' }">
        <div class="canvas-wrap">
          <div class="canvas-controls">
            <div class="canvas-controls__toggles">
              <span class="canvas-mode">{{ toolLabel }}</span>
              <label><input v-model="editor.showGrid" type="checkbox"> 网格</label>
              <label><input v-model="editor.showCoordinates" type="checkbox"> 坐标</label>
              <select v-model="editor.symbolMode" aria-label="格内标识">
                <option value="short_code">短色号</option>
                <option value="color_code">完整色号</option>
                <option value="none">无色号</option>
              </select>
              <button
                v-if="symbolZoomTarget !== null"
                type="button"
                class="symbol-zoom-hint"
                :title="symbolZoomTitle"
                :aria-label="symbolZoomTitle"
                @click="zoomForSymbols"
              >放大至 {{ Math.round(symbolZoomTarget * 100) }}%</button>
            </div>
            <span v-if="selectedColor" class="active-color" :title="`${selectedColor.code} · ${selectedColor.name_zh}`"><i :style="{ background: selectedColor.hex }" />{{ selectedColor.code }}</span>
            <span class="spacer" />
            <div class="zoom"><button class="button button--quiet" aria-label="缩小画布" @click="editor.zoom = Math.max(.5, editor.zoom - .1)">−</button><span>{{ Math.round(editor.zoom * 100) }}%</span><button class="button button--quiet" aria-label="放大画布" @click="editor.zoom = Math.min(2.5, editor.zoom + .1)">＋</button></div>
            <button class="sidebar-toggle" type="button" :aria-expanded="sidebarOpen" @click="sidebarOpen = !sidebarOpen">{{ sidebarOpen ? '收起面板' : '展开面板' }}</button>
          </div>
          <div class="canvas-scroller"><BeadCanvas :width="pattern.grid_width" :height="pattern.grid_height" :cells="pattern.cells" :draft-cells="editor.draftCells" :palette="palettes.current?.colors || []" :tool="editor.tool" :zoom="editor.zoom" :show-grid="editor.showGrid" :show-coordinates="editor.showCoordinates" :symbol-mode="editor.symbolMode" :selected-indices="editor.selectedIndices" :locked-indices="editor.lockedCellIndices" :reference-url="referenceUrl" :reference-visible="editor.layers.reference.visible" :reference-opacity="editor.layers.reference.opacity" :draft-visible="editor.layers.draft.visible" :finished-visible="editor.layers.finished.visible" :render-version="editor.renderVersion" @interact="interact" @select="editor.selectRectangle" @hover="updateHover" /></div>
        </div>
        <aside v-if="sidebarOpen" class="editor-sidebar">
          <header class="inspector-head">
            <div><span>PRO WORKSPACE</span><strong>{{ activeSidebarItem.label }}工作区</strong><small>{{ activeSidebarItem.hint }}</small></div>
            <button type="button" aria-label="关闭设置面板" @click="sidebarOpen = false">×</button>
          </header>
          <div class="inspector-body">
            <nav class="sidebar-tabs" aria-label="编辑器侧栏">
              <button v-for="item in sidebarItems" :key="item.id" type="button" :class="{ active: sidebarTab === item.id }" :title="item.hint" @click="sidebarTab = item.id">
                <span>{{ item.glyph }}</span><small>{{ item.label }}</small>
              </button>
            </nav>
            <div class="sidebar-panel">
              <PalettePanel v-if="sidebarTab === 'palette'" :colors="palettes.current?.colors || []" :selected-code="palettes.currentColorCode" :statistics="statistics.colors" @select="palettes.select" />
              <SelectionPanel v-else-if="sidebarTab === 'selection'" :selection-count="editor.selectionCount" :focused-code="focusedCode" :selected-color-code="palettes.currentColorCode" :active-layer="editor.activeLayer" :has-clipboard="editor.hasClipboard" :selection-locked="selectionLocked" :colors="palettes.current?.colors || []" @copy="editor.copySelection" @paste="editor.pasteSelection" @clear="editor.clearSelection" @select-by-color="smartSelect($event ? 'region' : 'color')" @select-similar="smartSelect('similar')" @transform="editor.transformSelection" @replace="editor.replaceColor" @lock="editor.toggleSelectionLock" />
              <LayerPanel v-else-if="sidebarTab === 'layers'" :active-layer="editor.activeLayer" :layers="editor.layers" :reference-available="Boolean(referenceImage)" :has-draft="editor.hasDraft" @active="editor.setActiveLayer" @visible="editor.setLayerVisibility" @opacity="editor.setReferenceOpacity" @apply-draft="applyDraft" @clear-draft="editor.clearDraft" />
              <template v-else-if="sidebarTab === 'materials'">
                <section class="statistics statistics--compact"><div class="statistics__head"><div><span class="eyebrow">MATERIALS</span><strong>材料概览</strong></div><span class="total">{{ statistics.total_beads.toLocaleString() }} 颗</span></div><p>{{ statistics.physical_width_mm }} × {{ statistics.physical_height_mm }} mm · {{ statistics.used_color_count }} 色</p><ol><li v-for="color in statistics.colors.slice(0, 5)" :key="color.color_code"><i :style="{ background: color.hex }" /><span>{{ color.color_code }}</span><b>{{ color.count }}</b></li></ol><RouterLink class="button button--quiet" :to="`/export/${projects.current?.id}`">前往导出 <span>→</span></RouterLink></section>
                <ColorReportPanel :report="pattern.color_report" />
              </template>
              <ProductionGuidePanel v-else-if="sidebarTab === 'guide'" :pattern-id="pattern.id" :project-id="String(route.params.projectId)" :progress="productionProgress" @update-progress="updateProductionProgress" @notice="app.showNotice" @error="app.showError" />
              <ProjectLifecyclePanel v-else-if="sidebarTab === 'project'" :project-id="String(route.params.projectId)" :project-name="projects.current?.name" :project-description="projects.current?.description" :current-pattern="pattern" :version-refresh-key="versionRefreshKey" :has-unsaved-changes="hasUnsavedChanges" @restored="reloadAfterRestore" />
              <CostQuotePanel v-else-if="sidebarTab === 'quote'" :statistics="statistics" :initial-settings="quoteSettings" @update="updateCostQuote" />
            </div>
          </div>
        </aside>
      </div>
      <BeadStatusBar :statistics="statistics" :zoom="editor.zoom" :coordinate="coordinate" />
    </section>
  </main>
  <main v-else class="loading">{{ loading ? '正在载入图纸…' : '无法打开图纸' }} <button v-if="!loading" class="button" @click="router.push('/projects')">返回项目</button></main>
</template>

<style scoped>
.editor-page { min-height: calc(100vh - 64px); padding: 19px; background: #12192b; }.editor-shell { overflow: hidden; border: 1px solid rgb(255 255 255 / 12%); border-radius: 16px; box-shadow: 0 20px 44px rgb(1 5 18 / 34%); }.editor-main { display: grid; grid-template-columns: minmax(0, 1fr) 292px; min-height: calc(100vh - 191px); }.canvas-wrap { display: grid; grid-template-rows: auto 1fr; min-width: 0; border-right: 1px solid #252e43; }.canvas-controls { display: flex; align-items: center; gap: 11px; padding: 9px 13px; border-bottom: 1px solid #283247; color: #c2c9dc; background: #1b253a; font-size: 11px; }.canvas-controls__toggles, .zoom { display: flex; align-items: center; gap: 11px; }.canvas-controls label { display: flex; align-items: center; gap: 5px; cursor: pointer; }.canvas-controls input { accent-color: #9177f6; }.canvas-controls select { border: 1px solid #3b4660; border-radius: 7px; padding: 5px 7px; color: #d8def0; background: #27334c; font-size: 11px; }.spacer { flex: 1; }.zoom { gap: 6px; padding: 2px 3px; border: 1px solid #39455e; border-radius: 8px; background: #11192a; }.zoom span { min-width: 39px; color: #e5e2fb; font-family: var(--font-mono); font-size: 10px; text-align: center; }.canvas-controls .button { min-height: 24px; padding: 1px 8px; border-color: transparent; color: #d7dcf0; background: transparent; }.canvas-controls .button:hover { background: #35425e; }.canvas-scroller { display: grid; min-height: 0; overflow: auto; place-items: start center; padding: 28px; background-color: #e9e7e2; background-image: radial-gradient(#c8c5c0 1px, transparent 1px); background-size: 12px 12px; } aside { overflow: auto; background: #fff; }.statistics { display: grid; gap: 11px; padding: 18px; border-top: 1px solid #e7e4ef; background: #fcfbff; }.statistics__head { display: flex; align-items: end; justify-content: space-between; gap: 8px; }.statistics__head > div { display: grid; gap: 3px; }.statistics__head strong { color: #1d2742; font-size: 15px; }.eyebrow { color: #7359e6; font-size: 9px; font-weight: 800; letter-spacing: .13em; }.total { border-radius: 99px; padding: 4px 6px; color: #615b7b; background: #efedf7; font-family: var(--font-mono); font-size: 9px; white-space: nowrap; }.statistics p { margin: 0; color: #77809a; font-size: 11px; line-height: 1.5; }.statistics ol { display: grid; gap: 5px; margin: 0; padding: 0; list-style: none; }.statistics li { display: flex; align-items: center; gap: 7px; padding: 4px 0; border-bottom: 1px solid #f1eff6; color: #5e6680; font-family: var(--font-mono); font-size: 10px; }.statistics i { width: 14px; height: 14px; border: 1px solid rgb(30 40 70 / 18%); border-radius: 50%; box-shadow: inset 2px 2px 2px rgb(255 255 255 / 60%); }.statistics b { margin-left: auto; color: #38415b; }.statistics .button { margin-top: 2px; text-align: center; }.statistics .button span { margin-left: 4px; }.loading { display: grid; min-height: calc(100vh - 62px); place-content: center; gap: 12px; color: #737b94; text-align: center; } @media (max-width: 900px) { .editor-main { grid-template-columns: 1fr; }.canvas-wrap { border-right: 0; }.canvas-scroller { min-height: 60vh; } aside { display: grid; grid-template-columns: 1fr 1fr; }.statistics { border-top: 0; border-left: 1px solid #e7e4ef; } } @media (max-width: 640px) { .editor-page { padding: 0; }.editor-shell { border: 0; border-radius: 0; }.canvas-controls { align-items: flex-start; flex-direction: column; }.canvas-controls__toggles { flex-wrap: wrap; }.canvas-controls .spacer { display: none; }.zoom { align-self: flex-end; margin-top: -28px; }.canvas-scroller { padding: 14px; } aside { grid-template-columns: 1fr; }.statistics { border-top: 1px solid #e7e4ef; border-left: 0; } }
</style>

<style scoped>
/* Viewport-bound professional inspector: every workspace scrolls independently. */
.editor-shell { display: grid; grid-template-rows: auto minmax(0, 1fr) auto; }
.editor-main { min-height: 0; grid-template-columns: minmax(0, 1fr) 360px; }
.canvas-wrap { min-height: 0; }
.editor-sidebar { display: grid; grid-template-rows: auto minmax(0, 1fr); min-width: 0; min-height: 0; overflow: hidden; border-left: 1px solid #e4e1eb; background: #fff; }
.inspector-head { display: flex; align-items: center; justify-content: space-between; min-height: 62px; padding: 10px 13px 10px 15px; border-bottom: 1px solid #e7e4ee; background: linear-gradient(135deg, #fcfbff, #f5f2ff); }
.inspector-head > div { display: grid; grid-template-columns: auto 1fr; align-items: baseline; gap: 2px 7px; min-width: 0; }
.inspector-head span { grid-column: 1 / -1; color: #7761d8; font-family: var(--font-mono); font-size: 8px; font-weight: 800; letter-spacing: .13em; }
.inspector-head strong { color: #242e48; font-size: 14px; }
.inspector-head small { overflow: hidden; color: #8c94a6; font-size: 9px; text-overflow: ellipsis; white-space: nowrap; }
.inspector-head button { width: 27px; height: 27px; flex: 0 0 27px; border: 1px solid #ded9ea; border-radius: 8px; color: #706985; background: #fff; font-size: 17px; line-height: 1; }
.inspector-head button:hover { border-color: #b9acee; color: #5c47bd; background: #f5f2ff; }
.inspector-body { display: grid; grid-template-columns: 64px minmax(0, 1fr); min-height: 0; }
.sidebar-tabs { display: flex; flex-direction: column; gap: 4px; min-width: 0; overflow-y: auto; border-right: 1px solid #e7e4ee; border-bottom: 0; padding: 9px 7px; background: #f7f6fa; scrollbar-width: none; }
.sidebar-tabs::-webkit-scrollbar { display: none; }
.sidebar-tabs button { display: grid; justify-items: center; gap: 3px; min-width: 0; border: 1px solid transparent; border-radius: 9px; padding: 7px 3px 6px; color: #7e8799; background: transparent; }
.sidebar-tabs button span { display: grid; width: 25px; height: 25px; place-items: center; border: 1px solid #e2dfea; border-radius: 8px; color: #697287; background: #fff; font-size: 10px; font-weight: 900; box-shadow: 0 2px 6px rgb(38 43 65 / 5%); }
.sidebar-tabs button small { font-size: 8px; font-weight: 800; }
.sidebar-tabs button:hover { border-color: #ddd7f6; color: #5f4bb9; background: #efecfb; }
.sidebar-tabs button.active { border-color: #d3c9fb; color: #513db2; background: #ece8ff; box-shadow: inset 0 0 0 1px rgb(255 255 255 / 70%); }
.sidebar-tabs button.active span { border-color: #8d78e7; color: #fff; background: linear-gradient(145deg, #6e55d8, #9279ef); box-shadow: 0 5px 10px rgb(83 61 180 / 22%); }
.sidebar-panel { min-width: 0; min-height: 0; overflow-y: auto; overscroll-behavior: contain; background: #fff; scrollbar-color: #c4bce9 transparent; }
.sidebar-panel :deep(.palette) { padding: 15px; }
.sidebar-panel :deep(.palette .colors) { max-height: none; }
.statistics--compact { border-top: 0; }
.statistics--compact ol { max-height: none; }

@media (min-width: 1001px) {
  .editor-page { height: calc(100vh - 64px); min-height: 650px; overflow: hidden; padding: 14px; }
  .editor-shell { height: 100%; min-height: 0; }
}

@media (max-width: 1000px) {
  .editor-page { height: auto; overflow: visible; }
  .editor-shell { height: auto; min-height: 0; }
  .editor-main, .editor-main--sidebar-closed { grid-template-columns: 1fr; }
  .editor-sidebar { max-height: min(620px, 72vh); border-top: 1px solid #283248; border-left: 0; }
  .inspector-body { grid-template-columns: 1fr; grid-template-rows: auto minmax(0, 1fr); }
  .sidebar-tabs { flex-direction: row; overflow-x: auto; overflow-y: hidden; border-right: 0; border-bottom: 1px solid #e7e4ee; padding: 7px 9px; }
  .sidebar-tabs button { grid-template-columns: auto auto; align-items: center; justify-items: start; flex: 0 0 auto; padding: 5px 8px; }
  .sidebar-tabs button span { width: 23px; height: 23px; }
  .sidebar-tabs button small { font-size: 9px; }
  .sidebar-panel :deep(.palette .colors) { max-height: 330px; }
}

@media (max-width: 640px) {
  .editor-sidebar { max-height: 610px; }
  .inspector-head { min-height: 55px; }
  .sidebar-tabs button { grid-template-columns: 1fr; justify-items: center; min-width: 48px; padding-inline: 5px; }
  .sidebar-panel :deep(.palette .colors) { max-height: 300px; }
}
</style>

<style scoped>
.editor-main { grid-template-columns: minmax(0, 1fr) 316px; min-height: calc(100vh - 183px); transition: grid-template-columns .2s ease; }.editor-main--sidebar-closed { grid-template-columns: minmax(0, 1fr); }.canvas-wrap { border-right: 1px solid #252e43; }.canvas-controls { gap: 9px; min-height: 48px; padding: 8px 12px; }.canvas-controls__toggles { gap: 10px; }.canvas-mode { border: 1px solid #3a4968; border-radius: 99px; padding: 3px 7px; color: #c9c1fb; background: #273450; font-family: var(--font-mono); font-size: 9px; }.symbol-zoom-hint { flex: 0 0 auto; border: 1px solid #6659a9; border-radius: 99px; padding: 4px 7px; color: #ded8ff; background: #312b58; font-family: var(--font-mono); font-size: 9px; font-weight: 800; white-space: nowrap; }.symbol-zoom-hint:hover { border-color: #9b89f0; color: #fff; background: #423873; }.active-color { display: inline-flex; align-items: center; gap: 5px; max-width: 90px; overflow: hidden; border: 1px solid #3b4a68; border-radius: 7px; padding: 4px 6px; color: #e0e6f2; background: #202d45; font-family: var(--font-mono); font-size: 9px; text-overflow: ellipsis; white-space: nowrap; }.active-color i { width: 12px; height: 12px; flex: 0 0 12px; border: 1px solid rgb(255 255 255 / 40%); border-radius: 50%; box-shadow: inset 1px 1px 2px rgb(255 255 255 / 45%); }.sidebar-toggle { flex: 0 0 auto; border: 1px solid #3a4968; border-radius: 7px; padding: 5px 8px; background: #202d45; color: #cbd4e7; font-size: 10px; font-weight: 800; }.sidebar-toggle:hover { border-color: #8071db; background: #2b3955; color: #fff; }.editor-sidebar { display: grid; grid-template-columns: minmax(0, 1fr); grid-template-rows: auto minmax(0, 1fr); min-width: 0; overflow: hidden; background: #fff; }.sidebar-tabs { display: grid; grid-template-columns: repeat(5, 1fr); border-bottom: 1px solid #e6e3ef; background: #faf9fd; }.sidebar-tabs button { min-width: 0; border: 0; border-bottom: 2px solid transparent; padding: 11px 3px 9px; background: transparent; color: #8a92a6; font-size: 9px; font-weight: 800; transition: background .16s, color .16s, border-color .16s; }.sidebar-tabs button:hover { color: #5b4ab8; background: #f3f1fb; }.sidebar-tabs button.active { border-color: #6c54d8; background: #fff; color: #4e3bad; }.sidebar-panel { min-height: 0; overflow-y: auto; overscroll-behavior: contain; scrollbar-color: #c4bce9 transparent; }.sidebar-panel :deep(.palette) { padding: 15px; }.sidebar-panel :deep(.palette .colors) { max-height: min(440px, calc(100vh - 310px)); }.statistics--compact { border-top: 0; }.statistics--compact ol { max-height: 156px; overflow: auto; }.statistics--compact .button { display: flex; justify-content: center; }.canvas-scroller { padding: clamp(16px, 3vw, 30px); }.status { position: relative; z-index: 2; }
@media (max-width: 900px) { .editor-main, .editor-main--sidebar-closed { grid-template-columns: 1fr; }.canvas-wrap { border-right: 0; }.editor-sidebar { max-height: min(590px, 68vh); border-top: 1px solid #2a344a; }.sidebar-panel :deep(.palette .colors) { max-height: 330px; }.sidebar-tabs { grid-template-columns: repeat(5, minmax(0, 1fr)); }.statistics--compact, .editor-sidebar :deep(.report), .editor-sidebar :deep(.mural), .editor-sidebar :deep(.lifecycle) { border-top: 1px solid #e7e4ef; } }
@media (max-width: 640px) { .canvas-controls { align-items: center; flex-direction: row; flex-wrap: wrap; gap: 7px; }.canvas-controls__toggles { width: 100%; gap: 7px; }.canvas-mode { display: none; }.active-color { margin-right: auto; }.sidebar-toggle { margin-left: auto; }.zoom { margin-top: 0; }.editor-sidebar { max-height: none; }.sidebar-tabs button { padding-block: 10px; font-size: 9px; }.sidebar-panel :deep(.palette .colors) { max-height: 290px; } }
</style>

<style scoped>
/* Final inspector overrides kept after legacy responsive rules. */
.editor-main { min-height: 0; grid-template-columns: minmax(0, 1fr) 360px; }
.editor-main.editor-main--guide { grid-template-columns: minmax(0, 1fr) clamp(430px, 36vw, 500px); }
.editor-main.editor-main--sidebar-closed { grid-template-columns: minmax(0, 1fr); }
.editor-main--sidebar-closed .canvas-wrap { border-right: 0; }
.editor-sidebar { grid-template-columns: minmax(0, 1fr); grid-template-rows: auto minmax(0, 1fr); min-height: 0; border-left: 1px solid #e4e1eb; }
.sidebar-tabs { display: flex; grid-template-columns: none; flex-direction: column; gap: 4px; overflow-y: auto; border-right: 1px solid #e7e4ee; border-bottom: 0; padding: 9px 7px; background: #f7f6fa; }
.sidebar-tabs button { display: grid; justify-items: center; gap: 3px; min-width: 0; border: 1px solid transparent; border-radius: 9px; padding: 7px 3px 6px; color: #7e8799; background: transparent; }
.sidebar-tabs button:hover { border-color: #ddd7f6; color: #5f4bb9; background: #efecfb; }
.sidebar-tabs button.active { border-color: #d3c9fb; color: #513db2; background: #ece8ff; }
.sidebar-panel :deep(.palette .colors) { max-height: none; }
.statistics--compact ol { max-height: none; }

@media (max-width: 1000px) {
  .editor-main, .editor-main.editor-main--guide, .editor-main--sidebar-closed { grid-template-columns: 1fr; }
  .editor-sidebar { max-height: min(620px, 72vh); border-top: 1px solid #283248; border-left: 0; }
  .sidebar-tabs { flex-direction: row; overflow-x: auto; overflow-y: hidden; border-right: 0; border-bottom: 1px solid #e7e4ee; padding: 7px 9px; }
  .sidebar-tabs button { grid-template-columns: auto auto; align-items: center; justify-items: start; flex: 0 0 auto; padding: 5px 8px; }
  .sidebar-panel :deep(.palette .colors) { max-height: 330px; }
}

@media (max-width: 640px) {
  .editor-sidebar { max-height: 610px; }
  .sidebar-tabs button { grid-template-columns: 1fr; justify-items: center; min-width: 48px; padding: 5px; }
  .sidebar-panel :deep(.palette .colors) { max-height: 300px; }
}
</style>
