import { defineStore } from 'pinia'

import { getPattern, patchPattern } from '@/api/patterns'
import { collectConnectedIndices, floodFill, getSelectionBounds, rectangleSelection } from '@/utils/grid'
import type {
  CellChange,
  CellClipboard,
  CellValue,
  EditorAction,
  EditorLayer,
  EditorTool,
  Pattern,
  ProfessionalEditorSettings,
  SymbolMode,
} from '@/types/bead'

const HISTORY_LIMIT = 100
const DEFAULT_LAYERS: ProfessionalEditorSettings['layers'] = {
  reference: { visible: true, opacity: 36 },
  draft: { visible: true },
  finished: { visible: true },
}

function copyLayers(layers: ProfessionalEditorSettings['layers']): ProfessionalEditorSettings['layers'] {
  return {
    reference: { visible: layers.reference.visible, opacity: layers.reference.opacity },
    draft: { visible: layers.draft.visible },
    finished: { visible: layers.finished.visible },
  }
}

function hasOwn(record: Record<string, string>, index: number): boolean {
  return Object.prototype.hasOwnProperty.call(record, String(index))
}

function colorDistance(left: string, right: string): number {
  const rgb = (hex: string) => [
    Number.parseInt(hex.slice(1, 3), 16),
    Number.parseInt(hex.slice(3, 5), 16),
    Number.parseInt(hex.slice(5, 7), 16),
  ]
  const [leftRed, leftGreen, leftBlue] = rgb(left)
  const [rightRed, rightGreen, rightBlue] = rgb(right)
  return Math.hypot(leftRed - rightRed, leftGreen - rightGreen, leftBlue - rightBlue)
}

export const useEditorStore = defineStore('editor', {
  state: () => ({
    pattern: null as Pattern | null,
    tool: 'brush' as EditorTool,
    zoom: 1,
    showGrid: true,
    showCoordinates: true,
    symbolMode: 'short_code' as SymbolMode,
    undoStack: [] as EditorAction[],
    redoStack: [] as EditorAction[],
    pending: new Map<number, CellChange>(),
    saving: false,
    renderVersion: 0,
    selectedIndices: [] as number[],
    clipboard: null as CellClipboard | null,
    activeLayer: 'finished' as EditorLayer,
    lockedCellIndices: [] as number[],
    draftCells: {} as Record<string, string>,
    layers: copyLayers(DEFAULT_LAYERS),
    workspaceVersion: 0,
  }),
  getters: {
    dirty: (state) => state.pending.size > 0,
    canUndo: (state) => state.undoStack.length > 0,
    canRedo: (state) => state.redoStack.length > 0,
    selectionCount: (state) => state.selectedIndices.length,
    selectionBounds: (state) => state.pattern ? getSelectionBounds(state.selectedIndices, state.pattern.grid_width) : null,
    hasClipboard: (state) => Boolean(state.clipboard),
    hasDraft: (state) => Object.keys(state.draftCells).length > 0,
  },
  actions: {
    resetWorkspace() {
      this.selectedIndices = []
      this.clipboard = null
      this.activeLayer = 'finished'
      this.lockedCellIndices = []
      this.draftCells = {}
      this.layers = copyLayers(DEFAULT_LAYERS)
      this.workspaceVersion += 1
    },
    hydrateWorkspace(settings: unknown) {
      this.resetWorkspace()
      if (!settings || typeof settings !== 'object') return
      const professional = (settings as Record<string, unknown>).professional_editor
      if (!professional || typeof professional !== 'object') return
      const saved = professional as Partial<ProfessionalEditorSettings>
      this.activeLayer = saved.active_layer === 'draft' ? 'draft' : 'finished'
      this.lockedCellIndices = Array.isArray(saved.locked_cell_indices)
        ? [...new Set(saved.locked_cell_indices.filter((item): item is number => Number.isInteger(item) && item >= 0 && (!this.pattern || item < this.pattern.cells.length)))]
        : []
      if (saved.draft_cells && typeof saved.draft_cells === 'object') {
        this.draftCells = Object.fromEntries(
          Object.entries(saved.draft_cells).filter(([index, code]) => (
            /^\d+$/.test(index)
            && typeof code === 'string'
            && (!this.pattern || Number(index) < this.pattern.cells.length)
          )),
        )
      }
      if (saved.layers && typeof saved.layers === 'object') {
        const layers = saved.layers as Partial<ProfessionalEditorSettings['layers']>
        this.layers.reference.visible = layers.reference?.visible !== false
        this.layers.reference.opacity = Math.max(0, Math.min(100, Number(layers.reference?.opacity ?? DEFAULT_LAYERS.reference.opacity)))
        this.layers.draft.visible = layers.draft?.visible !== false
        this.layers.finished.visible = layers.finished?.visible !== false
      }
      this.workspaceVersion += 1
    },
    workspaceSettings(): ProfessionalEditorSettings {
      return {
        version: 1,
        active_layer: this.activeLayer,
        locked_cell_indices: [...this.lockedCellIndices].sort((left, right) => left - right),
        draft_cells: { ...this.draftCells },
        layers: copyLayers(this.layers),
      }
    },
    touchWorkspace() {
      this.workspaceVersion += 1
      this.renderVersion += 1
    },
    async load(patternId: string) {
      this.pattern = await getPattern(patternId)
      this.undoStack = []
      this.redoStack = []
      this.pending.clear()
      this.resetWorkspace()
      this.renderVersion += 1
    },
    setPattern(pattern: Pattern) {
      this.pattern = pattern
      this.undoStack = []
      this.redoStack = []
      this.pending.clear()
      this.resetWorkspace()
      this.renderVersion += 1
    },
    isLocked(index: number): boolean {
      return this.lockedCellIndices.includes(index)
    },
    cellValue(index: number, layer?: EditorLayer): CellValue {
      if (!this.pattern) return null
      const targetLayer = layer ?? this.activeLayer
      return targetLayer === 'draft' && hasOwn(this.draftCells, index) ? this.draftCells[String(index)] : this.pattern.cells[index]
    },
    setSelection(indices: readonly number[]) {
      if (!this.pattern) return
      this.selectedIndices = [...new Set(indices.filter((index) => index >= 0 && index < this.pattern!.cells.length))]
      this.touchWorkspace()
    },
    selectRectangle(startIndex: number, endIndex: number) {
      if (!this.pattern) return
      this.setSelection(rectangleSelection(startIndex, endIndex, this.pattern.grid_width))
    },
    clearSelection() {
      if (!this.selectedIndices.length) return
      this.selectedIndices = []
      this.touchWorkspace()
    },
    selectByColor(index: number, contiguous = false) {
      if (!this.pattern) return
      const source = this.cellValue(index)
      const cells = this.pattern.cells.map((_, cellIndex) => this.cellValue(cellIndex))
      const selected = contiguous
        ? collectConnectedIndices(cells, this.pattern.grid_width, this.pattern.grid_height, index, (value) => value === source)
        : cells.flatMap((value, cellIndex) => value === source ? [cellIndex] : [])
      this.setSelection(selected)
    },
    selectSimilarColor(index: number, colorHexByCode: ReadonlyMap<string, string>, threshold = 82) {
      if (!this.pattern) return
      const source = this.cellValue(index)
      if (!source) { this.selectByColor(index); return }
      const sourceHex = colorHexByCode.get(source)
      if (!sourceHex) return
      this.setSelection(
        this.pattern.cells.flatMap((_, cellIndex) => {
          const code = this.cellValue(cellIndex)
          const hex = code ? colorHexByCode.get(code) : undefined
          return hex && colorDistance(sourceHex, hex) <= threshold ? [cellIndex] : []
        }),
      )
    },
    apply(changes: CellChange[], label: string, recordHistory = true, layer?: EditorLayer) {
      if (!this.pattern) return
      const targetLayer = layer ?? this.activeLayer
      const actual = changes
        .filter((change) => change.index >= 0 && change.index < this.pattern!.cells.length && !this.isLocked(change.index))
        .map((change) => ({
          index: change.index,
          before: targetLayer === 'draft'
            ? (hasOwn(this.draftCells, change.index) ? this.draftCells[String(change.index)] : null)
            : this.pattern!.cells[change.index],
          after: change.after,
        }))
        .filter((change) => change.before !== change.after)
      if (!actual.length) return
      if (targetLayer === 'draft') {
        for (const change of actual) {
          if (change.after) this.draftCells[String(change.index)] = change.after
          else delete this.draftCells[String(change.index)]
        }
        this.workspaceVersion += 1
      } else {
        for (const change of actual) {
          this.pattern.cells[change.index] = change.after
          const queued = this.pending.get(change.index)
          // `null` is a valid original value for a transparent cell. Checking it
          // with `??` loses that baseline after the same cell is edited again,
          // which makes the server compare against an intermediate local color.
          const merged = { index: change.index, before: queued ? queued.before : change.before, after: change.after }
          if (merged.before === merged.after) this.pending.delete(change.index)
          else this.pending.set(change.index, merged)
        }
      }
      this.renderVersion += 1
      if (recordHistory) {
        this.undoStack.push({ label, changes: actual, layer: targetLayer })
        if (this.undoStack.length > HISTORY_LIMIT) this.undoStack.shift()
        this.redoStack = []
      }
    },
    paint(index: number, value: CellValue) {
      this.apply([{ index, before: null, after: value }], value ? '绘制' : '擦除')
    },
    fill(index: number, value: CellValue) {
      if (!this.pattern) return
      const cells = this.pattern.cells.map((_, cellIndex) => this.cellValue(cellIndex))
      this.apply(floodFill(cells, this.pattern.grid_width, this.pattern.grid_height, index, value), '填充')
    },
    undo() {
      const action = this.undoStack.pop()
      if (!action) return
      this.apply(action.changes.map((change) => ({ ...change, after: change.before })), action.label, false, action.layer)
      this.redoStack.push(action)
    },
    redo() {
      const action = this.redoStack.pop()
      if (!action) return
      this.apply(action.changes, action.label, false, action.layer)
      this.undoStack.push(action)
    },
    copySelection() {
      if (!this.pattern || !this.selectedIndices.length) return
      const bounds = getSelectionBounds(this.selectedIndices, this.pattern.grid_width)
      if (!bounds) return
      const selected = new Set(this.selectedIndices)
      const cells: CellValue[] = []
      for (let row = bounds.top; row <= bounds.bottom; row += 1) {
        for (let column = bounds.left; column <= bounds.right; column += 1) {
          const index = row * this.pattern.grid_width + column
          cells.push(selected.has(index) ? this.cellValue(index) : null)
        }
      }
      this.clipboard = { width: bounds.width, height: bounds.height, cells }
      this.touchWorkspace()
    },
    pasteSelection(anchorIndex: number | null = null) {
      if (!this.pattern || !this.clipboard) return
      const bounds = getSelectionBounds(this.selectedIndices, this.pattern.grid_width)
      const start = anchorIndex ?? (bounds ? bounds.top * this.pattern.grid_width + bounds.left : 0)
      const top = Math.floor(start / this.pattern.grid_width)
      const left = start % this.pattern.grid_width
      const changes: CellChange[] = []
      const pasted: number[] = []
      for (let row = 0; row < this.clipboard.height; row += 1) {
        for (let column = 0; column < this.clipboard.width; column += 1) {
          const targetRow = top + row
          const targetColumn = left + column
          if (targetRow >= this.pattern.grid_height || targetColumn >= this.pattern.grid_width) continue
          const index = targetRow * this.pattern.grid_width + targetColumn
          const value = this.clipboard.cells[row * this.clipboard.width + column]
          if (value !== null) { changes.push({ index, before: null, after: value }); pasted.push(index) }
        }
      }
      this.apply(changes, '粘贴选区')
      this.setSelection(pasted)
    },
    transformSelection(kind: 'move-left' | 'move-right' | 'move-up' | 'move-down' | 'mirror-x' | 'mirror-y' | 'rotate-cw') {
      if (!this.pattern || !this.selectedIndices.length) return
      const bounds = getSelectionBounds(this.selectedIndices, this.pattern.grid_width)
      if (!bounds) return
      const width = this.pattern.grid_width
      const selected = new Set(this.selectedIndices)
      const source = new Map(this.selectedIndices.map((index) => [index, this.cellValue(index)]))
      const destination = new Map<number, CellValue>()
      let hasInvalidDestination = false
      if (kind.startsWith('move-')) {
        const delta = kind === 'move-left' ? -1 : kind === 'move-right' ? 1 : kind === 'move-up' ? -width : width
        for (const [index, value] of source) {
          const target = index + delta
          const sourceColumn = index % width
          const targetColumn = target % width
          if (target < 0 || target >= this.pattern.cells.length || (Math.abs(delta) === 1 && sourceColumn === width - 1 && targetColumn === 0) || (Math.abs(delta) === 1 && sourceColumn === 0 && targetColumn === width - 1)) {
            hasInvalidDestination = true
            break
          }
          destination.set(target, value)
        }
      } else {
        for (const [index, value] of source) {
          const row = Math.floor(index / width) - bounds.top
          const column = index % width - bounds.left
          let targetRow = bounds.top + row
          let targetColumn = bounds.left + column
          if (kind === 'mirror-x') targetColumn = bounds.right - column
          if (kind === 'mirror-y') targetRow = bounds.bottom - row
          if (kind === 'rotate-cw') {
            targetRow = bounds.top + column
            targetColumn = bounds.left + (bounds.height - 1 - row)
          }
          if (targetRow >= this.pattern.grid_height || targetColumn >= this.pattern.grid_width) {
            hasInvalidDestination = true
            break
          }
          destination.set(targetRow * width + targetColumn, value)
        }
      }
      if (!destination.size || hasInvalidDestination) return
      const changes = new Map<number, CellValue>()
      for (const index of selected) changes.set(index, null)
      for (const [index, value] of destination) changes.set(index, value)
      this.apply([...changes.entries()].map(([index, after]) => ({ index, before: null, after })), {
        'move-left': '向左移动选区', 'move-right': '向右移动选区', 'move-up': '向上移动选区', 'move-down': '向下移动选区',
        'mirror-x': '水平镜像选区', 'mirror-y': '垂直镜像选区', 'rotate-cw': '顺时针旋转选区',
      }[kind])
      this.setSelection([...destination.keys()])
    },
    replaceColor(from: CellValue, to: CellValue, selectedOnly: boolean) {
      if (!this.pattern || from === to) return
      const scope = selectedOnly ? this.selectedIndices : this.pattern.cells.map((_, index) => index)
      this.apply(
        scope.flatMap((index) => this.cellValue(index) === from ? [{ index, before: from, after: to }] : []),
        selectedOnly ? '选区批量替换色号' : '全图批量替换色号',
      )
    },
    toggleSelectionLock() {
      if (!this.selectedIndices.length) return
      const locked = new Set(this.lockedCellIndices)
      const shouldUnlock = this.selectedIndices.every((index) => locked.has(index))
      for (const index of this.selectedIndices) shouldUnlock ? locked.delete(index) : locked.add(index)
      this.lockedCellIndices = [...locked]
      this.touchWorkspace()
    },
    setLayerVisibility(layer: keyof typeof DEFAULT_LAYERS, visible: boolean) {
      this.layers[layer].visible = visible
      this.touchWorkspace()
    },
    setReferenceOpacity(opacity: number) {
      this.layers.reference.opacity = Math.max(0, Math.min(100, opacity))
      this.touchWorkspace()
    },
    setActiveLayer(layer: EditorLayer) {
      this.activeLayer = layer
      this.touchWorkspace()
    },
    clearDraft() {
      if (!Object.keys(this.draftCells).length) return
      this.draftCells = {}
      this.touchWorkspace()
    },
    applyDraftToFinished() {
      const transferable = Object.entries(this.draftCells)
        .map(([index, code]) => ({ index: Number(index), before: null, after: code }))
        .filter((change) => !this.isLocked(change.index))
      if (!transferable.length) return
      this.apply(transferable, '应用草稿到成品层', true, 'finished')
      for (const change of transferable) delete this.draftCells[String(change.index)]
      this.touchWorkspace()
    },
    async save() {
      if (!this.pattern || !this.pending.size || this.saving) return this.pattern
      this.saving = true
      try {
        const pattern = await patchPattern(this.pattern.id, [...this.pending.values()], this.pattern.revision)
        this.pattern = pattern
        this.pending.clear()
        this.renderVersion += 1
        return pattern
      } finally {
        this.saving = false
      }
    },
  },
})
