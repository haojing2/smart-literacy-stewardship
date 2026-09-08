import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const mocks = vi.hoisted(() => ({
  getProject: vi.fn(),
  getLatestProjectResearchSession: vi.fn(),
  createResearchSession: vi.fn(),
}))

vi.mock('@/api/projects', () => ({ getProject: mocks.getProject }))
vi.mock('@/api/research', () => ({
  createResearchSession: mocks.createResearchSession,
  getLatestProjectResearchSession: mocks.getLatestProjectResearchSession,
  confirmEvidenceCard: vi.fn(),
  confirmResearchAnalysis: vi.fn(),
  extractResearchText: vi.fn(),
  getEvidenceCard: vi.fn(),
  sendResearchMessage: vi.fn(),
  updateEvidenceCard: vi.fn(),
  updateResearchAnalysis: vi.fn(),
  uploadResearchResource: vi.fn(),
}))
import { useResearchStore } from '@/stores/research'

describe('research store message preconditions', () => {
  const project = {
    projectId: 12,
    title: '测试项目',
    topic: 'AI 信息核验',
    grade: 5,
    classHours: 2,
  }
  const projectSession = {
    sessionId: 71,
    projectId: 12,
    resourceId: null,
    title: '项目研教对话',
    status: 'ACTIVE' as const,
    messages: [],
    latestAnalysis: null,
    readiness: null,
    evidenceCardId: null,
    createdAt: '2026-09-07T00:00:00Z',
    updatedAt: '2026-09-07T00:00:00Z',
  }

  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    localStorage.clear()
    mocks.getProject.mockResolvedValue({ data: { data: project } })
  })

  it('creates a project knowledge-base session when a new project has none', async () => {
    mocks.getLatestProjectResearchSession.mockRejectedValue({
      isAxiosError: true,
      response: { status: 404 },
    })
    mocks.createResearchSession.mockResolvedValue({ data: { data: projectSession } })

    const store = useResearchStore()
    await store.initialize(12)

    expect(mocks.createResearchSession).toHaveBeenCalledWith(12, null)
    expect(store.currentSession?.resourceId).toBeNull()
    expect(store.currentSession?.sessionId).toBe(71)
  })

  it('restores the existing project knowledge-base session and its messages', async () => {
    mocks.getLatestProjectResearchSession.mockResolvedValue({
      data: {
        data: {
          ...projectSession,
          messages: [
            {
              messageId: 1,
              role: 'USER',
              sequenceNo: 1,
              content: '你好',
              createdAt: '2026-09-07T00:00:00Z',
            },
          ],
        },
      },
    })

    const store = useResearchStore()
    await store.initialize(12)

    expect(mocks.createResearchSession).not.toHaveBeenCalled()
    expect(store.currentSession?.sessionId).toBe(71)
    expect(store.messages.map((message) => message.content)).toEqual(['你好'])
  })

  it('returns false with an explicit recovery error only when session initialization failed', async () => {
    const store = useResearchStore()
    store.currentProject = {
      projectId: 12,
      title: '测试项目',
      topic: 'AI 信息核验',
      grade: 5,
      classHours: 2,
    }

    await expect(store.sendMessage('hello，测试')).resolves.toBe(false)
    expect(store.error).toBe('研教对话会话尚未准备好，请重新加载页面')
    expect(store.messages).toHaveLength(0)
  })
})
