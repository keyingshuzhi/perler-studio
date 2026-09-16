<script setup lang="ts">
import type { PatternStatistics } from '@/types/bead'

defineProps<{ statistics: PatternStatistics; zoom: number; coordinate: string }>()
</script>

<template>
  <footer class="status">
    <span>{{ coordinate || '移动到网格查看坐标' }}</span>
    <span>{{ statistics.grid_width }} × {{ statistics.grid_height }} 格</span>
    <span>{{ statistics.total_beads.toLocaleString() }} 颗拼豆</span>
    <span>{{ statistics.used_color_count }} 种颜色</span>
    <span>{{ Math.round(zoom * 100) }}%</span>
  </footer>
</template>

<style scoped>
.status { display: flex; gap: 17px; flex-wrap: wrap; padding: 9px 14px; border-top: 1px solid #29344a; color: #aeb8ce; background: #151e30; font-family: var(--font-mono); font-size: 10px; }.status span { display: inline-flex; align-items: center; gap: 5px; }.status span:not(:first-child)::before { width: 3px; height: 3px; border-radius: 50%; background: #7460d4; content: ''; }.status span:first-child { margin-right: auto; color: #d7dcef; }
</style>
