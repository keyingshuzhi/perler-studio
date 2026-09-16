import { request } from './http'
import type { Project, ProjectList, ProjectShare, ProjectVersion, ProjectVersionDetail } from '@/types/project'

export const listProjects = () => request<Project[]>({ method: 'GET', url: '/projects' })
export const listProjectsPage = (params: { query?: string; tag?: string; favorite?: boolean; page?: number; page_size?: number } = {}) => request<ProjectList>({ method: 'GET', url: '/projects/page', params })
export const getProject = (projectId: string) => request<Project>({ method: 'GET', url: `/projects/${projectId}` })
export const createProject = (payload: Pick<Project, 'name'> & Partial<Pick<Project, 'description' | 'pattern_id' | 'editor_settings'>>) => request<Project>({
  method: 'POST',
  url: '/projects',
  data: payload,
})
export const updateProject = (projectId: string, payload: Partial<Pick<Project, 'name' | 'description' | 'pattern_id' | 'editor_settings'>>) => request<Project>({
  method: 'PUT',
  url: `/projects/${projectId}`,
  data: payload,
})
export const duplicateProject = (projectId: string) => request<Project>({ method: 'POST', url: `/projects/${projectId}/duplicate` })
export const removeProject = (projectId: string) => request<void>({ method: 'DELETE', url: `/projects/${projectId}` })
export const listProjectVersions = (projectId: string) => request<ProjectVersion[]>({ method: 'GET', url: `/projects/${projectId}/versions` })
export const createProjectVersion = (projectId: string, label?: string, automatic = false) => request<ProjectVersion>({ method: 'POST', url: `/projects/${projectId}/versions`, data: { label, automatic } })
export const getProjectVersion = (projectId: string, versionId: string) => request<ProjectVersionDetail>({ method: 'GET', url: `/projects/${projectId}/versions/${versionId}` })
export const restoreProjectVersion = (projectId: string, versionId: string) => request<Project>({ method: 'POST', url: `/projects/${projectId}/versions/${versionId}/restore` })
export const createProjectShare = (projectId: string, title?: string) => request<ProjectShare>({ method: 'POST', url: `/projects/${projectId}/shares`, data: { title } })
