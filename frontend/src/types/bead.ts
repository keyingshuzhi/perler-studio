export type CellValue = string | null

export type EditorTool = 'brush' | 'eraser' | 'eyedropper' | 'fill' | 'select'
export type SymbolMode = 'color_code' | 'short_code' | 'none'
export type EditorLayer = 'finished' | 'draft'

export interface CellChange {
  index: number
  before: CellValue
  after: CellValue
}

export interface EditorAction {
  label: string
  changes: CellChange[]
  layer: EditorLayer
}

export interface SelectionBounds {
  top: number
  left: number
  bottom: number
  right: number
  width: number
  height: number
}

export interface CellClipboard {
  width: number
  height: number
  cells: CellValue[]
}

export interface ProfessionalEditorSettings {
  version: 1
  active_layer: EditorLayer
  locked_cell_indices: number[]
  draft_cells: Record<string, string>
  layers: {
    reference: { visible: boolean; opacity: number }
    draft: { visible: boolean }
    finished: { visible: boolean }
  }
}

export interface ColorStatistic {
  color_code: string
  color_name: string
  color_name_en?: string | null
  hex: string
  count: number
  count_with_waste: number
  ratio: number
}

export interface PatternStatistics {
  grid_width: number
  grid_height: number
  bead_size_mm: number
  total_cells: number
  transparent_cells: number
  total_beads: number
  total_beads_with_waste: number
  used_color_count: number
  physical_width_mm: number
  physical_height_mm: number
  waste_rate: number
  estimated_pegboards: number
  colors: ColorStatistic[]
}

export interface InventoryShortage {
  color_code: string
  color_name: string
  hex: string
  required_quantity: number
  available_quantity: number
  shortage_quantity: number
}

export interface ColorSubstitution {
  from_color_code: string
  to_color_code: string
  to_color_name: string
  to_hex: string
  available_quantity: number
  shortage_quantity: number
  delta_e_00: number
  assessment: string
}

export interface ColorReport {
  metric: 'CIEDE2000'
  matching_metric?: 'fidelity' | 'rgb' | 'cie76' | 'cie94' | 'ciede2000' | null
  quality_basis: 'measured_lab' | 'mixed_lab' | 'screen_rgb' | 'not_applicable'
  matching_color_basis: 'measured_lab' | 'mixed_lab' | 'screen_rgb' | 'not_applicable'
  measured_evaluated_cell_count: number
  measured_evaluated_percent: number
  palette_measured_color_count: number
  palette_measurement_coverage_percent: number
  calibration?: {
    color_space: 'CIELAB'
    illuminant: 'D65'
    observer: '2_degree'
    source: string
    instrument?: string | null
    measurement_geometry?: string | null
    measured_at?: string | null
    notes?: string | null
  } | null
  average_delta_e_00: number
  p95_delta_e_00: number
  maximum_delta_e_00: number
  oracle_average_delta_e_00?: number | null
  oracle_p95_delta_e_00?: number | null
  p95_oracle_gap?: number | null
  oracle_target_reachable?: boolean | null
  oracle_palette_color_count?: number
  target_p95_delta_e_00?: number | null
  target_met?: boolean | null
  quality_label: string
  quality_note: string
  evaluated_cells: number
  palette_color_count: number
  eligible_palette_color_count?: number
  special_colors_enabled?: boolean
  cleanup_adjusted_cell_count?: number
  cleanup_adjusted_percent?: number
  structure_aware_enabled?: boolean
  structure_protected_cell_count?: number
  structure_protected_percent?: number
  structure_weighted_average_delta_e_00?: number | null
  structure_protected_average_delta_e_00?: number | null
  structure_protected_p95_delta_e_00?: number | null
  selected_color_limit: number
  used_color_count: number
  inventory: {
    enabled: boolean
    owned_color_count: number
    required_beads: number
    covered_beads: number
    coverage_percent: number
    missing_colors: InventoryShortage[]
  }
  substitutions: ColorSubstitution[]
}

export interface Pattern {
  id: string
  revision: number
  image_id: string
  palette_id: string
  grid_width: number
  grid_height: number
  cells: CellValue[]
  settings: Record<string, unknown>
  statistics: PatternStatistics
  color_report?: ColorReport
  preview_url: string
  created_at: string
  updated_at: string
}

export interface ConversionHotspot {
  index: number
  row: number
  column: number
  color_code: string
  delta_e_00: number
}

export interface ConversionDiagnostics {
  metric: 'CIEDE2000'
  quality_basis: 'measured_lab' | 'mixed_lab' | 'screen_rgb' | 'not_applicable'
  measured_evaluated_cell_count: number
  measured_evaluated_percent: number
  average_delta_e_00: number
  p95_delta_e_00: number
  maximum_delta_e_00: number
  /** Packed ΔE00 values: an integer of 73 represents ΔE00 7.3. */
  cell_delta_e_00_tenths: number[]
  hotspots: ConversionHotspot[]
}

export interface PatternPreview {
  image_id: string
  palette_id: string
  grid_width: number
  grid_height: number
  cells: CellValue[]
  settings: Record<string, unknown>
  statistics: PatternStatistics
  color_report: ColorReport
  diagnostics: ConversionDiagnostics
}
