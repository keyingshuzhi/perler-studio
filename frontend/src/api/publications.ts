import { request } from './http'
import type { CommunityRemixResult, OwnerPublicationList, Publication, PublicationList, PublicPublication, PublicationSummary } from '@/types/publication'
import type { Project } from '@/types/project'

export const submitPublication = (projectId: string, payload: { title?: string; description?: string | null; tags?: string[]; finished_image_id?: string } = {}) => request<Publication>({ method: 'POST', url: `/projects/${projectId}/publications`, data: payload })
export const listMyPublications = () => request<Publication[]>({ method: 'GET', url: '/publications/mine' })
export const listMyPublicationsPage = (page = 1, pageSize = 12) => request<OwnerPublicationList>({ method: 'GET', url: '/publications/mine/page', params: { page, page_size: pageSize } })
export const resumePublication = (publicationId: string) => request<Project>({ method: 'POST', url: `/publications/${publicationId}/resume` })
export const withdrawPublication = (publicationId: string) => request<void>({ method: 'DELETE', url: `/publications/${publicationId}` })
export const deletePublication = (publicationId: string) => request<void>({ method: 'DELETE', url: `/publications/${publicationId}/record` })
export const getPublicPublication = (token: string) => request<PublicPublication>({ method: 'GET', url: `/publications/${token}` })
export const listPublications = (query = '', page = 1) => request<PublicationList>({ method: 'GET', url: '/publications', params: { query, page } })
export const listFavoritePublications = () => request<PublicationSummary[]>({ method: 'GET', url: '/publications/favorites/mine' })
export const listFavoritePublicationsPage = (page = 1, pageSize = 12, query = '') => request<PublicationList>({ method: 'GET', url: '/publications/favorites/mine/page', params: { page, page_size: pageSize, query } })
export const listFavoritePublicationTokens = () => request<{ items: string[] }>({ method: 'GET', url: '/publications/favorites/mine/tokens' })
export const favoritePublication = (token: string) => request<{ public_token: string; favorited: boolean }>({ method: 'POST', url: `/publications/${token}/favorite` })
export const unfavoritePublication = (token: string) => request<void>({ method: 'DELETE', url: `/publications/${token}/favorite` })
export const remixPublication = (token: string) => request<CommunityRemixResult>({ method: 'POST', url: `/publications/${token}/remix` })
