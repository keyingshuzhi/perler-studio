<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'

import { getAssemblyPlan } from '@/api/patterns'
import type { AssemblyPlan } from '@/types/design'

const props = defineProps<{ patternId: string }>()
const plan = ref<AssemblyPlan>()
const boardSize = ref(29)
const overlap = ref(0)
const loading = ref(false)
const error = ref('')

async function load() {
  loading.value = true
  error.value = ''
  try { plan.value = await getAssemblyPlan(props.patternId, boardSize.value, boardSize.value, overlap.value) } catch (reason) { error.value = reason instanceof Error ? reason.message : '无法生成拼接计划' } finally { loading.value = false }
}

onMounted(() => void load())
watch([boardSize, overlap, () => props.patternId], () => void load())
</script>

<template>
  <section class="mural">
    <div class="mural__head"><div><span class="eyebrow">ASSEMBLY PLAN</span><strong>多底板拼接</strong></div><span v-if="plan">{{ plan.board_count }} 板</span></div>
    <div class="controls"><label>底板<select v-model.number="boardSize"><option :value="29">29 × 29</option><option :value="30">30 × 30</option><option :value="60">60 × 60</option></select></label><label>重叠格<input v-model.number="overlap" type="number" min="0" :max="Math.max(0, boardSize - 1)"></label></div>
    <p v-if="loading" class="muted">正在计算拼接范围…</p><p v-else-if="error" class="error">{{ error }}</p>
    <template v-else-if="plan"><p class="description">{{ plan.grid_width }} × {{ plan.grid_height }} 格将拆为 {{ plan.board_rows }} × {{ plan.board_columns }} 块，按 A1 → {{ plan.boards.at(-1)?.id }} 顺序拼接。</p><div class="board-map" :style="{ gridTemplateColumns: `repeat(${plan.board_columns}, 1fr)` }"><span v-for="board in plan.boards" :key="board.id" :title="`行 ${board.row_range[0]}-${board.row_range[1]}，列 ${board.column_range[0]}-${board.column_range[1]}`">{{ board.id }}</span></div><ul><li v-for="board in plan.boards.slice(0, 3)" :key="board.id"><b>{{ board.id }}</b><span>行 {{ board.row_range[0] }}–{{ board.row_range[1] }} · 列 {{ board.column_range[0] }}–{{ board.column_range[1] }}</span></li></ul><p v-if="plan.overlap" class="join-note">相邻底板保留 {{ plan.overlap }} 格重叠区，用于校准拼接边缘。</p></template>
  </section>
</template>

<style scoped>
.mural { display: grid; gap: 10px; padding: 18px; border-top: 1px solid #e7e4ef; background: #fcfbff; }.mural__head { display: flex; align-items: end; justify-content: space-between; gap: 8px; }.mural__head > div { display: grid; gap: 3px; }.eyebrow { color: #7359e6; font-size: 9px; font-weight: 800; letter-spacing: .13em; }.mural__head strong { color: #1d2742; font-size: 15px; }.mural__head > span { border-radius: 99px; padding: 4px 7px; color: #5f50bc; background: #eeebff; font-family: var(--font-mono); font-size: 9px; white-space: nowrap; }.controls { display: grid; grid-template-columns: 1fr 1fr; gap: 7px; }.controls label { display: grid; gap: 4px; color: #788197; font-size: 9px; font-weight: 800; }.controls select, .controls input { width: 100%; min-height: 29px; border: 1px solid #e1deeb; border-radius: 7px; padding: 4px 6px; color: #4b5570; background: #fff; font-family: var(--font-mono); font-size: 10px; }.description, .join-note, .muted, .error { margin: 0; color: #737d94; font-size: 10px; line-height: 1.55; }.error { color: #bd5160; }.board-map { display: grid; gap: 4px; border: 1px solid #e5e1f1; border-radius: 9px; padding: 6px; background: #f5f3fb; }.board-map span { display: grid; min-width: 0; aspect-ratio: 1.25; place-items: center; border: 1px solid #cfc5f1; border-radius: 5px; background: linear-gradient(145deg, #fff, #f4f0ff); color: #5947b4; font-family: var(--font-mono); font-size: 9px; font-weight: 800; }.mural ul { display: grid; gap: 4px; margin: 0; padding: 0; list-style: none; }.mural li { display: flex; gap: 7px; color: #7c8498; font-family: var(--font-mono); font-size: 8px; }.mural li b { color: #4d3bad; }.join-note { color: #6b5ac0; }
</style>
