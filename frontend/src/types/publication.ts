import type { ColorReport, PatternStatistics } from './bead'

export type PublicationStatus = 'pending' | 'approved' | 'rejected' | 'withdrawn'
export type PublicationReviewCheck = 'pattern_content' | 'metadata' | 'rights_privacy'

export interface Publication {
  id: string
  public_token: string
  project_id: string
  pattern_id: string
  title: string
  description: string | null
  tags: string[]
  finished_image_id: string | null
  finished_photo_preview_url?: string | null
  status: PublicationStatus
  submitted_at: string
  reviewed_at: string | null
  review_note: string | null
  review_checks: PublicationReviewCheck[]
  author: { id: string; display_name: string }
  reviewer: { id: string; display_name: string } | null
}

export interface PublicPublication {
  publication: Publication
  pattern: {
    preview_url: string
    grid_width: number
    grid_height: number
    statistics: PatternStatistics
  }
  finished_photo_preview_url: string | null
}

export interface PublicationSummary extends Publication {
  preview_url: string
  finished_photo_preview_url: string | null
  grid_width: number
  grid_height: number
  statistics: PatternStatistics
}

export interface CommunityRemixResult {
  project: import('./project').Project
  pattern: import('./bead').Pattern
}

export interface PublicationList {
  items: PublicationSummary[]
  total: number
  page: number
  page_size: number
}

export interface OwnerPublicationList {
  items: Publication[]
  total: number
  page: number
  page_size: number
  status_counts: Partial<Record<PublicationStatus, number>>
}

export interface AdminPublicationSummary extends Publication {
  preview_url: string | null
  grid_width: number | null
  grid_height: number | null
  total_beads: number | null
  used_color_count: number | null
  review_ready: boolean
}

export interface AdminPublicationDetail {
  publication: Publication
  project: {
    id: string
    name: string | null
    description: string | null
    created_at: string | null
    updated_at: string | null
  } | null
  pattern: {
    id: string
    revision: number
    preview_url: string | null
    source_image_preview_url: string | null
    grid_width: number
    grid_height: number
    palette_id: string
    palette_name: string
    palette_brand: string | null
    statistics: PatternStatistics
    color_report: ColorReport | null
    created_at: string | null
    updated_at: string | null
  } | null
  finished_photo_preview_url: string | null
  review_readiness: {
    can_approve: boolean
    blocking_issues: string[]
    warnings: string[]
  }
}

export interface AdminPublicationList {
  items: AdminPublicationSummary[]
  total: number
  library_total: number
  page: number
  page_size: number
}
