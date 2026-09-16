export interface Project {
  id: string
  name: string
  description: string | null
  pattern_id: string | null
  editor_settings: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface ProjectList {
  items: Project[]
  total: number
  page: number
  page_size: number
  library_total: number
  favorite_count: number
  tagged_count: number
  available_tags: string[]
}

export interface ProductionGuideProgress {
  version: 1
  completed_step_ids: string[]
}

export interface ImageInfo {
  image_id: string
  filename: string
  width: number
  height: number
  mime_type: string
  has_alpha: boolean
  preview_url: string
  source_url: string
  parent_image_id?: string
  settings?: Record<string, unknown>
}

export interface ProjectVersion {
  id: string
  project_id: string
  label: string
  pattern_revision: number | null
  preview_url: string | null
  created_at: string
  automatic: boolean
}

export interface ProjectVersionDetail extends ProjectVersion {
  pattern: import('./bead').Pattern | null
}

export interface ShareComment {
  id: string
  message: string
  author_label: string
  created_at: string
  cell_index?: number
  row?: number
  column?: number
}

export interface ProjectShare {
  token: string
  project_id: string
  title: string
  created_at: string
  confirmation: { decision: 'approved' | 'changes_requested'; comment?: string | null; confirmed_at: string } | null
  comments: ShareComment[]
}

export interface PublicShare {
  share: ProjectShare
  project: Pick<Project, 'id' | 'name' | 'description'>
  pattern: { preview_url: string; grid_width: number; grid_height: number; statistics: import('./bead').PatternStatistics } | null
}

export interface CostQuoteSettings {
  version: 1
  bead_unit_price: number
  board_unit_price: number
  fuse_paper_sheet_price: number
  frame_price: number
  labor_hourly_rate: number
  beads_per_hour: number
  waste_rate: number
  overhead_rate: number
}

export interface ProjectMetadata {
  version: 1
  tags: string[]
  favorite: boolean
}
