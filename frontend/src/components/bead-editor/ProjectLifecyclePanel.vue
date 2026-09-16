<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import { createProjectShare, createProjectVersion, getProjectVersion, listProjectVersions, restoreProjectVersion } from '@/api/projects'
import { listMyPublications, submitPublication, withdrawPublication } from '@/api/publications'
import { uploadImage } from '@/api/images'
import type { Pattern } from '@/types/bead'
import type { ProjectShare, ProjectVersion, ProjectVersionDetail } from '@/types/project'
import type { Publication } from '@/types/publication'

const props = defineProps<{
  projectId: string
  projectName?: string
  projectDescription?: string | null
  currentPattern?: Pattern | null
  versionRefreshKey?: number
  hasUnsavedChanges?: boolean
}>()
const emit = defineEmits<{ restored: [] }>()
const versions = ref<ProjectVersion[]>([])
const share = ref<ProjectShare>()
const publication = ref<Publication>()
const comparedVersion = ref<ProjectVersionDetail>()
const compareVersionId = ref('')
const label = ref('')
const publicationTitle = ref('')
const publicationDescription = ref('')
const publicationTags = ref('')
const finishedPhoto = ref<File>()
const busy = ref(false)
const message = ref('')
const showAllVersions = ref(false)
const visibilityChoice = ref<'private' | 'public'>('private')
let publicationFormInitialized = false
const shareLink = computed(() => share.value ? `${window.location.origin}/share/${share.value.token}` : '')
const publicationLink = computed(() => publication.value?.status === 'approved' ? `${window.location.origin}/p/${publication.value.public_token}` : '')
const visibleVersions = computed(() => showAllVersions.value ? versions.value : versions.value.slice(0, 4))
const comparison = computed(() => {
  const before = comparedVersion.value?.pattern
  const after = props.currentPattern
  if (!before || !after) return undefined
  const length = Math.max(before.cells.length, after.cells.length)
  let changed = 0
  let added = 0
  let removed = 0
  let recolored = 0
  for (let index = 0; index < length; index += 1) {
    const previous = before.cells[index] ?? null
    const current = after.cells[index] ?? null
    if (previous === current) continue
    changed += 1
    if (!previous && current) added += 1
    else if (previous && !current) removed += 1
    else recolored += 1
  }
  return {
    changed,
    added,
    removed,
    recolored,
    gridChanged: before.grid_width !== after.grid_width || before.grid_height !== after.grid_height,
  }
})

const publicationStatus = computed(() => ({ pending: '审核中', approved: '已公开', rejected: '需修改', withdrawn: '已撤回' }[publication.value?.status || 'withdrawn']))
const canSubmitPublication = computed(() => !publication.value || ['rejected', 'withdrawn'].includes(publication.value.status))
const isPublicOrPending = computed(() => publication.value?.status === 'pending' || publication.value?.status === 'approved')
const publicationDescriptionCount = computed(() => Array.from(publicationDescription.value).length)

async function refresh() {
  const [nextVersions, publications] = await Promise.all([listProjectVersions(props.projectId), listMyPublications()])
  versions.value = nextVersions
  publication.value = publications.find((item) => item.project_id === props.projectId)
  if (!publicationFormInitialized) {
    publicationTitle.value = publication.value?.title || props.projectName || ''
    const sourceDescription = publication.value ? publication.value.description : props.projectDescription
    publicationDescription.value = (sourceDescription || '').slice(0, 50)
    publicationTags.value = publication.value?.tags.join('，') || ''
    publicationFormInitialized = true
  }
  visibilityChoice.value = isPublicOrPending.value ? 'public' : 'private'
}
async function snapshot() {
  if (props.hasUnsavedChanges) { message.value = '请先点击顶部“保存变更”，再创建版本快照'; return }
  busy.value = true
  message.value = ''
  try { const version = await createProjectVersion(props.projectId, label.value.trim() || undefined); label.value = ''; versions.value.unshift(version); message.value = '已保存版本快照' } catch (error) { message.value = error instanceof Error ? error.message : '版本保存失败' } finally { busy.value = false }
}
async function compareVersion() {
  if (!compareVersionId.value) { comparedVersion.value = undefined; return }
  busy.value = true
  message.value = ''
  try { comparedVersion.value = await getProjectVersion(props.projectId, compareVersionId.value) } catch (error) { message.value = error instanceof Error ? error.message : '无法读取版本内容' } finally { busy.value = false }
}
async function restore(version: ProjectVersion) {
  if (!window.confirm(`恢复到“${version.label}”？当前未保存的编辑内容会被覆盖。`)) return
  busy.value = true
  try { await restoreProjectVersion(props.projectId, version.id); message.value = '已恢复版本'; emit('restored') } catch (error) { message.value = error instanceof Error ? error.message : '恢复失败' } finally { busy.value = false }
}
async function createShare() {
  busy.value = true
  message.value = ''
  try { share.value = await createProjectShare(props.projectId); message.value = '已创建客户确认链接' } catch (error) { message.value = error instanceof Error ? error.message : '创建分享失败' } finally { busy.value = false }
}
async function copyShare() {
  if (!shareLink.value) return
  try { await navigator.clipboard.writeText(shareLink.value); message.value = '链接已复制' } catch { message.value = '请手动复制下方链接' }
}
async function publish() {
  if (props.hasUnsavedChanges) { message.value = '请先点击顶部“保存变更”，再提交发布审核'; return }
  if (publicationDescriptionCount.value > 50) { message.value = '作品简介最多 50 个字符'; return }
  busy.value = true
  message.value = ''
  try {
    const photo = finishedPhoto.value ? await uploadImage(finishedPhoto.value) : undefined
    const tags = [...new Set(publicationTags.value.split(/[，,]/).map((tag) => tag.trim()).filter(Boolean))].slice(0, 8)
    publication.value = await submitPublication(props.projectId, {
      title: publicationTitle.value.trim() || undefined,
      description: publicationDescription.value.trim() || null,
      tags,
      finished_image_id: photo?.image_id,
    })
    message.value = '已提交平台审核，审核通过后将公开展示'
  } catch (error) { message.value = error instanceof Error ? error.message : '提交审核失败' } finally { busy.value = false }
}
async function selectVisibility(next: 'private' | 'public') {
  if (next === 'public') {
    visibilityChoice.value = 'public'
    message.value = canSubmitPublication.value ? '补充作品信息后即可提交审核；通过前不会公开。' : ''
    return
  }
  if (!isPublicOrPending.value || !publication.value) {
    visibilityChoice.value = 'private'
    message.value = '当前作品仅自己可见，不会展示在社区。'
    return
  }
  const prompt = publication.value.status === 'approved'
    ? '撤回后，公开链接和社区展示会立即失效。确定设为仅自己可见吗？'
    : '撤回后，当前审核申请会取消。确定设为仅自己可见吗？'
  if (!window.confirm(prompt)) return
  busy.value = true
  message.value = ''
  try {
    await withdrawPublication(publication.value.id)
    await refresh()
    visibilityChoice.value = 'private'
    message.value = '已设为仅自己可见，作品不会显示在社区。'
  } catch (error) { message.value = error instanceof Error ? error.message : '撤回公开失败' } finally { busy.value = false }
}
function chooseFinishedPhoto(event: Event) {
  const input = event.target as HTMLInputElement
  finishedPhoto.value = input.files?.[0]
}
async function copyPublication() {
  if (!publicationLink.value) return
  try { await navigator.clipboard.writeText(publicationLink.value); message.value = '公开作品链接已复制' } catch { message.value = '请手动复制公开链接' }
}

onMounted(() => { void refresh() })
watch(() => props.projectId, () => {
  publicationFormInitialized = false
  publicationTitle.value = ''
  publicationDescription.value = ''
  publicationTags.value = ''
  finishedPhoto.value = undefined
  void refresh()
  share.value = undefined
  publication.value = undefined
  comparedVersion.value = undefined
  compareVersionId.value = ''
  visibilityChoice.value = 'private'
})
watch(() => props.versionRefreshKey, () => { void refresh() })
</script>

<template>
  <section class="lifecycle">
    <div class="lifecycle__head"><div><span class="eyebrow">PROJECT CONTROL</span><strong>版本、确认与发布</strong></div><span>{{ versions.length }} 版</span></div>
    <div class="snapshot"><input v-model="label" maxlength="120" placeholder="版本备注（可选）"><button type="button" :disabled="busy || hasUnsavedChanges" :title="hasUnsavedChanges ? '请先保存图纸变更' : '保存当前版本快照'" @click="snapshot">保存版本</button></div>
    <p class="muted">图纸修改只在点击顶部“保存变更”时保存；重要节点可在这里手动创建版本快照。</p>
    <ul v-if="versions.length" class="versions"><li v-for="version in visibleVersions" :key="version.id"><span><b>{{ version.label }} <em v-if="version.automatic">自动</em></b><small>修订 {{ version.pattern_revision ?? '—' }} · {{ new Date(version.created_at).toLocaleString() }}</small></span><button type="button" :disabled="busy" @click="restore(version)">恢复</button></li></ul><p v-else class="muted">在重要节点保存版本，随时可恢复到当前图纸快照。</p>
    <button v-if="versions.length > 4" class="more" type="button" @click="showAllVersions = !showAllVersions">{{ showAllVersions ? '收起版本记录' : `查看全部 ${versions.length} 个版本` }}</button>
    <div v-if="versions.length" class="compare"><label>与当前图纸对比<select v-model="compareVersionId" :disabled="busy" @change="compareVersion"><option value="">选择一个历史版本</option><option v-for="version in versions" :key="version.id" :value="version.id">{{ version.label }}</option></select></label><div v-if="comparedVersion && comparison" class="compare-result"><b>{{ comparison.changed.toLocaleString() }} 格变化</b><span>{{ comparison.added }} 新增 · {{ comparison.removed }} 清除 · {{ comparison.recolored }} 换色</span><span v-if="comparison.gridChanged">画布尺寸也有变更</span></div></div>
    <div class="share"><div><b>客户确认链接</b><small>只读预览，支持确认、退回与坐标定位留言。</small></div><button type="button" :disabled="busy" @click="createShare">{{ share ? '新建链接' : '创建链接' }}</button></div>
    <template v-if="share"><input class="share-link" :value="shareLink" readonly aria-label="客户确认链接" @focus="($event.target as HTMLInputElement).select()"><button class="copy" type="button" @click="copyShare">复制确认链接</button></template>
    <section class="visibility" aria-label="作品公开设置"><div class="visibility__head"><div><span class="eyebrow">WORK VISIBILITY</span><b>作品公开设置</b></div><small>{{ visibilityChoice === 'public' ? '公开前需管理员审核' : '默认仅自己可见' }}</small></div><div class="visibility__choices" role="group" aria-label="选择作品可见性"><button type="button" :class="{ active: visibilityChoice === 'private' }" :aria-pressed="visibilityChoice === 'private'" :disabled="busy" @click="selectVisibility('private')"><span>⌁</span><b>仅自己可见</b><small>不进入社区，可继续编辑</small></button><button type="button" :class="{ active: visibilityChoice === 'public' }" :aria-pressed="visibilityChoice === 'public'" :disabled="busy" @click="selectVisibility('public')"><span>↗</span><b>公开到社区</b><small>提交审核，通过后展示</small></button></div></section>
    <template v-if="visibilityChoice === 'public'">
      <section v-if="canSubmitPublication" class="publish-details">
        <div class="publish-details__head"><b>确认社区展示信息</b><small>标题和简介可在发布前单独编辑</small></div>
        <div class="publish-fields">
          <label>作品标题<input v-model="publicationTitle" maxlength="120" placeholder="默认使用项目名称"></label>
          <label><span>作品简介 <small>{{ publicationDescriptionCount }}/50</small></span><textarea v-model="publicationDescription" maxlength="50" placeholder="用一句话介绍作品（最多 50 字）" /></label>
          <label>主题标签<input v-model="publicationTags" maxlength="200" placeholder="例如：挂件，动漫，送礼"></label>
          <label>成品实拍<input accept="image/png,image/jpeg,image/webp" type="file" @change="chooseFinishedPhoto"><small>{{ finishedPhoto?.name || '上传后会和图纸一起进入审核，不会提前公开。' }}</small></label>
        </div>
      </section>
      <p v-if="hasUnsavedChanges && canSubmitPublication" class="unsaved-hint">图纸还有未保存内容，请先点击顶部“保存变更”。</p>
      <div class="publication"><div><b>发布到作品社区</b><small v-if="publication">状态：<em :class="publication.status">{{ publicationStatus }}</em>{{ publication.review_note ? ` · ${publication.review_note}` : '' }}</small><small v-else>提交后由管理员审核，审核通过才会公开。</small></div><button type="button" :disabled="busy || !canSubmitPublication || hasUnsavedChanges" @click="publish">{{ publication?.status === 'pending' ? '审核中' : publication?.status === 'approved' ? '已公开' : '提交审核' }}</button></div>
      <template v-if="publicationLink"><input class="share-link" :value="publicationLink" readonly aria-label="公开作品链接" @focus="($event.target as HTMLInputElement).select()"><button class="copy" type="button" @click="copyPublication">复制公开链接</button></template>
    </template>
    <p v-if="message" class="message">{{ message }}</p>
  </section>
</template>

<style scoped>
.lifecycle { display: grid; gap: 10px; padding: 18px; border-top: 1px solid #e7e4ef; background: #fff; }.lifecycle__head { display: flex; align-items: end; justify-content: space-between; gap: 8px; }.lifecycle__head > div { display: grid; gap: 3px; }.eyebrow { color: #7359e6; font-size: 9px; font-weight: 800; letter-spacing: .13em; }.lifecycle__head strong { color: #1d2742; font-size: 15px; }.lifecycle__head > span { color: #8c94a6; font-family: var(--font-mono); font-size: 9px; }.snapshot { display: grid; grid-template-columns: 1fr auto; gap: 6px; }.snapshot input, .share-link, .compare select, .publish-fields input, .publish-fields textarea { min-width: 0; border: 1px solid #dfdce9; border-radius: 7px; padding: 6px 7px; color: #4d5770; background: #fbfaff; font-size: 10px; }.snapshot button, .share button, .publication button, .versions button, .copy, .more { border: 1px solid #dfd9f2; border-radius: 7px; padding: 5px 7px; background: #f6f3ff; color: #6150bb; font-size: 9px; font-weight: 800; }.versions { display: grid; gap: 5px; margin: 0; padding: 0; list-style: none; }.versions li { display: flex; align-items: center; justify-content: space-between; gap: 6px; border-bottom: 1px solid #f0eef5; padding-bottom: 5px; }.versions span { display: grid; min-width: 0; gap: 2px; }.versions b { overflow: hidden; color: #49536c; font-size: 10px; text-overflow: ellipsis; white-space: nowrap; }.versions b em { margin-left: 3px; border-radius: 99px; padding: 1px 4px; color: #7257cd; background: #ede9ff; font-size: 8px; font-style: normal; }.versions small, .muted, .message { color: #8991a4; font-family: var(--font-mono); font-size: 8px; }.muted, .message { margin: 0; line-height: 1.5; }.more { justify-self: start; border-style: dashed; background: #fff; }.compare { display: grid; gap: 5px; border: 1px solid #e8e4f3; border-radius: 9px; padding: 8px; background: #fbfaff; }.compare label { display: grid; gap: 4px; color: #68728a; font-size: 9px; font-weight: 800; }.compare-result { display: grid; gap: 2px; border-top: 1px solid #ebe8f3; padding-top: 6px; color: #738097; font-family: var(--font-mono); font-size: 8px; line-height: 1.45; }.compare-result b { color: #4e409d; font-size: 10px; }.share, .publication { display: flex; align-items: center; justify-content: space-between; gap: 7px; margin-top: 2px; border-top: 1px solid #f0eef5; padding-top: 10px; }.share div, .publication div { display: grid; gap: 2px; }.share b, .publication b { color: #4a536c; font-size: 10px; }.share small, .publication small { color: #8991a4; font-size: 8px; }.publication em { font-style: normal; font-weight: 800; }.publication em.pending { color: #a97834; }.publication em.approved { color: #3b9b75; }.publication em.rejected { color: #bd5d64; }.visibility { display: grid; gap: 7px; margin-top: 2px; border-top: 1px solid #f0eef5; padding-top: 10px; }.visibility__head { display: flex; align-items: end; justify-content: space-between; gap: 8px; }.visibility__head > div { display: grid; gap: 2px; }.visibility__head b { color: #3d4963; font-size: 11px; }.visibility__head small { color: #8a94a6; font-size: 8px; }.visibility__choices { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }.visibility__choices button { display: grid; grid-template-columns: auto 1fr; gap: 1px 6px; min-width: 0; border: 1px solid #e4e0ec; border-radius: 9px; padding: 8px; background: #fcfbff; color: #657087; text-align: left; transition: border-color .16s, background .16s, box-shadow .16s; }.visibility__choices button:hover { border-color: #bcb1eb; background: #f8f6ff; }.visibility__choices button.active { border-color: #7862d9; background: linear-gradient(135deg, #f1eeff, #f8fbff); box-shadow: inset 0 0 0 1px rgb(104 84 232 / 8%); }.visibility__choices button > span { grid-row: span 2; display: grid; width: 21px; height: 21px; place-items: center; border-radius: 7px; color: #7862d9; background: #ede9ff; font-size: 11px; }.visibility__choices button:first-child.active > span { color: #35846a; background: #eaf8f1; }.visibility__choices b { overflow: hidden; color: #4c5670; font-size: 9px; text-overflow: ellipsis; white-space: nowrap; }.visibility__choices small { overflow: hidden; color: #8a94a6; font-size: 8px; text-overflow: ellipsis; white-space: nowrap; }.visibility__choices button:disabled { cursor: not-allowed; opacity: .55; }.publish-details { border: 1px solid #e4e0ee; border-radius: 8px; background: #fcfbff; }.publish-details summary { cursor: pointer; padding: 7px 8px; color: #5c50a5; font-size: 9px; font-weight: 800; }.publish-details summary small { margin-left: 3px; color: #9299aa; font-size: 8px; font-weight: 500; }.publish-fields { display: grid; gap: 6px; padding: 0 8px 8px; }.publish-fields label { display: grid; gap: 3px; color: #737d94; font-size: 8px; font-weight: 800; }.publish-fields textarea { min-height: 56px; resize: vertical; }.publish-fields input[type='file'] { padding: 4px; background: #fff; font-size: 8px; }.publish-fields small { color: #959cad; font-size: 8px; font-weight: 500; }.share-link { width: 100%; font-family: var(--font-mono); font-size: 8px; }.copy { justify-self: start; }.message { color: #5d9a7e; }
.publish-details { overflow: hidden; }
.publish-details__head { display: grid; gap: 2px; padding: 8px; border-bottom: 1px solid #ece8f4; background: #f8f6ff; }
.publish-details__head b { color: #5c50a5; font-size: 9px; }
.publish-details__head small { color: #9299aa; font-size: 8px; }
.publish-fields { gap: 7px; padding-top: 8px; }
.publish-fields label > span { display: flex; align-items: center; justify-content: space-between; gap: 6px; }
.unsaved-hint { margin: 0; border-radius: 7px; padding: 6px 7px; color: #9a6429; background: #fff6e7; font-size: 8px; line-height: 1.5; }
</style>
