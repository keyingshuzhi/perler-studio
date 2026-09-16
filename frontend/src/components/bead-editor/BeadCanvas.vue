<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { contrastText, shortCode } from '@/utils/color'
import { coordinateLabelIndices, editorBaseCellSize, rectangleSelection, shouldRenderCellSymbols } from '@/utils/grid'
import type { CellValue, EditorTool, SymbolMode } from '@/types/bead'
import type { PaletteColor } from '@/types/palette'

const props = defineProps<{
  width: number
  height: number
  cells: readonly CellValue[]
  draftCells: Readonly<Record<string, string>>
  palette: readonly PaletteColor[]
  tool: EditorTool
  zoom: number
  showGrid: boolean
  showCoordinates: boolean
  symbolMode: SymbolMode
  selectedIndices: readonly number[]
  lockedIndices: readonly number[]
  referenceUrl?: string
  referenceVisible: boolean
  referenceOpacity: number
  draftVisible: boolean
  finishedVisible: boolean
  renderVersion: number
}>()

const emit = defineEmits<{
  interact: [index: number, erase: boolean]
  hover: [position: { row: number; column: number; index: number }]
  select: [startIndex: number, endIndex: number]
}>()

const canvas = ref<HTMLCanvasElement>()
const baseCell = computed(() => editorBaseCellSize(props.width, props.height))
const margin = computed(() => (props.showCoordinates ? Math.max(26, String(Math.max(props.width, props.height)).length * 6 + 12) : 0))
const logicalWidth = computed(() => margin.value * 2 + props.width * baseCell.value)
const logicalHeight = computed(() => margin.value * 2 + props.height * baseCell.value)
const style = computed(() => ({ width: `${logicalWidth.value * props.zoom}px`, height: `${logicalHeight.value * props.zoom}px` }))
let frame = 0
let lastIndex = -1
let selectionStart: number | null = null
let selectionEnd: number | null = null
let referenceImage: HTMLImageElement | undefined

interface SymbolLayout {
  lines: string[]
  fontSize: number
  lineHeight: number
}

function symbolFont(context: CanvasRenderingContext2D, size: number) {
  context.font = `700 ${size}px ui-monospace, SFMono-Regular, Menlo, Consolas, monospace`
}

function resolveSymbolLayout(
  context: CanvasRenderingContext2D,
  code: string,
  mode: Exclude<SymbolMode, 'none'>,
  cell: number,
): SymbolLayout | null {
  const screenCell = cell * props.zoom
  const desiredScreenFont = mode === 'short_code'
    ? Math.min(11, Math.max(6, screenCell * .34))
    : Math.min(9, Math.max(6, screenCell * .28))
  const desiredFont = desiredScreenFont / props.zoom
  const availableWidth = Math.max(1, cell - 4 / props.zoom)
  const availableHeight = Math.max(1, cell - 3 / props.zoom)
  const label = mode === 'short_code' ? shortCode(code) : code

  symbolFont(context, desiredFont)
  if (context.measureText(label).width <= availableWidth) {
    return { lines: [label], fontSize: desiredFont, lineHeight: desiredFont * 1.08 }
  }

  const separator = mode === 'color_code' ? code.lastIndexOf('-') : -1
  const lines = separator > 0 && separator < code.length - 1
    ? [code.slice(0, separator), code.slice(separator + 1)]
    : [label]
  const widestLine = Math.max(...lines.map((line) => context.measureText(line).width))
  const widthScale = availableWidth / Math.max(1, widestLine)
  const heightScale = availableHeight / (desiredFont * 1.08 * lines.length)
  const fittedFont = desiredFont * Math.min(1, widthScale, heightScale)

  // Tiny text is visually noisy and cannot be read reliably. The toolbar offers
  // a one-click zoom action until the cell reaches the legible screen threshold.
  if (fittedFont * props.zoom < 5.5) return null
  return { lines, fontSize: fittedFont, lineHeight: fittedFont * 1.08 }
}

function drawCellSymbol(
  context: CanvasRenderingContext2D,
  layout: SymbolLayout,
  color: PaletteColor,
  x: number,
  y: number,
  cell: number,
) {
  context.fillStyle = contrastText(color.hex)
  symbolFont(context, layout.fontSize)
  context.textAlign = 'center'
  context.textBaseline = 'middle'
  const firstLineY = y + cell / 2 - (layout.lines.length - 1) * layout.lineHeight / 2
  layout.lines.forEach((line, index) => {
    context.fillText(line, x + cell / 2, firstLineY + index * layout.lineHeight)
  })
}

function scheduleRender() {
  if (frame) return
  frame = window.requestAnimationFrame(() => { frame = 0; render() })
}

function drawSelection(context: CanvasRenderingContext2D, indices: readonly number[], cell: number, offset: number) {
  if (!indices.length) return
  context.fillStyle = 'rgb(114 86 230 / 20%)'
  context.strokeStyle = '#6248d2'
  context.lineWidth = 1.5
  for (const index of indices) {
    const row = Math.floor(index / props.width)
    const column = index % props.width
    const x = offset + column * cell
    const y = offset + row * cell
    context.fillRect(x + 1, y + 1, cell - 2, cell - 2)
    context.strokeRect(x + .75, y + .75, cell - 1.5, cell - 1.5)
  }
}

function render() {
  const element = canvas.value
  if (!element || !props.width || !props.height) return
  const ratio = window.devicePixelRatio || 1
  element.width = logicalWidth.value * ratio
  element.height = logicalHeight.value * ratio
  const context = element.getContext('2d')
  if (!context) return
  context.setTransform(ratio, 0, 0, ratio, 0, 0)
  context.clearRect(0, 0, logicalWidth.value, logicalHeight.value)

  const cell = baseCell.value
  const offset = margin.value
  const colors = new Map(props.palette.map((color) => [color.code, color]))
  const renderSymbols = shouldRenderCellSymbols(cell, props.zoom, props.symbolMode)
  const symbolLayouts = new Map<string, SymbolLayout | null>()
  context.fillStyle = '#f2eee7'
  context.fillRect(0, 0, logicalWidth.value, logicalHeight.value)
  context.fillStyle = '#fffdf9'
  context.fillRect(offset, offset, props.width * cell, props.height * cell)

  if (props.referenceVisible && referenceImage?.complete && referenceImage.naturalWidth) {
    context.save()
    context.globalAlpha = props.referenceOpacity / 100
    context.drawImage(referenceImage, offset, offset, props.width * cell, props.height * cell)
    context.restore()
  }

  if (props.finishedVisible) {
    for (let index = 0; index < props.cells.length; index += 1) {
      const code = props.cells[index]
      if (!code) continue
      const color = colors.get(code)
      if (!color) continue
      const row = Math.floor(index / props.width)
      const column = index % props.width
      const x = offset + column * cell
      const y = offset + row * cell
      context.fillStyle = color.hex
      context.fillRect(x, y, cell, cell)
      if (renderSymbols && props.symbolMode !== 'none') {
        let layout = symbolLayouts.get(code)
        if (layout === undefined) {
          layout = resolveSymbolLayout(context, code, props.symbolMode, cell)
          symbolLayouts.set(code, layout)
        }
        if (layout) drawCellSymbol(context, layout, color, x, y, cell)
      }
    }
  }

  if (props.draftVisible) {
    for (const [indexString, code] of Object.entries(props.draftCells)) {
      const index = Number(indexString)
      const color = colors.get(code)
      if (!Number.isInteger(index) || !color) continue
      const row = Math.floor(index / props.width)
      const column = index % props.width
      const x = offset + column * cell
      const y = offset + row * cell
      context.save()
      context.globalAlpha = .58
      context.fillStyle = color.hex
      context.fillRect(x, y, cell, cell)
      context.globalAlpha = .7
      context.strokeStyle = contrastText(color.hex)
      context.lineWidth = 1
      context.beginPath()
      for (let diagonal = -cell; diagonal < cell; diagonal += 5) {
        context.moveTo(x + diagonal, y)
        context.lineTo(x + diagonal + cell, y + cell)
      }
      context.stroke()
      context.restore()
    }
  }

  if (props.showGrid) {
    context.strokeStyle = 'rgb(76 68 60 / 40%)'
    context.lineWidth = 1
    context.beginPath()
    for (let column = 0; column <= props.width; column += 1) {
      const x = offset + column * cell + .5
      context.moveTo(x, offset)
      context.lineTo(x, offset + props.height * cell)
    }
    for (let row = 0; row <= props.height; row += 1) {
      const y = offset + row * cell + .5
      context.moveTo(offset, y)
      context.lineTo(offset + props.width * cell, y)
    }
    context.stroke()
  }

  const locked = new Set(props.lockedIndices)
  if (locked.size) {
    context.fillStyle = 'rgb(30 39 59 / 57%)'
    for (const index of locked) {
      const row = Math.floor(index / props.width)
      const column = index % props.width
      const x = offset + column * cell
      const y = offset + row * cell
      context.fillRect(x + 2, y + 2, Math.min(5, cell - 4), Math.min(5, cell - 4))
    }
  }

  const preview = selectionStart !== null && selectionEnd !== null
    ? rectangleSelection(selectionStart, selectionEnd, props.width)
    : props.selectedIndices
  drawSelection(context, preview, cell, offset)

  if (props.showCoordinates) {
    context.fillStyle = '#70675e'
    context.font = '10px sans-serif'
    context.textAlign = 'center'
    context.textBaseline = 'middle'
    const columnLabelGap = Math.ceil(context.measureText(String(props.width)).width + 8)
    const columnLabels = coordinateLabelIndices(props.width, cell, columnLabelGap)
    const rowLabels = coordinateLabelIndices(props.height, cell, 14)
    for (const column of columnLabels) {
      const x = offset + column * cell + cell / 2
      context.fillText(String(column + 1), x, offset / 2)
      context.fillText(String(column + 1), x, offset + props.height * cell + offset / 2)
    }
    context.textAlign = 'right'
    for (const row of rowLabels) {
      const y = offset + row * cell + cell / 2
      context.fillText(String(row + 1), offset - 4, y)
    }
    context.textAlign = 'left'
    for (const row of rowLabels) {
      const y = offset + row * cell + cell / 2
      context.fillText(String(row + 1), offset + props.width * cell + 4, y)
    }
  }
}

function indexAt(event: PointerEvent): number | null {
  const element = canvas.value
  if (!element) return null
  const rect = element.getBoundingClientRect()
  const localX = (event.clientX - rect.left) / props.zoom - margin.value
  const localY = (event.clientY - rect.top) / props.zoom - margin.value
  const column = Math.floor(localX / baseCell.value)
  const row = Math.floor(localY / baseCell.value)
  if (row < 0 || row >= props.height || column < 0 || column >= props.width) return null
  const index = row * props.width + column
  emit('hover', { row, column, index })
  return index
}

function interact(event: PointerEvent, dragging = false) {
  const index = indexAt(event)
  if (index === null || (dragging && index === lastIndex)) return
  lastIndex = index
  emit('interact', index, event.button === 2 || (dragging && event.buttons === 2))
}

function onPointerDown(event: PointerEvent) {
  if (event.button > 1) return
  event.preventDefault()
  const index = indexAt(event)
  if (index === null) return
  canvas.value?.setPointerCapture(event.pointerId)
  if (props.tool === 'select') {
    selectionStart = index
    selectionEnd = index
    scheduleRender()
    return
  }
  interact(event)
}

function onPointerMove(event: PointerEvent) {
  if (props.tool === 'select' && selectionStart !== null && event.buttons) {
    const index = indexAt(event)
    if (index !== null && index !== selectionEnd) { selectionEnd = index; scheduleRender() }
    return
  }
  if (event.buttons && (props.tool === 'brush' || props.tool === 'eraser')) interact(event, true)
  else indexAt(event)
}

function onPointerUp(event: PointerEvent) {
  if (props.tool === 'select' && selectionStart !== null) {
    const end = indexAt(event) ?? selectionEnd ?? selectionStart
    emit('select', selectionStart, end)
    selectionStart = null
    selectionEnd = null
    scheduleRender()
  }
  lastIndex = -1
  if (canvas.value?.hasPointerCapture(event.pointerId)) canvas.value.releasePointerCapture(event.pointerId)
}

watch(() => props.referenceUrl, (url) => {
  referenceImage = undefined
  if (!url) { scheduleRender(); return }
  const image = new Image()
  image.onload = () => { referenceImage = image; scheduleRender() }
  image.onerror = () => { referenceImage = undefined; scheduleRender() }
  image.src = url
}, { immediate: true })
watch(
  () => [
    props.width, props.height, props.zoom, props.showGrid, props.showCoordinates, props.symbolMode,
    props.renderVersion, props.palette, props.referenceVisible, props.referenceOpacity, props.draftVisible, props.finishedVisible,
  ],
  scheduleRender,
  { deep: false },
)
onMounted(() => nextTick(scheduleRender))
onBeforeUnmount(() => window.cancelAnimationFrame(frame))
</script>

<template>
  <canvas
    ref="canvas"
    class="bead-canvas"
    :class="`bead-canvas--${tool}`"
    :style="style"
    @contextmenu.prevent
    @pointerdown="onPointerDown"
    @pointermove="onPointerMove"
    @pointerup="onPointerUp"
    @pointercancel="onPointerUp"
  />
</template>

<style scoped>
.bead-canvas { display: block; touch-action: none; box-shadow: 0 3px 18px rgb(58 44 29 / 13%); }
.bead-canvas--brush, .bead-canvas--eraser { cursor: crosshair; }
.bead-canvas--eyedropper { cursor: copy; }
.bead-canvas--fill { cursor: cell; }
.bead-canvas--select { cursor: crosshair; }
</style>
