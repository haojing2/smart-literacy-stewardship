import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, shallowMount } from '@vue/test-utils'
import ElementPlus, { ElMessageBox } from 'element-plus'
import router from '@/router'
import AdminUsers from '@/views/admin/AdminUsers.vue'
import HomeView from '@/views/HomeView.vue'
import * as adminApi from '@/api/admin'

vi.mock('@/api/admin', async (importOriginal) => {
  const original = await importOriginal<typeof import('@/api/admin')>()
  return {
    ...original,
    getAdminUsers: vi.fn(),
    approveUser: vi.fn(),
    rejectUser: vi.fn(),
    disableUser: vi.fn(),
    enableUser: vi.fn(),
  }
})

describe('admin RBAC navigation', () => {
  beforeEach(async () => {
    sessionStorage.clear()
    await router.replace('/')
  })

  it('routes ADMIN away from login to /admin', async () => {
    sessionStorage.setItem('access_token', 'token')
    sessionStorage.setItem('current_user', JSON.stringify({ role: 'ADMIN' }))
    await router.push('/login')
    expect(router.currentRoute.value.path).toBe('/admin')
  })

  it('routes USER away from login to /projects', async () => {
    sessionStorage.setItem('access_token', 'token')
    sessionStorage.setItem('current_user', JSON.stringify({ role: 'USER' }))
    await router.push('/login')
    expect(router.currentRoute.value.path).toBe('/projects')
  })

  it('prevents USER from visiting /admin', async () => {
    sessionStorage.setItem('access_token', 'token')
    sessionStorage.setItem('current_user', JSON.stringify({ role: 'USER' }))
    await router.push('/admin')
    expect(router.currentRoute.value.path).toBe('/projects')
  })
})

describe('admin user management', () => {
  beforeEach(async () => {
    vi.clearAllMocks()
    sessionStorage.setItem('access_token', 'token')
    sessionStorage.setItem('current_user', JSON.stringify({ role: 'ADMIN' }))
    vi.mocked(adminApi.getAdminUsers).mockResolvedValue({
      data: { code: 0, message: 'success', requestId: null, data: { items: [{
        id: 8, username: 'pending-user', displayName: '待审批教师', role: 'USER',
        status: 'PENDING', createdAt: '2026-09-11T08:00:00', updatedAt: '2026-09-11T08:00:00',
      }], total: 1, page: 1, pageSize: 20 } },
    } as never)
    vi.mocked(adminApi.approveUser).mockResolvedValue({} as never)
    vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue('confirm' as never)
    await router.replace('/admin/users')
  })

  it('shows PENDING users as 待审批', async () => {
    const wrapper = mount(AdminUsers, { global: { plugins: [ElementPlus, router] } })
    await flushPromises()
    expect(wrapper.text()).toContain('待审批教师')
    expect(wrapper.text()).toContain('待审批')
  })

  it('refreshes the list after approving a pending user', async () => {
    const wrapper = mount(AdminUsers, { global: { plugins: [ElementPlus, router] } })
    await flushPromises()
    const approveButton = wrapper.findAll('button').find(button => button.text() === '通过')
    expect(approveButton).toBeTruthy()
    await approveButton!.trigger('click')
    await flushPromises()
    expect(adminApi.approveUser).toHaveBeenCalledWith(8)
    expect(adminApi.getAdminUsers).toHaveBeenCalledTimes(2)
  })
})

it('does not label a USER as 管理员 in HomeView', async () => {
  sessionStorage.setItem('current_user', JSON.stringify({ username: 'teacher', role: 'USER' }))
  await router.replace('/projects')
  const wrapper = shallowMount(HomeView, { global: { plugins: [router] } })
  expect(wrapper.text()).toContain('普通用户')
})
