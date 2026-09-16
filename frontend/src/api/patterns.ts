import { request } from './http'
import type { CellChange, Pattern, PatternPreview } from '@/types/bead'
import type { AssemblyPlan, ProductionPlan, ProductionStrategy } from '@/types/design'

export interface GeneratePatternPayload {
  image_id: string
  grid_width: number
  grid_height: number
  resize_mode: 'stretch' | 'contain' | 'cover' | 'pixel'
  sampling_mode: 'adaptive' | 'edge_aware' | 'smooth'
  palette_id: string
  distance_method: 'fidelity' | 'rgb' | 'cie76' | 'cie94' | 'ciede2000'
  max_colors?: number
  auto_color_limit?: boolean
  target_p95_delta_e_00?: number
  include_special_colors?: boolean
  minimum_color_count: number
  cleanup_level: 'off' | 'light' | 'medium'
  structure_aware?: boolean
  transparent_background: boolean
  disabled_colors: string[]
  locked_colors: string[]
  inventory?: Array<{ color_code: string; quantity: number }>
  inventory_mode?: 'report' | 'only'
  bead_size_mm: number
  waste_rate: number
  conversion_preset?: 'custom' | 'portrait' | 'illustration' | 'pixel_art' | 'landscape'
  subject_crop?: boolean
  focus_x?: number
  focus_y?: number
  focus_zoom?: number
  focus_radius?: number
  background_weaken?: number
  detail_priorities?: Array<'facial' | 'text' | 'outline'>
}

export const generatePattern = (payload: GeneratePatternPayload) => request<Pattern>({ method: 'POST', url: '/patterns/generate', data: payload })
export const previewPattern = (payload: GeneratePatternPayload) => request<PatternPreview>({ method: 'POST', url: '/patterns/preview', data: payload })
export const regeneratePattern = (patternId: string, payload: GeneratePatternPayload) => request<Pattern>({ method: 'POST', url: `/patterns/${patternId}/regenerate`, data: payload })
export const getPattern = (patternId: string) => request<Pattern>({ method: 'GET', url: `/patterns/${patternId}` })
export const createBlankPattern = (payload: { grid_width: number; grid_height: number; palette_id: string; bead_size_mm: number; waste_rate: number }) => request<Pattern>({ method: 'POST', url: '/patterns/blank', data: payload })
export const createTemplatePattern = (payload: { template_id: string; palette_id: string; foreground_code?: string; accent_code?: string; bead_size_mm: number; waste_rate: number }) => request<Pattern>({ method: 'POST', url: '/patterns/template', data: payload })
export const createTextPattern = (payload: { text: string; style: 'keychain' | 'nameplate'; palette_id: string; foreground_code?: string; accent_code?: string; bead_size_mm: number; waste_rate: number }) => request<Pattern>({ method: 'POST', url: '/patterns/text', data: payload })
export const getAssemblyPlan = (patternId: string, boardWidth: number, boardHeight: number, overlap: number) => request<AssemblyPlan>({ method: 'GET', url: `/patterns/${patternId}/assembly-plan`, params: { board_width: boardWidth, board_height: boardHeight, overlap } })
export const getProductionPlan = (
  patternId: string,
  options: { board_template_id: string; overlap: number; strategy: ProductionStrategy; beads_per_hour: number },
) => request<ProductionPlan>({ method: 'GET', url: `/patterns/${patternId}/production-plan`, params: options })
export const patchPattern = (patternId: string, changes: CellChange[], baseRevision: number) => request<Pattern>({
  method: 'PUT',
  url: `/patterns/${patternId}`,
  data: { changes, base_revision: baseRevision },
})
