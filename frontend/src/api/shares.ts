import { request } from './http'
import type { PublicShare } from '@/types/project'

export const getShare = (token: string) => request<PublicShare>({ method: 'GET', url: `/shares/${token}` })
export const confirmShare = (token: string, decision: 'approved' | 'changes_requested', comment?: string) => request<PublicShare>({
  method: 'POST',
  url: `/shares/${token}/confirmation`,
  data: { decision, comment: comment || undefined },
})
export const addShareComment = (token: string, message: string, cellIndex?: number) => request<PublicShare>({
  method: 'POST',
  url: `/shares/${token}/comments`,
  data: { message, cell_index: cellIndex },
})
