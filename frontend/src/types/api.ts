export interface ApiEnvelope<T> {
  success: boolean
  data: T
  message: string | null
  code: string | null
}

export interface ApiErrorPayload {
  success?: boolean
  data?: unknown
  message?: string
  code?: string
}
