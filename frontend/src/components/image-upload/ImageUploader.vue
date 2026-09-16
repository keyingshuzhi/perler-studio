<script setup lang="ts">
import { ref } from 'vue'

import { uploadImage } from '@/api/images'
import type { ImageInfo } from '@/types/project'

const emit = defineEmits<{ uploaded: [image: ImageInfo]; error: [error: unknown] }>()
const input = ref<HTMLInputElement>()
const loading = ref(false)
const dragging = ref(false)

async function choose(file?: File) {
  if (!file) return
  if (!['image/png', 'image/jpeg', 'image/webp'].includes(file.type)) {
    emit('error', new Error('请选择 PNG、JPG 或 WebP 图片'))
    return
  }
  loading.value = true
  try {
    emit('uploaded', await uploadImage(file))
  } catch (error) {
    emit('error', error)
  } finally {
    loading.value = false
    if (input.value) input.value.value = ''
  }
}
</script>

<template>
  <div class="uploader" :class="{ dragging, loading }" @dragenter.prevent="dragging = true" @dragover.prevent="dragging = true" @dragleave.prevent="dragging = false" @drop.prevent="dragging = false; choose($event.dataTransfer?.files[0])">
    <input ref="input" class="sr-only" type="file" accept="image/png,image/jpeg,image/webp" @change="choose(($event.target as HTMLInputElement).files?.[0])">
    <div class="uploader__icon"><span>↑</span></div>
    <strong>{{ loading ? '正在安全上传图片…' : dragging ? '松开即可上传' : '把图片拖到这里' }}</strong>
    <p>PNG、JPG 或 WebP · 最大 20 MB</p>
    <button class="button button--quiet" :disabled="loading" @click="input?.click()">从设备选择</button>
  </div>
</template>

<style scoped>
.uploader { display: grid; min-height: 350px; place-content: center; justify-items: center; gap: 10px; padding: 28px; border: 1.5px dashed #c8c2f0; border-radius: 16px; background: linear-gradient(135deg, #faf9ff, #f3faff); text-align: center; transition: border-color .2s ease, background .2s ease, transform .2s ease; }.uploader:hover, .uploader.dragging { border-color: #725feb; background: linear-gradient(135deg, #f3f1ff, #eafaf6); }.uploader.dragging { transform: scale(1.01); }.uploader.loading { pointer-events: none; }.uploader__icon { display: grid; width: 54px; height: 54px; place-items: center; border-radius: 17px; background: linear-gradient(135deg, #6c58e9, #8b78f5); box-shadow: 0 10px 20px rgb(104 84 232 / 23%); color: #fff; font-size: 26px; font-weight: 800; }.uploader strong { color: #283247; font-size: 15px; } p { margin: 0 0 10px; color: #778196; font-size: 12px; }
</style>
