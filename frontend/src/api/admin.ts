import { request } from './http'
import type { AdminUser, AdminUserList } from '@/types/auth'
import type { AdminPublicationDetail, AdminPublicationList, AdminPublicationSummary, Publication, PublicationReviewCheck, PublicationStatus } from '@/types/publication'

export const listAdminUsers = (query = '', page = 1, pageSize = 30) => request<AdminUserList>({ method: 'GET', url: '/admin/users', params: { query, page, page_size: pageSize } })
export const createAdminUser = (payload: { email: string; password: string; display_name: string; role: 'user' | 'admin'; is_active: boolean }) => request<AdminUser>({ method: 'POST', url: '/admin/users', data: payload })
export const updateAdminUser = (userId: string, payload: Partial<Pick<AdminUser, 'email' | 'display_name' | 'role' | 'is_active'>>) => request<AdminUser>({ method: 'PATCH', url: `/admin/users/${userId}`, data: payload })
export const resetAdminUserPassword = (userId: string, password: string) => request<void>({ method: 'PUT', url: `/admin/users/${userId}/password`, data: { password } })
export const deleteAdminUser = (userId: string) => request<void>({ method: 'DELETE', url: `/admin/users/${userId}` })
export const listAdminPublications = (status: PublicationStatus | '' = 'pending', query = '') => request<AdminPublicationSummary[]>({ method: 'GET', url: '/admin/publications', params: { ...(status ? { status } : {}), ...(query.trim() ? { query: query.trim() } : {}) } })
export const listAdminPublicationsPage = (status: PublicationStatus | '' = 'pending', query = '', page = 1, pageSize = 20) => request<AdminPublicationList>({ method: 'GET', url: '/admin/publications/page', params: { ...(status ? { status } : {}), ...(query.trim() ? { query: query.trim() } : {}), page, page_size: pageSize } })
export const getAdminPublication = (publicationId: string) => request<AdminPublicationDetail>({ method: 'GET', url: `/admin/publications/${publicationId}` })
export const reviewPublication = (publicationId: string, decision: 'approved' | 'rejected', note?: string, checks: PublicationReviewCheck[] = []) => request<Publication>({ method: 'POST', url: `/admin/publications/${publicationId}/review`, data: { decision, note, checks } })
export const withdrawAdminPublication = (publicationId: string, note: string) => request<void>({ method: 'DELETE', url: `/admin/publications/${publicationId}`, params: { note } })
