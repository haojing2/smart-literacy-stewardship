import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const mocks = vi.hoisted(() => ({
  getProject: vi.fn(),
  getLatestProjectResearchSession: vi.fn(),
  getLatestResourceResearchSession: vi.fn(),
  getProjectResearchResources: vi.fn(),
  getEvidenceCard: vi.fn(),
  createResearchSession: vi.fn(),
}))

vi.mock('@/api/projects', () => ({ getProject: mocks.getProject }))
vi.mock('@/api/research', () => ({
  createResearchSession: mocks.createResearchSession,
  getLatestProjectResearchSession: mocks.getLatestProjectResearchSession,
  getLatestResourceResearchSession: mocks.getLatestResourceResearchSession,
  getProjectResearchResources: mocks.getProjectResearchResources,
  confirmEvidenceCard: vi.fn(),
  confirmResearchAnalysis: vi.fn(),
  extractResearchText: vi.fn(),
  getEvidenceCard: mocks.getEvidenceCard,
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
    mocks.getProjectResearchResources.mockResolvedValue({ data: { data: [] } })
    mocks.getLatestResourceResearchSession.mockRejectedValue({
      isAxiosError: true,
      response: { status: 404 },
    })
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

  it('restores resources and the latest resource analysis from backend without localStorage', async () => {
    localStorage.clear()
    mocks.getProjectResearchResources.mockResolvedValue({
      data: {
        data: [{
          resourceId: 91,
          fileName: 'study.pdf',
          mimeType: 'application/pdf',
          fileSize: 1024,
          processingStatus: 'TEXT_EXTRACTED',
          indexStatus: 'ready',
        }],
      },
    })
    mocks.getLatestProjectResearchSession.mockResolvedValue({ data: { data: projectSession } })
    mocks.getLatestResourceResearchSession.mockResolvedValue({
      data: {
        data: {
          ...projectSession,
          sessionId: 92,
          resourceId: 91,
          latestAnalysis: {
            researchSubjects: ['五年级学生'],
            researchTopics: ['协作学习'],
            aiLiteracyDimensions: [],
            teachingStrategies: [],
            interventionDuration: null,
            assessmentTools: [],
            mainFindings: [],
            limitations: [],
          },
        },
      },
    })

    const store = useResearchStore()
    await store.initialize(12)

    expect(store.resources.map((item) => item.fileName)).toEqual(['study.pdf'])
    expect(store.currentSession?.sessionId).toBe(71)
    expect(store.resourceSession?.sessionId).toBe(92)
    expect(store.analysis?.participants).toEqual(['五年级学生'])
  })

  it('restores the resource session evidence card from the database', async () => {
    mocks.getLatestProjectResearchSession.mockResolvedValue({ data: { data: projectSession } })
    mocks.getLatestResourceResearchSession.mockResolvedValue({
      data: { data: { ...projectSession, sessionId: 92, resourceId: 91, evidenceCardId: 301 } },
    })
    mocks.getEvidenceCard.mockResolvedValue({
      data: {
        data: {
          evidenceCardId: 301,
          researchAnalysisId: 201,
          researchFinding: '研究发现',
          applicableAudience: '五年级学生',
          recommendedStrategies: [],
          implementationConditions: [],
          teachingImplications: '',
          limitations: '',
          source: {
            resourceId: 91,
            projectId: 12,
            originalFilename: 'study.pdf',
            sha256: 'abc',
          },
          cardStatus: 'DRAFT',
        },
      },
    })

    const store = useResearchStore()
    await store.initialize(12)

    expect(store.evidenceDraft?.evidenceCardId).toBe(301)
    expect(store.evidenceDraft?.sourceDocument).toBe('study.pdf')
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
