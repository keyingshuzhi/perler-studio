import { request } from './http'
import type { Session, User } from '@/types/auth'

export const register = (payload: { email: string; password: string; display_name: string }) => request<Session>({ method: 'POST', url: '/auth/register', data: payload })
export const login = (payload: { account: string; password: string }) => request<Session>({ method: 'POST', url: '/auth/login', data: payload })
export const getCurrentUser = () => request<User>({ method: 'GET', url: '/auth/me' })
export const updateCurrentUser = (display_name: string) => request<User>({ method: 'PATCH', url: '/auth/me', data: { display_name } })
export const changeCurrentPassword = (current_password: string, new_password: string) => request<void>({ method: 'PUT', url: '/auth/me/password', data: { current_password, new_password } })
export const logout = () => request<void>({ method: 'POST', url: '/auth/logout' })
