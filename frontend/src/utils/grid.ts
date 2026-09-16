import type { CellChange, CellValue, SelectionBounds, SymbolMode } from '@/types/bead'

const EDITOR_CANVAS_TARGET_SIZE = 1_250
const MINIMUM_SHORT_CODE_CELL_PX = 14
const MINIMUM_FULL_CODE_CELL_PX = 20

export function editorBaseCellSize(width: number, height: number): number {
  const longestSide = Math.max(width, height)
  if (!Number.isFinite(longestSide) || longestSide <= 0) return 30
  return Math.max(10, Math.min(30, Math.floor(EDITOR_CANVAS_TARGET_SIZE / longestSide)))
}

export function minimumSymbolScreenCell(mode: SymbolMode): number {
  if (mode === 'short_code') return MINIMUM_SHORT_CODE_CELL_PX
  if (mode === 'color_code') return MINIMUM_FULL_CODE_CELL_PX
  return 0
}

export function shouldRenderCellSymbols(cellSize: number, zoom: number, mode: SymbolMode): boolean {
  if (mode === 'none') return false
  return cellSize * zoom >= minimumSymbolScreenCell(mode)
}

export function minimumEditorSymbolZoom(width: number, height: number, mode: SymbolMode): number {
  const minimumCell = minimumSymbolScreenCell(mode)
  return minimumCell ? minimumCell / editorBaseCellSize(width, height) : 0
}

export function gridIndex(row: number, column: number, width: number): number {
  return row * width + column
}

export function coordinateLabelIndices(count: number, cellSize: number, minimumGap: number): number[] {
  if (!Number.isFinite(count) || count <= 0) return []
  const total = Math.floor(count)
  const safeCellSize = Number.isFinite(cellSize) ? Math.max(1, cellSize) : 1
  const safeMinimumGap = Number.isFinite(minimumGap) ? Math.max(1, minimumGap) : 1
  const step = Math.max(1, Math.ceil(safeMinimumGap / safeCellSize))
  const indices: number[] = []

  for (let index = 0; index < total; index += step) indices.push(index)

  const lastIndex = total - 1
  const finalIndex = indices.at(-1)
  if (finalIndex !== lastIndex) {
    if (indices.length > 1 && finalIndex !== undefined && lastIndex - finalIndex < step) indices[indices.length - 1] = lastIndex
    else indices.push(lastIndex)
  }
  return indices
}

export function floodFill(cells: readonly CellValue[], width: number, height: number, startIndex: number, nextValue: CellValue): CellChange[] {
  const source = cells[startIndex]
  if (source === nextValue) return []

  const changes: CellChange[] = []
  const queue = [startIndex]
  const visited = new Uint8Array(cells.length)
  visited[startIndex] = 1

  while (queue.length) {
    const index = queue.shift()
    if (index === undefined || cells[index] !== source) continue
    changes.push({ index, before: source, after: nextValue })
    const row = Math.floor(index / width)
    const column = index % width
    const neighbours = [
      row > 0 ? index - width : -1,
      row + 1 < height ? index + width : -1,
      column > 0 ? index - 1 : -1,
      column + 1 < width ? index + 1 : -1,
    ]
    for (const neighbour of neighbours) {
      if (neighbour >= 0 && !visited[neighbour] && cells[neighbour] === source) {
        visited[neighbour] = 1
        queue.push(neighbour)
      }
    }
  }
  return changes
}

export function rectangleSelection(startIndex: number, endIndex: number, width: number): number[] {
  const startRow = Math.floor(startIndex / width)
  const startColumn = startIndex % width
  const endRow = Math.floor(endIndex / width)
  const endColumn = endIndex % width
  const top = Math.min(startRow, endRow)
  const bottom = Math.max(startRow, endRow)
  const left = Math.min(startColumn, endColumn)
  const right = Math.max(startColumn, endColumn)
  const result: number[] = []
  for (let row = top; row <= bottom; row += 1) {
    for (let column = left; column <= right; column += 1) result.push(gridIndex(row, column, width))
  }
  return result
}

export function getSelectionBounds(indices: readonly number[], width: number): SelectionBounds | null {
  if (!indices.length) return null
  let top = Number.POSITIVE_INFINITY
  let bottom = -1
  let left = Number.POSITIVE_INFINITY
  let right = -1
  for (const index of indices) {
    const row = Math.floor(index / width)
    const column = index % width
    top = Math.min(top, row)
    bottom = Math.max(bottom, row)
    left = Math.min(left, column)
    right = Math.max(right, column)
  }
  return { top, left, bottom, right, width: right - left + 1, height: bottom - top + 1 }
}

export function collectConnectedIndices(
  cells: readonly CellValue[],
  width: number,
  height: number,
  startIndex: number,
  predicate: (value: CellValue) => boolean,
): number[] {
  if (!predicate(cells[startIndex])) return []
  const selected: number[] = []
  const queue = [startIndex]
  const visited = new Uint8Array(cells.length)
  visited[startIndex] = 1
  while (queue.length) {
    const index = queue.pop()
    if (index === undefined || !predicate(cells[index])) continue
    selected.push(index)
    const row = Math.floor(index / width)
    const column = index % width
    const neighbours = [
      row > 0 ? index - width : -1,
      row + 1 < height ? index + width : -1,
      column > 0 ? index - 1 : -1,
      column + 1 < width ? index + 1 : -1,
    ]
    for (const neighbour of neighbours) {
      if (neighbour >= 0 && !visited[neighbour]) { visited[neighbour] = 1; queue.push(neighbour) }
    }
  }
  return selected
}
