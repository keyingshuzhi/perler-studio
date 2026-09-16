<script setup lang="ts">
import type { EditorLayer, ProfessionalEditorSettings } from '@/types/bead'

defineProps<{
  activeLayer: EditorLayer
  layers: ProfessionalEditorSettings['layers']
  referenceAvailable: boolean
  hasDraft: boolean
}>()
const emit = defineEmits<{
  active: [layer: EditorLayer]
  visible: [layer: keyof ProfessionalEditorSettings['layers'], visible: boolean]
  opacity: [value: number]
  applyDraft: []
  clearDraft: []
}>()
</script>

<template>
  <section class="layer-panel">
    <div class="panel-head"><div><span class="eyebrow">LAYERS</span><strong>图层工作流</strong></div><span>3 层</span></div>
    <p>原图用于对照，草稿层可安全试色，成品层才会写入最终图纸。</p>
    <article class="layer" :class="{ disabled: !referenceAvailable }"><div><i class="reference" /><span><b>原图参考</b><small>{{ referenceAvailable ? `透明度 ${layers.reference.opacity}%` : '空白创作无原图' }}</small></span></div><label><input :checked="layers.reference.visible" :disabled="!referenceAvailable" type="checkbox" @change="emit('visible', 'reference', ($event.target as HTMLInputElement).checked)"> 显示</label><input v-if="referenceAvailable && layers.reference.visible" :value="layers.reference.opacity" type="range" min="0" max="100" step="5" aria-label="原图参考透明度" @input="emit('opacity', Number(($event.target as HTMLInputElement).value))"></article>
    <article class="layer" :class="{ active: activeLayer === 'draft' }"><div><i class="draft" /><span><b>草稿层</b><small>{{ hasDraft ? '含临时修改' : '安全试色与布局' }}</small></span></div><div class="layer-actions"><label><input :checked="layers.draft.visible" type="checkbox" @change="emit('visible', 'draft', ($event.target as HTMLInputElement).checked)"> 显示</label><button type="button" @click="emit('active', 'draft')">{{ activeLayer === 'draft' ? '正在编辑' : '编辑草稿' }}</button></div></article>
    <article class="layer" :class="{ active: activeLayer === 'finished' }"><div><i class="finished" /><span><b>成品层</b><small>导出与保存的正式图纸</small></span></div><div class="layer-actions"><label><input :checked="layers.finished.visible" type="checkbox" @change="emit('visible', 'finished', ($event.target as HTMLInputElement).checked)"> 显示</label><button type="button" @click="emit('active', 'finished')">{{ activeLayer === 'finished' ? '正在编辑' : '编辑成品' }}</button></div></article>
    <div v-if="hasDraft" class="draft-actions"><button type="button" @click="emit('applyDraft')">应用草稿到成品层</button><button type="button" @click="emit('clearDraft')">清空草稿</button></div>
  </section>
</template>

<style scoped>
.layer-panel { display: grid; gap: 10px; padding: 17px; }.panel-head { display: flex; align-items: end; justify-content: space-between; }.panel-head > div { display: grid; gap: 3px; }.eyebrow { color: #7359e6; font-size: 9px; font-weight: 800; letter-spacing: .13em; }.panel-head strong { color: #1d2742; font-size: 15px; }.panel-head > span { color: #8d95a7; font-family: var(--font-mono); font-size: 9px; }.layer-panel > p { margin: -2px 0 1px; color: #858ea2; font-size: 10px; line-height: 1.55; }.layer { display: grid; gap: 8px; border: 1px solid #e4e0ed; border-radius: 10px; padding: 10px; background: #fff; transition: border-color .15s, background .15s; }.layer.active { border-color: #aa9aef; background: #faf9ff; }.layer.disabled { opacity: .55; }.layer > div:first-child { display: flex; align-items: center; gap: 8px; }.layer i { width: 20px; height: 20px; border-radius: 6px; background: #7261d9; }.layer i.reference { background: linear-gradient(135deg, #f0a27c, #8172df); }.layer i.draft { background: repeating-linear-gradient(45deg, #9a8aec 0 3px, #f0edff 3px 6px); }.layer i.finished { background: linear-gradient(135deg, #3fba9a, #68d1b4); }.layer span { display: grid; gap: 1px; }.layer b { color: #424b65; font-size: 11px; }.layer small { color: #939aab; font-size: 8px; }.layer label { color: #6b748a; font-size: 9px; white-space: nowrap; }.layer input[type='checkbox'] { accent-color: #6b53d9; }.layer input[type='range'] { width: 100%; accent-color: #6b53d9; }.layer-actions { display: flex; align-items: center; justify-content: space-between; gap: 5px; }.layer-actions button, .draft-actions button { border: 1px solid #ded9ee; border-radius: 7px; padding: 5px 6px; color: #5d4ab7; background: #f6f3ff; font: inherit; font-size: 8px; font-weight: 800; }.draft-actions { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; border-top: 1px solid #ebe8f1; padding-top: 10px; }.draft-actions button:last-child { color: #a4605c; background: #fff7f6; }
</style>
