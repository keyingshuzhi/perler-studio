<script setup lang="ts">
import { computed } from 'vue'

import type { ColorReport } from '@/types/bead'

const props = defineProps<{ report?: ColorReport }>()
const qualityClass = computed(() => {
  if (!props.report) return ''
  if (props.report.quality_label === '优秀') return 'excellent'
  if (props.report.quality_label === '原创设计') return 'original'
  if (props.report.quality_label === '良好') return 'good'
  if (props.report.quality_label === '可制作') return 'usable'
  return 'refine'
})
const qualityBasisLabel = computed(() => {
  if (props.report?.quality_basis === 'measured_lab') return '实体 LAB'
  if (props.report?.quality_basis === 'mixed_lab') return `混合校准 ${props.report.measured_evaluated_percent}%`
  if (props.report?.quality_basis === 'screen_rgb') return '屏幕 RGB 参考'
  return '无参考图'
})
</script>

<template>
  <section v-if="report" class="report">
    <div class="report__head"><div><span class="eyebrow">COLOR SCIENCE</span><strong>色彩报告</strong></div><span class="quality" :class="qualityClass">{{ report.quality_label }}</span></div>
    <p class="report__note">{{ report.quality_note }}</p>
    <dl class="metrics"><div><dt>平均 ΔE00</dt><dd>{{ report.average_delta_e_00 }}</dd></div><div><dt>95% ΔE00</dt><dd>{{ report.p95_delta_e_00 }}</dd></div><div><dt>最大 ΔE00</dt><dd>{{ report.maximum_delta_e_00 }}</dd></div></dl>
    <p v-if="report.oracle_p95_delta_e_00 != null" class="oracle" :class="{ 'oracle--limited': report.oracle_target_reachable === false }">全色卡理论 P95 {{ report.oracle_p95_delta_e_00 }} · 当前差距 {{ report.p95_oracle_gap ?? '—' }}<span v-if="report.oracle_target_reachable === false">色卡色域不足以达到当前目标</span><span v-else-if="report.target_met === false">理论可达，仍有优化空间</span></p>
    <p class="report__caption">{{ report.metric }} · {{ qualityBasisLabel }} · {{ report.used_color_count }} / {{ report.selected_color_limit }} 色 · {{ report.evaluated_cells.toLocaleString() }} 格已评估</p>
    <template v-if="report.inventory.enabled">
      <div class="inventory-status"><div><span>库存覆盖</span><b>{{ report.inventory.coverage_percent }}%</b></div><progress :value="report.inventory.coverage_percent" max="100" /></div>
      <ul v-if="report.inventory.missing_colors.length" class="shortages"><li v-for="item in report.inventory.missing_colors.slice(0, 3)" :key="item.color_code"><i :style="{ background: item.hex }" /><span><b>{{ item.color_code }}</b> 缺 {{ item.shortage_quantity.toLocaleString() }} 颗</span></li></ul>
      <p v-else class="inventory-ok">库存可覆盖本图纸（已包含损耗）。</p>
      <div v-if="report.substitutions.length" class="alternative"><span>最近库存替代</span><p>{{ report.substitutions[0].from_color_code }} → <b>{{ report.substitutions[0].to_color_code }}</b> · ΔE {{ report.substitutions[0].delta_e_00 }}</p><small>{{ report.substitutions[0].assessment }}，仅供手动替换参考。</small></div>
    </template>
    <p v-else class="report__empty">尚未录入库存；在图纸设置中添加后，可显示缺色数量和最接近的现有替代色。</p>
  </section>
</template>

<style scoped>
.report { display: grid; gap: 10px; padding: 18px; border-top: 1px solid #e7e4ef; background: #fff; }.report__head { display: flex; align-items: end; justify-content: space-between; gap: 8px; }.report__head > div { display: grid; gap: 3px; }.report__head strong { color: #1d2742; font-size: 15px; }.eyebrow { color: #7359e6; font-size: 9px; font-weight: 800; letter-spacing: .13em; }.quality { border-radius: 99px; padding: 4px 7px; font-size: 9px; font-weight: 800; white-space: nowrap; }.quality.excellent { color: #17815f; background: #e8f8ef; }.quality.original { color: #6a55c3; background: #f0edff; }.quality.good { color: #4963b9; background: #eef1ff; }.quality.usable { color: #a56a18; background: #fff4dd; }.quality.refine { color: #b34f5b; background: #fff0f1; }.report__note, .report__caption, .report__empty { margin: 0; color: #778196; font-size: 10px; line-height: 1.55; }.metrics { display: grid; grid-template-columns: repeat(3, 1fr); gap: 5px; margin: 0; }.metrics div { padding: 7px 5px; border: 1px solid #eceaf2; border-radius: 8px; background: #fbfaff; text-align: center; }.metrics dt { color: #8991a5; font-size: 8px; }.metrics dd { margin: 2px 0 0; color: #2f3853; font-family: var(--font-mono); font-size: 12px; font-weight: 800; }.oracle { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 3px 7px; margin: 0; border-left: 2px solid #7562d6; padding: 5px 7px; background: #f6f4ff; color: #5f52af; font-family: var(--font-mono); font-size: 8px; line-height: 1.45; }.oracle span { color: #8176b8; }.oracle--limited { border-color: #d78767; background: #fff6f1; color: #ad5d43; }.oracle--limited span { color: #b36d55; }.report__caption { color: #9aa0b2; font-family: var(--font-mono); font-size: 8px; }.inventory-status { display: grid; gap: 5px; padding-top: 1px; }.inventory-status div { display: flex; justify-content: space-between; color: #65708a; font-size: 10px; }.inventory-status b { color: #2e8b68; font-family: var(--font-mono); }.inventory-status progress { width: 100%; height: 6px; overflow: hidden; border: 0; border-radius: 99px; background: #e8edf0; }.inventory-status progress::-webkit-progress-bar { background: #e8edf0; }.inventory-status progress::-webkit-progress-value { border-radius: 99px; background: linear-gradient(90deg, #41b78b, #7bd8b6); }.shortages { display: grid; gap: 4px; margin: 0; padding: 0; list-style: none; }.shortages li { display: flex; align-items: center; gap: 6px; color: #707a91; font-family: var(--font-mono); font-size: 9px; }.shortages i { width: 12px; height: 12px; border: 1px solid rgb(30 40 70 / 15%); border-radius: 50%; }.shortages b { color: #424c64; }.inventory-ok { margin: 0; color: #278264; font-size: 10px; font-weight: 700; }.alternative { display: grid; gap: 2px; border-left: 2px solid #9b88ef; padding: 4px 0 4px 8px; background: linear-gradient(90deg, #f8f6ff, transparent); }.alternative > span { color: #7762cd; font-size: 9px; font-weight: 800; }.alternative p, .alternative small { margin: 0; color: #606a80; font-size: 9px; line-height: 1.45; }.alternative b { color: #4f42ae; }.alternative small { color: #8c94a6; }
</style>
