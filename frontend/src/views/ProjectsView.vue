<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { duplicateProject, listProjectsPage, removeProject, updateProject } from '@/api/projects'
import InfiniteScrollTrigger from '@/components/common/InfiniteScrollTrigger.vue'
import { useAppStore } from '@/stores/app'
import { useProjectStore } from '@/stores/project'
import type { Project, ProjectMetadata } from '@/types/project'

const app = useAppStore()
const projects = useProjectStore()
const router = useRouter()
const busyId = ref('')
const query = ref('')
const selectedTag = ref('')
const favoritesOnly = ref(false)
const editingNameFor = ref('')
const nameDraft = ref('')
const editingTagsFor = ref('')
const tagDraft = ref('')
const loading = ref(false)
const page = ref(1)
const total = ref(0)
const libraryTotal = ref(0)
const favoriteCount = ref(0)
const taggedProjectCount = ref(0)
const availableTags = ref<string[]>([])
const hasMore = computed(() => projects.projects.length < total.value)

function metadata(project: Project): ProjectMetadata {
  const raw = project.editor_settings.project_metadata
  if (!raw || typeof raw !== 'object') return { version: 1, tags: [], favorite: false }
  const value = raw as Partial<ProjectMetadata>
  return {
    version: 1,
    tags: Array.isArray(value.tags) ? value.tags.filter((tag): tag is string => typeof tag === 'string').slice(0, 12) : [],
    favorite: value.favorite === true,
  }
}
async function loadProjects(reset = false) {
  if (loading.value) return
  const targetPage = reset ? 1 : page.value + 1
  loading.value = true
  try {
    const result = await listProjectsPage({
      query: query.value.trim(),
      tag: selectedTag.value,
      favorite: favoritesOnly.value,
      page: targetPage,
      page_size: 16,
    })
    page.value = targetPage
    total.value = result.total
    libraryTotal.value = result.library_total
    favoriteCount.value = result.favorite_count
    taggedProjectCount.value = result.tagged_count
    availableTags.value = result.available_tags
    projects.projects = reset ? result.items : [...projects.projects, ...result.items]
  } catch (error) { app.showError(error) } finally { loading.value = false }
}

function selectTag(tag: string) {
  selectedTag.value = selectedTag.value === tag ? '' : tag
  void loadProjects(true)
}

function toggleFavoritesFilter() {
  favoritesOnly.value = !favoritesOnly.value
  void loadProjects(true)
}

async function saveMetadata(project: Project, patch: Partial<ProjectMetadata>) {
  busyId.value = project.id
  try {
    const current = metadata(project)
    const updated = await updateProject(project.id, { editor_settings: { ...project.editor_settings, project_metadata: { ...current, ...patch, version: 1 } } })
    projects.projects = projects.projects.map((item) => item.id === project.id ? updated : item)
    if (projects.current?.id === project.id) projects.current = updated
    await loadProjects(true)
  } catch (error) { app.showError(error) } finally { busyId.value = '' }
}
async function toggleFavorite(project: Project) { await saveMetadata(project, { favorite: !metadata(project).favorite }) }
function editName(project: Project) {
  editingTagsFor.value = ''
  editingNameFor.value = project.id
  nameDraft.value = project.name
}
function cancelNameEdit() {
  editingNameFor.value = ''
  nameDraft.value = ''
}
async function applyName(project: Project) {
  const name = nameDraft.value.trim()
  if (!name) { app.showError(new Error('图纸名称不能为空')); return }
  if (name === project.name) { cancelNameEdit(); return }
  busyId.value = project.id
  try {
    const updated = await updateProject(project.id, { name })
    projects.projects = projects.projects.map((item) => item.id === project.id ? updated : item)
    if (projects.current?.id === project.id) projects.current = updated
    cancelNameEdit()
    app.showNotice('图纸已重命名')
  } catch (error) { app.showError(error) } finally { busyId.value = '' }
}
function editTags(project: Project) { cancelNameEdit(); editingTagsFor.value = project.id; tagDraft.value = metadata(project).tags.join('，') }
async function applyTags(project: Project) {
  const tags = [...new Set(tagDraft.value.split(/[，,]/).map((tag) => tag.trim()).filter(Boolean))].slice(0, 12)
  await saveMetadata(project, { tags })
  editingTagsFor.value = ''
}

async function duplicate(project: Project) {
  busyId.value = project.id
  try { const copy = await duplicateProject(project.id); app.showNotice('已创建项目副本'); await router.push(`/editor/${copy.id}`) } catch (error) { app.showError(error) } finally { busyId.value = '' }
}
async function remove(project: Project) {
  if (!window.confirm(`删除“${project.name}”？已导出的文件不会受影响。`)) return
  busyId.value = project.id
  try { await removeProject(project.id); await loadProjects(true); app.showNotice('项目已删除') } catch (error) { app.showError(error) } finally { busyId.value = '' }
}
onMounted(() => { void loadProjects(true) })
</script>

<template>
  <main class="projects">
    <header class="projects__hero">
      <div><p class="eyebrow">PROJECT LIBRARY</p><h1>我的图纸</h1><p class="intro">集中管理每一张拼豆图纸，随时回到工作台继续精修。</p></div>
      <div class="new-projects"><RouterLink class="button button--quiet" to="/convert">图片转换</RouterLink><RouterLink class="button new-project" to="/create"><span>＋</span> 新建创作</RouterLink></div>
    </header>
    <section v-if="libraryTotal" class="library-summary" aria-label="项目概览">
      <div><span>全部图纸</span><strong>{{ libraryTotal }}</strong><small>个可编辑项目</small></div>
      <div><span>已收藏</span><strong>{{ favoriteCount }}</strong><small>个常用方案</small></div>
      <div><span>已分类</span><strong>{{ taggedProjectCount }}</strong><small>个带项目标签</small></div>
      <p><i>✦</i> 使用收藏和标签，能更快找到需要继续制作的图纸。</p>
    </section>
    <section v-if="libraryTotal" class="library-tools"><label class="search"><span>⌕</span><input v-model="query" type="search" placeholder="搜索项目、描述或标签" @keyup.enter="loadProjects(true)"></label><div class="filters"><button type="button" :class="{ active: !selectedTag }" @click="selectTag('')">全部</button><button v-for="tag in availableTags" :key="tag" type="button" :class="{ active: selectedTag === tag }" @click="selectTag(tag)">{{ tag }}</button><button type="button" :class="{ active: favoritesOnly }" @click="toggleFavoritesFilter">★ 收藏</button></div></section>
    <section v-if="projects.projects.length" class="project-grid">
      <article v-for="(project, index) in projects.projects" :key="project.id" class="card project-card">
        <div class="project__icon"><i v-for="n in 9" :key="n" :class="`bead bead--${(n + index) % 5}`" /></div>
        <div class="project__body"><div class="project__title"><form v-if="editingNameFor === project.id" class="name-editor" @submit.prevent="applyName(project)"><label class="sr-only" :for="`project-name-${project.id}`">图纸名称</label><input :id="`project-name-${project.id}`" v-model="nameDraft" maxlength="120" autocomplete="off" @keydown.esc.prevent="cancelNameEdit"><button type="submit" :disabled="busyId === project.id">保存</button><button type="button" :disabled="busyId === project.id" @click="cancelNameEdit">取消</button></form><template v-else><h2 :title="project.name">{{ project.name }}</h2><button class="rename-button" type="button" :disabled="busyId === project.id" :aria-label="`重命名${project.name}`" @click="editName(project)">重命名</button></template><span class="project__status">已保存</span></div><p>{{ project.description || '拼豆图纸项目' }}</p><div class="tag-list"><button class="favorite" type="button" :class="{ active: metadata(project).favorite }" :disabled="busyId === project.id" :aria-label="metadata(project).favorite ? '取消收藏' : '收藏项目'" @click="toggleFavorite(project)">{{ metadata(project).favorite ? '★ 已收藏' : '☆ 收藏' }}</button><span v-for="tag in metadata(project).tags" :key="tag">{{ tag }}</span><button class="tag-edit" type="button" :disabled="busyId === project.id" @click="editTags(project)">标签</button></div><form v-if="editingTagsFor === project.id" class="tag-editor" @submit.prevent="applyTags(project)"><input v-model="tagDraft" maxlength="120" placeholder="例如：定制，人物，待报价"><button type="submit" :disabled="busyId === project.id">保存</button><button type="button" @click="editingTagsFor = ''">取消</button></form><time>最后编辑 · {{ new Date(project.updated_at).toLocaleString() }}</time></div>
        <div class="project__actions"><button class="button" @click="router.push(`/editor/${project.id}`)">打开编辑器 <span>→</span></button><button class="button button--quiet" :disabled="busyId === project.id" @click="duplicate(project)">{{ busyId === project.id ? '处理中…' : '复制为新方案' }}</button><button class="text-button" :disabled="busyId === project.id" @click="remove(project)">{{ busyId === project.id ? '处理中…' : '删除项目' }}</button></div>
      </article>
    </section>
    <InfiniteScrollTrigger v-if="projects.projects.length" :has-more="hasMore" :loading="loading" end-text="项目已全部加载" @load="loadProjects()" />
    <section v-else-if="libraryTotal && !loading" class="empty card"><p class="eyebrow">NO RESULTS</p><h2>没有匹配的项目</h2><p>试试调整关键词、标签或收藏筛选。</p><button class="button button--quiet" type="button" @click="query = ''; selectedTag = ''; favoritesOnly = false; loadProjects(true)">清除筛选</button></section>
    <section v-else-if="!loading" class="empty card"><div class="empty__mark"><i v-for="n in 9" :key="n" /></div><p class="eyebrow">EMPTY WORKSPACE</p><h2>从一个灵感开始</h2><p>上传图片转换，或直接在空白画布、模板和文字挂件中开始创作。</p><div class="empty__actions"><RouterLink class="button" to="/convert">从图片开始 <span>→</span></RouterLink><RouterLink class="button button--quiet" to="/create">空白创作</RouterLink></div></section>
  </main>
</template>

<style scoped>
.projects { max-width: 1120px; margin: 0 auto; padding: 56px 28px 70px; }.projects__hero { display: flex; align-items: end; justify-content: space-between; gap: 24px; }.eyebrow { margin: 0; color: #7258e7; font-family: var(--font-mono); font-size: 11px; font-weight: 800; letter-spacing: .13em; }.projects h1 { margin: 7px 0 8px; color: #17213a; font-size: clamp(34px, 5vw, 54px); letter-spacing: -.055em; }.intro { max-width: 495px; margin: 0; color: #66708c; line-height: 1.65; }.new-projects { display: flex; flex-wrap: wrap; gap: 8px; }.new-projects .button--quiet { min-height: 46px; padding-inline: 14px; }.new-project { flex: none; min-height: 46px; padding-inline: 18px; background: linear-gradient(135deg, #5c42cd, #8d70ef); box-shadow: 0 10px 21px rgb(82 57 187 / 25%); }.new-project span { font-size: 20px; line-height: 12px; }.library-summary { display: grid; grid-template-columns: repeat(3, minmax(0, 132px)) minmax(220px, 1fr); gap: 1px; margin-top: 28px; overflow: hidden; border: 1px solid #e4e0f1; border-radius: 14px; background: #e9e5f3; box-shadow: 0 6px 18px rgb(36 35 80 / 4%); }.library-summary > div, .library-summary > p { min-width: 0; margin: 0; padding: 12px 14px; background: rgb(255 255 255 / 87%); }.library-summary > div { display: grid; gap: 1px; }.library-summary span { color: #8991a4; font-family: var(--font-mono); font-size: 9px; }.library-summary strong { color: #35405a; font-family: Fraunces, Georgia, serif; font-size: 23px; line-height: 1.12; }.library-summary small { overflow: hidden; color: #8b93a6; font-size: 9px; text-overflow: ellipsis; white-space: nowrap; }.library-summary > p { display: flex; align-items: center; gap: 7px; color: #68738b; font-size: 10px; line-height: 1.55; }.library-summary p i { display: grid; width: 20px; height: 20px; flex: 0 0 20px; place-items: center; border-radius: 7px; color: #6650c7; background: #f0edff; font-size: 10px; font-style: normal; }.library-tools { display: grid; grid-template-columns: minmax(230px, .9fr) 1.6fr; gap: 10px; margin-top: 16px; }.search { display: flex; align-items: center; gap: 7px; border: 1px solid #e2dff0; border-radius: 10px; padding: 0 10px; background: #fff; color: #7468b9; }.search input { width: 100%; min-height: 36px; border: 0; outline: 0; color: #4c5670; background: transparent; font: inherit; font-size: 12px; }.filters { display: flex; align-items: center; gap: 5px; overflow-x: auto; padding: 2px; }.filters button { flex: 0 0 auto; border: 1px solid #e3dff0; border-radius: 99px; padding: 6px 8px; background: #fff; color: #727b91; font-size: 10px; white-space: nowrap; }.filters button.active { border-color: #d0c5fa; color: #5b45c5; background: #f3f0ff; font-weight: 800; }.project-grid { display: grid; gap: 12px; margin-top: 15px; }.project-card { position: relative; display: grid; grid-template-columns: 76px minmax(0, 1fr) auto; gap: 19px; align-items: center; overflow: hidden; padding: 18px 19px; border: 1px solid #e8e5f2; background: linear-gradient(120deg, #fff, #fcfbff); transition: transform .2s, box-shadow .2s, border-color .2s; }.project-card::before { position: absolute; inset: 0 auto 0 0; width: 3px; background: linear-gradient(#8b70ed, #e96e7b); content: ''; opacity: 0; transition: opacity .2s; }.project-card:hover { border-color: #d6cffa; transform: translateY(-2px); box-shadow: 0 15px 31px rgb(29 27 74 / 10%); }.project-card:hover::before { opacity: 1; }.project__icon { display: grid; grid-template-columns: repeat(3, 12px); gap: 4px; width: 66px; height: 66px; place-content: center; border: 1px solid #e8e2ff; border-radius: 16px; background: #f4f1ff; }.bead { width: 12px; height: 12px; border-radius: 50%; box-shadow: inset 2px 2px 3px rgb(255 255 255 / 55%), inset -2px -2px 3px rgb(0 0 0 / 15%), 0 1px 2px rgb(32 25 75 / 15%); }.bead--0 { background: #7659df; }.bead--1 { background: #ef7181; }.bead--2 { background: #ffc763; }.bead--3 { background: #68cab3; }.bead--4 { background: #5d8be8; }.project__body { min-width: 0; }.project__title { display: flex; align-items: center; min-width: 0; gap: 7px; }.project__body h2 { flex: 1 1 auto; min-width: 0; overflow: hidden; margin: 0; color: #1e2740; font-size: 17px; text-overflow: ellipsis; white-space: nowrap; }.rename-button { flex: 0 0 auto; border: 0; border-radius: 7px; padding: 4px 6px; color: #6b5ab8; background: transparent; font-size: 9px; font-weight: 800; }.rename-button:hover { background: #f1eeff; }.name-editor { display: grid; grid-template-columns: minmax(100px, 1fr) auto auto; flex: 1 1 auto; min-width: 0; gap: 4px; }.name-editor input { width: 100%; min-width: 0; border: 1px solid #8c79e6; border-radius: 7px; padding: 5px 7px; outline: none; color: #28344d; background: #fff; font: inherit; font-size: 13px; box-shadow: 0 0 0 3px rgb(108 84 216 / 10%); }.name-editor button { border: 1px solid #ddd7ef; border-radius: 7px; padding: 4px 6px; color: #6251b7; background: #f7f5ff; font-size: 9px; font-weight: 800; }.project__status { display: inline-flex; flex: 0 0 auto; align-items: center; min-height: 22px; border: 1px solid #dcefe3; border-radius: 99px; padding: 2px 7px; color: #38815e; background: #f2fbf5; font-size: 10px; line-height: 1; white-space: nowrap; }.project__body p, time { display: block; overflow: hidden; margin: 5px 0 0; color: #737c95; font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }.project__body time { color: #9a9eb1; font-family: var(--font-mono); font-size: 10px; }.tag-list { display: flex; align-items: center; flex-wrap: wrap; gap: 4px; margin-top: 7px; }.tag-list > span, .favorite, .tag-edit { border: 1px solid #e5e1f0; border-radius: 99px; padding: 3px 6px; color: #737c95; background: #fbfaff; font-size: 9px; }.favorite.active { border-color: #f2d991; color: #9e761f; background: #fff9e8; }.tag-edit { border-style: dashed; cursor: pointer; }.tag-editor { display: grid; grid-template-columns: minmax(0, 1fr) auto auto; gap: 5px; margin-top: 7px; }.tag-editor input { min-width: 0; border: 1px solid #ded9ec; border-radius: 7px; padding: 5px 6px; color: #536078; font-size: 10px; }.tag-editor button { border: 1px solid #ded9ec; border-radius: 7px; padding: 4px 6px; background: #fff; color: #6152ae; font-size: 9px; }.project__actions { display: flex; gap: 7px; align-items: center; }.project__actions .button:first-child { background: #233151; }.project__actions .button span { margin-left: 3px; }.text-button { border: 0; border-radius: 8px; padding: 7px; background: transparent; color: #ae5565; font-size: 12px; }.text-button:hover { background: #fff2f3; }.empty { display: grid; justify-items: center; gap: 10px; margin-top: 35px; padding: 69px 20px; border: 1px dashed #d5cfeb; background: linear-gradient(145deg, #fff, #f8f7ff); text-align: center; }.empty__mark { display: grid; grid-template-columns: repeat(3, 12px); gap: 4px; margin-bottom: 5px; }.empty__mark i { width: 12px; height: 12px; border-radius: 50%; background: #8d72ec; box-shadow: inset 2px 2px 2px rgb(255 255 255 / 55%), inset -1px -1px 2px rgb(38 25 103 / 23%); }.empty__mark i:nth-child(2n) { background: #ef7b88; }.empty__mark i:nth-child(3n) { background: #f5c75b; }.empty h2, .empty p { margin: 0; }.empty h2 { color: #202a45; font-size: 24px; }.empty > p:not(.eyebrow) { max-width: 360px; color: #737b93; line-height: 1.6; }.empty__actions { display: flex; flex-wrap: wrap; justify-content: center; gap: 8px; }.empty .button { margin-top: 7px; } @media (max-width: 760px) { .projects { padding: 37px 18px 50px; }.projects__hero { align-items: start; flex-direction: column; }.library-summary { grid-template-columns: repeat(3, minmax(0, 1fr)); }.library-summary > p { display: none; }.library-tools { grid-template-columns: 1fr; }.project-card { grid-template-columns: 62px 1fr; }.project__icon { width: 56px; height: 56px; }.project__actions { grid-column: 1 / -1; padding-top: 2px; } } @media (max-width: 560px) { .project__title { flex-wrap: wrap; }.name-editor { order: 1; flex-basis: 100%; }.project__status { margin-left: auto; } } @media (max-width: 420px) { .library-summary { grid-template-columns: 1fr; }.library-summary > p { display: flex; }.project__actions .button:first-child { flex: 1; }.project__actions { flex-wrap: wrap; }.tag-editor, .name-editor { grid-template-columns: 1fr auto; }.tag-editor input, .name-editor input { grid-column: 1 / -1; } }
</style>
