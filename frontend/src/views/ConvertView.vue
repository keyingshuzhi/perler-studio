<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { getImage, preprocessImage } from '@/api/images'
import { mediaUrl } from '@/api/http'
import { generatePattern, getPattern, previewPattern, regeneratePattern, type GeneratePatternPayload } from '@/api/patterns'
import { getGridPresets } from '@/api/presets'
import ConversionPreview from '@/components/conversion/ConversionPreview.vue'
import ImageUploader from '@/components/image-upload/ImageUploader.vue'
import InventoryPanel from '@/components/color-palette/InventoryPanel.vue'
import { useAppStore } from '@/stores/app'
import { usePaletteStore } from '@/stores/palette'
import { useProjectStore } from '@/stores/project'
import type { GridPreset } from '@/types/preset'
import type { ImageInfo } from '@/types/project'
import type { ConversionHotspot, PatternPreview } from '@/types/bead'
import type { ColorimetryStatus } from '@/types/palette'

const router = useRouter()
const route = useRoute()
const app = useAppStore()
const palettes = usePaletteStore()
const projects = useProjectStore()
const image = ref<ImageInfo>()
const generating = ref(false)
const preprocessing = ref(false)
const settingsLoading = ref(false)
const presets = ref<GridPreset[]>([])
const editingProjectId = ref('')
const editingPatternId = ref('')
const inventory = ref<Record<string, number>>({})
const conversionPreview = ref<PatternPreview>()
const previewing = ref(false)
const previewError = ref('')
const activePreviewIndex = ref<number | null>(null)
const heatmapVisible = ref(false)
let previewTimer: number | undefined
let previewRequestId = 0
const INVENTORY_STORAGE_KEY = 'perler-studio:palette-inventory:v1'
const form = reactive({
  gridWidth: 64,
  gridHeight: 64,
  resizeMode: 'contain' as 'stretch' | 'contain' | 'cover' | 'pixel',
  samplingMode: 'adaptive' as 'adaptive' | 'edge_aware' | 'smooth',
  distance: 'ciede2000' as 'fidelity' | 'rgb' | 'cie76' | 'cie94' | 'ciede2000',
  maxColors: 48,
  autoColorLimit: true,
  targetP95DeltaE: 6,
  includeSpecialColors: false,
  minimumColorCount: 0,
  cleanupLevel: 'medium' as 'off' | 'light' | 'medium',
  structureAware: true,
  inventoryMode: 'report' as 'report' | 'only',
  transparent: true,
  beadSize: 5,
  wasteRate: 0.05,
  brightness: 1,
  contrast: 1,
  saturation: 1,
  removeBackground: false,
  conversionPreset: 'custom' as 'custom' | 'portrait' | 'illustration' | 'pixel_art' | 'landscape',
  subjectCrop: false,
  focusX: 0.5,
  focusY: 0.5,
  focusZoom: 1,
  focusRadius: 0.38,
  backgroundWeaken: 0,
  detailPriorities: [] as Array<'facial' | 'text' | 'outline'>,
})
const conversionPresets = [
  { id: 'portrait', label: '人物', description: '聚焦五官，弱化杂乱背景', sampling: 'adaptive', cleanup: 'medium', structure: true, maxColors: 40, crop: true, zoom: 1.12, background: 0.36, radius: 0.34, priorities: ['facial', 'outline'] },
  { id: 'illustration', label: '插画', description: '保留色块与清晰轮廓', sampling: 'adaptive', cleanup: 'medium', structure: true, maxColors: 36, crop: false, zoom: 1, background: 0.08, radius: 0.4, priorities: ['outline'] },
  { id: 'pixel_art', label: '像素画', description: '避免混色，保留像素边缘', sampling: 'edge_aware', cleanup: 'off', structure: false, maxColors: 32, crop: false, zoom: 1, background: 0, radius: 0.38, priorities: ['outline'] },
  { id: 'landscape', label: '风景', description: '平衡远近层次与色彩过渡', sampling: 'smooth', cleanup: 'medium', structure: true, maxColors: 48, crop: false, zoom: 1, background: 0.04, radius: 0.55, priorities: [] },
] as const
const eligiblePaletteColorCount = computed(() => palettes.current?.colors.filter(
  (color) => form.includeSpecialColors || color.effect !== 'special',
).length || 0)
const imageTitle = computed(() => image.value?.filename.replace(/\.[^.]+$/, '') || '未命名图纸')
const physicalSize = computed(() => {
  const widthMm = form.gridWidth * form.beadSize
  const heightMm = form.gridHeight * form.beadSize
  return `${(widthMm / 10).toFixed(1)} × ${(heightMm / 10).toFixed(1)} cm`
})
const selectedPreset = computed(() => presets.value.find(isPresetActive)?.name_zh || '自定义尺寸')
const isRevising = computed(() => Boolean(editingProjectId.value && editingPatternId.value))
const paletteGroups = computed(() => {
  const groups = new Map<string, typeof palettes.summaries>()
  for (const palette of palettes.summaries) groups.set(palette.brand, [...(groups.get(palette.brand) || []), palette])
  return [...groups.entries()].map(([brand, items]) => ({ brand, items }))
})
function colorimetryLabel(status: ColorimetryStatus) {
  if (status === 'measured_lab') return '实体校准'
  if (status === 'mixed_lab') return '部分校准'
  return '屏幕参考'
}
const paletteColorimetryHint = computed(() => {
  const palette = palettes.current
  if (!palette || !['measured_lab', 'mixed_lab'].includes(palette.colorimetry_status)) {
    return '当前色卡无实体 LAB，匹配与报告基于屏幕参考；特殊材质色需手动启用'
  }
  if (palette.colorimetry_status === 'mixed_lab') {
    return `实体 LAB 覆盖 ${palette.measurement_coverage_percent}%，其余色号回退屏幕参考；特殊材质色需手动启用`
  }
  return 'D65/2° 实体 LAB 已完整覆盖；特殊材质色仍需手动启用'
})
const inventoryItems = computed(() => Object.entries(inventory.value).filter(([, quantity]) => quantity > 0).map(([color_code, quantity]) => ({ color_code, quantity })))
const stockedColorCount = computed(() => inventoryItems.value.length)
const activeHotspot = computed<ConversionHotspot | undefined>(() => conversionPreview.value?.diagnostics.hotspots.find((hotspot) => hotspot.index === activePreviewIndex.value))
const previewSourceUrl = computed(() => image.value ? mediaUrl(image.value.preview_url) : '')
const colorStrategyLabel = computed(() => {
  if (!form.autoColorLimit) return `${form.maxColors} 色`
  const selected = conversionPreview.value?.color_report.selected_color_limit
  return selected
    ? `自动 ${selected} 色 · P95 目标 ${form.targetP95DeltaE}`
    : `质量控色（P95 ≤ ${form.targetP95DeltaE}，上限 ${form.maxColors}）`
})

function inventoryStoragePaletteId(paletteId: string) {
  return /^mard-(24|48|72|96|120|144|168|192|221|264|291)$/.test(paletteId) ? 'mard-291' : paletteId
}

function loadInventory(paletteId: string) {
  try {
    const saved = JSON.parse(window.localStorage.getItem(INVENTORY_STORAGE_KEY) || '{}') as Record<string, Record<string, number>>
    inventory.value = saved[inventoryStoragePaletteId(paletteId)] || {}
  } catch { inventory.value = {} }
}

function saveInventory() {
  const paletteId = palettes.current?.id
  if (!paletteId) return
  try {
    const saved = JSON.parse(window.localStorage.getItem(INVENTORY_STORAGE_KEY) || '{}') as Record<string, Record<string, number>>
    saved[inventoryStoragePaletteId(paletteId)] = inventory.value
    window.localStorage.setItem(INVENTORY_STORAGE_KEY, JSON.stringify(saved))
  } catch { /* Local storage can be unavailable in private browsing modes. */ }
}

function restoreInventorySnapshot(value: unknown) {
  if (!Array.isArray(value)) return
  inventory.value = Object.fromEntries(value.flatMap((item) => {
    if (!item || typeof item !== 'object') return []
    const { color_code, quantity } = item as { color_code?: unknown; quantity?: unknown }
    return typeof color_code === 'string' && typeof quantity === 'number' && quantity > 0 ? [[color_code, quantity]] : []
  }))
}

function restorePatternSettings(existing: Awaited<ReturnType<typeof getPattern>>) {
  const settings = existing.settings
  const assign = <T extends string>(key: string, allowed: readonly T[], apply: (value: T) => void) => {
    const value = settings[key]
    if (typeof value === 'string' && allowed.includes(value as T)) apply(value as T)
  }
  assign('resize_mode', ['stretch', 'contain', 'cover', 'pixel'] as const, (value) => { form.resizeMode = value })
  assign('sampling_mode', ['adaptive', 'edge_aware', 'smooth'] as const, (value) => { form.samplingMode = value })
  assign('distance_method', ['fidelity', 'rgb', 'cie76', 'cie94', 'ciede2000'] as const, (value) => { form.distance = value })
  assign('cleanup_level', ['off', 'light', 'medium'] as const, (value) => { form.cleanupLevel = value })
  form.gridWidth = existing.grid_width
  form.gridHeight = existing.grid_height
  form.beadSize = existing.statistics.bead_size_mm
  form.wasteRate = existing.statistics.waste_rate
  if (typeof settings.max_colors === 'number') form.maxColors = settings.max_colors
  if (typeof settings.auto_color_limit === 'boolean') form.autoColorLimit = settings.auto_color_limit
  if (typeof settings.target_p95_delta_e_00 === 'number') form.targetP95DeltaE = settings.target_p95_delta_e_00
  if (typeof settings.include_special_colors === 'boolean') form.includeSpecialColors = settings.include_special_colors
  if (typeof settings.minimum_color_count === 'number') form.minimumColorCount = settings.minimum_color_count
  if (typeof settings.structure_aware === 'boolean') form.structureAware = settings.structure_aware
  if (typeof settings.transparent_background === 'boolean') form.transparent = settings.transparent_background
  if (settings.inventory_mode === 'only' || settings.inventory_mode === 'report') form.inventoryMode = settings.inventory_mode
  assign('conversion_preset', ['custom', 'portrait', 'illustration', 'pixel_art', 'landscape'] as const, (value) => { form.conversionPreset = value })
  if (typeof settings.subject_crop === 'boolean') form.subjectCrop = settings.subject_crop
  if (typeof settings.focus_x === 'number') form.focusX = settings.focus_x
  if (typeof settings.focus_y === 'number') form.focusY = settings.focus_y
  if (typeof settings.focus_zoom === 'number') form.focusZoom = settings.focus_zoom
  if (typeof settings.focus_radius === 'number') form.focusRadius = settings.focus_radius
  if (typeof settings.background_weaken === 'number') form.backgroundWeaken = settings.background_weaken
  if (Array.isArray(settings.detail_priorities)) {
    form.detailPriorities = settings.detail_priorities.filter(
      (priority): priority is 'facial' | 'text' | 'outline' => priority === 'facial' || priority === 'text' || priority === 'outline',
    )
  }
  restoreInventorySnapshot(settings.inventory)
}

async function loadProjectSettings(projectId: string) {
  settingsLoading.value = true
  try {
    const project = await projects.load(projectId)
    if (!project.pattern_id) throw new Error('该项目还没有关联图纸')
    const existing = await getPattern(project.pattern_id)
    image.value = await getImage(existing.image_id)
    editingProjectId.value = project.id
    editingPatternId.value = existing.id
    restorePatternSettings(existing)
    const imageSettings = image.value.settings || {}
    if (typeof imageSettings.brightness === 'number') form.brightness = imageSettings.brightness
    if (typeof imageSettings.contrast === 'number') form.contrast = imageSettings.contrast
    if (typeof imageSettings.saturation === 'number') form.saturation = imageSettings.saturation
    if (typeof imageSettings.remove_background === 'boolean') form.removeBackground = imageSettings.remove_background
    await palettes.ensure(existing.palette_id)
    restoreInventorySnapshot(existing.settings.inventory)
  } finally {
    settingsLoading.value = false
    schedulePreview()
  }
}

onMounted(async () => {
  try {
    const [items] = await Promise.all([getGridPresets(), palettes.load()])
    presets.value = items
    const projectId = typeof route.query.project === 'string' ? route.query.project : ''
    if (projectId) await loadProjectSettings(projectId)
  } catch (error) { app.showError(error) }
})

watch(() => palettes.current?.id, (paletteId) => { if (paletteId) loadInventory(paletteId) })
watch(inventory, saveInventory, { deep: true })
watch(stockedColorCount, (count) => { if (!count && form.inventoryMode === 'only') form.inventoryMode = 'report' })

const previewSignature = computed(() => JSON.stringify({
  imageId: image.value?.image_id,
  paletteId: palettes.current?.id,
  gridWidth: form.gridWidth,
  gridHeight: form.gridHeight,
  resizeMode: form.resizeMode,
  samplingMode: form.samplingMode,
  distance: form.distance,
  maxColors: form.maxColors,
  autoColorLimit: form.autoColorLimit,
  targetP95DeltaE: form.targetP95DeltaE,
  includeSpecialColors: form.includeSpecialColors,
  minimumColorCount: form.minimumColorCount,
  cleanupLevel: form.cleanupLevel,
  structureAware: form.structureAware,
  transparent: form.transparent,
  beadSize: form.beadSize,
  wasteRate: form.wasteRate,
  inventory: inventoryItems.value,
  inventoryMode: form.inventoryMode,
  conversionPreset: form.conversionPreset,
  subjectCrop: form.subjectCrop,
  focusX: form.focusX,
  focusY: form.focusY,
  focusZoom: form.focusZoom,
  focusRadius: form.focusRadius,
  backgroundWeaken: form.backgroundWeaken,
  detailPriorities: form.detailPriorities,
}))

watch(previewSignature, () => schedulePreview(), { immediate: true })

onBeforeUnmount(() => { if (previewTimer) window.clearTimeout(previewTimer) })

function applyPreset(preset: GridPreset) {
  form.gridWidth = preset.grid_width
  form.gridHeight = preset.grid_height
  form.beadSize = preset.recommended_bead_size_mm
}

function isPresetActive(preset: GridPreset) {
  return preset.grid_width === form.gridWidth
    && preset.grid_height === form.gridHeight
    && preset.recommended_bead_size_mm === form.beadSize
}

function presetPhysicalSize(preset: GridPreset) {
  const beadSize = preset.recommended_bead_size_mm
  return `${(preset.grid_width * beadSize / 10).toFixed(1)} × ${(preset.grid_height * beadSize / 10).toFixed(1)} cm`
}

async function selectPalette(paletteId: string) {
  await palettes.load(paletteId)
  const capacity = eligiblePaletteColorCount.value || 221
  const presetCeiling = conversionPresets.find((item) => item.id === form.conversionPreset)?.maxColors ?? 48
  form.maxColors = form.autoColorLimit ? Math.min(presetCeiling, capacity) : Math.min(form.maxColors, capacity)
}

function applyConversionPreset(presetId: typeof conversionPresets[number]['id']) {
  if (form.conversionPreset === presetId) {
    // Keep the values currently on the canvas, but clear the preset marker so
    // creators can continue making manual adjustments without being locked in.
    form.conversionPreset = 'custom'
    return
  }
  const preset = conversionPresets.find((item) => item.id === presetId)
  if (!preset) return
  form.conversionPreset = preset.id
  form.samplingMode = preset.sampling
  form.cleanupLevel = preset.cleanup
  form.structureAware = preset.structure
  form.autoColorLimit = true
  form.maxColors = preset.maxColors
  form.subjectCrop = preset.crop
  form.focusZoom = preset.zoom
  form.backgroundWeaken = preset.background
  form.focusRadius = preset.radius
  form.detailPriorities = [...preset.priorities]
}

function setFocus(point: { x: number; y: number }) {
  form.focusX = point.x
  form.focusY = point.y
}

function clearImage() {
  image.value = undefined
  conversionPreview.value = undefined
  activePreviewIndex.value = null
}

function selectPreviewCell(index: number) {
  activePreviewIndex.value = index
}

function useHotspot(hotspot: ConversionHotspot) {
  activePreviewIndex.value = hotspot.index
}

function buildPayload(): GeneratePatternPayload | undefined {
  if (!image.value || !palettes.current) return undefined
  return {
    image_id: image.value.image_id,
    grid_width: form.gridWidth,
    grid_height: form.gridHeight,
    resize_mode: form.resizeMode,
    sampling_mode: form.samplingMode,
    palette_id: palettes.current.id,
    distance_method: form.distance,
    max_colors: form.maxColors || undefined,
    auto_color_limit: form.autoColorLimit,
    target_p95_delta_e_00: form.targetP95DeltaE,
    include_special_colors: form.includeSpecialColors,
    minimum_color_count: form.minimumColorCount,
    cleanup_level: form.cleanupLevel,
    structure_aware: form.structureAware,
    transparent_background: form.transparent,
    disabled_colors: [],
    locked_colors: [],
    inventory: inventoryItems.value,
    inventory_mode: form.inventoryMode,
    bead_size_mm: form.beadSize,
    waste_rate: form.wasteRate,
    conversion_preset: form.conversionPreset,
    subject_crop: form.subjectCrop,
    focus_x: form.focusX,
    focus_y: form.focusY,
    focus_zoom: form.focusZoom,
    focus_radius: form.focusRadius,
    background_weaken: form.backgroundWeaken,
    detail_priorities: form.detailPriorities,
  }
}

function schedulePreview() {
  if (previewTimer) window.clearTimeout(previewTimer)
  const payload = buildPayload()
  if (!payload || settingsLoading.value) {
    conversionPreview.value = undefined
    previewError.value = ''
    return
  }
  previewTimer = window.setTimeout(() => { void refreshPreview(payload) }, 420)
}

async function refreshPreview(payload: GeneratePatternPayload) {
  const requestId = ++previewRequestId
  previewing.value = true
  previewError.value = ''
  try {
    const preview = await previewPattern(payload)
    if (requestId !== previewRequestId) return
    conversionPreview.value = preview
    if (activePreviewIndex.value !== null && activePreviewIndex.value >= preview.cells.length) activePreviewIndex.value = null
  } catch (error) {
    if (requestId === previewRequestId) {
      conversionPreview.value = undefined
      previewError.value = error instanceof Error ? error.message : '预览生成失败，请检查图纸参数'
    }
  } finally {
    if (requestId === previewRequestId) previewing.value = false
  }
}

async function preprocess() {
  if (!image.value) return
  preprocessing.value = true
  try {
    image.value = await preprocessImage({
      image_id: image.value.image_id,
      brightness: form.brightness,
      contrast: form.contrast,
      saturation: form.saturation,
      remove_background: form.removeBackground,
    })
    app.showNotice('已更新预处理预览')
  } catch (error) { app.showError(error) } finally { preprocessing.value = false }
}

async function createPattern() {
  const payload = buildPayload()
  if (!payload) return
  generating.value = true
  try {
    const pattern = isRevising.value
      ? await regeneratePattern(editingPatternId.value, payload)
      : await generatePattern(payload)
    const project = isRevising.value
      ? { id: editingProjectId.value }
      : await projects.create(imageTitle.value, pattern.id)
    app.showNotice(isRevising.value ? '图纸设置已更新，已保留在原项目中' : '图纸已生成，可以开始逐格修正')
    await router.push(`/editor/${project.id}`)
  } catch (error) { app.showError(error) } finally { generating.value = false }
}
</script>

<template>
  <main class="convert">
    <header class="page-heading">
      <div><p class="eyebrow">{{ isRevising ? 'Pattern settings' : 'New pattern' }}</p><h1>{{ isRevising ? '调整图纸设置。' : '从图片，做成图纸。' }}</h1><p>{{ isRevising ? '修改尺寸、色卡或匹配方式后，将在当前项目中重新生成图纸。' : '设定成品尺寸与颜色策略，生成后仍可在编辑器中精细调整。' }}</p></div>
      <ol class="progress" aria-label="制作流程"><li class="active"><b>1</b>图片</li><li><b>2</b>图纸</li><li><b>3</b>编辑</li></ol>
    </header>
    <section class="conversion-guide" aria-label="当前图纸生成进度">
      <div :class="{ ready: Boolean(image) }"><span>1</span><p><b>{{ image ? '素材已就绪' : '导入参考图片' }}</b><small>{{ image ? image.filename : '支持常见图片与透明背景' }}</small></p></div>
      <i aria-hidden="true" />
      <div :class="{ ready: Boolean(palettes.current) }"><span>2</span><p><b>确认图纸规格</b><small>{{ selectedPreset }} · {{ physicalSize }}</small></p></div>
      <i aria-hidden="true" />
      <div :class="{ ready: Boolean(conversionPreview) }"><span>3</span><p><b>{{ previewing ? '正在预览色差' : conversionPreview ? '预览可供检查' : '生成前实时预览' }}</b><small>{{ conversionPreview ? '可点击高色差格进行定位' : '参数变更后自动更新' }}</small></p></div>
    </section>

    <div class="convert__grid">
      <div class="asset-column">
        <section class="asset-card card">
        <div class="section-title"><span class="section-title__index">01</span><div><h2>选择素材</h2><p>支持透明背景，上传后可以快速调色。</p></div></div>
        <div v-if="settingsLoading" class="image-loading">正在恢复当前图纸的素材与设置…</div>
        <ImageUploader v-else-if="!image" @uploaded="image = $event" @error="app.showError" />
        <template v-else>
          <div class="image-preview"><img :src="mediaUrl(image.preview_url)" :alt="image.filename"><span class="image-preview__badge">已载入</span></div>
          <div class="asset-meta"><div><strong>{{ image.filename }}</strong><span>{{ image.width }} × {{ image.height }} px</span></div><button class="button button--quiet" @click="clearImage">更换图片</button></div>
          <details class="tune-panel">
            <summary><span>快速预处理</span><small>亮度、对比度、饱和度</small></summary>
            <div class="tune-panel__content"><div class="three-fields"><label class="field">亮度<input v-model.number="form.brightness" type="number" min="0" max="3" step=".1"></label><label class="field">对比度<input v-model.number="form.contrast" type="number" min="0" max="3" step=".1"></label><label class="field">饱和度<input v-model.number="form.saturation" type="number" min="0" max="3" step=".1"></label></div><label class="switch"><input v-model="form.removeBackground" type="checkbox"><span />移除纯色背景</label><button class="button button--quiet" :disabled="preprocessing" @click="preprocess">{{ preprocessing ? '正在更新…' : '应用到预览' }}</button></div>
          </details>
        </template>
        </section>
        <aside class="output-brief card" aria-label="当前图纸方案摘要">
          <div class="output-brief__head"><div><p class="eyebrow">PATTERN BRIEF</p><h2>当前成品方案</h2></div><span :class="{ ready: Boolean(image) }">{{ image ? '已就绪' : '等待素材' }}</span></div>
          <dl><div><dt>图纸用途</dt><dd>{{ selectedPreset }}</dd></div><div><dt>网格规格</dt><dd>{{ form.gridWidth }} × {{ form.gridHeight }} 格</dd></div><div><dt>成品尺寸</dt><dd>{{ physicalSize }}</dd></div><div><dt>颜色策略</dt><dd>{{ colorStrategyLabel }} · {{ form.inventoryMode === 'only' ? '严格库存' : '保真匹配' }}</dd></div></dl>
          <p><i>✦</i>{{ image ? '调整右侧参数时，预览与下方生成摘要会同步更新。' : '导入图片后，可先选用途，再按需微调色彩与主体。' }}</p>
        </aside>
      </div>

      <section class="settings-card card">
        <div class="section-title"><span class="section-title__index">02</span><div><h2>设定图纸</h2><p>从成品用途开始，再调整颜色细节。</p></div></div>
        <div class="settings-callout"><span>建议顺序</span><p><b>先选尺寸与转换预设</b>，确认实时预览后，再按需要展开库存和高级质量选项。</p></div>
        <div class="setting-group"><div class="setting-group__head"><strong>成品尺寸</strong><span>{{ selectedPreset }}</span></div><div class="presets"><button v-for="preset in presets" :key="preset.id" type="button" class="preset" :class="{ active: isPresetActive(preset) }" @click="applyPreset(preset)"><b>{{ preset.name_zh }}</b><small>{{ preset.use_case }}</small><em>{{ preset.grid_width }} × {{ preset.grid_height }} 格 · {{ presetPhysicalSize(preset) }}</em></button></div><div class="two-fields"><label class="field">宽度 <input v-model.number="form.gridWidth" type="number" min="1" max="500"></label><label class="field">高度 <input v-model.number="form.gridHeight" type="number" min="1" max="500"></label></div><p class="physical-size">成品约 {{ physicalSize }} · {{ form.beadSize }} mm 拼豆</p></div>
        <div class="setting-group conversion-group"><div class="setting-group__head"><strong>转换预设</strong><span>{{ form.conversionPreset === 'custom' ? '点击预设可一键应用策略' : '再次点击当前预设即可取消标记' }}</span></div><div class="conversion-presets"><button v-for="preset in conversionPresets" :key="preset.id" type="button" :class="{ active: form.conversionPreset === preset.id }" :aria-pressed="form.conversionPreset === preset.id" @click="applyConversionPreset(preset.id)"><b>{{ preset.label }}</b><small>{{ preset.description }}</small></button></div><div class="focus-controls"><label class="switch"><input v-model="form.subjectCrop" type="checkbox"><span />主体裁切</label><label class="field range-field">主体缩放 <output>{{ form.focusZoom.toFixed(2) }}×</output><input v-model.number="form.focusZoom" type="range" min="1" max="2.4" step=".04"></label><label class="field range-field">背景弱化 <output>{{ Math.round(form.backgroundWeaken * 100) }}%</output><input v-model.number="form.backgroundWeaken" type="range" min="0" max=".8" step=".04"></label><label class="field range-field">焦点范围 <output>{{ Math.round(form.focusRadius * 100) }}%</output><input v-model.number="form.focusRadius" type="range" min=".15" max=".75" step=".02"></label></div><div class="detail-priorities"><span>关键区域保护</span><label><input v-model="form.detailPriorities" type="checkbox" value="facial">五官</label><label><input v-model="form.detailPriorities" type="checkbox" value="text">文字</label><label><input v-model="form.detailPriorities" type="checkbox" value="outline">轮廓</label><small>可在下方原图中直接点击，设定焦点位置。</small></div></div>
        <div class="setting-group"><div class="setting-group__head"><strong>专业色彩工作台</strong><span>ΔE00 保真</span></div><div class="two-fields"><label class="field">品牌色卡<select :value="palettes.current?.id" @change="selectPalette(($event.target as HTMLSelectElement).value)"><optgroup v-for="group in paletteGroups" :key="group.brand" :label="group.brand"><option v-for="palette in group.items" :key="palette.id" :value="palette.id">{{ palette.name }}（{{ palette.color_count }} 色）· {{ colorimetryLabel(palette.colorimetry_status) }}</option></optgroup></select><small>{{ paletteColorimetryHint }}</small></label><label class="field">库存策略<select v-model="form.inventoryMode"><option value="report">报告模式：保留最佳配色</option><option value="only" :disabled="!stockedColorCount">严格库存：只使用现有颜色</option></select><small>{{ stockedColorCount ? `已录入 ${stockedColorCount} 个库存色` : '先在下方录入库存色' }}</small></label></div><InventoryPanel v-if="palettes.current" v-model="inventory" :colors="palettes.current.colors" /></div>
        <details class="advanced"><summary>高级质量选项 <span>结构、色差和色块清理</span></summary><div class="advanced__content"><label class="field">缩放方式<select v-model="form.resizeMode"><option value="contain">保持比例并补透明边</option><option value="cover">保持比例并裁剪</option><option value="stretch">拉伸到网格</option><option value="pixel">原像素一比一</option></select></label><label class="field">网格采样<select v-model="form.samplingMode"><option value="adaptive">智能保真（推荐）</option><option value="edge_aware">轮廓优先（像素插画）</option><option value="smooth">平滑混色（柔和插画）</option></select></label><label class="field">色差算法<select v-model="form.distance"><option value="ciede2000">LAB + CIEDE2000（推荐）</option><option value="fidelity">旧版混合感知距离</option><option value="cie94">CIE94</option><option value="cie76">CIE76</option><option value="rgb">RGB 欧氏距离</option></select></label><label class="field">色块清理<select v-model="form.cleanupLevel"><option value="off">关闭（像素画适用）</option><option value="light">轻度（仅清理单格杂点）</option><option value="medium">边缘感知区域优化（推荐）</option></select></label><label class="switch"><input v-model="form.structureAware" type="checkbox"><span />结构感知重点保护</label><label class="switch"><input v-model="form.autoColorLimit" type="checkbox"><span />按质量目标自动选色</label><label class="field">P95 ΔE00 目标<input v-model.number="form.targetP95DeltaE" type="number" min=".5" max="30" step=".5" :disabled="!form.autoColorLimit"><small>达到目标后停止增加色号，越小越保真</small></label><label class="field">作品颜色上限<input v-model.number="form.maxColors" type="number" min="1" :max="eligiblePaletteColorCount || 221"><small>{{ form.autoColorLimit ? '质量选色的生产上限' : '固定限制本次图纸使用的颜色数' }}</small></label><label class="switch"><input v-model="form.includeSpecialColors" type="checkbox"><span />允许扩展／特殊材质色</label><label class="field">低频合并<input v-model.number="form.minimumColorCount" type="number" min="0" max="100"><small>0 表示关闭，避免误删眼睛等细节</small></label><label class="field">拼豆尺寸<select v-model.number="form.beadSize"><option :value="2.6">迷你豆 2.6 mm</option><option :value="5">中号豆 5.0 mm</option></select></label><label class="field">损耗率<input v-model.number="form.wasteRate" type="number" min="0" max="1" step=".01"></label><label class="switch"><input v-model="form.transparent" type="checkbox"><span />透明背景保留为空格</label></div></details>
      </section>
    </div>
    <ConversionPreview v-if="image" :source-url="previewSourceUrl" :source-width="image.width" :source-height="image.height" :preview="conversionPreview" :colors="palettes.current?.colors || []" :loading="previewing" :focus-x="form.focusX" :focus-y="form.focusY" :subject-crop="form.subjectCrop" :active-index="activePreviewIndex" :show-heatmap="heatmapVisible" @focus="setFocus" @select="selectPreviewCell" @update-heatmap="heatmapVisible = $event" />
    <section v-if="conversionPreview?.diagnostics.hotspots.length" class="hotspot-panel card"><div><p class="eyebrow">CORRECTION QUEUE</p><h2>优先修正高色差格</h2><p>{{ activeHotspot ? `当前定位：第 ${activeHotspot.column} 列、第 ${activeHotspot.row} 行，ΔE00 ${activeHotspot.delta_e_00}` : '点击任意热点，图纸预览会标记对应格子。' }}</p></div><div class="hotspot-list"><button v-for="hotspot in conversionPreview.diagnostics.hotspots.slice(0, 8)" :key="hotspot.index" type="button" :class="{ active: activePreviewIndex === hotspot.index }" @click="useHotspot(hotspot)"><b>{{ hotspot.column }},{{ hotspot.row }}</b><span>{{ hotspot.color_code }}</span><em>ΔE {{ hotspot.delta_e_00 }}</em></button></div></section>
    <p v-if="previewError" class="preview-error">预览暂不可用：{{ previewError }}</p>
    <footer class="create-bar" :class="{ 'create-bar--ready': Boolean(image && palettes.current) }" aria-live="polite"><div class="create-bar__summary"><i aria-hidden="true" /><div><strong>{{ form.gridWidth }} × {{ form.gridHeight }}</strong><span>{{ !image ? '请先导入一张参考图片' : !palettes.current ? '正在载入品牌色卡…' : `${palettes.current.brand} · ${colorStrategyLabel} · ${form.inventoryMode === 'only' ? '严格库存' : '库存报告'}` }}</span></div></div><button class="button create" :disabled="!image || !palettes.current || generating || settingsLoading" @click="createPattern">{{ generating ? '正在生成图纸…' : isRevising ? '更新图纸并返回编辑器 →' : '生成图纸并进入编辑器 →' }}</button></footer>
  </main>
</template>

<style scoped>
.convert { max-width: 1220px; margin: 0 auto; padding: 48px clamp(18px, 4vw, 42px) 72px; }.page-heading { display: flex; align-items: end; justify-content: space-between; gap: 24px; margin-bottom: 23px; }.page-heading h1 { margin: 10px 0 9px; font-family: Fraunces, Georgia, serif; font-size: clamp(34px, 4vw, 50px); letter-spacing: -2.1px; }.page-heading > div > p:last-child { max-width: 590px; margin: 0; color: var(--ink-soft); font-size: 14px; line-height: 1.65; }.progress { display: flex; gap: 13px; padding: 0; margin: 0; color: #929aab; list-style: none; font-size: 11px; font-weight: 800; }.progress li { display: flex; align-items: center; gap: 5px; }.progress b { display: grid; width: 22px; height: 22px; place-items: center; border: 1px solid var(--line-strong); border-radius: 50%; font-family: "DM Mono", monospace; font-size: 10px; }.progress .active { color: var(--violet); }.progress .active b { border-color: var(--violet); background: var(--violet); color: #fff; box-shadow: 0 4px 10px rgb(104 84 232 / 22%); }.conversion-guide { display: grid; grid-template-columns: 1fr auto 1fr auto 1fr; align-items: center; gap: 9px; margin: 0 0 18px; padding: 11px 13px; border: 1px solid #e2dff0; border-radius: 14px; background: rgb(255 255 255 / 70%); box-shadow: 0 5px 15px rgb(35 45 75 / 4%); }.conversion-guide > div { display: flex; min-width: 0; align-items: center; gap: 8px; padding: 3px; color: #7b8599; }.conversion-guide > div > span { display: grid; width: 24px; height: 24px; flex: 0 0 24px; place-items: center; border: 1px solid #d7d4e2; border-radius: 8px; background: #f6f5f9; color: #8a93a4; font-family: var(--font-mono); font-size: 9px; font-weight: 800; }.conversion-guide > div.ready > span { border-color: #b9ead9; background: #ebfaf3; color: #278668; }.conversion-guide p { display: grid; min-width: 0; gap: 2px; margin: 0; }.conversion-guide b, .conversion-guide small { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }.conversion-guide b { color: #4c566d; font-size: 10px; }.conversion-guide .ready b { color: #35725e; }.conversion-guide small { color: #929aaa; font-size: 9px; }.conversion-guide > i { width: 22px; height: 1px; background: #dedbe7; }.image-loading { display: grid; min-height: 278px; place-items: center; border: 1px dashed #d7d2eb; border-radius: 15px; color: #747e95; font-size: 12px; text-align: center; }
.convert__grid { display: grid; grid-template-columns: minmax(330px, .78fr) minmax(500px, 1.22fr); gap: 18px; align-items: start; }.asset-column { position: sticky; top: 86px; display: grid; gap: 14px; align-content: start; }.asset-card, .settings-card { padding: 21px; }.section-title { display: flex; gap: 12px; align-items: start; margin-bottom: 20px; }.section-title__index { display: grid; flex: 0 0 auto; width: 30px; height: 30px; place-items: center; border-radius: 10px; background: #eeeaff; color: var(--violet); font-family: "DM Mono", monospace; font-size: 10px; font-weight: 700; }.section-title h2 { margin: 0; font-size: 16px; }.section-title p { margin: 3px 0 0; color: #7a8495; font-size: 11px; }.output-brief { padding: 17px 18px; border-color: #ded9f2; background: linear-gradient(135deg, #fff, #f8f7ff); }.output-brief__head { display: flex; align-items: start; justify-content: space-between; gap: 10px; }.output-brief .eyebrow { font-size: 9px; }.output-brief h2 { margin: 4px 0 0; color: #313c59; font-size: 15px; }.output-brief__head > span { flex: 0 0 auto; border: 1px solid #e1dee9; border-radius: 99px; padding: 4px 7px; color: #858da0; background: #fafaff; font-size: 9px; font-weight: 800; white-space: nowrap; }.output-brief__head > span.ready { border-color: #cdecdE; color: #2c896b; background: #effaf4; }.output-brief dl { display: grid; gap: 0; margin: 14px 0 0; }.output-brief dl div { display: flex; justify-content: space-between; gap: 10px; border-top: 1px solid #ece9f3; padding: 8px 0; }.output-brief dt { color: #8b94a6; font-size: 10px; }.output-brief dd { max-width: 58%; overflow: hidden; margin: 0; color: #4d5870; font-family: var(--font-mono); font-size: 9px; font-weight: 700; text-align: right; text-overflow: ellipsis; white-space: nowrap; }.output-brief > p { display: flex; gap: 6px; margin: 6px 0 0; color: #778298; font-size: 10px; line-height: 1.55; }.output-brief > p i { display: grid; width: 17px; height: 17px; flex: 0 0 17px; place-items: center; border-radius: 6px; color: #6953cc; background: #eeebff; font-size: 9px; font-style: normal; }.settings-callout { display: flex; align-items: center; gap: 10px; margin: -4px 0 4px; border: 1px solid #e5e1f2; border-radius: 11px; padding: 9px 10px; background: #faf9ff; }.settings-callout > span { flex: 0 0 auto; border-radius: 99px; padding: 4px 6px; color: #5f4cb9; background: #eeeaff; font-size: 9px; font-weight: 800; white-space: nowrap; }.settings-callout p { margin: 0; color: #798398; font-size: 10px; line-height: 1.55; }.settings-callout b { color: #4a3ca6; }.image-preview { position: relative; display: grid; min-height: 278px; overflow: hidden; place-items: center; border-radius: 15px; background: repeating-conic-gradient(#f0f2f7 0 25%, #fff 0 50%) 50% / 22px 22px; }.image-preview img { display: block; width: 100%; max-height: 395px; object-fit: contain; }.image-preview__badge { position: absolute; top: 12px; left: 12px; padding: 5px 8px; border: 1px solid rgb(255 255 255 / 70%); border-radius: 99px; background: rgb(25 35 59 / 78%); color: #fff; font-size: 10px; font-weight: 800; backdrop-filter: blur(8px); }.asset-meta { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 14px 2px 0; }.asset-meta strong, .asset-meta span { display: block; }.asset-meta strong { max-width: 220px; overflow: hidden; font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }.asset-meta span { margin-top: 3px; color: #778196; font-family: "DM Mono", monospace; font-size: 10px; }.asset-meta .button { min-height: 34px; padding: 6px 10px; font-size: 11px; }
.setting-group { display: grid; gap: 11px; padding: 16px 0; border-top: 1px solid var(--line); }.setting-group__head { display: flex; justify-content: space-between; align-items: center; }.setting-group__head strong { font-size: 13px; }.setting-group__head span { color: #788396; font-family: "DM Mono", monospace; font-size: 10px; }.presets { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 6px; max-height: 156px; overflow: auto; }.preset { display: grid; min-width: 0; gap: 3px; padding: 8px; border: 1px solid var(--line); border-radius: 10px; background: #fbfcff; color: #526073; text-align: left; transition: border-color .18s ease, background .18s ease, transform .18s ease; }.preset:hover { border-color: #aaa0f4; transform: translateY(-1px); }.preset.active { border-color: var(--violet); background: #f1efff; color: #4031ba; box-shadow: inset 0 0 0 1px rgb(104 84 232 / 8%); }.preset b, .preset small, .preset em { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }.preset b { font-size: 10px; }.preset small { color: #8490a2; font-size: 9px; }.preset em { color: #69758b; font-family: "DM Mono", monospace; font-size: 8px; font-style: normal; }.preset.active em { color: #5e4bc7; }.two-fields, .three-fields { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 9px; }.three-fields { grid-template-columns: repeat(3, minmax(0, 1fr)); }.physical-size { margin: -2px 0 0; color: #6f7b90; font-size: 11px; }
.advanced, .tune-panel { border: 1px solid var(--line); border-radius: 12px; background: #fafbfe; }.advanced summary, .tune-panel summary { display: flex; align-items: center; justify-content: space-between; padding: 11px 12px; color: #3c485c; cursor: pointer; font-size: 12px; font-weight: 800; list-style: none; }.advanced summary::-webkit-details-marker, .tune-panel summary::-webkit-details-marker { display: none; }.advanced summary span, .tune-panel summary small { color: #8791a3; font-size: 10px; font-weight: 600; }.advanced[open] summary, .tune-panel[open] summary { border-bottom: 1px solid var(--line); }.advanced__content { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; padding: 12px; }.tune-panel { margin-top: 13px; }.tune-panel__content { display: grid; gap: 11px; padding: 12px; }.switch { display: inline-flex; align-items: center; gap: 8px; color: #4b5669; font-size: 12px; font-weight: 700; }.switch input { position: absolute; opacity: 0; }.switch span { position: relative; width: 33px; height: 19px; border-radius: 99px; background: #d8deea; transition: background .18s ease; }.switch span::after { position: absolute; top: 3px; left: 3px; width: 13px; height: 13px; border-radius: 50%; background: #fff; box-shadow: 0 1px 3px rgb(20 30 50 / 20%); content: ''; transition: transform .18s ease; }.switch input:checked + span { background: var(--violet); }.switch input:checked + span::after { transform: translateX(14px); }
.conversion-group { gap: 13px; }.conversion-presets { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 7px; }.conversion-presets button { display: grid; min-height: 64px; gap: 3px; padding: 9px; border: 1px solid #e4e1ed; border-radius: 10px; background: #fbfcff; color: #515b70; text-align: left; transition: border-color .18s ease, background .18s ease, transform .18s ease; }.conversion-presets button:hover { border-color: #b6aaef; transform: translateY(-1px); }.conversion-presets button.active { border-color: #7660dc; background: linear-gradient(135deg, #f2efff, #f6fbff); color: #4f3db6; box-shadow: inset 0 0 0 1px rgb(104 84 232 / 9%); }.conversion-presets b { font-size: 11px; }.conversion-presets small { color: #818b9d; font-size: 9px; line-height: 1.45; }.focus-controls { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 9px; padding: 10px; border: 1px solid #e8e6f0; border-radius: 10px; background: #fbfcff; }.focus-controls .switch { grid-column: 1 / -1; }.range-field { grid-template-columns: 1fr auto; align-items: center; gap: 4px 8px; font-size: 10px; }.range-field output { color: #6c5cc6; font-family: var(--font-mono); font-size: 9px; }.range-field input { grid-column: 1 / -1; width: 100%; accent-color: var(--violet); }.detail-priorities { display: flex; flex-wrap: wrap; align-items: center; gap: 7px; color: #596377; font-size: 10px; }.detail-priorities > span { color: #3e485b; font-weight: 800; }.detail-priorities label { display: inline-flex; align-items: center; gap: 4px; padding: 4px 7px; border: 1px solid #e1deea; border-radius: 99px; background: #fff; }.detail-priorities input { accent-color: var(--violet); }.detail-priorities small { width: 100%; color: #8891a2; font-size: 9px; }.hotspot-panel { display: grid; grid-template-columns: minmax(190px, .52fr) minmax(0, 1fr); gap: 18px; align-items: center; margin-top: 18px; padding: 18px 21px; }.hotspot-panel h2 { margin: 6px 0 4px; font-size: 15px; }.hotspot-panel p:last-child { margin: 0; color: #778196; font-size: 10px; line-height: 1.55; }.hotspot-list { display: flex; flex-wrap: wrap; gap: 6px; }.hotspot-list button { display: grid; grid-template-columns: auto auto; gap: 1px 6px; min-width: 78px; padding: 6px 7px; border: 1px solid #e4e1ec; border-radius: 8px; background: #fbfcff; color: #697388; text-align: left; }.hotspot-list button:hover, .hotspot-list button.active { border-color: #ef9a83; background: #fff6f2; color: #b55744; }.hotspot-list b { font-family: var(--font-mono); font-size: 10px; }.hotspot-list span, .hotspot-list em { font-size: 8px; font-style: normal; }.hotspot-list em { grid-column: 1 / -1; color: #bb6b59; }.preview-error { margin: 13px 2px -4px; color: #b44f57; font-size: 11px; }
.create-bar { position: sticky; z-index: 4; bottom: 18px; display: flex; align-items: center; justify-content: space-between; gap: 14px; margin-top: 19px; padding: 12px 13px 12px 17px; border: 1px solid rgb(205 198 248 / 92%); border-radius: 16px; background: rgb(255 255 255 / 93%); box-shadow: 0 18px 42px rgb(38 45 77 / 15%); backdrop-filter: blur(15px); }.create-bar__summary { display: flex; min-width: 0; align-items: center; gap: 10px; }.create-bar__summary > i { width: 9px; height: 9px; flex: 0 0 9px; border-radius: 50%; background: #c9ced9; box-shadow: 0 0 0 5px #f1f2f5; transition: background .2s ease, box-shadow .2s ease; }.create-bar--ready .create-bar__summary > i { background: #43b38d; box-shadow: 0 0 0 5px #e6f8f0; }.create-bar strong, .create-bar span { display: block; }.create-bar strong { color: #343f56; font-family: "DM Mono", monospace; font-size: 12px; }.create-bar span { overflow: hidden; margin-top: 3px; color: #7c8799; font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }.create { min-height: 44px; }
@media (max-width: 900px) { .convert__grid { grid-template-columns: 1fr; }.asset-column { position: static; grid-template-columns: minmax(0, 1.15fr) minmax(250px, .85fr); align-items: stretch; }.asset-card { order: 0; }.settings-card { order: 1; }.image-preview { min-height: 230px; }.presets { grid-template-columns: repeat(4, minmax(0, 1fr)); }.hotspot-panel { grid-template-columns: 1fr; } } @media (max-width: 600px) { .convert { padding: 32px 15px 58px; }.page-heading { align-items: start; flex-direction: column; margin-bottom: 18px; }.progress { width: 100%; justify-content: space-between; }.progress li { font-size: 10px; }.conversion-guide { grid-template-columns: 1fr; gap: 5px; padding: 9px; }.conversion-guide > i { display: none; }.conversion-guide > div { padding: 5px; }.asset-column { grid-template-columns: 1fr; }.asset-card, .settings-card { padding: 15px; border-radius: 15px; }.output-brief { padding: 15px; }.settings-callout { align-items: start; flex-direction: column; gap: 6px; }.presets, .conversion-presets { grid-template-columns: repeat(2, minmax(0, 1fr)); }.focus-controls, .advanced__content { grid-template-columns: 1fr; }.create-bar { bottom: 10px; }.create-bar span { display: none; }.create { flex: 1; } }
</style>
