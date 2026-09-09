import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const mocks = vi.hoisted(() => ({
  getProject: vi.fn(),
  getLatestProjectResearchSession: vi.fn(),
  getLatestResourceResearchSession: vi.fn(),
  getProjectResearchResources: vi.fn(),
  getEvidenceCard: vi.fn(),
  createResearchSession: vi.fn(),
  sendResearchMessage: vi.fn(),
  uploadResearchResource: vi.fn(),
  extractResearchText: vi.fn(),
}))

vi.mock('@/api/projects', () => ({ getProject: mocks.getProject }))
vi.mock('@/api/research', () => ({
  createResearchSession: mocks.createResearchSession,
  getLatestProjectResearchSession: mocks.getLatestProjectResearchSession,
  getLatestResourceResearchSession: mocks.getLatestResourceResearchSession,
  getProjectResearchResources: mocks.getProjectResearchResources,
  confirmEvidenceCard: vi.fn(),
  confirmResearchAnalysis: vi.fn(),
  extractResearchText: mocks.extractResearchText,
  getEvidenceCard: mocks.getEvidenceCard,
  sendResearchMessage: mocks.sendResearchMessage,
  updateEvidenceCard: vi.fn(),
  updateResearchAnalysis: vi.fn(),
  uploadResearchResource: mocks.uploadResearchResource,
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
    expect(store.analysis).toBeNull()
  })

  it('preloads resource evidence without replacing the active project workspace', async () => {
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

    expect(mocks.getEvidenceCard).toHaveBeenCalledWith(301)
    expect(store.evidenceDraft).toBeNull()
    expect(store.activeSession?.sessionId).toBe(71)
  })

  it('keeps historical project messages active when a resource session is also restored', async () => {
    mocks.getProjectResearchResources.mockResolvedValue({ data: { data: [{
      resourceId: 91, fileName: 'study.pdf', mimeType: 'application/pdf', fileSize: 1024,
      processingStatus: 'TEXT_EXTRACTED', indexStatus: 'ready',
    }] } })
    mocks.getLatestProjectResearchSession.mockResolvedValue({ data: { data: {
      ...projectSession,
      messages: [{ messageId: 1, role: 'ASSISTANT', sequenceNo: 1, content: 'project history', createdAt: '2026-09-07T00:00:00Z' }],
    } } })
    mocks.getLatestResourceResearchSession.mockResolvedValue({ data: { data: {
      ...projectSession, sessionId: 92, resourceId: 91,
      messages: [{ messageId: 2, role: 'ASSISTANT', sequenceNo: 1, content: 'resource history', createdAt: '2026-09-07T00:00:00Z' }],
    } } })
    mocks.sendResearchMessage.mockResolvedValue({ data: { data: {
      userMessage: { messageId: 3, role: 'USER', sequenceNo: 2, content: 'question', createdAt: '2026-09-07T00:00:01Z' },
      assistantMessage: { messageId: 4, role: 'ASSISTANT', sequenceNo: 3, content: 'answer', createdAt: '2026-09-07T00:00:02Z' },
      latestAnalysis: null, readiness: null,
    } } })

    const store = useResearchStore()
    await store.initialize(12)
    expect(store.activeSession?.sessionId).toBe(71)
    expect(store.resourceSession?.sessionId).toBe(92)
    expect(store.selectedResources).toEqual([])
    expect(store.messages.map((message) => message.content)).toEqual(['project history'])

    await store.sendMessage('question')
    expect(mocks.sendResearchMessage).toHaveBeenCalledWith(71, 'question')
  })

  it('checks that the uploaded resource index is ready before creating its session', async () => {
    mocks.getLatestProjectResearchSession.mockResolvedValue({ data: { data: projectSession } })
    const uploaded = {
      resourceId: 93, fileName: 'new.pdf', mimeType: 'application/pdf', fileSize: 10,
      processingStatus: 'UPLOADED', indexStatus: 'pending',
    }
    const ready = { ...uploaded, processingStatus: 'TEXT_EXTRACTED', indexStatus: 'ready' }
    mocks.uploadResearchResource.mockResolvedValue({ data: { data: uploaded } })
    mocks.extractResearchText.mockResolvedValue({ data: { data: {
      resourceId: 93, processingStatus: 'TEXT_EXTRACTED', indexStatus: 'pending', extractedText: 'text',
    } } })
    mocks.getProjectResearchResources
      .mockResolvedValueOnce({ data: { data: [] } })
      .mockResolvedValueOnce({ data: { data: [ready] } })
    mocks.createResearchSession.mockResolvedValue({ data: { data: {
      ...projectSession, sessionId: 94, resourceId: 93, messages: [],
    } } })

    const store = useResearchStore()
    await store.initialize(12)
    await store.uploadAndProcess(new File(['pdf'], 'new.pdf', { type: 'application/pdf' }))

    expect(mocks.getProjectResearchResources).toHaveBeenCalledTimes(2)
    expect(mocks.createResearchSession).toHaveBeenLastCalledWith(12, 93)
    expect(store.activeSession?.sessionId).toBe(94)
  })

  it('stops before session creation when the uploaded resource index fails', async () => {
    mocks.getLatestProjectResearchSession.mockResolvedValue({ data: { data: projectSession } })
    const uploaded = {
      resourceId: 95, fileName: 'bad.pdf', mimeType: 'application/pdf', fileSize: 10,
      processingStatus: 'UPLOADED', indexStatus: 'pending',
    }
    mocks.uploadResearchResource.mockResolvedValue({ data: { data: uploaded } })
    mocks.extractResearchText.mockResolvedValue({ data: { data: {
      resourceId: 95, processingStatus: 'TEXT_EXTRACTED', indexStatus: 'pending', extractedText: 'text',
    } } })
    mocks.getProjectResearchResources
      .mockResolvedValueOnce({ data: { data: [] } })
      .mockResolvedValueOnce({ data: { data: [{ ...uploaded, indexStatus: 'error' }] } })

    const store = useResearchStore()
    await store.initialize(12)
    mocks.createResearchSession.mockClear()
    await store.uploadAndProcess(new File(['pdf'], 'bad.pdf', { type: 'application/pdf' }))

    expect(mocks.createResearchSession).not.toHaveBeenCalled()
    expect(store.uploadStatus).toBe('FAILED')
    expect(store.error).toContain('索引')
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
