<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import type { CellValue, EditorLayer } from '@/types/bead'
import type { PaletteColor } from '@/types/palette'

const props = defineProps<{
  selectionCount: number
  focusedCode: CellValue
  selectedColorCode: string
  activeLayer: EditorLayer
  hasClipboard: boolean
  selectionLocked: boolean
  colors: readonly PaletteColor[]
}>()
const emit = defineEmits<{
  copy: []
  paste: []
  clear: []
  selectByColor: [contiguous: boolean]
  selectSimilar: []
  transform: [kind: 'move-left' | 'move-right' | 'move-up' | 'move-down' | 'mirror-x' | 'mirror-y' | 'rotate-cw']
  replace: [from: CellValue, to: CellValue, selectedOnly: boolean]
  lock: []
}>()

const replaceFrom = ref<CellValue>(props.focusedCode)
const replaceTo = ref<CellValue>(props.selectedColorCode)
const selectedOnly = ref(true)
const canAct = computed(() => props.selectionCount > 0)

watch(() => props.focusedCode, (code) => { if (code !== null) replaceFrom.value = code })
watch(() => props.selectedColorCode, (code) => { replaceTo.value = code })

function replace() {
  if (replaceFrom.value === replaceTo.value) return
  emit('replace', replaceFrom.value, replaceTo.value || null, selectedOnly.value)
}
</script>

<template>
  <section class="selection-panel">
    <div class="panel-head"><div><span class="eyebrow">SELECTION</span><strong>选区与变换</strong></div><span class="count">{{ selectionCount }} 格</span></div>
    <p class="help">使用“选择”工具拖拽框选。基于当前选中格可按颜色、连续区域或相似颜色扩展选区。</p>
    <div class="smart-actions"><button type="button" :disabled="!canAct" @click="emit('selectByColor', false)">同色全部</button><button type="button" :disabled="!canAct" @click="emit('selectByColor', true)">连续区域</button><button type="button" :disabled="!canAct || !focusedCode" @click="emit('selectSimilar')">相似颜色</button></div>
    <div class="section"><span>复制与移动</span><div class="grid-actions"><button type="button" :disabled="!canAct" @click="emit('copy')">复制</button><button type="button" :disabled="!hasClipboard || !canAct" @click="emit('paste')">粘贴到选区</button><button type="button" :disabled="!canAct" @click="emit('clear')">清除选择</button></div><div class="nudge"><button type="button" :disabled="!canAct" aria-label="向上移动选区" @click="emit('transform', 'move-up')">↑</button><button type="button" :disabled="!canAct" aria-label="向左移动选区" @click="emit('transform', 'move-left')">←</button><button type="button" :disabled="!canAct" aria-label="向右移动选区" @click="emit('transform', 'move-right')">→</button><button type="button" :disabled="!canAct" aria-label="向下移动选区" @click="emit('transform', 'move-down')">↓</button></div></div>
    <div class="section"><span>镜像与旋转</span><div class="grid-actions"><button type="button" :disabled="!canAct" @click="emit('transform', 'mirror-x')">水平镜像</button><button type="button" :disabled="!canAct" @click="emit('transform', 'mirror-y')">垂直镜像</button><button type="button" :disabled="!canAct" @click="emit('transform', 'rotate-cw')">顺时针 90°</button></div></div>
    <div class="section"><span>批量色号替换</span><div class="replace"><select v-model="replaceFrom" aria-label="替换前色号"><option :value="null">透明格</option><option v-for="color in colors" :key="color.code" :value="color.code">{{ color.code }} · {{ color.name_zh }}</option></select><span>→</span><select v-model="replaceTo" aria-label="替换后色号"><option :value="null">透明格</option><option v-for="color in colors" :key="color.code" :value="color.code">{{ color.code }} · {{ color.name_zh }}</option></select></div><label class="scope"><input v-model="selectedOnly" type="checkbox"> 仅在当前选区替换</label><button class="replace-button" type="button" :disabled="selectedOnly && !canAct" @click="replace">执行替换</button></div>
    <button class="lock" type="button" :disabled="!canAct" @click="emit('lock')">{{ selectionLocked ? '解除区域锁定' : '锁定当前区域' }} <small>保护 {{ activeLayer === 'draft' ? '草稿' : '成品' }}编辑</small></button>
  </section>
</template>

<style scoped>
.selection-panel { display: grid; gap: 12px; padding: 17px; }.panel-head { display: flex; align-items: end; justify-content: space-between; gap: 8px; }.panel-head > div { display: grid; gap: 3px; }.eyebrow { color: #7359e6; font-size: 9px; font-weight: 800; letter-spacing: .13em; }.panel-head strong { color: #1d2742; font-size: 15px; }.count { border-radius: 99px; padding: 4px 7px; color: #6257a1; background: #efecfb; font-family: var(--font-mono); font-size: 9px; }.help { margin: -3px 0 0; color: #8790a3; font-size: 10px; line-height: 1.55; }.smart-actions, .grid-actions { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; }.smart-actions button, .grid-actions button, .nudge button, .replace-button, .lock { border: 1px solid #dfdbea; border-radius: 7px; padding: 7px 6px; color: #5f5681; background: #faf9ff; font: inherit; font-size: 9px; font-weight: 800; }.smart-actions button:hover:not(:disabled), .grid-actions button:hover:not(:disabled), .nudge button:hover:not(:disabled) { border-color: #b6a9ef; color: #5543b5; background: #f1efff; }.section { display: grid; gap: 7px; border-top: 1px solid #ece9f2; padding-top: 11px; }.section > span { color: #68728b; font-family: var(--font-mono); font-size: 9px; font-weight: 800; letter-spacing: .06em; }.nudge { display: grid; grid-template-columns: repeat(4, 1fr); gap: 5px; }.nudge button { padding: 5px; font-size: 13px; }.replace { display: grid; grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr); align-items: center; gap: 4px; }.replace select { min-width: 0; border: 1px solid #dedbe9; border-radius: 7px; padding: 6px; color: #4f5870; background: #fff; font-size: 9px; }.replace span { color: #866de5; }.scope { display: flex; align-items: center; gap: 5px; color: #788197; font-size: 9px; }.scope input { accent-color: #7056dc; }.replace-button { border-color: #d7d0f5; color: #5c49ba; background: #f5f2ff; }.lock { display: grid; gap: 2px; border-color: #e5dfcc; color: #866837; background: #fffaf0; text-align: left; }.lock small { color: #a18c68; font-size: 8px; font-weight: 500; }button:disabled { cursor: not-allowed; opacity: .42; }
</style>
