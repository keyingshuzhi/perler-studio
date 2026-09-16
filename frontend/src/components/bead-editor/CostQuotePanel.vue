<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import type { PatternStatistics } from '@/types/bead'
import type { CostQuoteSettings } from '@/types/project'

const props = defineProps<{ statistics: PatternStatistics; initialSettings?: unknown }>()
const emit = defineEmits<{ update: [settings: CostQuoteSettings] }>()

const defaults: CostQuoteSettings = {
  version: 1,
  bead_unit_price: 0.035,
  board_unit_price: 8,
  fuse_paper_sheet_price: 1.5,
  frame_price: 0,
  labor_hourly_rate: 40,
  beads_per_hour: 300,
  waste_rate: 0.08,
  overhead_rate: 0.1,
}
const settings = ref<CostQuoteSettings>({ ...defaults })

function numberOrDefault(value: unknown, fallback: number) {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0 ? value : fallback
}
function normalize(value: unknown): CostQuoteSettings {
  if (!value || typeof value !== 'object') return { ...defaults }
  const source = value as Partial<CostQuoteSettings>
  return {
    version: 1,
    bead_unit_price: numberOrDefault(source.bead_unit_price, defaults.bead_unit_price),
    board_unit_price: numberOrDefault(source.board_unit_price, defaults.board_unit_price),
    fuse_paper_sheet_price: numberOrDefault(source.fuse_paper_sheet_price, defaults.fuse_paper_sheet_price),
    frame_price: numberOrDefault(source.frame_price, defaults.frame_price),
    labor_hourly_rate: numberOrDefault(source.labor_hourly_rate, defaults.labor_hourly_rate),
    beads_per_hour: Math.max(1, numberOrDefault(source.beads_per_hour, defaults.beads_per_hour)),
    waste_rate: numberOrDefault(source.waste_rate, defaults.waste_rate),
    overhead_rate: numberOrDefault(source.overhead_rate, defaults.overhead_rate),
  }
}

let syncingFromProps = false
watch(settings, (value) => {
  if (syncingFromProps) { syncingFromProps = false; return }
  emit('update', { ...value })
}, { deep: true, flush: 'sync' })
watch(() => props.initialSettings, (value) => {
  syncingFromProps = true
  settings.value = normalize(value)
}, { immediate: true })

const quote = computed(() => {
  const requiredBeads = Math.ceil(props.statistics.total_beads * (1 + settings.value.waste_rate))
  const spareBeads = Math.max(0, requiredBeads - props.statistics.total_beads)
  const boardCount = Math.max(1, props.statistics.estimated_pegboards)
  const paperSheets = Math.max(1, Math.ceil(requiredBeads / 841))
  const laborHours = props.statistics.total_beads / settings.value.beads_per_hour
  const beadCost = requiredBeads * settings.value.bead_unit_price
  const boardCost = boardCount * settings.value.board_unit_price
  const paperCost = paperSheets * settings.value.fuse_paper_sheet_price
  const laborCost = laborHours * settings.value.labor_hourly_rate
  const subtotal = beadCost + boardCost + paperCost + settings.value.frame_price + laborCost
  const overhead = subtotal * settings.value.overhead_rate
  return { requiredBeads, spareBeads, boardCount, paperSheets, laborHours, beadCost, boardCost, paperCost, laborCost, subtotal, overhead, total: subtotal + overhead }
})

const money = (value: number) => `¥${value.toFixed(2)}`
</script>

<template>
  <section class="quote">
    <div class="quote__head"><div><span class="eyebrow">COST ESTIMATE</span><strong>制作报价</strong></div><b>{{ money(quote.total) }}</b></div>
    <p>按当前图纸 {{ statistics.total_beads.toLocaleString() }} 颗、{{ statistics.estimated_pegboards }} 块估算；单价可按你的实际采购成本调整。</p>
    <details>
      <summary>调整单价与损耗</summary>
      <div class="fields"><label>每颗拼豆（元）<input v-model.number="settings.bead_unit_price" min="0" step="0.001" type="number"></label><label>每块底板（元）<input v-model.number="settings.board_unit_price" min="0" step="0.1" type="number"></label><label>每张烫纸（元）<input v-model.number="settings.fuse_paper_sheet_price" min="0" step="0.1" type="number"></label><label>装框（元）<input v-model.number="settings.frame_price" min="0" step="1" type="number"></label><label>人工时薪（元）<input v-model.number="settings.labor_hourly_rate" min="0" step="1" type="number"></label><label>每小时制作颗数<input v-model.number="settings.beads_per_hour" min="1" step="10" type="number"></label><label>拼豆损耗<input v-model.number="settings.waste_rate" min="0" max="1" step="0.01" type="number"></label><label>管理及利润<input v-model.number="settings.overhead_rate" min="0" max="1" step="0.01" type="number"></label></div>
    </details>
    <ul><li><span>拼豆 {{ quote.requiredBeads.toLocaleString() }} 颗 <small>含损耗 {{ quote.spareBeads.toLocaleString() }} 颗</small></span><b>{{ money(quote.beadCost) }}</b></li><li><span>底板 {{ quote.boardCount }} 块</span><b>{{ money(quote.boardCost) }}</b></li><li><span>烫纸 {{ quote.paperSheets }} 张</span><b>{{ money(quote.paperCost) }}</b></li><li v-if="settings.frame_price"><span>装框</span><b>{{ money(settings.frame_price) }}</b></li><li><span>人工 {{ quote.laborHours.toFixed(1) }} 小时</span><b>{{ money(quote.laborCost) }}</b></li><li><span>管理及利润</span><b>{{ money(quote.overhead) }}</b></li></ul>
    <div class="quote__total"><span>建议报价</span><b>{{ money(quote.total) }}</b></div>
  </section>
</template>

<style scoped>
.quote { display: grid; gap: 10px; padding: 18px; border-top: 1px solid #e7e4ef; background: #fcfbff; }.quote__head { display: flex; align-items: end; justify-content: space-between; gap: 8px; }.quote__head > div { display: grid; gap: 3px; }.eyebrow { color: #7359e6; font-size: 9px; font-weight: 800; letter-spacing: .13em; }.quote__head strong { color: #1d2742; font-size: 15px; }.quote__head > b { color: #4a36a6; font-family: var(--font-mono); font-size: 18px; }.quote > p { margin: 0; color: #77809a; font-size: 10px; line-height: 1.55; }.quote details { border: 1px solid #e3dff0; border-radius: 8px; background: #fff; }.quote summary { cursor: pointer; padding: 7px 8px; color: #5e509d; font-size: 10px; font-weight: 800; }.fields { display: grid; grid-template-columns: 1fr 1fr; gap: 7px; padding: 0 8px 8px; }.fields label { display: grid; gap: 3px; color: #7a8398; font-size: 8px; }.fields input { min-width: 0; border: 1px solid #dfdce9; border-radius: 6px; padding: 5px; color: #46516a; font-family: var(--font-mono); font-size: 9px; }.quote ul { display: grid; gap: 5px; margin: 0; padding: 0; list-style: none; }.quote li { display: flex; justify-content: space-between; gap: 8px; border-bottom: 1px solid #ece9f3; padding-bottom: 4px; color: #606a82; font-size: 10px; }.quote li span { display: grid; gap: 1px; }.quote li small { color: #9299aa; font-size: 8px; }.quote li b { color: #434c65; font-family: var(--font-mono); font-size: 9px; }.quote__total { display: flex; justify-content: space-between; color: #43338e; font-size: 11px; font-weight: 800; }.quote__total b { font-family: var(--font-mono); font-size: 15px; }
</style>
