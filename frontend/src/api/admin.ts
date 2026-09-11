import http from './http'

export type UserStatus = 'PENDING' | 'ACTIVE' | 'REJECTED' | 'DISABLED'
export interface AdminUser { id: number; username: string; displayName: string | null; role: string; status: UserStatus; createdAt: string; updatedAt: string }
export interface UserListData { items: AdminUser[]; total: number; page: number; pageSize: number }
export interface SystemStatus { api: string; database: string; version: string; environment: string; registeredUsers: number; pendingUsers: number; activeUsers: number; projectCount: number }
interface Envelope<T> { code: number; message: string; data: T; requestId: string | null }

export const getAdminUsers = (params: { page: number; pageSize: number; status?: UserStatus; keyword?: string }) =>
  http.get<Envelope<UserListData>>('/admin/users', { params })
export const approveUser = (id: number) => http.post<Envelope<AdminUser>>(`/admin/users/${id}/approve`)
export const rejectUser = (id: number) => http.post<Envelope<AdminUser>>(`/admin/users/${id}/reject`)
export const disableUser = (id: number) => http.post<Envelope<AdminUser>>(`/admin/users/${id}/disable`)
export const enableUser = (id: number) => http.post<Envelope<AdminUser>>(`/admin/users/${id}/enable`)
export const getAdminSystemStatus = () => http.get<Envelope<SystemStatus>>('/admin/system/status')
