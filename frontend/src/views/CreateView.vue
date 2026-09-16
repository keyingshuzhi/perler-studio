<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import { createBlankPattern, createTemplatePattern, createTextPattern } from '@/api/patterns'
import { getDesignTemplates } from '@/api/presets'
import { useAppStore } from '@/stores/app'
import { usePaletteStore } from '@/stores/palette'
import { useProjectStore } from '@/stores/project'
import type { DesignTemplate } from '@/types/design'
import { colorsForTheme, creativeThemes } from '@/utils/theme-palettes'

const router = useRouter()
const app = useAppStore()
const palettes = usePaletteStore()
const projects = useProjectStore()
const mode = ref<'blank' | 'template' | 'text'>('blank')
const templates = ref<DesignTemplate[]>([])
const selectedTemplate = ref('heart-charm')
const selectedTheme = ref<'all' | 'skin' | 'anime' | 'retro' | 'mosaic' | 'morandi'>('all')
const creating = ref(false)
const form = reactive({
  name: '未命名创作',
  width: 32,
  height: 32,
  text: 'HELLO',
  textStyle: 'keychain' as 'keychain' | 'nameplate',
  foreground: '',
  accent: '',
  beadSize: 5,
  wasteRate: 0.05,
})
const availableColors = computed(() => palettes.current?.colors.filter((color) => color.available) || [])
const creationColors = computed(() => colorsForTheme(selectedTheme.value, palettes.current?.colors || []))
const selectedTemplateInfo = computed(() => templates.value.find((item) => item.id === selectedTemplate.value))

function presetName() {
  if (mode.value === 'blank') return `${form.width} × ${form.height} 空白图纸`
  if (mode.value === 'template') return selectedTemplateInfo.value?.name_zh || '模板图纸'
  return `${form.text.toUpperCase()} ${form.textStyle === 'keychain' ? '挂件' : '字牌'}`
}

function applyTheme(themeId: typeof selectedTheme.value) {
  selectedTheme.value = themeId
  const colors = colorsForTheme(themeId, palettes.current?.colors || [])
  if (!colors.length) return
  form.foreground = colors[0].code
  form.accent = colors.find((color) => color.code !== form.foreground)?.code || form.foreground
}

async function create() {
  if (!palettes.current) return
  creating.value = true
  try {
    const common = { palette_id: palettes.current.id, bead_size_mm: form.beadSize, waste_rate: form.wasteRate }
    const pattern = mode.value === 'blank'
      ? await createBlankPattern({ ...common, grid_width: form.width, grid_height: form.height })
      : mode.value === 'template'
        ? await createTemplatePattern({ ...common, template_id: selectedTemplate.value, foreground_code: form.foreground || undefined, accent_code: form.accent || undefined })
        : await createTextPattern({ ...common, text: form.text, style: form.textStyle, foreground_code: form.foreground || undefined, accent_code: form.accent || undefined })
    const project = await projects.create(form.name.trim() || presetName(), pattern.id)
    app.showNotice('创作已建立，开始逐格调整吧')
    await router.push(`/editor/${project.id}`)
  } catch (error) { app.showError(error) } finally { creating.value = false }
}

onMounted(async () => {
  try {
    const [, items] = await Promise.all([palettes.load(), getDesignTemplates()])
    templates.value = items
    form.foreground = availableColors.value.find((color) => color.hex.toLowerCase() === '#242628')?.code || availableColors.value[0]?.code || ''
    form.accent = availableColors.value.find((color) => color.hex.toLowerCase() === '#fd543d')?.code || form.foreground
  } catch (error) { app.showError(error) }
})
</script>

<template>
  <main class="create-page">
    <header class="heading"><div><p class="eyebrow">DESIGN STUDIO</p><h1>从空白格，开始创作。</h1><p>不必先准备图片。直接绘制像素画、从模板开始，或制作名字挂件和字牌。</p></div><div class="heading-actions"><RouterLink class="button button--quiet" to="/templates">社区模板</RouterLink><RouterLink class="button button--quiet" to="/convert">从图片转换</RouterLink></div></header>
    <section class="studio card">
      <nav class="modes" aria-label="创作方式"><button type="button" :class="{ active: mode === 'blank' }" @click="mode = 'blank'"><span>01</span>空白像素画</button><button type="button" :class="{ active: mode === 'template' }" @click="mode = 'template'"><span>02</span>模板库</button><button type="button" :class="{ active: mode === 'text' }" @click="mode = 'text'"><span>03</span>文字与挂件</button></nav>
      <div class="studio__body">
        <section class="settings">
          <template v-if="mode === 'blank'"><div class="section-heading"><span>01</span><div><h2>空白画布</h2><p>先设定成品网格，随后在专业编辑器中逐格设计。</p></div></div><div class="fields"><label class="field">宽度<input v-model.number="form.width" type="number" min="4" max="500"></label><label class="field">高度<input v-model.number="form.height" type="number" min="4" max="500"></label></div><div class="quick-sizes"><button v-for="size in [16, 29, 48, 64]" :key="size" type="button" @click="form.width = size; form.height = size">{{ size }} × {{ size }}</button></div></template>
          <template v-else-if="mode === 'template'"><div class="section-heading"><span>02</span><div><h2>常用模板</h2><p>选一个基础形状，再按你的色卡和库存进行精修。</p></div></div><div class="template-grid"><button v-for="item in templates" :key="item.id" type="button" class="template" :class="{ active: selectedTemplate === item.id }" @click="selectedTemplate = item.id"><span class="template__preview" :style="{ '--columns': item.grid_width }"><i v-for="(cell, index) in item.preview.join('')" :key="index" :class="{ filled: cell !== '.' }" /></span><b>{{ item.name_zh }}</b><small>{{ item.grid_width }} × {{ item.grid_height }} · {{ item.category }}</small></button></div></template>
          <template v-else><div class="section-heading"><span>03</span><div><h2>文字与挂件</h2><p>适合英文名、缩写、数字和符号；可再进编辑器扩展成中文设计。</p></div></div><div class="fields fields--wide"><label class="field">文字<input v-model="form.text" maxlength="14" placeholder="HELLO"></label><label class="field">样式<select v-model="form.textStyle"><option value="keychain">钥匙扣挂件</option><option value="nameplate">边框字牌</option></select></label></div><p class="hint">当前点阵字体支持 A–Z、0–9、空格、-、!、?；未知字符以 ? 占位，之后可逐格修改。</p></template>

          <div class="section-heading section-heading--color"><span>✦</span><div><h2>创作颜色</h2><p>{{ palettes.current?.brand || '加载中' }} 色号会直接保存在图纸内。</p></div></div><div class="theme-palette"><div><b>主题色板</b><small>一键选用专业色彩方向，仍可在编辑器自由替换。</small></div><div class="theme-options"><button v-for="theme in creativeThemes" :key="theme.id" type="button" :class="{ active: selectedTheme === theme.id }" @click="applyTheme(theme.id)"><span><i v-for="color in colorsForTheme(theme.id, palettes.current?.colors || []).slice(0, 4)" :key="color.code" :style="{ background: color.hex }" /></span><b>{{ theme.name }}</b><small>{{ theme.description }}</small></button></div></div><div class="fields"><label class="field">主色<select v-model="form.foreground"><option v-for="color in creationColors" :key="color.code" :value="color.code">{{ color.code }} · {{ color.name_zh }}</option></select></label><label class="field">强调色<select v-model="form.accent"><option v-for="color in creationColors" :key="color.code" :value="color.code">{{ color.code }} · {{ color.name_zh }}</option></select></label></div><div class="fields"><label class="field">拼豆尺寸<select v-model.number="form.beadSize"><option :value="2.6">迷你豆 2.6 mm</option><option :value="5">中号豆 5.0 mm</option></select></label><label class="field">项目名称<input v-model="form.name" :placeholder="presetName()"></label></div>
        </section>
        <aside class="preview"><p class="eyebrow">READY TO DESIGN</p><h2>{{ presetName() }}</h2><div class="preview__grid" :class="`preview__grid--${mode}`"><template v-if="mode === 'template' && selectedTemplateInfo"><i v-for="(cell, index) in selectedTemplateInfo.preview.join('')" :key="index" :class="{ primary: cell === 'A', accent: cell === 'B' }" /></template><template v-else-if="mode === 'text'"><span class="text-preview">{{ form.text.toUpperCase() || 'TEXT' }}</span></template><template v-else><i v-for="cell in Math.min(form.width * form.height, 256)" :key="cell" /></template></div><dl><div><dt>色卡</dt><dd>{{ palettes.current?.name || '—' }}</dd></div><div><dt>成品尺寸</dt><dd>{{ mode === 'blank' ? `${form.width} × ${form.height} 格` : mode === 'template' ? `${selectedTemplateInfo?.grid_width || '—'} × ${selectedTemplateInfo?.grid_height || '—'} 格` : '自动适配文字' }}</dd></div></dl><p>创建后会保留全部编辑、材料统计、版本与导出能力。</p></aside>
      </div>
      <footer><div><strong>可随时回到编辑器继续修改</strong><span>模板和文字只是起点，不会锁定你的图纸。</span></div><button class="button" :disabled="creating || !palettes.current || (mode === 'text' && !form.text.trim())" @click="create">{{ creating ? '正在建立创作…' : '建立并打开编辑器 →' }}</button></footer>
    </section>
  </main>
</template>

<style scoped>
.create-page { max-width: 1200px; margin: 0 auto; padding: 48px clamp(18px, 4vw, 42px) 72px; }.heading { display: flex; align-items: end; justify-content: space-between; gap: 24px; margin-bottom: 28px; }.heading h1 { margin: 8px 0; color: #1a2440; font-family: Fraunces, Georgia, serif; font-size: clamp(34px, 4.7vw, 56px); letter-spacing: -2.4px; }.heading p:last-child { max-width: 580px; margin: 0; color: #6a748b; line-height: 1.65; }.heading-actions { display: flex; flex-wrap: wrap; gap: 7px; }.modes { display: grid; grid-template-columns: repeat(3, 1fr); border-bottom: 1px solid #e4e2ec; background: #fbfaff; }.modes button { display: flex; align-items: center; justify-content: center; gap: 8px; border: 0; border-bottom: 2px solid transparent; padding: 15px; background: transparent; color: #7b8499; font-size: 12px; font-weight: 800; }.modes button span { color: #b3abc9; font-family: var(--font-mono); font-size: 9px; }.modes button.active { border-color: #7058df; color: #4d3cb1; background: #fff; }.modes button.active span { color: #7258e7; }.studio { overflow: hidden; }.studio__body { display: grid; grid-template-columns: minmax(0, 1fr) 360px; }.settings { display: grid; align-content: start; gap: 18px; padding: 25px; }.section-heading { display: flex; align-items: start; gap: 10px; }.section-heading > span { display: grid; width: 26px; height: 26px; flex: 0 0 auto; place-items: center; border-radius: 8px; background: #eeeaff; color: #694fe1; font-family: var(--font-mono); font-size: 10px; font-weight: 800; }.section-heading h2 { margin: 1px 0 2px; color: #27314d; font-size: 16px; }.section-heading p, .hint { margin: 0; color: #7c8599; font-size: 11px; line-height: 1.55; }.section-heading--color { margin-top: 4px; padding-top: 18px; border-top: 1px solid #eeecf3; }.fields { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }.fields--wide { grid-template-columns: 1.4fr .6fr; }.quick-sizes { display: flex; flex-wrap: wrap; gap: 6px; }.quick-sizes button { border: 1px solid #e1deec; border-radius: 8px; padding: 6px 9px; background: #fbfaff; color: #666f86; font-family: var(--font-mono); font-size: 10px; }.quick-sizes button:hover { border-color: #ac9df3; background: #f4f1ff; }.template-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 9px; }.template { display: grid; justify-items: start; gap: 5px; overflow: hidden; border: 1px solid #e5e2ed; border-radius: 10px; padding: 8px; background: #fff; color: #4c5670; text-align: left; }.template:hover { border-color: #ae9ef0; }.template.active { border-color: #7058de; box-shadow: inset 0 0 0 1px #7058de; }.template__preview { display: grid; grid-template-columns: repeat(var(--columns), 4px); gap: 1px; min-height: 30px; align-content: center; }.template__preview i { width: 4px; height: 4px; border-radius: 1px; background: #f0eef4; }.template__preview i.filled { background: #836ae9; }.template b { font-size: 11px; }.template small { color: #8a92a5; font-family: var(--font-mono); font-size: 8px; }.theme-palette { display: grid; gap: 8px; border: 1px solid #e5e1ef; border-radius: 10px; padding: 10px; background: linear-gradient(135deg, #fbfaff, #f9fcff); }.theme-palette > div:first-child { display: grid; gap: 2px; }.theme-palette > div:first-child b { color: #414a64; font-size: 11px; }.theme-palette > div:first-child small { color: #838ca0; font-size: 9px; }.theme-options { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 5px; }.theme-options button { display: grid; gap: 3px; min-width: 0; border: 1px solid #e2dfea; border-radius: 8px; padding: 6px; background: #fff; color: #697388; text-align: left; }.theme-options button.active { border-color: #9179eb; background: #f2efff; color: #513bb4; box-shadow: inset 0 0 0 1px rgb(117 88 221 / 10%); }.theme-options span { display: flex; }.theme-options i { width: 10px; height: 10px; margin-right: -2px; border: 1px solid rgb(28 36 61 / 18%); border-radius: 50%; }.theme-options b { overflow: hidden; font-size: 9px; text-overflow: ellipsis; white-space: nowrap; }.theme-options small { display: none; }.preview { display: grid; align-content: start; gap: 13px; padding: 26px; border-left: 1px solid #e7e4ef; background: linear-gradient(150deg, #202b48, #121a2e); color: #fff; }.preview h2 { margin: -7px 0 0; font-size: 20px; }.preview__grid { display: grid; grid-template-columns: repeat(16, 1fr); gap: 3px; min-height: 180px; align-content: center; padding: 16px; border: 1px solid rgb(255 255 255 / 13%); border-radius: 14px; background: repeating-conic-gradient(rgb(255 255 255 / 4%) 0 25%, transparent 0 50%) 50% / 18px 18px; }.preview__grid i { aspect-ratio: 1; border-radius: 2px; background: rgb(255 255 255 / 8%); }.preview__grid--template { grid-template-columns: repeat(16, 1fr); }.preview__grid i.primary { background: #9179f2; }.preview__grid i.accent { background: #ff8a77; }.preview__grid--text { display: grid; place-items: center; }.text-preview { max-width: 100%; overflow: hidden; color: #7ce0c2; font-family: var(--font-mono); font-size: clamp(20px, 4vw, 40px); font-weight: 800; letter-spacing: .08em; text-overflow: ellipsis; white-space: nowrap; }.preview dl { display: grid; gap: 7px; margin: 0; }.preview dl div { display: flex; justify-content: space-between; gap: 9px; border-bottom: 1px solid rgb(255 255 255 / 11%); padding-bottom: 7px; font-size: 10px; }.preview dt { color: #9aa7c6; }.preview dd { margin: 0; color: #e5e9f4; font-family: var(--font-mono); text-align: right; }.preview > p { margin: 0; color: #a7b1c9; font-size: 10px; line-height: 1.6; }.studio footer { display: flex; align-items: center; justify-content: space-between; gap: 15px; padding: 15px 18px 15px 25px; border-top: 1px solid #e7e4ef; background: #fcfbff; }.studio footer strong, .studio footer span { display: block; }.studio footer strong { color: #3d465d; font-size: 11px; }.studio footer span { margin-top: 3px; color: #8a92a5; font-size: 10px; }.studio footer .button { min-height: 41px; white-space: nowrap; }
@media (max-width: 850px) { .studio__body { grid-template-columns: 1fr; }.preview { border-top: 1px solid #e7e4ef; border-left: 0; }.preview__grid { min-height: 130px; }.heading { align-items: start; flex-direction: column; } } @media (max-width: 560px) { .create-page { padding: 32px 15px 54px; }.modes button { flex-direction: column; gap: 3px; padding: 11px 5px; font-size: 10px; }.settings, .preview { padding: 18px; }.fields, .fields--wide { grid-template-columns: 1fr; }.template-grid { grid-template-columns: 1fr; }.studio footer { align-items: stretch; flex-direction: column; padding: 15px; }.studio footer .button { width: 100%; } }
</style>
