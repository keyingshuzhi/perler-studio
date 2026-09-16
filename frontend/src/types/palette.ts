export type ColorimetryStatus = 'measured_lab' | 'mixed_lab' | 'screen_rgb' | 'not_applicable'

export interface PaletteCalibration {
  color_space: 'CIELAB'
  illuminant: 'D65'
  observer: '2_degree'
  source: string
  instrument?: string | null
  measurement_geometry?: string | null
  measured_at?: string | null
  notes?: string | null
}

export interface PaletteColor {
  code: string
  name_zh: string
  name_en?: string | null
  hex: string
  rgb: [number, number, number]
  measured_lab?: [number, number, number] | null
  category?: string | null
  series?: string
  effect?: 'standard' | 'special' | string
  available: boolean
}

export interface PaletteSummary {
  id: string
  name: string
  brand: string
  version: string
  color_count: number
  color_tier?: number
  colorimetry_status: ColorimetryStatus
  measured_color_count: number
  measurement_coverage_percent: number
  is_system: boolean
}

export interface Palette {
  id: string
  name: string
  brand: string
  version: string
  colors: PaletteColor[]
  calibration?: PaletteCalibration | null
  colorimetry_status: ColorimetryStatus
  measured_color_count: number
  measurement_coverage_percent: number
  is_system: boolean
  description?: string
  color_tier?: number
  base_palette_id?: string
}
