<script setup lang="ts">
import { computed, ref } from 'vue'

import type { PaletteColor } from '@/types/palette'

const props = defineProps<{
  colors: readonly PaletteColor[]
  modelValue: Record<string, number>
}>()
const emit = defineEmits<{ 'update:modelValue': [value: Record<string, number>] }>()

const query = ref('')
const stockedCount = computed(() => Object.values(props.modelValue).filter((quantity) => quantity > 0).length)
const stockedBeads = computed(() => Object.values(props.modelValue).reduce((total, quantity) => total + Math.max(0, quantity), 0))
const filtered = computed(() => {
  const needle = query.value.trim().toLowerCase()
  return props.colors.filter((color) => !needle || `${color.code} ${color.name_zh} ${color.name_en || ''}`.toLowerCase().includes(needle))
})

function update(code: string, value: string | number) {
  const quantity = Math.max(0, Math.min(1_000_000, Math.floor(Number(value) || 0)))
  const next = { ...props.modelValue }
  if (quantity) next[code] = quantity
  else delete next[code]
  emit('update:modelValue', next)
}

function fillAll() {
  emit('update:modelValue', Object.fromEntries(props.colors.filter((color) => color.available).map((color) => [color.code, 999])))
}
</script>

<template>
  <details class="inventory">
    <summary><span><b>我的库存</b><small>按实际数量限制或核对材料</small></span><output>{{ stockedCount }} 色 · {{ stockedBeads.toLocaleString() }} 颗</output></summary>
    <div class="inventory__body">
      <p>库存保存在当前设备。严格库存会只使用已录入且数量大于 0 的颜色；报告模式则保留图纸配色并给出缺色与替代建议。</p>
      <div class="inventory__tools"><label><span>⌕</span><input v-model="query" aria-label="搜索库存色号" placeholder="搜索色号或名称"></label><button type="button" @click="fillAll">全部拥有</button><button type="button" @click="emit('update:modelValue', {})">清空</button></div>
      <div class="inventory__list">
        <label v-for="color in filtered" :key="color.code" class="inventory__item" :class="{ stocked: (modelValue[color.code] || 0) > 0 }">
          <i :style="{ background: color.hex }" />
          <span><b>{{ color.code }}</b><small>{{ color.name_zh }}</small></span>
          <input :value="modelValue[color.code] || ''" type="number" min="0" max="1000000" inputmode="numeric" :aria-label="`${color.code} 库存数量`" placeholder="0" @change="update(color.code, ($event.target as HTMLInputElement).value)">
        </label>
      </div>
    </div>
  </details>
</template>

<style scoped>
.inventory { border: 1px solid var(--line); border-radius: 12px; background: #fafbfe; }.inventory summary { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 11px 12px; cursor: pointer; list-style: none; }.inventory summary::-webkit-details-marker { display: none; }.inventory summary > span { display: grid; gap: 2px; color: #3c485c; font-size: 12px; }.inventory summary small, .inventory summary output { color: #8791a3; font-size: 10px; font-weight: 600; }.inventory summary output { flex: 0 0 auto; color: #5f50bc; font-family: "DM Mono", monospace; white-space: nowrap; }.inventory[open] summary { border-bottom: 1px solid var(--line); }.inventory__body { display: grid; gap: 10px; padding: 12px; }.inventory__body > p { margin: 0; color: #778196; font-size: 10px; line-height: 1.55; }.inventory__tools { display: grid; grid-template-columns: 1fr auto auto; gap: 6px; }.inventory__tools label { display: flex; align-items: center; gap: 5px; min-width: 0; border: 1px solid #dfe1eb; border-radius: 8px; padding: 0 7px; background: #fff; color: #8178ad; }.inventory__tools input { width: 100%; min-width: 0; border: 0; padding: 7px 0; outline: 0; background: transparent; font-size: 10px; }.inventory__tools button { border: 1px solid #e0dcef; border-radius: 8px; padding: 0 7px; background: #fff; color: #6656bd; font-size: 10px; font-weight: 800; white-space: nowrap; }.inventory__tools button:hover { border-color: #b7a9f2; background: #f6f3ff; }.inventory__list { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 5px; max-height: 245px; overflow: auto; padding-right: 2px; }.inventory__item { display: grid; grid-template-columns: 14px minmax(0, 1fr) 42px; gap: 6px; align-items: center; border: 1px solid #e6e5ec; border-radius: 8px; padding: 5px; background: #fff; color: #68728a; }.inventory__item.stocked { border-color: #b5e1cd; background: #f5fcf8; }.inventory__item i { width: 14px; height: 14px; border: 1px solid rgb(20 30 50 / 16%); border-radius: 50%; box-shadow: inset 1px 1px 2px rgb(255 255 255 / 64%); }.inventory__item span { display: grid; min-width: 0; gap: 1px; }.inventory__item b { overflow: hidden; color: #374159; font-family: "DM Mono", monospace; font-size: 9px; text-overflow: ellipsis; white-space: nowrap; }.inventory__item small { overflow: hidden; font-size: 8px; text-overflow: ellipsis; white-space: nowrap; }.inventory__item input { width: 100%; min-height: 24px; border: 1px solid #e2e0eb; border-radius: 6px; padding: 2px 4px; color: #434c62; font-family: "DM Mono", monospace; font-size: 9px; text-align: right; }.inventory__item input:focus { border-color: #8170e9; outline: 0; }
@media (max-width: 480px) { .inventory__tools { grid-template-columns: 1fr 1fr; }.inventory__tools label { grid-column: 1 / -1; }.inventory__list { grid-template-columns: 1fr; } }
</style>
