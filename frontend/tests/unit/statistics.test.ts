import { describe, expect, it } from 'vitest'

import { liveStatistics } from '@/utils/statistics'

describe('liveStatistics', () => {
  it('uses the same one-dimensional grid semantics as the backend', () => {
    const statistics = liveStatistics(
      ['MARD-A01', null, 'MARD-A01', 'MARD-A06'],
      2,
      2,
      [
        { code: 'MARD-A01', name_zh: '白', hex: '#FFFFFF', rgb: [255, 255, 255], available: true },
        { code: 'MARD-A06', name_zh: '黑', hex: '#000000', rgb: [0, 0, 0], available: true },
      ],
      5,
      0.05,
    )
    expect(statistics.total_beads).toBe(3)
    expect(statistics.transparent_cells).toBe(1)
    expect(statistics.colors[0].count_with_waste).toBe(3)
  })
})
