import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const mocks = vi.hoisted(() => ({
  getProject: vi.fn(),
  getLatestProjectResearchSession: vi.fn(),
  getLatestResourceResearchSession: vi.fn(),
  getLatestResearchSessionForResource: vi.fn(),
  getProjectResearchResources: vi.fn(),
  getEvidenceCard: vi.fn(),
  getResearchSession: vi.fn(),
  createResearchSession: vi.fn(),
  confirmEvidenceCard: vi.fn(),
  sendResearchMessage: vi.fn(),
  uploadResearchResource: vi.fn(),
  extractResearchText: vi.fn(),
}))

vi.mock('@/api/projects', () => ({ getProject: mocks.getProject }))
vi.mock('@/api/research', () => ({
  createResearchSession: mocks.createResearchSession,
  getLatestProjectResearchSession: mocks.getLatestProjectResearchSession,
  getLatestResourceResearchSession: mocks.getLatestResourceResearchSession,
  getLatestResearchSessionForResource: mocks.getLatestResearchSessionForResource,
  getProjectResearchResources: mocks.getProjectResearchResources,
  confirmEvidenceCard: mocks.confirmEvidenceCard,
  confirmResearchAnalysis: vi.fn(),
  extractResearchText: mocks.extractResearchText,
  getEvidenceCard: mocks.getEvidenceCard,
  getResearchSession: mocks.getResearchSession,
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
    expect(store.activeAnalysisScope).toBe('PROJECT')
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

  it('restores the persisted RESOURCE scope and exposes FAILED generation status', async () => {
    localStorage.setItem('research-active-scope:12', JSON.stringify({ scope: 'RESOURCE', resourceId: 91 }))
    mocks.getProjectResearchResources.mockResolvedValue({ data: { data: [{
      resourceId: 91, fileName: 'study.pdf', mimeType: 'application/pdf', fileSize: 1024,
      processingStatus: 'TEXT_EXTRACTED', indexStatus: 'ready',
    }] } })
    mocks.getLatestProjectResearchSession.mockResolvedValue({ data: { data: projectSession } })
    mocks.getLatestResearchSessionForResource.mockResolvedValue({ data: { data: {
      ...projectSession,
      sessionId: 92,
      resourceId: 91,
      analysisGenerationStatus: 'FAILED',
      latestAnalysis: {
        researchSubjects: ['resource 91 participants'], researchTopics: [], aiLiteracyDimensions: [],
        teachingStrategies: [], interventionDuration: null, assessmentTools: [],
        mainFindings: [], limitations: [],
      },
    } } })

    const store = useResearchStore()
    await store.initialize(12)

    expect(mocks.getLatestResearchSessionForResource).toHaveBeenCalledWith(12, 91)
    expect(store.activeSession?.sessionId).toBe(92)
    expect(store.activeAnalysisScope).toBe('RESOURCE')
    expect(store.activeAnalysisSource).toBe('study.pdf')
    expect(store.analysisGenerationStatus).toBe('FAILED')
    expect(store.analysis?.participants).toEqual(['resource 91 participants'])
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
      latestAnalysis: {
        researchSubjects: ['new resource participants'], researchTopics: [],
        aiLiteracyDimensions: [], teachingStrategies: [], interventionDuration: null,
        assessmentTools: [], mainFindings: [], limitations: [],
      },
      analysisGenerationStatus: 'READY',
    } } })

    const store = useResearchStore()
    await store.initialize(12)
    await store.uploadAndProcess(new File(['pdf'], 'new.pdf', { type: 'application/pdf' }))

    expect(mocks.getProjectResearchResources).toHaveBeenCalledTimes(2)
    expect(mocks.createResearchSession).toHaveBeenLastCalledWith(12, 93)
    expect(store.activeSession?.sessionId).toBe(94)
    expect(store.activeSession?.resourceId).toBe(93)
    expect(store.selectedResources).toEqual([93])
    expect(store.analysis?.participants).toEqual(['new resource participants'])
    expect(store.activeAnalysisScope).toBe('RESOURCE')
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

  it('replaces an old evidence draft whenever sendMessage returns a current evidenceCardId', async () => {
    const store = useResearchStore()
    store.currentProject = project
    store.projectSession = { ...projectSession }
    store.evidenceDraft = evidence(5013, 201)
    mocks.sendResearchMessage.mockResolvedValue({ data: { data: {
      userMessage: backendMessage(10, 'USER', '继续分析'),
      assistantMessage: backendMessage(11, 'ASSISTANT', '解析已更新'),
      latestAnalysis: backendAnalysis('最新研究主题'),
      readiness: ready,
      evidenceDraftGenerated: false,
      evidenceCardId: 5014,
    } } })
    mocks.getEvidenceCard.mockResolvedValue({ data: { data: backendEvidence(5014, 202) } })

    await expect(store.sendMessage('继续分析')).resolves.toBe(true)

    expect(mocks.getEvidenceCard).toHaveBeenCalledWith(5014)
    expect(store.evidenceDraft?.evidenceCardId).toBe(5014)
    expect(store.evidenceDraft?.researchAnalysisId).toBe(202)
  })

  it('clears an old evidence draft when analysis changes without a current evidenceCardId', async () => {
    const store = useResearchStore()
    store.currentProject = project
    store.projectSession = { ...projectSession }
    store.evidenceDraft = evidence(5013, 201)
    mocks.sendResearchMessage.mockResolvedValue({ data: { data: {
      userMessage: backendMessage(10, 'USER', '删除关键发现'),
      assistantMessage: backendMessage(11, 'ASSISTANT', '解析已更新'),
      latestAnalysis: backendAnalysis('不完整研究主题'),
      readiness: { ...ready, readinessStatus: 'INCOMPLETE' },
      evidenceDraftGenerated: false,
      evidenceCardId: null,
    } } })

    await expect(store.sendMessage('删除关键发现')).resolves.toBe(true)

    expect(store.evidenceDraft).toBeNull()
    expect(mocks.getEvidenceCard).not.toHaveBeenCalled()
  })

  it('recovers from 40906 and confirms the refreshed card on the next attempt', async () => {
    const store = useResearchStore()
    store.currentProject = project
    store.projectSession = { ...projectSession, evidenceCardId: 5013 } as never
    store.evidenceDraft = evidence(5013, 201)
    mocks.confirmEvidenceCard
      .mockRejectedValueOnce({
        isAxiosError: true,
        response: { status: 409, data: { code: 40906, message: 'stale' } },
      })
      .mockResolvedValueOnce({ data: { data: backendEvidence(5014, 202, 'CONFIRMED') } })
    mocks.getResearchSession.mockResolvedValue({ data: { data: {
      ...projectSession,
      evidenceCardId: 5014,
      messages: [],
      latestAnalysis: backendAnalysis('最新研究主题'),
      readiness: ready,
    } } })
    mocks.getEvidenceCard.mockResolvedValue({ data: { data: backendEvidence(5014, 202) } })

    await expect(store.confirmEvidence()).resolves.toBe(false)
    expect(store.error).toBe('研究解析已更新，证据卡已同步到最新版本，请重新确认。')
    expect(store.evidenceDraft?.evidenceCardId).toBe(5014)
    await expect(store.confirmEvidence()).resolves.toBe(true)
    expect(mocks.confirmEvidenceCard.mock.calls.map(([id]) => id)).toEqual([5013, 5014])
  })
})

const ready = {
  readinessScore: 100,
  readinessStatus: 'READY' as const,
  missingRequiredFields: [],
  missingRecommendedFields: [],
}

function backendMessage(messageId: number, role: 'USER' | 'ASSISTANT', content: string) {
  return { messageId, role, sequenceNo: messageId, content, createdAt: '2026-09-10T00:00:00Z' }
}

function backendAnalysis(topic: string) {
  return {
    researchSubjects: ['五年级学生'], researchTopics: [topic], aiLiteracyDimensions: [],
    teachingStrategies: ['比较来源'], interventionDuration: '8周', assessmentTools: [],
    mainFindings: ['表现提升'], limitations: ['单校样本'],
  }
}

function backendEvidence(evidenceCardId: number, researchAnalysisId: number, cardStatus = 'DRAFT') {
  return {
    evidenceCardId, researchAnalysisId, researchFinding: '表现提升', applicableAudience: '五年级学生',
    recommendedStrategies: ['比较来源'], implementationConditions: ['8周'], teachingImplications: '',
    limitations: '单校样本', source: { resourceId: null, projectId: 12, originalFilename: null, sha256: null },
    cardStatus,
  }
}

function evidence(evidenceCardId: number, researchAnalysisId: number) {
  return {
    evidenceCardId, researchAnalysisId, projectId: 12, resourceId: null, status: 'DRAFT' as const,
    researchFinding: '旧发现', applicableAudience: '五年级学生', recommendedStrategies: [],
    implementationConditions: [], teachingImplications: '', limitations: '',
    sourceDocument: '知识库', sourceTraceId: '',
  }
}
