import { request } from './http'
import type { Palette, PaletteSummary } from '@/types/palette'

export const getPalettes = () => request<PaletteSummary[]>({ method: 'GET', url: '/palettes' })
export const getPalette = (paletteId: string) => request<Palette>({ method: 'GET', url: `/palettes/${paletteId}` })
