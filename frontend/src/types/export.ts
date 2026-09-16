import type { SymbolMode } from './bead'

export type ExportKind = 'png' | 'pdf' | 'guide' | 'svg' | 'csv' | 'project'

export interface ExportRecord {
  id: string
  project_id: string | null
  pattern_id: string
  export_type: ExportKind
  status: 'running' | 'success' | 'failed'
  settings: Record<string, unknown>
  file_path: string
  file_size: number | null
  file_url: string | null
  error_message: string | null
  created_at: string
  completed_at: string | null
}

export interface BaseExportRequest {
  project_id?: string
  pattern_id?: string
}

export interface PngExportRequest extends BaseExportRequest {
  cell_size_px: number
  show_grid: boolean
  show_coordinates: boolean
  show_symbols: boolean
  symbol_mode: SymbolMode
  background: 'white' | 'transparent'
  include_legend: boolean
}

export interface PdfExportRequest extends BaseExportRequest {
  paper_size: 'A4' | 'A3'
  orientation: 'portrait' | 'landscape'
  mode: 'single' | 'multipage' | 'guide'
  show_grid: boolean
  show_coordinates: boolean
  show_symbols: boolean
  symbol_mode: SymbolMode
  include_legend: boolean
  include_statistics: boolean
  overlap_cells: number
  margin_mm: number
  assembly_board_width: number
  assembly_board_height: number
  assembly_overlap: number
}

export interface SvgExportRequest extends BaseExportRequest {
  cell_size_px: number
  show_grid: boolean
  show_coordinates: boolean
  show_symbols: boolean
  symbol_mode: SymbolMode
  background: 'white' | 'transparent'
  include_legend: boolean
}
