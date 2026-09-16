import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { patchPattern } from '@/api/patterns'
import { useEditorStore } from '@/stores/editor'
import type { Pattern } from '@/types/bead'

vi.mock('@/api/patterns', () => ({
  getPattern: vi.fn(),
  patchPattern: vi.fn(),
}))

function patternWith(cells: Pattern['cells']): Pattern {
  return {
    id: 'pattern-test',
    revision: 1,
    image_id: '',
    palette_id: 'mard-291',
    grid_width: cells.length,
    grid_height: 1,
    cells,
    settings: {},
    statistics: {
      grid_width: cells.length,
      grid_height: 1,
      bead_size_mm: 5,
      total_cells: cells.length,
      transparent_cells: cells.filter((cell) => cell === null).length,
      total_beads: cells.filter(Boolean).length,
      total_beads_with_waste: cells.filter(Boolean).length,
      used_color_count: new Set(cells.filter(Boolean)).size,
      physical_width_mm: cells.length * 5,
      physical_height_mm: 5,
      waste_rate: 0,
      estimated_pegboards: 1,
      colors: [],
    },
    preview_url: '',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  }
}

describe('professional editor store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('serializes reactive layer state into plain cloneable objects', () => {
    const editor = useEditorStore()
    editor.layers.reference.opacity = 52
    editor.layers.draft.visible = false

    const settings = editor.workspaceSettings()

    expect(settings.layers).toEqual({
      reference: { visible: true, opacity: 52 },
      draft: { visible: false },
      finished: { visible: true },
    })
    expect(() => structuredClone(settings)).not.toThrow()
  })

  it('keeps a transparent cell as the save baseline across repeated unsaved edits', () => {
    const editor = useEditorStore()
    editor.setPattern(patternWith([null]))

    editor.paint(0, 'A1')
    editor.paint(0, 'B1')
    editor.paint(0, 'C1')

    expect(editor.pending.get(0)).toEqual({ index: 0, before: null, after: 'C1' })
  })

  it('sends the original transparent baseline when saving repeated edits', async () => {
    const editor = useEditorStore()
    editor.setPattern(patternWith([null]))
    editor.paint(0, 'A1')
    editor.paint(0, 'B1')
    editor.paint(0, 'C1')
    const saved = patternWith(['C1'])
    saved.revision = 2
    vi.mocked(patchPattern).mockResolvedValue(saved)

    await editor.save()

    expect(patchPattern).toHaveBeenCalledWith(
      'pattern-test',
      [{ index: 0, before: null, after: 'C1' }],
      1,
    )
    expect(editor.pattern?.revision).toBe(2)
    expect(editor.pending.size).toBe(0)
  })

  it('removes a queued change when repeated edits return to the original transparent value', () => {
    const editor = useEditorStore()
    editor.setPattern(patternWith([null]))

    editor.paint(0, 'A1')
    editor.paint(0, null)

    expect(editor.pending.size).toBe(0)
    expect(editor.dirty).toBe(false)
  })
})
