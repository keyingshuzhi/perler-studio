export interface User {
  id: string
  email: string
  display_name: string
  role: 'user' | 'admin'
  created_at: string
}

export interface Session {
  access_token: string
  token_type: 'bearer'
  expires_at: string
  user: User
}

export interface AdminUser extends User {
  is_active: boolean
  updated_at: string
  deleted_at: string | null
}

export interface AdminUserList {
  items: AdminUser[]
  total: number
  page: number
  page_size: number
}
