import { request } from './http'
import type { ImageInfo } from '@/types/project'

export function uploadImage(file: File): Promise<ImageInfo> {
  const body = new FormData()
  body.append('file', file)
  return request<ImageInfo>({ method: 'POST', url: '/images/upload', data: body })
}

export const getImage = (imageId: string) => request<ImageInfo>({ method: 'GET', url: `/images/${imageId}` })

export function preprocessImage(payload: Record<string, unknown>): Promise<ImageInfo> {
  return request<ImageInfo>({ method: 'POST', url: '/images/preprocess', data: payload })
}
