export interface GridPreset {
  id: string
  name_zh: string
  name_en: string
  grid_width: number
  grid_height: number
  use_case: string
  recommended_max_colors: number
  recommended_bead_size_mm: number
  dimensions: Record<string, {
    width_mm: number
    height_mm: number
    width_in: number
    height_in: number
  }>
}
