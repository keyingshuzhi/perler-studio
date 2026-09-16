<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = withDefaults(defineProps<{
  hasMore: boolean
  loading: boolean
  endText?: string
}>(), { endText: '已加载全部内容' })

const emit = defineEmits<{ load: [] }>()
const sentinel = ref<HTMLElement | null>(null)
let observer: IntersectionObserver | undefined

function requestLoad() {
  if (props.hasMore && !props.loading) emit('load')
}

function reconnect() {
  observer?.disconnect()
  observer = undefined
  if (!sentinel.value || !props.hasMore || props.loading) return
  observer = new IntersectionObserver((entries) => {
    if (entries.some((entry) => entry.isIntersecting)) {
      observer?.disconnect()
      requestLoad()
    }
  }, { rootMargin: '280px 0px' })
  observer.observe(sentinel.value)
}

watch(() => [props.hasMore, props.loading], () => { void nextTick(reconnect) })
onMounted(reconnect)
onBeforeUnmount(() => observer?.disconnect())
</script>

<template>
  <div ref="sentinel" class="infinite-trigger" role="status" aria-live="polite">
    <template v-if="loading"><span class="spinner" aria-hidden="true" />正在加载更多内容…</template>
    <button v-else-if="hasMore" type="button" @click="requestLoad">继续加载</button>
    <span v-else class="end-text">{{ endText }}</span>
  </div>
</template>

<style scoped>
.infinite-trigger { display: flex; min-height: 54px; align-items: center; justify-content: center; gap: 8px; color: #8a93a5; font-size: 11px; }
.infinite-trigger button { border: 1px solid #ded9eb; border-radius: 999px; padding: 7px 12px; color: #6554b6; background: #faf9ff; font: inherit; font-weight: 800; cursor: pointer; }
.spinner { width: 14px; height: 14px; border: 2px solid #ddd8ed; border-top-color: #725bd6; border-radius: 50%; animation: spin .7s linear infinite; }
.end-text::before { margin-right: 6px; color: #55a78e; content: '✓'; font-weight: 900; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
