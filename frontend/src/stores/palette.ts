import { defineStore } from 'pinia'

import { getPalette, getPalettes } from '@/api/palettes'
import type { Palette, PaletteColor, PaletteSummary } from '@/types/palette'

export const usePaletteStore = defineStore('palette', {
  state: () => ({
    summaries: [] as PaletteSummary[],
    current: null as Palette | null,
    currentColorCode: '' as string,
    loading: false,
  }),
  getters: {
    currentColor(state): PaletteColor | undefined {
      return state.current?.colors.find((color) => color.code === state.currentColorCode)
    },
    colorByCode: (state) => (code: string | null): PaletteColor | undefined => state.current?.colors.find((color) => color.code === code),
  },
  actions: {
    async load(paletteId = 'mard-291') {
      this.loading = true
      try {
        this.summaries = await getPalettes()
        this.current = await getPalette(paletteId)
        if (!this.current.colors.some((color) => color.available && color.code === this.currentColorCode)) {
          this.currentColorCode = this.current.colors.find((color) => color.available)?.code || ''
        }
      } finally {
        this.loading = false
      }
    },
    async ensure(paletteId: string) {
      if (this.current?.id !== paletteId) await this.load(paletteId)
    },
    select(code: string) {
      this.currentColorCode = code
    },
  },
})
