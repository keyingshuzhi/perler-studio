<script setup lang="ts">
import type { EditorTool } from '@/types/bead'

defineProps<{ tool: EditorTool; canUndo: boolean; canRedo: boolean; canEditSettings: boolean; saving: boolean; dirty: boolean }>()
const emit = defineEmits<{ tool: [tool: EditorTool]; undo: []; redo: []; save: []; settings: [] }>()

const tools: Array<{ id: EditorTool; label: string; key: string }> = [
  { id: 'brush', label: '画笔', key: 'B' },
  { id: 'eraser', label: '橡皮擦', key: 'E' },
  { id: 'eyedropper', label: '吸管', key: 'I' },
  { id: 'fill', label: '填充', key: 'F' },
  { id: 'select', label: '选择', key: 'V' },
]
</script>

<template>
  <div class="toolbar">
    <div class="tools"><span class="toolbar__label">工具</span>
      <button v-for="item in tools" :key="item.id" class="tool" :class="{ active: tool === item.id }" :title="`${item.label} (${item.key})`" @click="emit('tool', item.id)">{{ item.label }} <kbd>{{ item.key }}</kbd></button>
    </div>
    <div class="actions">
      <button class="tool tool--settings" :disabled="!canEditSettings" :title="canEditSettings ? '返回图纸设置' : '仅图片转换生成的图纸可调整转换设置'" @click="emit('settings')">图纸设置</button>
      <button class="tool tool--history" title="撤销 (⌘Z)" :disabled="!canUndo" @click="emit('undo')">撤销</button>
      <button class="tool tool--history" title="重做 (⌘⇧Z)" :disabled="!canRedo" @click="emit('redo')">重做</button>
      <button class="button" :class="{ 'button--saved': !dirty && !saving }" :disabled="!dirty || saving" @click="emit('save')"><span class="save-dot" />{{ saving ? '保存中…' : dirty ? '保存变更' : '已保存' }}</button>
    </div>
  </div>
</template>

<style scoped>
.toolbar { display: flex; align-items: center; justify-content: space-between; gap: 14px; padding: 10px 13px; border-bottom: 1px solid #29344a; background: linear-gradient(90deg, #1b253a, #1d2940); }.tools, .actions { display: flex; align-items: center; gap: 5px; }.toolbar__label { margin-right: 3px; color: #8791ad; font-family: var(--font-mono); font-size: 10px; letter-spacing: .08em; text-transform: uppercase; }.tool { display: inline-flex; align-items: center; gap: 5px; border: 1px solid transparent; border-radius: 7px; padding: 6px 8px; background: transparent; color: #bdc5da; font-size: 12px; transition: background .16s, color .16s, border-color .16s; }.tool:hover { border-color: #3c4a66; background: #293750; color: #fff; }.tool.active { border-color: #745ce1; background: #4936a5; color: #fff; box-shadow: 0 3px 9px rgb(40 22 113 / 35%); }.tool kbd { border: 1px solid rgb(255 255 255 / 16%); border-radius: 3px; padding: 1px 3px; color: #c9c2ee; font-family: var(--font-mono); font-size: 8px; }.tool.active kbd { border-color: rgb(255 255 255 / 24%); color: #fff; }.tool:disabled { opacity: .3; cursor: not-allowed; }.tool--history { font-size: 11px; }.tool--settings { border-color: #405072; color: #e0e6f8; }.button { display: inline-flex; align-items: center; gap: 6px; min-height: 31px; padding-inline: 11px; border-radius: 8px; background: linear-gradient(135deg, #6d50e3, #9276ef); font-size: 11px; box-shadow: 0 5px 12px rgb(57 35 151 / 28%); }.button:disabled:not(.button--saved) { opacity: .55; }.button--saved { color: #b6e8cf; background: #285746; box-shadow: none; }.save-dot { width: 6px; height: 6px; border-radius: 50%; background: currentColor; }.button:not(.button--saved) .save-dot { background: #fff; } @media (max-width: 700px) { .toolbar { align-items: stretch; flex-direction: column; } .tools { overflow-x: auto; }.actions { justify-content: flex-end; } }
</style>
