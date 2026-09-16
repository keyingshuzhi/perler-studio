import { describe, expect, it } from 'vitest'

import {
  collectConnectedIndices,
  coordinateLabelIndices,
  editorBaseCellSize,
  floodFill,
  getSelectionBounds,
  gridIndex,
  minimumEditorSymbolZoom,
  rectangleSelection,
  shouldRenderCellSymbols,
} from '@/utils/grid'

describe('grid utilities', () => {
  it('converts row and column to an index', () => {
    expect(gridIndex(2, 3, 10)).toBe(23)
  })

  it('fills only the contiguous area', () => {
    const cells = ['A', 'A', 'B', 'A', 'B', 'B']
    const changes = floodFill(cells, 3, 2, 0, 'C')
    expect(changes.map((change) => change.index).sort()).toEqual([0, 1, 3])
  })

  it('builds rectangular and connected selections for professional editor tools', () => {
    expect(rectangleSelection(1, 10, 4)).toEqual([1, 2, 5, 6, 9, 10])
    expect(getSelectionBounds([1, 2, 8, 10], 4)).toMatchObject({ top: 0, left: 0, bottom: 2, right: 2, width: 3, height: 3 })
    const cells = ['A', 'A', 'B', 'A', 'B', 'B']
    expect(collectConnectedIndices(cells, 3, 2, 0, (value) => value === 'A').sort()).toEqual([0, 1, 3])
  })

  it('spaces dense coordinate labels while preserving both grid edges', () => {
    expect(coordinateLabelIndices(8, 20, 18)).toEqual([0, 1, 2, 3, 4, 5, 6, 7])
    expect(coordinateLabelIndices(10, 10, 24)).toEqual([0, 3, 6, 9])
    expect(coordinateLabelIndices(11, 10, 24)).toEqual([0, 3, 6, 10])
    expect(coordinateLabelIndices(0, 10, 24)).toEqual([])
  })

  it('uses the visible cell size when deciding whether editor symbols are legible', () => {
    expect(editorBaseCellSize(64, 64)).toBe(19)
    expect(editorBaseCellSize(128, 96)).toBe(10)
    expect(shouldRenderCellSymbols(10, 1, 'short_code')).toBe(false)
    expect(shouldRenderCellSymbols(10, 1.4, 'short_code')).toBe(true)
    expect(shouldRenderCellSymbols(10, 1.9, 'color_code')).toBe(false)
    expect(shouldRenderCellSymbols(10, 2, 'color_code')).toBe(true)
    expect(shouldRenderCellSymbols(30, 2, 'none')).toBe(false)
    expect(minimumEditorSymbolZoom(128, 96, 'short_code')).toBe(1.4)
    expect(minimumEditorSymbolZoom(128, 96, 'color_code')).toBe(2)
  })
})
