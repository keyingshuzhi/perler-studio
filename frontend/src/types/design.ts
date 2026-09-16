export interface DesignTemplate {
  id: string
  name_zh: string
  category: string
  description: string
  grid_width: number
  grid_height: number
  preview: string[]
}

export interface AssemblyBoard {
  id: string
  row: number
  column: number
  row_range: [number, number]
  column_range: [number, number]
  grid_width: number
  grid_height: number
  join_right: string | null
  join_bottom: string | null
}

export interface AssemblyPlan {
  grid_width: number
  grid_height: number
  board_width: number
  board_height: number
  overlap: number
  board_rows: number
  board_columns: number
  board_count: number
  boards: AssemblyBoard[]
}

export interface PegboardTemplate {
  id: string
  name_zh: string
  board_width: number
  board_height: number
  usable_holes: number
  bead_size_mm: number
  layout_kind: 'rectangular'
  description: string
}

export type ProductionStrategy = 'color' | 'region' | 'rows' | 'columns'

export interface ProductionBoard extends AssemblyBoard {
  bead_count: number
  used_color_count: number
  color_counts: Record<string, number>
}

export interface ProductionStep {
  id: string
  ordinal: number
  title: string
  instruction: string
  bead_count: number
  estimated_minutes?: number
  targets?: string[]
  board_id?: string
}

export interface ProductionPlan {
  board_template: PegboardTemplate
  assembly: Omit<AssemblyPlan, 'boards'> & { boards: ProductionBoard[]; installation_steps: ProductionStep[] }
  strategy: ProductionStrategy
  beads_per_hour: number
  estimated_minutes: number
  make_steps: ProductionStep[]
  materials: {
    tracked: boolean
    coverage_percent: number | null
    shortages: Array<{
      color_code: string
      required_quantity: number
      available_quantity: number
      shortage_quantity: number
    }>
  }
}
