<script setup lang="ts">
import { computed, ref } from 'vue'

import type { ColorStatistic } from '@/types/bead'
import type { PaletteColor } from '@/types/palette'

const props = defineProps<{
  colors: readonly PaletteColor[]
  selectedCode: string
  statistics: readonly ColorStatistic[]
}>()
const emit = defineEmits<{ select: [code: string] }>()
const query = ref('')
const effect = ref<'all' | 'standard' | 'special'>('all')
const series = ref('all')
const counts = computed(() => new Map(props.statistics.map((item) => [item.color_code, item.count])))
const seriesOptions = computed(() => [...new Set(props.colors.map((color) => color.series).filter(Boolean))].sort())
const filtered = computed(() => {
  const needle = query.value.trim().toLowerCase()
  return props.colors.filter((color) => {
    const matchesQuery = !needle || `${color.code} ${color.name_zh} ${color.name_en || ''}`.toLowerCase().includes(needle)
    const matchesEffect = effect.value === 'all' || color.effect === effect.value
    const matchesSeries = series.value === 'all' || color.series === series.value
    return matchesQuery && matchesEffect && matchesSeries
  })
})
</script>

<template>
  <section class="palette">
    <div class="palette__head">
      <div><span class="eyebrow">调色板</span><strong>选择一颗拼豆</strong></div>
      <span class="count">{{ colors.length }} 色</span>
    </div>
    <label class="search"><span>⌕</span><input v-model="query" aria-label="搜索色卡" placeholder="搜索色号或名称"></label>
    <div class="filters">
      <select v-model="effect" aria-label="色卡范围"><option value="all">全部颜色</option><option value="standard">常规色</option><option value="special">扩展／特殊色</option></select>
      <select v-model="series" aria-label="色系"><option value="all">全部色系</option><option v-for="item in seriesOptions" :key="item" :value="item">{{ item }} 系</option></select>
    </div>
    <div class="colors">
      <button
        v-for="color in filtered"
        :key="color.code"
        class="color"
        :class="{ selected: color.code === selectedCode }"
        :title="`${color.code} · ${color.name_zh}`"
        @click="emit('select', color.code)"
      >
        <span class="swatch" :style="{ background: color.hex }" />
        <span class="color__label"><b>{{ color.code }}</b><small>{{ counts.get(color.code) || 0 }}</small></span>
      </button>
    </div>
  </section>
</template>

<style scoped>
.palette { display: grid; gap: 12px; padding: 18px; }
.palette__head { display: flex; align-items: end; justify-content: space-between; gap: 12px; }.palette__head > div { display: grid; gap: 3px; }.palette__head strong { color: #17213a; font-size: 15px; }.eyebrow { color: #7457e8; font-size: 10px; font-weight: 800; letter-spacing: .13em; }.count { border: 1px solid #e7e5f5; border-radius: 99px; padding: 4px 7px; color: #706990; background: #f8f7ff; font-family: var(--font-mono); font-size: 10px; }
.search { display: flex; align-items: center; gap: 7px; border: 1px solid #dedbea; border-radius: 10px; padding: 0 9px; background: #fbfaff; color: #7a70aa; transition: border-color .2s, box-shadow .2s; }.search:focus-within { border-color: #8168ef; box-shadow: 0 0 0 3px rgb(129 104 239 / 12%); }.search span { font-size: 19px; line-height: 1; } input { width: 100%; min-width: 0; border: 0; padding: 9px 0; outline: 0; background: transparent; font-size: 12px; }
.filters { display: grid; grid-template-columns: 1fr 1fr; gap: 7px; }.filters select { min-width: 0; border: 1px solid #e1deec; border-radius: 8px; padding: 7px; color: #4e5571; background: #fff; font-size: 11px; }
.colors { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 7px; max-height: 358px; overflow: auto; padding: 2px; scrollbar-color: #c5bded transparent; }
.color { position: relative; min-width: 0; padding: 0; overflow: hidden; border: 2px solid #f0eef6; border-radius: 10px; background: #f5f1eb; aspect-ratio: 1; box-shadow: 0 2px 5px rgb(22 28 54 / 6%); transition: transform .16s, border-color .16s, box-shadow .16s; }.color:hover { z-index: 1; border-color: #9b89f5; transform: translateY(-2px); box-shadow: 0 7px 13px rgb(71 51 161 / 20%); }.color.selected { z-index: 1; border-color: #5d43d0; box-shadow: 0 0 0 2px #dcd5ff, 0 6px 14px rgb(71 51 161 / 23%); }
.swatch { position: absolute; inset: 0; }.color::after { position: absolute; inset: 5px; border: 1px solid rgb(255 255 255 / 34%); border-radius: 6px; content: ''; pointer-events: none; }
.color__label { position: absolute; z-index: 1; inset: auto 0 0; display: flex; align-items: center; justify-content: space-between; padding: 3px 4px; color: #fff; background: linear-gradient(transparent, rgb(5 8 20 / 78%)); font-family: var(--font-mono); font-size: 9px; text-align: left; }.color__label b { overflow: hidden; text-overflow: ellipsis; } .color__label small { font-size: 8px; }
</style>
