<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import { addShareComment, confirmShare, getShare } from '@/api/shares'
import { mediaUrl } from '@/api/http'
import type { PublicShare } from '@/types/project'

const route = useRoute()
const share = ref<PublicShare>()
const loading = ref(true)
const saving = ref(false)
const error = ref('')
const confirmationComment = ref('')
const annotationComment = ref('')
const annotationSaving = ref(false)
const selectedCell = ref<number>()
const confirmation = computed(() => share.value?.share.confirmation)
const selectedCoordinate = computed(() => {
  if (selectedCell.value === undefined || !share.value?.pattern) return undefined
  const width = share.value.pattern.grid_width
  return { row: Math.floor(selectedCell.value / width) + 1, column: selectedCell.value % width + 1 }
})
const markerStyle = computed(() => {
  if (!selectedCoordinate.value || !share.value?.pattern) return undefined
  return {
    left: `${(selectedCoordinate.value.column - .5) / share.value.pattern.grid_width * 100}%`,
    top: `${(selectedCoordinate.value.row - .5) / share.value.pattern.grid_height * 100}%`,
  }
})

async function load() {
  loading.value = true
  try { share.value = await getShare(String(route.params.token)) } catch (reason) { error.value = reason instanceof Error ? reason.message : '无法打开此分享链接' } finally { loading.value = false }
}
async function respond(decision: 'approved' | 'changes_requested') {
  saving.value = true
  try { share.value = await confirmShare(String(route.params.token), decision, confirmationComment.value); confirmationComment.value = '' } catch (reason) { error.value = reason instanceof Error ? reason.message : '提交失败' } finally { saving.value = false }
}
function selectCell(event: MouseEvent) {
  if (!share.value?.pattern) return
  const image = event.currentTarget as HTMLImageElement
  const bounds = image.getBoundingClientRect()
  const column = Math.min(share.value.pattern.grid_width - 1, Math.max(0, Math.floor((event.clientX - bounds.left) / bounds.width * share.value.pattern.grid_width)))
  const row = Math.min(share.value.pattern.grid_height - 1, Math.max(0, Math.floor((event.clientY - bounds.top) / bounds.height * share.value.pattern.grid_height)))
  selectedCell.value = row * share.value.pattern.grid_width + column
}
async function leaveComment() {
  const message = annotationComment.value.trim()
  if (!message) return
  annotationSaving.value = true
  try {
    share.value = await addShareComment(String(route.params.token), message, selectedCell.value)
    annotationComment.value = ''
  } catch (reason) { error.value = reason instanceof Error ? reason.message : '留言发送失败' } finally { annotationSaving.value = false }
}
onMounted(() => void load())
</script>

<template>
  <main class="share-page"><section v-if="loading" class="state card">正在打开图纸…</section><section v-else-if="error || !share" class="state card"><h1>链接不可用</h1><p>{{ error || '未找到这份图纸。' }}</p></section><section v-else class="share-card card"><header><p class="eyebrow">PERLER STUDIO · CLIENT REVIEW</p><h1>{{ share.share.title }}</h1><p>{{ share.project.description || '请预览本次拼豆图纸，并确认是否可以开始制作。' }}</p></header><div v-if="share.pattern" class="content"><figure><div class="grid-preview"><img :src="mediaUrl(share.pattern.preview_url)" :alt="`${share.project.name} 图纸预览`" title="点击格子添加定位留言" @click="selectCell"><i v-if="markerStyle" class="cell-marker" :style="markerStyle" /></div><figcaption>{{ share.pattern.grid_width }} × {{ share.pattern.grid_height }} 格 · {{ share.pattern.statistics.total_beads.toLocaleString() }} 颗 · {{ share.pattern.statistics.used_color_count }} 色</figcaption><small class="hint">点击图纸任意格，可将留言定位到对应坐标。</small></figure><aside><span class="eyebrow">REVIEW STATUS</span><template v-if="confirmation"><h2 :class="confirmation.decision">{{ confirmation.decision === 'approved' ? '已确认制作' : '已要求修改' }}</h2><p>{{ confirmation.comment || '未附加备注。' }}</p><time>{{ new Date(confirmation.confirmed_at).toLocaleString() }}</time></template><template v-else><h2>确认图纸</h2><p>确认后，创作者会看到你的决定和备注；你也可以直接要求修改。</p><label>备注（可选）<textarea v-model="confirmationComment" maxlength="2000" placeholder="例如：颜色、尺寸或细节需要调整…" /></label><div class="actions"><button class="button button--quiet" :disabled="saving" @click="respond('changes_requested')">需要修改</button><button class="button" :disabled="saving" @click="respond('approved')">{{ saving ? '正在提交…' : '确认制作' }}</button></div></template><section class="annotations"><div><b>定位留言</b><small>{{ selectedCoordinate ? `已选第 ${selectedCoordinate.row} 行、第 ${selectedCoordinate.column} 列` : '未选坐标（可作为普通留言）' }}</small></div><label>留言<textarea v-model="annotationComment" maxlength="2000" placeholder="例如：这里的轮廓再圆润一些…" /></label><div class="annotation-actions"><button v-if="selectedCoordinate" type="button" @click="selectedCell = undefined">取消定位</button><button class="button" type="button" :disabled="annotationSaving || !annotationComment.trim()" @click="leaveComment">{{ annotationSaving ? '发送中…' : '发送留言' }}</button></div><ul v-if="share.share.comments.length"><li v-for="item in share.share.comments.slice().reverse()" :key="item.id"><b>{{ item.cell_index === undefined ? '整体' : `第 ${item.row} 行 · 第 ${item.column} 列` }}</b><p>{{ item.message }}</p><time>{{ new Date(item.created_at).toLocaleString() }}</time></li></ul></section></aside></div><p v-else class="state">当前项目没有可预览的图纸。</p><footer>此链接仅用于查看、定位反馈与客户确认，不会开放图纸编辑权限。</footer></section></main>
</template>

<style scoped>
.share-page { display: grid; min-height: calc(100vh - 62px); place-items: center; padding: 35px 18px; }.share-card { width: min(960px, 100%); overflow: hidden; }.share-card > header { padding: 32px 34px 25px; border-bottom: 1px solid #e6e3ef; background: linear-gradient(120deg, #fbfaff, #f1efff); }.eyebrow { margin: 0; color: #6f55dd; font-family: var(--font-mono); font-size: 10px; font-weight: 800; letter-spacing: .12em; }.share-card h1 { margin: 9px 0; color: #1d2743; font-family: Fraunces, Georgia, serif; font-size: clamp(30px, 5vw, 47px); letter-spacing: -1.9px; }.share-card header > p:last-child { max-width: 600px; margin: 0; color: #6e7890; font-size: 13px; line-height: 1.65; }.content { display: grid; grid-template-columns: minmax(0, 1.2fr) minmax(290px, .8fr); }.content figure { display: grid; align-content: start; gap: 9px; margin: 0; padding: 25px; background: repeating-conic-gradient(#eef0f5 0 25%, #fff 0 50%) 50% / 20px 20px; }.grid-preview { position: relative; }.content img { display: block; width: 100%; max-height: 500px; cursor: crosshair; object-fit: contain; border: 1px solid #dedbe7; border-radius: 10px; background: #fff; box-shadow: 0 10px 28px rgb(38 44 73 / 12%); }.cell-marker { position: absolute; width: 14px; height: 14px; border: 2px solid #fff; border-radius: 50%; background: #6a4bdd; box-shadow: 0 0 0 2px #6a4bdd, 0 3px 9px rgb(46 35 111 / 35%); transform: translate(-50%, -50%); pointer-events: none; }.content figcaption { color: #6f7890; font-family: var(--font-mono); font-size: 10px; text-align: center; }.hint { color: #7a7194; font-size: 10px; text-align: center; }.content aside { display: grid; align-content: start; gap: 12px; padding: 28px; border-left: 1px solid #e6e3ef; }.content h2 { margin: -5px 0 0; color: #23304d; font-size: 21px; }.content h2.approved { color: #258363; }.content h2.changes_requested { color: #b86555; }.content aside > p { margin: 0; color: #758096; font-size: 12px; line-height: 1.65; }.content label { display: grid; gap: 6px; color: #626d83; font-size: 11px; font-weight: 800; }.content textarea { min-height: 78px; resize: vertical; border: 1px solid #dedbe8; border-radius: 9px; padding: 9px; color: #46516a; font: inherit; font-size: 11px; }.actions, .annotation-actions { display: grid; grid-template-columns: 1fr 1fr; gap: 7px; }.actions .button, .annotation-actions .button { min-height: 37px; padding: 7px; font-size: 11px; }.annotation-actions > button:not(.button) { border: 1px solid #e1ddec; border-radius: 8px; background: #fff; color: #697389; font-size: 10px; }.content time { color: #9299aa; font-family: var(--font-mono); font-size: 9px; }.annotations { display: grid; gap: 8px; border-top: 1px solid #ebe8f1; padding-top: 13px; }.annotations > div { display: grid; gap: 2px; }.annotations > div b { color: #38435e; font-size: 12px; }.annotations > div small { color: #817a96; font-size: 9px; }.annotations ul { display: grid; gap: 6px; max-height: 210px; margin: 0; padding: 0; overflow: auto; list-style: none; }.annotations li { display: grid; gap: 3px; border: 1px solid #e6e1f0; border-radius: 8px; padding: 7px; background: #fbfaff; }.annotations li b { color: #6554b2; font-size: 9px; }.annotations li p { margin: 0; color: #667187; font-size: 10px; line-height: 1.45; }.share-card footer { padding: 12px 20px; border-top: 1px solid #e6e3ef; color: #8b93a5; font-size: 10px; text-align: center; }.state { display: grid; gap: 8px; padding: 40px; color: #727d92; text-align: center; }.state h1, .state p { margin: 0; }
@media (max-width: 700px) { .share-card > header { padding: 24px 20px; }.content { grid-template-columns: 1fr; }.content aside { border-top: 1px solid #e6e3ef; border-left: 0; }.content figure { padding: 18px; } }
</style>
