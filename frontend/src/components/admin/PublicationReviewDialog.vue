<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { mediaUrl } from '@/api/http'
import type { AdminPublicationDetail, PublicationReviewCheck } from '@/types/publication'

const props = defineProps<{
  detail?: AdminPublicationDetail
  loading: boolean
  loadError: string
  submitError: string
  working: boolean
  reviewMode: boolean
}>()

const emit = defineEmits<{
  close: []
  retry: []
  decide: [decision: 'approved' | 'rejected', note: string | undefined, checks: PublicationReviewCheck[]]
}>()

const note = ref('')
const formError = ref('')
const selectedChecks = ref<PublicationReviewCheck[]>([])
const expandedImage = ref<{ src: string; label: string } | null>(null)
const pattern = computed(() => props.detail?.pattern ?? null)
const statistics = computed(() => pattern.value?.statistics ?? null)
const colorReport = computed(() => pattern.value?.color_report ?? null)
const requiredChecks: Array<{ value: PublicationReviewCheck; label: string; help: string }> = [
  { value: 'pattern_content', label: '图纸内容已核对', help: '已查看完整图纸、原始参考图和成品实拍，未发现违法违规内容。' },
  { value: 'metadata', label: '发布文案已核对', help: '标题、简介与标签无广告引流、联系方式或攻击性表达。' },
  { value: 'rights_privacy', label: '权利与隐私已核对', help: '未发现明显的侵权、他人隐私或未成年人安全风险。' },
]
const allChecksComplete = computed(() => requiredChecks.every((item) => selectedChecks.value.includes(item.value)))
const statusLabel = computed(() => ({ pending: '待审核', approved: '已公开', rejected: '已驳回', withdrawn: '已下架' }[props.detail?.publication.status ?? 'pending']))

let previousBodyOverflow = ''

watch(
  () => props.detail?.publication.id,
  () => {
    note.value = props.detail?.publication.review_note ?? ''
    selectedChecks.value = [...(props.detail?.publication.review_checks ?? [])]
    formError.value = ''
    expandedImage.value = null
  },
  { immediate: true },
)

function close() {
  if (!props.working) emit('close')
}

function showImage(src: string | null | undefined, label: string) {
  if (src) expandedImage.value = { src: mediaUrl(src), label }
}

function submit(decision: 'approved' | 'rejected') {
  formError.value = ''
  const normalizedNote = note.value.trim()
  if (decision === 'rejected' && !normalizedNote) {
    formError.value = '请填写具体驳回原因，便于创作者修改后重新提交。'
    return
  }
  if (decision === 'approved' && !props.detail?.review_readiness.can_approve) {
    formError.value = '当前作品存在阻断项，不能通过审核。'
    return
  }
  if (decision === 'approved' && !allChecksComplete.value) {
    formError.value = '通过前请完成全部合规检查项。'
    return
  }
  emit('decide', decision, normalizedNote || undefined, [...selectedChecks.value])
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key !== 'Escape') return
  if (expandedImage.value) {
    expandedImage.value = null
    return
  }
  close()
}

onMounted(() => {
  previousBodyOverflow = document.body.style.overflow
  document.body.style.overflow = 'hidden'
  window.addEventListener('keydown', handleKeydown)
})

onBeforeUnmount(() => {
  document.body.style.overflow = previousBodyOverflow
  window.removeEventListener('keydown', handleKeydown)
})
</script>

<template>
  <Teleport to="body">
    <div class="review-overlay" role="presentation" @click.self="close">
      <section class="review-dialog" role="dialog" aria-modal="true" aria-labelledby="review-dialog-title">
        <header class="dialog-head">
          <div>
            <span class="eyebrow">PUBLICATION REVIEW</span>
            <h2 id="review-dialog-title">{{ reviewMode ? '作品详情与合规审核' : '已公开作品详情' }}</h2>
          </div>
          <div class="head-actions">
            <span v-if="detail" class="status-pill" :class="detail.publication.status">{{ statusLabel }}</span>
            <button type="button" :disabled="working" aria-label="关闭审核详情" @click="close">×</button>
          </div>
        </header>

        <div v-if="loading" class="dialog-state"><span class="spinner" />正在载入图纸与审核材料…</div>
        <div v-else-if="loadError" class="dialog-state dialog-state--error"><b>详情加载失败</b><p>{{ loadError }}</p><button type="button" @click="emit('retry')">重新加载</button></div>

        <div v-else-if="detail" class="dialog-body">
          <main class="evidence-column">
            <section class="publication-copy">
              <div class="copy-meta"><span>{{ detail.publication.author.display_name }}</span><time :datetime="detail.publication.submitted_at">{{ new Date(detail.publication.submitted_at).toLocaleString() }}</time></div>
              <h3>{{ detail.publication.title }}</h3>
              <p>{{ detail.publication.description || '创作者未填写作品简介。' }}</p>
              <div v-if="detail.publication.tags.length" class="tags"><span v-for="tag in detail.publication.tags" :key="tag">{{ tag }}</span></div>
            </section>

            <section class="evidence-section">
              <div class="section-head"><div><span class="eyebrow">VISUAL EVIDENCE</span><h4>图纸与作品材料</h4></div><small>点击图片可全屏查看</small></div>
              <figure v-if="pattern?.preview_url" class="pattern-preview">
                <button type="button" @click="showImage(pattern.preview_url, '完整图纸预览')"><img :src="mediaUrl(pattern.preview_url)" :alt="`${detail.publication.title}完整图纸预览`"></button>
                <figcaption><b>完整图纸</b><span>{{ pattern.grid_width }} × {{ pattern.grid_height }} 格 · 修订 {{ pattern.revision }}</span></figcaption>
              </figure>
              <div v-else class="missing-evidence">当前无法显示图纸预览，不应通过审核。</div>
              <div v-if="pattern?.source_image_preview_url || detail.finished_photo_preview_url" class="supporting-media">
                <figure v-if="pattern?.source_image_preview_url"><button type="button" @click="showImage(pattern.source_image_preview_url, '原始参考图')"><img :src="mediaUrl(pattern.source_image_preview_url)" alt="创作原始参考图"></button><figcaption><b>原始参考图</b><span>用于核对图案来源与内容</span></figcaption></figure>
                <figure v-if="detail.finished_photo_preview_url"><button type="button" @click="showImage(detail.finished_photo_preview_url, '成品实拍')"><img :src="mediaUrl(detail.finished_photo_preview_url)" alt="创作者上传的成品实拍"></button><figcaption><b>成品实拍</b><span>创作者提交的可选材料</span></figcaption></figure>
              </div>
            </section>

            <section v-if="statistics" class="evidence-section">
              <div class="section-head"><div><span class="eyebrow">PATTERN DATA</span><h4>图纸与材料数据</h4></div><small>{{ pattern?.palette_brand || pattern?.palette_name }} · {{ pattern?.palette_id }}</small></div>
              <dl class="stats-grid">
                <div><dt>网格尺寸</dt><dd>{{ statistics.grid_width }} × {{ statistics.grid_height }}</dd></div>
                <div><dt>拼豆总数</dt><dd>{{ statistics.total_beads.toLocaleString() }} 颗</dd></div>
                <div><dt>使用颜色</dt><dd>{{ statistics.used_color_count }} 色</dd></div>
                <div><dt>成品尺寸</dt><dd>{{ statistics.physical_width_mm }} × {{ statistics.physical_height_mm }} mm</dd></div>
              </dl>
              <div v-if="colorReport" class="quality-card"><div><span>色差质量</span><b>{{ colorReport.quality_label }}</b></div><dl><div><dt>平均 ΔE00</dt><dd>{{ colorReport.average_delta_e_00 }}</dd></div><div><dt>95% ΔE00</dt><dd>{{ colorReport.p95_delta_e_00 }}</dd></div><div><dt>最大 ΔE00</dt><dd>{{ colorReport.maximum_delta_e_00 }}</dd></div></dl><p>{{ colorReport.quality_note }}</p></div>
              <details v-if="statistics.colors.length" class="color-details">
                <summary>查看全部 {{ statistics.colors.length }} 种色号与用量</summary>
                <div class="color-table-wrap"><table><thead><tr><th>色号</th><th>名称</th><th>数量</th><th>含损耗</th></tr></thead><tbody><tr v-for="color in statistics.colors" :key="color.color_code"><td><i :style="{ background: color.hex }" />{{ color.color_code }}</td><td>{{ color.color_name }}</td><td>{{ color.count.toLocaleString() }}</td><td>{{ color.count_with_waste.toLocaleString() }}</td></tr></tbody></table></div>
              </details>
            </section>

            <section class="audit-ids"><span>项目 {{ detail.publication.project_id }}</span><span>图纸 {{ detail.publication.pattern_id }}</span><span v-if="detail.project">项目名：{{ detail.project.name }}</span></section>
          </main>

          <aside class="decision-column">
            <section class="readiness" :class="{ blocked: !detail.review_readiness.can_approve }">
              <div class="readiness-head"><span>{{ detail.review_readiness.can_approve ? '✓' : '!' }}</span><div><b>{{ detail.review_readiness.can_approve ? reviewMode ? '审核材料可用' : '审核记录与材料可用' : '存在阻断问题' }}</b><small>{{ detail.review_readiness.can_approve ? reviewMode ? '请继续人工合规判断' : '可查看原审核勾选与备注' : reviewMode ? '解决前不能通过作品' : '公开作品的当前材料已异常' }}</small></div></div>
              <ul v-if="detail.review_readiness.blocking_issues.length" class="issue-list blocking"><li v-for="issue in detail.review_readiness.blocking_issues" :key="issue">{{ issue }}</li></ul>
              <ul v-if="detail.review_readiness.warnings.length" class="issue-list warnings"><li v-for="warning in detail.review_readiness.warnings" :key="warning">{{ warning }}</li></ul>
            </section>

            <section class="checklist">
              <div><span class="eyebrow">COMPLIANCE CHECKLIST</span><h4>{{ reviewMode ? '合规审核确认' : '已记录的审核项' }}</h4><p>{{ reviewMode ? '请在查看左侧全部材料后逐项确认。' : '以下内容由原审核管理员确认。' }}</p></div>
              <label v-for="item in requiredChecks" :key="item.value" :class="{ checked: selectedChecks.includes(item.value) }"><input v-model="selectedChecks" type="checkbox" :value="item.value" :disabled="!reviewMode || working"><span><b>{{ item.label }}</b><small>{{ item.help }}</small></span></label>
            </section>

            <section v-if="reviewMode" class="decision-form">
              <label for="review-note">审核意见 <span>{{ note.length }}/2000</span></label>
              <textarea id="review-note" v-model="note" maxlength="2000" :disabled="working" placeholder="驳回时必填；通过时可记录补充说明。" />
              <p v-if="formError || submitError" class="form-error" role="alert">{{ formError || submitError }}</p>
              <div class="decision-actions">
                <button class="reject" type="button" :disabled="working" @click="submit('rejected')">{{ working ? '处理中…' : '驳回并告知原因' }}</button>
                <button class="approve" type="button" :disabled="working || !detail.review_readiness.can_approve || !allChecksComplete" @click="submit('approved')">{{ working ? '处理中…' : '通过并公开' }}</button>
              </div>
              <small class="decision-hint">审核结果、意见与合规确认项将一并留存。</small>
            </section>
            <section v-else class="published-actions">
              <a :href="`/p/${detail.publication.public_token}`" target="_blank" rel="noopener">打开公开作品页 ↗</a>
              <div v-if="detail.publication.reviewer" class="review-audit"><b>{{ detail.publication.reviewer.display_name }}</b><span>于 {{ detail.publication.reviewed_at ? new Date(detail.publication.reviewed_at).toLocaleString() : '未记录时间' }} 完成审核</span></div>
              <p v-if="detail.publication.review_note">审核备注：{{ detail.publication.review_note }}</p>
            </section>
          </aside>
        </div>
      </section>
    </div>
  </Teleport>

  <Teleport to="body">
    <div v-if="expandedImage" class="image-lightbox" role="dialog" aria-modal="true" :aria-label="expandedImage.label" @click.self="expandedImage = null">
      <button type="button" aria-label="关闭大图" @click="expandedImage = null">×</button>
      <img :src="expandedImage.src" :alt="expandedImage.label">
      <p>{{ expandedImage.label }}</p>
    </div>
  </Teleport>
</template>

<style scoped>
.review-overlay {
  position: fixed;
  z-index: 1000;
  inset: 0;
  display: grid;
  overflow: auto;
  padding: 22px;
  background: rgb(22 27 45 / 68%);
  backdrop-filter: blur(8px);
  place-items: center;
}

.review-dialog {
  display: flex;
  width: min(1180px, 100%);
  max-height: calc(100vh - 44px);
  overflow: hidden;
  border: 1px solid rgb(255 255 255 / 60%);
  border-radius: 22px;
  background: #f8f8fc;
  box-shadow: 0 30px 90px rgb(17 22 42 / 38%);
  flex-direction: column;
}

.dialog-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 18px 22px;
  border-bottom: 1px solid #e4e3ec;
  background: rgb(255 255 255 / 94%);
}

.dialog-head h2 {
  margin: 4px 0 0;
  color: #202c47;
  font-size: 20px;
}

.eyebrow {
  color: #715bd3;
  font-family: var(--font-mono);
  font-size: 9px;
  font-weight: 800;
  letter-spacing: .13em;
}

.head-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.head-actions button {
  display: grid;
  width: 34px;
  height: 34px;
  border: 1px solid #dedce7;
  border-radius: 10px;
  color: #6e778a;
  background: #fff;
  font-size: 22px;
  cursor: pointer;
  place-items: center;
}

.status-pill {
  border-radius: 999px;
  padding: 5px 9px;
  font-size: 10px;
  font-weight: 800;
}

.status-pill.pending { color: #9a6d20; background: #fff5dc; }
.status-pill.approved { color: #277d61; background: #eaf9f2; }
.status-pill.rejected,
.status-pill.withdrawn { color: #a14d58; background: #fff0f2; }

.dialog-state {
  display: grid;
  min-height: 420px;
  color: #6e788f;
  font-size: 13px;
  place-content: center;
  justify-items: center;
  gap: 12px;
}

.spinner {
  width: 28px;
  height: 28px;
  border: 3px solid #ddd8f4;
  border-top-color: #7059dc;
  border-radius: 50%;
  animation: spin .8s linear infinite;
}

.dialog-state--error b { color: #a04452; font-size: 17px; }
.dialog-state--error p { max-width: 520px; margin: 0; text-align: center; }
.dialog-state--error button {
  border: 0;
  border-radius: 8px;
  padding: 8px 11px;
  color: #fff;
  background: #6752c7;
  font: inherit;
  font-weight: 800;
}

.dialog-body {
  display: grid;
  min-height: 0;
  overflow: auto;
  grid-template-columns: minmax(0, 1.55fr) minmax(310px, .9fr);
}

.evidence-column {
  display: grid;
  min-width: 0;
  align-content: start;
  gap: 14px;
  padding: 20px;
}

.publication-copy,
.evidence-section {
  border: 1px solid #e3e1eb;
  border-radius: 15px;
  padding: 16px;
  background: #fff;
}

.copy-meta {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 5px 15px;
  color: #8b93a5;
  font-family: var(--font-mono);
  font-size: 9px;
}

.copy-meta span { color: #705ac7; font-weight: 800; }
.publication-copy h3 { margin: 8px 0 5px; color: #222e49; font-size: 22px; }
.publication-copy > p {
  margin: 0;
  color: #69748a;
  font-size: 12px;
  line-height: 1.7;
  white-space: pre-wrap;
}

.tags {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  margin-top: 10px;
}

.tags span {
  border-radius: 999px;
  padding: 4px 7px;
  color: #675c94;
  background: #f0eef8;
  font-size: 9px;
}

.section-head {
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.section-head h4 { margin: 3px 0 0; color: #303b55; font-size: 14px; }
.section-head small {
  color: #9299aa;
  font-family: var(--font-mono);
  font-size: 8px;
  text-align: right;
}

.pattern-preview {
  margin: 0;
  overflow: hidden;
  border: 1px solid #e2e0e8;
  border-radius: 13px;
  background: #f5f5f8;
}

.pattern-preview button {
  display: grid;
  width: 100%;
  min-height: 330px;
  border: 0;
  padding: 16px;
  background: #f6f6f9;
  cursor: zoom-in;
  place-items: center;
}

.pattern-preview img {
  display: block;
  max-width: 100%;
  height: min(48vh, 500px);
  object-fit: contain;
  image-rendering: pixelated;
}

.pattern-preview figcaption,
.supporting-media figcaption {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 10px 12px;
  border-top: 1px solid #e6e4eb;
  color: #7d8698;
  background: #fff;
  font-size: 9px;
}

.pattern-preview figcaption b,
.supporting-media figcaption b { color: #404b63; font-size: 10px; }

.missing-evidence {
  border: 1px dashed #dca8ad;
  border-radius: 12px;
  padding: 34px 18px;
  color: #a24854;
  background: #fff4f5;
  font-size: 12px;
  text-align: center;
}

.supporting-media {
  display: grid;
  gap: 10px;
  margin-top: 10px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.supporting-media figure {
  min-width: 0;
  margin: 0;
  overflow: hidden;
  border: 1px solid #e2e0e8;
  border-radius: 12px;
  background: #f5f5f8;
}

.supporting-media button {
  display: grid;
  width: 100%;
  height: 180px;
  border: 0;
  padding: 8px;
  background: #f5f5f8;
  cursor: zoom-in;
  place-items: center;
}

.supporting-media img {
  display: block;
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
}

.supporting-media figcaption { align-items: start; flex-direction: column; }

.stats-grid {
  display: grid;
  gap: 7px;
  margin: 0;
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.stats-grid div {
  min-width: 0;
  border: 1px solid #ebe9f0;
  border-radius: 10px;
  padding: 9px;
  background: #faf9fc;
}

.stats-grid dt { color: #9198a9; font-size: 8px; }
.stats-grid dd {
  overflow: hidden;
  margin: 3px 0 0;
  color: #333e57;
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 800;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.quality-card {
  display: grid;
  gap: 8px;
  margin-top: 10px;
  border-left: 3px solid #7a66d6;
  border-radius: 8px;
  padding: 10px;
  background: #f7f5ff;
}

.quality-card > div {
  display: flex;
  justify-content: space-between;
  color: #687288;
  font-size: 10px;
}

.quality-card > div b { color: #5f4fb3; }
.quality-card dl {
  display: grid;
  gap: 5px;
  margin: 0;
  grid-template-columns: repeat(3, 1fr);
}

.quality-card dl div {
  border-radius: 7px;
  padding: 5px;
  background: rgb(255 255 255 / 70%);
  text-align: center;
}

.quality-card dt { color: #9299aa; font-size: 8px; }
.quality-card dd {
  margin: 2px 0 0;
  color: #414b64;
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 800;
}

.quality-card p { margin: 0; color: #7b8498; font-size: 9px; line-height: 1.5; }

.color-details {
  margin-top: 10px;
  border: 1px solid #e7e4ee;
  border-radius: 10px;
}

.color-details summary {
  cursor: pointer;
  padding: 10px;
  color: #6253aa;
  font-size: 10px;
  font-weight: 800;
}

.color-table-wrap {
  max-height: 260px;
  overflow: auto;
  border-top: 1px solid #e9e7ef;
}

.color-table-wrap table { width: 100%; border-collapse: collapse; }
.color-table-wrap th,
.color-table-wrap td {
  padding: 7px 9px;
  border-bottom: 1px solid #f0eef4;
  color: #687287;
  font-size: 9px;
  text-align: left;
}

.color-table-wrap th {
  position: sticky;
  z-index: 1;
  top: 0;
  color: #8d95a6;
  background: #faf9fc;
}

.color-table-wrap td:first-child {
  color: #3d4860;
  font-family: var(--font-mono);
  font-weight: 800;
}

.color-table-wrap i {
  display: inline-block;
  width: 11px;
  height: 11px;
  margin-right: 6px;
  border: 1px solid rgb(30 40 60 / 15%);
  border-radius: 50%;
  vertical-align: -2px;
}

.audit-ids {
  display: flex;
  flex-wrap: wrap;
  gap: 5px 12px;
  padding: 0 4px;
  color: #9aa1b1;
  font-family: var(--font-mono);
  font-size: 8px;
}

.decision-column {
  display: grid;
  min-width: 0;
  align-content: start;
  gap: 12px;
  padding: 20px;
  border-left: 1px solid #e2e0e9;
  background: #f4f3f8;
}

.readiness,
.checklist,
.decision-form,
.published-actions {
  border: 1px solid #e1dfeb;
  border-radius: 14px;
  padding: 14px;
  background: #fff;
}

.readiness { border-color: #cce8dc; background: #f4fbf8; }
.readiness.blocked { border-color: #edc5c9; background: #fff5f6; }
.readiness-head { display: flex; align-items: center; gap: 10px; }
.readiness-head > span {
  display: grid;
  width: 30px;
  height: 30px;
  flex: 0 0 auto;
  border-radius: 9px;
  color: #258164;
  background: #dff5eb;
  font-size: 15px;
  font-weight: 900;
  place-items: center;
}

.blocked .readiness-head > span { color: #a2424e; background: #f9dfe2; }
.readiness-head div { display: grid; gap: 2px; }
.readiness-head b { color: #345547; font-size: 11px; }
.blocked .readiness-head b { color: #86434b; }
.readiness-head small { color: #809489; font-size: 8px; }

.issue-list {
  display: grid;
  gap: 5px;
  margin: 10px 0 0;
  padding: 9px 9px 9px 25px;
  border-radius: 8px;
  font-size: 9px;
  line-height: 1.45;
}

.issue-list.blocking { color: #9d4752; background: #fff; }
.issue-list.warnings { color: #8b6c33; background: #fff9e9; }
.checklist > div h4 { margin: 4px 0; color: #303b55; font-size: 14px; }
.checklist > div p { margin: 0 0 11px; color: #7b8599; font-size: 9px; line-height: 1.5; }
.checklist > label {
  display: flex;
  gap: 8px;
  margin-top: 7px;
  border: 1px solid #e6e3ed;
  border-radius: 10px;
  padding: 9px;
  background: #fbfafd;
  cursor: pointer;
}

.checklist > label.checked { border-color: #bcded0; background: #f2fbf7; }
.checklist input { margin: 2px 0 0; accent-color: #3b9a77; }
.checklist label span { display: grid; gap: 3px; }
.checklist label b { color: #505a70; font-size: 10px; }
.checklist label small { color: #8a92a3; font-size: 8px; line-height: 1.45; }

.decision-form { display: grid; gap: 8px; }
.decision-form > label {
  display: flex;
  justify-content: space-between;
  color: #535e75;
  font-size: 10px;
  font-weight: 800;
}

.decision-form > label span {
  color: #a0a6b4;
  font-family: var(--font-mono);
  font-size: 8px;
  font-weight: 500;
}

.decision-form textarea {
  min-height: 95px;
  border: 1px solid #dad6e6;
  border-radius: 9px;
  outline: 0;
  padding: 9px;
  color: #3e485e;
  background: #fbfaff;
  font: inherit;
  font-size: 10px;
  line-height: 1.55;
  resize: vertical;
}

.decision-form textarea:focus {
  border-color: #8d79df;
  box-shadow: 0 0 0 3px rgb(112 88 218 / 10%);
}

.form-error { margin: 0; color: #ad4451; font-size: 9px; line-height: 1.45; }
.decision-actions {
  display: grid;
  gap: 7px;
  grid-template-columns: 1fr 1.05fr;
}

.decision-actions button {
  border-radius: 9px;
  padding: 10px 8px;
  font: inherit;
  font-size: 9px;
  font-weight: 800;
  cursor: pointer;
}

.decision-actions .reject { border: 1px solid #deb7bc; color: #a34853; background: #fff5f6; }
.decision-actions .approve { border: 1px solid #5c49ba; color: #fff; background: #624fc4; }
.decision-actions button:disabled,
.head-actions button:disabled { cursor: not-allowed; opacity: .5; }
.decision-hint { color: #9299aa; font-size: 8px; line-height: 1.45; }

.published-actions { display: grid; gap: 8px; }
.published-actions a {
  border-radius: 9px;
  padding: 10px;
  color: #fff;
  background: #6250c2;
  font-size: 10px;
  font-weight: 800;
  text-align: center;
  text-decoration: none;
}

.published-actions p { margin: 0; color: #7d8699; font-size: 9px; line-height: 1.5; }
.review-audit {
  display: grid;
  gap: 2px;
  border-left: 2px solid #8b78df;
  padding: 5px 0 5px 8px;
  color: #7b8497;
  font-size: 8px;
}

.review-audit b { color: #5547a4; font-size: 10px; }

.image-lightbox {
  position: fixed;
  z-index: 1100;
  inset: 0;
  display: grid;
  padding: 50px 24px 24px;
  background: rgb(12 15 25 / 92%);
  place-items: center;
}

.image-lightbox > button {
  position: absolute;
  top: 16px;
  right: 20px;
  width: 36px;
  height: 36px;
  border: 1px solid rgb(255 255 255 / 28%);
  border-radius: 10px;
  color: #fff;
  background: rgb(255 255 255 / 10%);
  font-size: 23px;
}

.image-lightbox img {
  max-width: 96vw;
  max-height: calc(100vh - 100px);
  object-fit: contain;
  image-rendering: auto;
}

.image-lightbox p {
  position: absolute;
  bottom: 12px;
  margin: 0;
  color: #fff;
  font-size: 11px;
}

.image-lightbox img[alt*='图纸'] { image-rendering: pixelated; }

@keyframes spin { to { transform: rotate(360deg); } }

@media (max-width: 900px) {
  .review-overlay { padding: 10px; place-items: start center; }
  .review-dialog { max-height: calc(100vh - 20px); border-radius: 16px; }
  .dialog-body { grid-template-columns: 1fr; }
  .decision-column { border-top: 1px solid #e2e0e9; border-left: 0; }
  .pattern-preview button { min-height: 260px; }
  .stats-grid { grid-template-columns: repeat(2, 1fr); }
}

@media (max-width: 560px) {
  .review-overlay { padding: 0; }
  .review-dialog {
    width: 100%;
    min-height: 100vh;
    max-height: 100vh;
    border-radius: 0;
  }
  .dialog-head { padding: 14px; }
  .dialog-head h2 { font-size: 16px; }
  .status-pill { display: none; }
  .evidence-column,
  .decision-column { padding: 12px; }
  .publication-copy,
  .evidence-section { padding: 12px; }
  .pattern-preview button { min-height: 210px; padding: 8px; }
  .supporting-media { grid-template-columns: 1fr; }
  .supporting-media button { height: 210px; }
  .decision-actions { grid-template-columns: 1fr; }
}
</style>
