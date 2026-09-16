import { defineStore } from 'pinia'

import { createProject, getProject, listProjects, updateProject } from '@/api/projects'
import type { Project } from '@/types/project'

export const useProjectStore = defineStore('project', {
  state: () => ({
    current: null as Project | null,
    projects: [] as Project[],
  }),
  actions: {
    async refresh() {
      this.projects = await listProjects()
    },
    async load(projectId: string) {
      this.current = await getProject(projectId)
      return this.current
    },
    async create(name: string, patternId: string) {
      this.current = await createProject({ name, pattern_id: patternId, editor_settings: {} })
      return this.current
    },
    async rename(name: string) {
      if (!this.current) return
      this.current = await updateProject(this.current.id, { name })
    },
    async saveEditorSettings(editorSettings: Record<string, unknown>) {
      if (!this.current) return
      this.current = await updateProject(this.current.id, { editor_settings: editorSettings })
    },
  },
})
