import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({
  getCourseDesign: vi.fn(),
  getResourceCreation: vi.fn(),
  getTeachingResource: vi.fn(),
  createResourceJob: vi.fn(),
  updateResourceJob: vi.fn(),
  recommendResourceSettings: vi.fn(),
  generateResources: vi.fn(),
  regenerateResources: vi.fn(),
  saveTeachingResourceVersion: vi.fn(),
  transformTeachingResource: vi.fn(),
  reviewTeachingResource: vi.fn(),
  createResourceSuggestion: vi.fn(),
  acceptResourceSuggestion: vi.fn(),
  reviseResourceSuggestion: vi.fn(),
  rejectResourceSuggestion: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { projectId: '42' }, query: {} }),
}))
vi.mock('@/api/courseDesign', () => ({ getCourseDesign: api.getCourseDesign }))
vi.mock('@/api/resourceCreation', () => api)

import ResourceCreation from '@/views/resource-creation/ResourceCreation.vue'

const persistedState = {
  job: {
    jobId: 7,
    mode: 'COURSE_GENERATE',
    currentStep: 2,
    selectedTypes: ['WORKSHEET'],
    commonSettings: { difficulty: '适中' },
    resourceSettings: { worksheet: { duration: '15分钟' } },
    status: 'READY',
    updatedAt: '2026-09-10T10:00:00Z',
  },
  resources: [{ resourceId: 11, resourceType: 'WORKSHEET', currentVersionNo: 4 }],
}

async function mountResourceCreation() {
  const wrapper = mount(ResourceCreation, {
    attachTo: document.body,
    global: { plugins: [ElementPlus] },
  })
  await flushPromises()
  await flushPromises()
  return wrapper
}

function buttonByText(wrapper: ReturnType<typeof mount>, text: string) {
  const button = wrapper.findAll('button').find((item) => item.text().includes(text))
  if (!button) throw new Error(`Button not found: ${text}`)
  return button
}

describe('ResourceCreation persisted resource recovery', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    api.getCourseDesign.mockResolvedValue({ data: { data: {
      project: { title: 'AI 信息核验' },
      context: { grade: 7, lessonMinutes: 40 },
      objectives: [{}], activities: [{}], pedagogy: { name: '探究学习' },
    } } })
    api.getResourceCreation.mockResolvedValue({ data: { data: persistedState } })
    api.getTeachingResource.mockResolvedValue({ data: { data: {
      currentVersion: {
        versionId: 44,
        versionNo: 4,
        content: {
          title: '服务器上的 worksheet v4',
          blocks: [{ key: 'task', title: '真实任务', content: '实际生成内容' }],
          metadata: {},
        },
      },
      suggestions: [],
    } } })
  })

  it('reopens and refreshes directly into the persisted v4 AI co-creation view', async () => {
    const first = await mountResourceCreation()
    expect(first.text()).toContain('资源预览与编辑')
    expect(first.text()).toContain('服务器上的 worksheet v4')
    expect(first.text()).toContain('已保存 · v4')
    expect(api.generateResources).not.toHaveBeenCalled()
    first.unmount()

    const refreshed = await mountResourceCreation()
    expect(refreshed.text()).toContain('服务器上的 worksheet v4')
    expect(api.generateResources).not.toHaveBeenCalled()
    refreshed.unmount()
  })

  it('uses 查看草稿 for real content rather than the generation-settings drawer', async () => {
    const wrapper = await mountResourceCreation()
    await buttonByText(wrapper, '生成设置').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('生成条件')

    await buttonByText(wrapper, '查看草稿').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('服务器上的 worksheet v4')
    expect((wrapper.vm as unknown as { settingsViewerVisible: boolean }).settingsViewerVisible).toBe(false)
    expect(api.generateResources).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('navigates from generation settings back to AI co-creation without generating v5', async () => {
    const wrapper = await mountResourceCreation()
    const flowButtons = wrapper.find('.creation-flow').findAll('button')
    await flowButtons[1]!.trigger('click')
    expect(wrapper.text()).toContain('生成条件')
    await flowButtons[2]!.trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('服务器上的 worksheet v4')
    expect(wrapper.text()).toContain('已保存 · v4')
    expect(api.generateResources).not.toHaveBeenCalled()
    expect(api.regenerateResources).not.toHaveBeenCalled()
    wrapper.unmount()
  })
})
