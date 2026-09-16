import { request } from './http'
import type { GridPreset } from '@/types/preset'
import type { DesignTemplate, PegboardTemplate } from '@/types/design'

export const getGridPresets = async (): Promise<GridPreset[]> => {
  const data = await request<{ items: GridPreset[] }>({ method: 'GET', url: '/presets/grids' })
  return data.items
}

export const getDesignTemplates = async (): Promise<DesignTemplate[]> => {
  const data = await request<{ items: DesignTemplate[] }>({ method: 'GET', url: '/presets/templates' })
  return data.items
}

export const getPegboardTemplates = async (): Promise<PegboardTemplate[]> => {
  const data = await request<{ items: PegboardTemplate[] }>({ method: 'GET', url: '/presets/boards' })
  return data.items
}
