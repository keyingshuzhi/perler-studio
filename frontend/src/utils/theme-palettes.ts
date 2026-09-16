import type { PaletteColor } from '@/types/palette'

export interface CreativeTheme {
  id: 'all' | 'skin' | 'anime' | 'retro' | 'mosaic' | 'morandi'
  name: string
  description: string
}

export const creativeThemes: CreativeTheme[] = [
  { id: 'all', name: '全色创作', description: '不限制色彩，适合自由设计' },
  { id: 'skin', name: '自然肤色', description: '肤色、棕色与明暗轮廓' },
  { id: 'anime', name: '动漫高饱和', description: '角色发色、服装和高光' },
  { id: 'retro', name: '复古游戏', description: '低明度对比与像素氛围' },
  { id: 'mosaic', name: '马赛克', description: '多色块层次与拼贴感' },
  { id: 'morandi', name: '莫兰迪', description: '低饱和、柔和配色' },
]

function saturation(color: PaletteColor) {
  const [red, green, blue] = color.rgb.map((value) => value / 255)
  return Math.max(red, green, blue) - Math.min(red, green, blue)
}

function lightness(color: PaletteColor) {
  const [red, green, blue] = color.rgb.map((value) => value / 255)
  return (Math.max(red, green, blue) + Math.min(red, green, blue)) / 2
}

export function colorsForTheme(themeId: CreativeTheme['id'], colors: PaletteColor[]) {
  const available = colors.filter((color) => color.available)
  const includesCategory = (color: PaletteColor, pattern: RegExp) => pattern.test(color.category || '')
  const selected = available.filter((color) => {
    if (themeId === 'all' || themeId === 'mosaic') return true
    if (themeId === 'skin') return includesCategory(color, /肤|棕|黑白灰/) || lightness(color) > .82
    if (themeId === 'anime') return saturation(color) > .34 || includesCategory(color, /肤|黑白灰/)
    if (themeId === 'retro') return saturation(color) > .22 && lightness(color) < .72
    return includesCategory(color, /莫兰迪/) || (saturation(color) < .38 && lightness(color) > .24 && lightness(color) < .82)
  })
  return selected.length ? selected : available
}
