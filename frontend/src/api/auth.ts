import http from './http'

export interface LoginResponse {
  code: number
  message: string
  data: {
    access_token: string
    token_type: string
    expires_in: number
    user: { id: number; username: string; display_name: string | null; role: string }
  }
}

export const login = (username: string, password: string) =>
  http.post<LoginResponse>('/auth/login', { username, password })
