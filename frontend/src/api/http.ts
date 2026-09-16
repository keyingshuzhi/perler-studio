import axios, { AxiosError, type AxiosRequestConfig } from 'axios'

import type { ApiEnvelope, ApiErrorPayload } from '@/types/api'
import { AUTH_TOKEN_STORAGE_KEY } from '@/utils/auth-token'

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || '/api/v1'

export const http = axios.create({
  baseURL: apiBaseUrl,
  timeout: 60_000,
})

http.interceptors.request.use((config) => {
  const token = window.localStorage.getItem(AUTH_TOKEN_STORAGE_KEY)
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

export class ApiError extends Error {
  constructor(
    message: string,
    readonly code: string | null = null,
    readonly details: unknown = null,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

export async function request<T>(config: AxiosRequestConfig): Promise<T> {
  try {
    const response = await http.request<ApiEnvelope<T>>(config)
    if (response.status === 204) return undefined as T
    if (!response.data.success) {
      throw new ApiError(response.data.message || '请求失败', response.data.code, response.data.data)
    }
    return response.data.data
  } catch (error) {
    if (error instanceof ApiError) throw error
    const payload = (error as AxiosError<ApiErrorPayload>).response?.data
    throw new ApiError(payload?.message || '无法连接到后端服务', payload?.code || null, payload?.data)
  }
}

export function mediaUrl(path: string): string {
  const token = window.localStorage.getItem(AUTH_TOKEN_STORAGE_KEY)
  const signedPath = token && !/[?&](share_token|publication_token)=/.test(path)
    ? `${path}${path.includes('?') ? '&' : '?'}access_token=${encodeURIComponent(token)}`
    : path
  if (/^https?:\/\//.test(signedPath)) return signedPath
  if (apiBaseUrl.startsWith('http')) return new URL(signedPath, apiBaseUrl).toString()
  return signedPath
}
