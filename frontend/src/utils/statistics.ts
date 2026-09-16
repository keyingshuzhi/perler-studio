import type { CellValue, PatternStatistics } from '@/types/bead'
import type { PaletteColor } from '@/types/palette'

export function liveStatistics(
  cells: readonly CellValue[],
  width: number,
  height: number,
  palette: readonly PaletteColor[],
  beadSizeMm: number,
  wasteRate: number,
): PatternStatistics {
  const paletteByCode = new Map(palette.map((color) => [color.code, color]))
  const counts = new Map<string, number>()
  for (const code of cells) {
    if (code) counts.set(code, (counts.get(code) || 0) + 1)
  }
  const colors = [...counts.entries()]
    .map(([code, count]) => {
      const color = paletteByCode.get(code)
      return {
        color_code: code,
        color_name: color?.name_zh || code,
        color_name_en: color?.name_en,
        hex: color?.hex || '#CCCCCC',
        count,
        count_with_waste: Math.ceil(count * (1 + wasteRate)),
        ratio: count / cells.length,
      }
    })
    .sort((left, right) => right.count - left.count || left.color_code.localeCompare(right.color_code))
  const nonTransparent = [...counts.values()].reduce((total, count) => total + count, 0)
  return {
    grid_width: width,
    grid_height: height,
    bead_size_mm: beadSizeMm,
    total_cells: cells.length,
    transparent_cells: cells.length - nonTransparent,
    total_beads: nonTransparent,
    total_beads_with_waste: Math.ceil(nonTransparent * (1 + wasteRate)),
    used_color_count: counts.size,
    physical_width_mm: width * beadSizeMm,
    physical_height_mm: height * beadSizeMm,
    waste_rate: wasteRate,
    estimated_pegboards: Math.ceil(width / 29) * Math.ceil(height / 29),
    colors,
  }
}
