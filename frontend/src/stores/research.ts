import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { isAxiosError } from 'axios'
import { getProject } from '@/api/projects'
import {
  confirmEvidenceCard as confirmEvidenceCardApi,
  confirmResearchAnalysis as confirmResearchAnalysisApi,
  createResearchSession as createResearchSessionApi,
  extractResearchText as extractResearchTextApi,
  generateEvidenceCard as generateEvidenceCardApi,
  getEvidenceCard as getEvidenceCardApi,
  getResearchSession as getResearchSessionApi,
  getLatestProjectResearchSession as getLatestProjectResearchSessionApi,
  getLatestResourceResearchSession as getLatestResourceResearchSessionApi,
  getLatestResearchSessionForResource as getLatestResearchSessionForResourceApi,
  getProjectResearchResources as getProjectResearchResourcesApi,
  sendResearchMessage as sendResearchMessageApi,
  updateEvidenceCard as updateEvidenceCardApi,
  updateResearchAnalysis as updateResearchAnalysisApi,
  uploadResearchResource as uploadResearchResourceApi,
  type BackendAnalysisPayload,
  type BackendChatMessage,
  type BackendEvidenceCard,
  type BackendSessionPayload,
} from '@/api/research'
import { researchMockService } from '@/mocks/researchMockService'
import type {
  AnalysisGenerationStatus,
  EvidenceCard,
  EvidenceCardEditableFields,
  ReadinessStatus,
  ResearchAnalysis,
  ResearchAnalysisContentKey,
  ResearchChatMessage,
  ResearchChatSession,
  ResearchProjectContext,
  ResearchResource,
  SendResearchMessageResult,
  UploadStatus,
} from '@/types/research'

const useMock = import.meta.env.VITE_RESEARCH_USE_MOCK === 'true'
const sessionStorageKey = (projectId: number) => `research-session:${projectId}`
const resourcesStorageKey = (projectId: number) => `research-resources:${projectId}`
const activeScopeStorageKey = (projectId: number) => `research-active-scope:${projectId}`

type ActiveScopeState = { scope: 'PROJECT' | 'RESOURCE'; resourceId?: number }

function loadActiveScope(projectId: number): ActiveScopeState | null {
  try {
    const value = JSON.parse(localStorage.getItem(activeScopeStorageKey(projectId)) ?? 'null') as ActiveScopeState | null
    if (!value || !['PROJECT', 'RESOURCE'].includes(value.scope)) return null
    if (value.scope === 'RESOURCE' && (!Number.isInteger(value.resourceId) || Number(value.resourceId) <= 0)) return null
    return value
  } catch {
    return null
  }
}

function backendAnalysis(
  payload: BackendAnalysisPayload | null,
  metadata: Pick<BackendSessionPayload, 'fieldSources' | 'teacherConfirmed' | 'version' | 'analysisGenerationStatus'> = {},
): ResearchAnalysis | null {
  if (!payload) return null
  return {
    participants: payload.researchSubjects,
    researchTopics: payload.researchTopics,
    aiLiteracyDimensions: payload.aiLiteracyDimensions,
    teachingStrategies: payload.teachingStrategies,
    intervention: payload.interventionDuration,
    assessmentTools: payload.assessmentTools,
    mainFindings: payload.mainFindings,
    limitations: payload.limitations,
    teachingImplications: payload.teachingImplications ?? null,
    fieldSources: metadata.fieldSources,
    teacherConfirmed: metadata.teacherConfirmed,
    version: metadata.version,
    generationStatus: metadata.analysisGenerationStatus ?? undefined,
  }
}

function backendMessage(payload: BackendChatMessage): ResearchChatMessage {
  return { ...payload, messageType: 'TEXT', sendStatus: 'SENT' }
}

function backendSession(payload: BackendSessionPayload): ResearchChatSession {
  return {
    sessionId: payload.sessionId,
    projectId: payload.projectId,
    resourceId: payload.resourceId,
    title: payload.title,
    status: payload.status,
    createdAt: payload.createdAt,
    updatedAt: payload.updatedAt,
  }
}

function backendEvidence(payload: BackendEvidenceCard): EvidenceCard {
  return {
    evidenceCardId: payload.evidenceCardId,
    projectId: payload.source.projectId,
    resourceId: payload.source.resourceId,
    researchAnalysisId: payload.researchAnalysisId,
    status: payload.cardStatus,
    researchFinding: payload.researchFinding,
    applicableAudience: payload.applicableAudience,
    recommendedStrategies: payload.recommendedStrategies,
    implementationConditions: payload.implementationConditions,
    teachingImplications: payload.teachingImplications,
    limitations: payload.limitations,
    sourceDocument: payload.source.originalFilename ?? payload.source.sourceLabel ?? '讯飞研教智联知识库',
    sourceTraceId: payload.source.sha256 ?? payload.source.chunkId ?? '',
    confirmedBy: payload.confirmedBy,
    confirmedAt: payload.confirmedAt,
  }
}

function messageFromError(error: unknown, fallback: string) {
  if (isAxiosError<{ message?: string; detail?: { message?: string } }>(error)) {
    return error.response?.data?.detail?.message ?? error.response?.data?.message ?? fallback
  }
  return error instanceof Error ? error.message : fallback
}

function isRequestTimeout(error: unknown): boolean {
  return isAxiosError(error)
    && (error.code === 'ECONNABORTED'
      || error.code === 'ETIMEDOUT'
      || error.message.toLowerCase().includes('timeout'))
}

class IndexingTimeoutError extends Error {
  constructor() {
    super('文本解析已完成，知识索引仍在后台构建，请稍后刷新。')
    this.name = 'IndexingTimeoutError'
  }
}

class AnalysisStillProcessingError extends Error {
  constructor() {
    super('研究对话仍在初始化，请稍后刷新')
    this.name = 'AnalysisStillProcessingError'
  }
}

function isStaleEvidenceError(error: unknown): boolean {
  if (!isAxiosError<{ code?: number; detail?: { code?: number } }>(error)) return false
  const code = error.response?.data?.code ?? error.response?.data?.detail?.code
  return error.response?.status === 409 && code === 40906
}

export const useResearchStore = defineStore('research', () => {
  const currentProject = ref<ResearchProjectContext | null>(null)
  const projectSession = ref<ResearchChatSession | null>(null)
  const resourceSession = ref<ResearchChatSession | null>(null)
  const resources = ref<ResearchResource[]>([])
  const selectedResources = ref<number[]>([])
  const messages = ref<ResearchChatMessage[]>([])
  const analysis = ref<ResearchAnalysis | null>(null)
  const evidenceDraft = ref<EvidenceCard | null>(null)
  const readinessScore = ref(0)
  const readinessStatus = ref<ReadinessStatus>('INCOMPLETE')
  const missingRequiredFields = ref<string[]>([])
  const missingRecommendedFields = ref<string[]>([])
  const analysisGenerationStatus = ref<AnalysisGenerationStatus | null>(null)
  const uploadStatus = ref<UploadStatus | 'IDLE'>('IDLE')
  const isUploading = ref(false)
  const isExtracting = ref(false)
  const isAnalyzing = ref(false)
  const isSending = ref(false)
  const isUpdatingAnalysis = ref(false)
  const isGeneratingEvidence = ref(false)
  const isUpdatingEvidence = ref(false)
  const isConfirmingEvidence = ref(false)
  const loading = ref(false)
  const error = ref('')
  type WorkspaceState = {
    session: ResearchChatSession
    messages: ResearchChatMessage[]
    analysis: ResearchAnalysis | null
    readiness: Parameters<typeof setReadiness>[0] | null
    evidenceDraft: EvidenceCard | null
    analysisGenerationStatus: AnalysisGenerationStatus | null
  }
  const projectWorkspace = ref<WorkspaceState | null>(null)
  const resourceWorkspaces = new Map<number, WorkspaceState>()
  const activeWorkspace = ref<WorkspaceState | null>(null)

  const selectedResourceItems = computed(() =>
    resources.value.filter((resource) => selectedResources.value[0] === resource.resourceId),
  )
  const activeSession = computed(() => activeWorkspace.value?.session ?? projectSession.value)
  const activeScopeLabel = computed(() =>
    activeSession.value?.resourceId == null
      ? '当前研究依据：项目知识库（全部已就绪研究资源）'
      : `当前研究依据：${selectedResourceItems.value[0]?.fileName ?? '已选资源'}`,
  )
  const activeAnalysisScope = computed(() => activeSession.value?.resourceId == null ? 'PROJECT' : 'RESOURCE')
  const activeAnalysisSource = computed(() =>
    activeAnalysisScope.value === 'RESOURCE'
      ? selectedResourceItems.value[0]?.fileName ?? '已选研究资源'
      : '全部已就绪研究资源',
  )
  const resourceCount = computed(() => resources.value.length)
  const evidenceCount = computed(() => (evidenceDraft.value ? 1 : 0))

  function setReadiness(value: {
    readinessScore: number
    readinessStatus: ReadinessStatus
    missingRequiredFields: string[]
    missingRecommendedFields: string[]
  }) {
    readinessScore.value = value.readinessScore
    readinessStatus.value = value.readinessStatus
    missingRequiredFields.value = [...value.missingRequiredFields]
    missingRecommendedFields.value = [...value.missingRecommendedFields]
  }

  function resetWorkspace() {
    projectSession.value = null
    resourceSession.value = null
    resources.value = []
    selectedResources.value = []
    messages.value = []
    analysis.value = null
    evidenceDraft.value = null
    readinessScore.value = 0
    readinessStatus.value = 'INCOMPLETE'
    missingRequiredFields.value = []
    missingRecommendedFields.value = []
    analysisGenerationStatus.value = null
    uploadStatus.value = 'IDLE'
    error.value = ''
    projectWorkspace.value = null
    resourceWorkspaces.clear()
    activeWorkspace.value = null
  }

  function addSystemMessage(content: string, messageType: ResearchChatMessage['messageType'] = 'PROCESS') {
    messages.value.push({
      messageId: `system-${Date.now()}-${messages.value.length}`,
      role: 'SYSTEM',
      messageType,
      content,
      createdAt: new Date().toISOString(),
      sendStatus: 'SENT',
    })
  }

  function activateWorkspace(state: WorkspaceState) {
    activeWorkspace.value = state
    selectedResources.value = state.session.resourceId === null ? [] : [state.session.resourceId]
    messages.value = [...state.messages]
    analysis.value = state.analysis
    if (state.readiness) setReadiness(state.readiness)
    else setReadiness({ readinessScore: 0, readinessStatus: 'INCOMPLETE', missingRequiredFields: [], missingRecommendedFields: [] })
    evidenceDraft.value = state.evidenceDraft
    analysisGenerationStatus.value = state.analysisGenerationStatus
  }

  function applySnapshot(snapshot: {
    session: ResearchChatSession
    resources?: ResearchResource[]
    messages: ResearchChatMessage[]
    analysis?: ResearchAnalysis | null
    readiness?: Parameters<typeof setReadiness>[0] | null
    evidenceDraft?: EvidenceCard | null
    analysisGenerationStatus?: AnalysisGenerationStatus | null
  }, options: { activate?: boolean } = {}) {
    const state: WorkspaceState = {
      session: snapshot.session,
      messages: snapshot.messages,
      analysis: snapshot.analysis ?? null,
      readiness: snapshot.readiness ?? null,
      evidenceDraft: snapshot.evidenceDraft ?? null,
      analysisGenerationStatus: snapshot.analysisGenerationStatus ?? null,
    }
    if (snapshot.session.resourceId === null) {
      projectSession.value = snapshot.session
      projectWorkspace.value = state
    } else {
      resourceSession.value = snapshot.session
      resourceWorkspaces.set(snapshot.session.resourceId, state)
    }
    if (snapshot.resources) resources.value = snapshot.resources
    if (options.activate === false) return
    activateWorkspace(state)
  }

  function cacheActiveWorkspace() {
    const session = activeSession.value
    if (!session) return
    const state: WorkspaceState = {
      session,
      messages: [...messages.value], analysis: analysis.value,
      readiness: {
        readinessScore: readinessScore.value, readinessStatus: readinessStatus.value,
        missingRequiredFields: [...missingRequiredFields.value],
        missingRecommendedFields: [...missingRecommendedFields.value],
      },
      evidenceDraft: evidenceDraft.value,
      analysisGenerationStatus: analysisGenerationStatus.value,
    }
    activeWorkspace.value = state
    const resourceId = session.resourceId
    if (resourceId == null) projectWorkspace.value = state
    else resourceWorkspaces.set(resourceId, state)
  }

  async function waitForIndexReady(projectId: number, resourceId: number) {
    const deadline = Date.now() + 120_000
    while (Date.now() < deadline) {
      let latest: ResearchResource[]
      try {
        latest = (await getProjectResearchResourcesApi(projectId)).data.data
      } catch {
        await new Promise((resolve) => window.setTimeout(resolve, 900))
        continue
      }
      const refreshed = latest.find((item) => item.resourceId === resourceId)
      if (!refreshed) throw new Error('上传的研究资源已不存在')
      const localIndex = resources.value.findIndex((item) => item.resourceId === resourceId)
      if (localIndex >= 0) resources.value.splice(localIndex, 1, refreshed)
      if (refreshed.indexStatus === 'ready') return refreshed
      if (refreshed.indexStatus === 'error') {
        throw new Error(refreshed.errorMessage || '论文知识索引构建失败')
      }
      await new Promise((resolve) => window.setTimeout(resolve, 900))
    }
    throw new IndexingTimeoutError()
  }

  function updateResourceFromBackend(refreshed: ResearchResource): ResearchResource {
    const localIndex = resources.value.findIndex((item) => item.resourceId === refreshed.resourceId)
    const localResource = localIndex >= 0 ? resources.value[localIndex] : undefined
    if (localResource) Object.assign(localResource, refreshed)
    return localResource ?? refreshed
  }

  async function waitForTextExtraction(projectId: number, resourceId: number) {
    const deadline = Date.now() + 120_000
    while (Date.now() < deadline) {
      try {
        const latest = (await getProjectResearchResourcesApi(projectId)).data.data
        const refreshed = latest.find((item) => item.resourceId === resourceId)
        if (!refreshed) throw new Error('上传的研究资源已不存在')
        const resource = updateResourceFromBackend(refreshed)
        if (resource.processingStatus === 'FAILED') {
          throw new Error(resource.errorMessage || '文本提取失败')
        }
        if (resource.indexStatus === 'error') {
          throw new Error(resource.errorMessage || '论文知识索引构建失败')
        }
        if (resource.indexStatus === 'ready' || resource.processingStatus === 'TEXT_EXTRACTED') {
          return resource
        }
      } catch (pollError) {
        if (!isAxiosError(pollError)) throw pollError
      }
      await new Promise((resolve) => window.setTimeout(resolve, 900))
    }
    throw new IndexingTimeoutError()
  }

  async function extractTextWithRecovery(projectId: number, resource: ResearchResource) {
    try {
      const payload = (await extractResearchTextApi(resource.resourceId)).data.data
      if (payload.processingStatus === 'FAILED') {
        throw new Error('文本提取失败')
      }
      Object.assign(resource, payload)
      return resource
    } catch (requestError) {
      if (!isRequestTimeout(requestError)) throw requestError
      addSystemMessage('文本解析仍在后台处理中，正在确认处理状态……')
      return waitForTextExtraction(projectId, resource.resourceId)
    }
  }

  async function createResourceSessionWithRecovery(projectId: number, resourceId: number) {
    try {
      const payload = (await createResearchSessionApi(projectId, resourceId)).data.data
      return payload
    } catch (requestError) {
      if (!isRequestTimeout(requestError)) throw requestError
      addSystemMessage('研究对话仍在初始化，正在确认会话状态……')
    }

    const deadline = Date.now() + 120_000
    while (Date.now() < deadline) {
      try {
        const payload = (await getLatestResearchSessionForResourceApi(
          projectId,
          resourceId,
        )).data.data
        return payload
      } catch (pollError) {
        if (!isAxiosError(pollError)) throw pollError
      }
      await new Promise((resolve) => window.setTimeout(resolve, 900))
    }
    throw new AnalysisStillProcessingError()
  }

  async function loadEvidenceDraft(evidenceCardId: number | null | undefined): Promise<EvidenceCard | null> {
    if (!evidenceCardId) return null
    return backendEvidence((await getEvidenceCardApi(evidenceCardId)).data.data)
  }

  async function refreshActiveResearchState() {
    const session = activeSession.value
    if (!session || useMock) return
    const payload = (await getResearchSessionApi(session.sessionId)).data.data
    const currentEvidence = await loadEvidenceDraft(payload.evidenceCardId)
    applySnapshot({
      session: backendSession(payload),
      messages: payload.messages.map(backendMessage),
      analysis: backendAnalysis(payload.latestAnalysis, payload),
      readiness: payload.readiness,
      evidenceDraft: currentEvidence,
      analysisGenerationStatus: payload.analysisGenerationStatus ?? null,
    })
  }

  async function initialize(projectId: number) {
    loading.value = true
    resetWorkspace()
    try {
      const response = await getProject(projectId)
      const project = response.data.data
      currentProject.value = {
        projectId: project.projectId,
        title: project.title,
        topic: project.topic,
        grade: project.grade,
        classHours: project.classHours,
      }
      if (useMock) {
        const snapshot = await researchMockService.getWorkspace(projectId)
        if (snapshot) applySnapshot(snapshot)
        return
      }

      resources.value = (await getProjectResearchResourcesApi(projectId)).data.data
      let sessionResponse
      try {
        // The database is authoritative. A browser-local session id may have
        // been deleted, or may belong to an older project snapshot.
        sessionResponse = await getLatestProjectResearchSessionApi(projectId)
      } catch (sessionError) {
        if (isAxiosError(sessionError) && sessionError.response?.status === 404) {
          sessionResponse = await createResearchSessionApi(projectId, null)
        } else {
          throw sessionError
        }
      }
      const payload = sessionResponse.data.data
      const projectEvidence = await loadEvidenceDraft(payload.evidenceCardId)
      applySnapshot({
        session: backendSession(payload),
        messages: payload.messages.map(backendMessage),
        analysis: backendAnalysis(payload.latestAnalysis, payload),
        readiness: payload.readiness,
        evidenceDraft: projectEvidence,
        analysisGenerationStatus: payload.analysisGenerationStatus ?? null,
      })

      try {
        const savedScope = loadActiveScope(projectId)
        const resourcePayload = savedScope?.scope === 'RESOURCE' && savedScope.resourceId
          ? (await getLatestResearchSessionForResourceApi(projectId, savedScope.resourceId)).data.data
          : (await getLatestResourceResearchSessionApi(projectId)).data.data
        const resourceEvidence = await loadEvidenceDraft(resourcePayload.evidenceCardId)
        applySnapshot({
          session: backendSession(resourcePayload),
          messages: resourcePayload.messages.map(backendMessage),
          analysis: backendAnalysis(resourcePayload.latestAnalysis, resourcePayload),
          readiness: resourcePayload.readiness,
          evidenceDraft: resourceEvidence,
          analysisGenerationStatus: resourcePayload.analysisGenerationStatus ?? null,
        }, { activate: savedScope?.scope === 'RESOURCE' })
      } catch (resourceSessionError) {
        if (!isAxiosError(resourceSessionError) || resourceSessionError.response?.status !== 404) {
          throw resourceSessionError
        }
      }
      localStorage.setItem(sessionStorageKey(projectId), String(payload.sessionId))
    } catch (requestError) {
      error.value = messageFromError(requestError, '研教智联工作台加载失败')
      throw requestError
    } finally {
      loading.value = false
    }
  }

  async function uploadAndProcess(file: File) {
    const project = currentProject.value
    if (!project || isUploading.value) return
    error.value = ''
    isUploading.value = true
    uploadStatus.value = 'UPLOADING'
    const placeholderId = -Date.now()
    let processingStage: 'upload' | 'text-extraction' | 'indexing' | 'session-initialization' = 'upload'
    let uploadedResource: ResearchResource | null = null
    resources.value.push({
      resourceId: placeholderId,
      fileName: file.name,
      mimeType: file.type,
      fileSize: file.size,
      processingStatus: 'UPLOADING',
    })
    messages.value.push({
      messageId: `file-${placeholderId}`,
      role: 'SYSTEM',
      messageType: 'FILE',
      content: file.name,
      resourceId: placeholderId,
      createdAt: new Date().toISOString(),
      sendStatus: 'SENDING',
    })
    try {
      const uploaded = useMock
        ? await researchMockService.uploadResource(project.projectId, file)
        : (await uploadResearchResourceApi(project.projectId, file)).data.data
      uploadedResource = uploaded
      const placeholderIndex = resources.value.findIndex((item) => item.resourceId === placeholderId)
      if (placeholderIndex >= 0) resources.value.splice(placeholderIndex, 1, uploaded)
      uploadStatus.value = 'UPLOADED'
      addSystemMessage('文件上传完成')
      const fileMessage = messages.value.find((message) => message.resourceId === placeholderId)
      if (fileMessage) {
        fileMessage.messageId = `file-${uploaded.resourceId}`
        fileMessage.resourceId = uploaded.resourceId
        fileMessage.content = uploaded.fileName
        fileMessage.sendStatus = 'SENT'
      }

      isExtracting.value = true
      processingStage = 'text-extraction'
      uploadStatus.value = 'TEXT_EXTRACTING'
      uploaded.processingStatus = 'TEXT_EXTRACTING'
      addSystemMessage('正在提取论文文本…')
      const extracted = useMock
        ? await researchMockService.extractText(project.projectId, uploaded.resourceId)
        : await extractTextWithRecovery(project.projectId, uploaded)
      Object.assign(uploaded, extracted)
      uploadStatus.value = 'TEXT_EXTRACTED'
      addSystemMessage('文本提取已完成')

      if (!useMock) {
        processingStage = 'indexing'
        if (uploaded.indexStatus !== 'ready') {
          uploadStatus.value = 'INDEXING'
          uploaded.indexStatus = 'indexing'
          addSystemMessage('正在进行论文向量化与建立检索索引…')
          Object.assign(uploaded, await waitForIndexReady(project.projectId, uploaded.resourceId))
          addSystemMessage('论文向量化与检索已完成')
        }
      }
      processingStage = 'session-initialization'
      cacheActiveWorkspace()
      if (useMock) {
        const snapshot = await researchMockService.createSession(
          project.projectId,
          uploaded.resourceId,
          project.topic,
        )
        applySnapshot(snapshot)
      } else {
        const payload = await createResourceSessionWithRecovery(
          project.projectId,
          uploaded.resourceId,
        )
        const resourceEvidence = await loadEvidenceDraft(payload.evidenceCardId)
        applySnapshot({
          session: backendSession(payload), messages: payload.messages.map(backendMessage),
          analysis: backendAnalysis(payload.latestAnalysis, payload), readiness: payload.readiness,
          evidenceDraft: resourceEvidence,
          analysisGenerationStatus: payload.analysisGenerationStatus ?? null,
        })
        localStorage.setItem(activeScopeStorageKey(project.projectId), JSON.stringify({
          scope: 'RESOURCE', resourceId: uploaded.resourceId,
        }))
        localStorage.setItem(resourcesStorageKey(project.projectId), JSON.stringify(resources.value))
      }
      addSystemMessage('论文知识库已就绪，可通过下方研究探索逐步完善研究解析')
      const completedResource = resources.value.find((item) => item.resourceId === uploaded.resourceId)
      if (completedResource) {
        completedResource.processingStatus = 'TEXT_EXTRACTED'
        completedResource.errorMessage = null
      }
      uploadStatus.value = 'TEXT_EXTRACTED'
    } catch (requestError) {
      const resource = uploadedResource
        ? resources.value.find((item) => item.resourceId === uploadedResource?.resourceId) ?? uploadedResource
        : resources.value.find((item) => item.resourceId === placeholderId)
      if (requestError instanceof IndexingTimeoutError) {
        if (resource) {
          resource.errorMessage = null
          if (resource.processingStatus !== 'TEXT_EXTRACTING') {
            resource.processingStatus = 'TEXT_EXTRACTED'
            resource.indexStatus = resource.indexStatus === 'ready' ? 'ready' : 'indexing'
          }
        }
        uploadStatus.value = resource?.processingStatus === 'TEXT_EXTRACTING' ? 'TEXT_EXTRACTING' : 'INDEXING'
        error.value = ''
        addSystemMessage(requestError.message)
        return
      }
      if (requestError instanceof AnalysisStillProcessingError) {
        if (resource) {
          resource.processingStatus = 'TEXT_EXTRACTED'
          resource.indexStatus = 'ready'
          resource.errorMessage = null
        }
        uploadStatus.value = 'TEXT_EXTRACTED'
        error.value = ''
        addSystemMessage(requestError.message)
        return
      }
      if (processingStage === 'session-initialization') {
        if (resource) {
          resource.processingStatus = 'TEXT_EXTRACTED'
          resource.indexStatus = 'ready'
          resource.errorMessage = null
        }
        uploadStatus.value = 'TEXT_EXTRACTED'
        error.value = messageFromError(requestError, '研究对话初始化失败，请稍后重试')
        addSystemMessage(error.value)
        return
      }
      if (resource) {
        if (processingStage === 'indexing') {
          resource.processingStatus = 'TEXT_EXTRACTED'
          resource.indexStatus = requestError instanceof IndexingTimeoutError ? 'indexing' : 'error'
        } else {
          resource.processingStatus = 'FAILED'
        }
        resource.errorMessage = messageFromError(
          requestError,
          processingStage === 'upload'
            ? '文件上传失败'
            : processingStage === 'text-extraction'
              ? '文本提取失败'
              : processingStage === 'indexing'
                ? '知识索引构建失败'
                : '研究对话初始化失败',
        )
      }
      uploadStatus.value = 'FAILED'
      error.value = resource?.errorMessage ?? '研究资源处理失败'
      addSystemMessage(error.value)
    } finally {
      isUploading.value = false
      isExtracting.value = false
      isAnalyzing.value = false
    }
  }

  async function retryResource(resourceId: number) {
    const project = currentProject.value
    const resource = resources.value.find((item) => item.resourceId === resourceId)
    if (!project || !resource || isExtracting.value || isAnalyzing.value) return
    if (resourceId < 0) {
      error.value = '上传未完成，请重新选择原始文件'
      return
    }
    const sessionOnly = resource.indexStatus === 'ready'
      && ['TEXT_EXTRACTED', 'REVIEWED', 'CARD_READY'].includes(resource.processingStatus)
    isExtracting.value = !sessionOnly
    error.value = ''
    if (!sessionOnly) resource.processingStatus = 'TEXT_EXTRACTING'
    let processingStage: 'text-extraction' | 'indexing' | 'session-initialization' = sessionOnly ? 'session-initialization' : 'text-extraction'
    addSystemMessage(sessionOnly ? '正在准备研究对话…' : '正在重新提取论文文本…')
    try {
      if (sessionOnly) {
        if (useMock) {
          const snapshot = await researchMockService.createSession(project.projectId, resourceId, project.topic)
          applySnapshot(snapshot)
        } else {
          const payload = await createResourceSessionWithRecovery(project.projectId, resourceId)
          const resourceEvidence = await loadEvidenceDraft(payload.evidenceCardId)
          applySnapshot({
            session: backendSession(payload), messages: payload.messages.map(backendMessage),
            analysis: backendAnalysis(payload.latestAnalysis, payload), readiness: payload.readiness,
            evidenceDraft: resourceEvidence,
            analysisGenerationStatus: payload.analysisGenerationStatus ?? null,
          })
          localStorage.setItem(activeScopeStorageKey(project.projectId), JSON.stringify({
            scope: 'RESOURCE', resourceId,
          }))
        }
        addSystemMessage('论文知识库已就绪，可通过下方研究探索逐步完善研究解析')
        return
      }
      const extracted = useMock
        ? await researchMockService.extractText(project.projectId, resourceId)
        : await extractTextWithRecovery(project.projectId, resource)
      Object.assign(resource, extracted)
      resource.processingStatus = 'TEXT_EXTRACTED'
      addSystemMessage('文本提取已完成')
      if (useMock) {
        processingStage = 'session-initialization'
        const snapshot = await researchMockService.createSession(project.projectId, resourceId, project.topic)
        applySnapshot(snapshot)
      } else {
        processingStage = 'indexing'
        if (resource.indexStatus !== 'ready') {
          resource.indexStatus = 'indexing'
          addSystemMessage('正在进行论文向量化与建立检索索引…')
          Object.assign(resource, await waitForIndexReady(project.projectId, resourceId))
          addSystemMessage('论文向量化与检索已完成')
        }
        processingStage = 'session-initialization'
        const payload = await createResourceSessionWithRecovery(project.projectId, resourceId)
        const resourceEvidence = await loadEvidenceDraft(payload.evidenceCardId)
        applySnapshot({
          session: backendSession(payload), messages: payload.messages.map(backendMessage),
          analysis: backendAnalysis(payload.latestAnalysis, payload), readiness: payload.readiness,
          evidenceDraft: resourceEvidence,
          analysisGenerationStatus: payload.analysisGenerationStatus ?? null,
        })
        localStorage.setItem(activeScopeStorageKey(project.projectId), JSON.stringify({
          scope: 'RESOURCE', resourceId,
        }))
      }
      addSystemMessage('论文知识库已就绪，可通过下方研究探索逐步完善研究解析')
    } catch (requestError) {
      const currentResource = resources.value.find((item) => item.resourceId === resourceId) ?? resource
      if (requestError instanceof IndexingTimeoutError) {
        currentResource.errorMessage = null
        if (currentResource.processingStatus !== 'TEXT_EXTRACTING') {
          currentResource.processingStatus = 'TEXT_EXTRACTED'
          currentResource.indexStatus = currentResource.indexStatus === 'ready' ? 'ready' : 'indexing'
        }
        error.value = ''
        addSystemMessage(requestError.message)
        return
      }
      if (requestError instanceof AnalysisStillProcessingError) {
        currentResource.processingStatus = 'TEXT_EXTRACTED'
        currentResource.indexStatus = 'ready'
        currentResource.errorMessage = null
        error.value = ''
        addSystemMessage(requestError.message)
        return
      }
      if (processingStage === 'session-initialization') {
        currentResource.processingStatus = 'TEXT_EXTRACTED'
        currentResource.indexStatus = 'ready'
        currentResource.errorMessage = null
        error.value = messageFromError(requestError, '研究对话初始化失败，请稍后重试')
        addSystemMessage(error.value)
        return
      }
      if (processingStage === 'indexing') {
        currentResource.processingStatus = 'TEXT_EXTRACTED'
        currentResource.indexStatus = requestError instanceof IndexingTimeoutError ? 'indexing' : 'error'
      } else {
        currentResource.processingStatus = 'FAILED'
      }
      currentResource.errorMessage = messageFromError(
        requestError,
        processingStage === 'text-extraction'
          ? '文本提取失败'
          : processingStage === 'indexing'
            ? '知识索引构建失败'
            : 'AI研究解析失败',
      )
      error.value = currentResource.errorMessage
    } finally {
      isExtracting.value = false
      isAnalyzing.value = false
    }
  }

  async function sendMessage(content: string, retryMessageId?: number | string, analysisTargetField?: ResearchAnalysisContentKey): Promise<boolean> {
    const project = currentProject.value
    const normalizedContent = content.trim()
    if (!project) {
      error.value = '当前教学项目不可用，请先选择项目'
      return false
    }
    const session = activeSession.value
    if (!session) {
      error.value = '研教对话会话尚未准备好，请重新加载页面'
      return false
    }
    if (isSending.value || !normalizedContent) return false
    isSending.value = true
    error.value = ''
    const temporaryId = retryMessageId ?? `pending-${Date.now()}`
    const existing = messages.value.find((message) => message.messageId === temporaryId)
    if (existing) existing.sendStatus = 'SENDING'
    else {
      messages.value.push({
        messageId: temporaryId,
        role: 'USER',
        messageType: 'TEXT',
        content: normalizedContent,
        createdAt: new Date().toISOString(),
        sendStatus: 'SENDING',
      })
    }
    try {
      let normalized: SendResearchMessageResult
      if (useMock) {
        normalized = await researchMockService.sendMessage(project.projectId, normalizedContent)
      } else {
        const response = analysisTargetField
          ? await sendResearchMessageApi(session.sessionId, normalizedContent, analysisTargetField)
          : await sendResearchMessageApi(session.sessionId, normalizedContent)
        const payload = response.data.data
        normalized = {
          userMessage: backendMessage(payload.userMessage),
          assistantMessage: backendMessage(payload.assistantMessage),
          updatedAnalysis: backendAnalysis(payload.latestAnalysis, payload),
          readiness: payload.readiness,
          evidenceDraftGenerated: payload.evidenceDraftGenerated ?? false,
          evidenceCardId: payload.evidenceCardId ?? null,
        }
      }
      const pendingIndex = messages.value.findIndex((message) => message.messageId === temporaryId)
      if (pendingIndex >= 0) messages.value.splice(pendingIndex, 1, normalized.userMessage)
      messages.value.push(normalized.assistantMessage)
      if (normalized.updatedAnalysis) {
        analysis.value = normalized.updatedAnalysis
        analysisGenerationStatus.value = normalized.updatedAnalysis.generationStatus ?? 'READY'
      }
      if (normalized.readiness) setReadiness(normalized.readiness)
      if (normalized.evidenceCardId) {
        evidenceDraft.value = useMock
          ? await researchMockService.getEvidenceCard(project.projectId)
          : await loadEvidenceDraft(normalized.evidenceCardId)
      } else if (normalized.updatedAnalysis) {
        evidenceDraft.value = null
      }
      cacheActiveWorkspace()
      return true
    } catch (requestError) {
      const failed = messages.value.find((message) => message.messageId === temporaryId)
      if (failed) failed.sendStatus = 'FAILED'
      error.value = messageFromError(requestError, '消息发送失败')
      return false
    } finally {
      isSending.value = false
      isGeneratingEvidence.value = false
    }
  }

  async function updateAnalysis(updated: ResearchAnalysis) {
    const project = currentProject.value
    const session = activeSession.value
    if (!project || !session || isUpdatingAnalysis.value) return false
    isUpdatingAnalysis.value = true
    error.value = ''
    const hadEvidenceDraft = Boolean(evidenceDraft.value)
    try {
      if (useMock) {
        const result = await researchMockService.updateAnalysis(project.projectId, updated)
        analysis.value = result.analysis
        analysisGenerationStatus.value = 'READY'
        setReadiness(result.readiness)
        evidenceDraft.value = null
      } else {
        const response = await updateResearchAnalysisApi(session.sessionId, updated)
        const data = response.data.data
        analysis.value = {
          ...data.latestAnalysis,
          fieldSources: data.fieldSources,
          teacherConfirmed: data.teacherConfirmed,
          version: data.version,
          generationStatus: data.generationStatus,
        }
        analysisGenerationStatus.value = data.generationStatus
        setReadiness(response.data.data.readiness)
        evidenceDraft.value = null
      }
      addSystemMessage(
        hadEvidenceDraft
          ? '研究解析已更新，请重新生成当前版本证据卡。'
          : '研究解析已更新',
        'ANALYSIS_UPDATE',
      )
      return true
    } catch (requestError) {
      error.value = messageFromError(requestError, '研究解析保存失败')
      return false
    } finally {
      isUpdatingAnalysis.value = false
    }
  }

  async function confirmAnalysis() {
    const project = currentProject.value
    const session = activeSession.value
    if (!project || !session || readinessStatus.value !== 'READY') return false
    try {
      if (useMock) {
        const result = await researchMockService.confirmAnalysis(project.projectId)
        analysis.value = result.analysis
        setReadiness(result.readiness)
      } else {
        const response = await confirmResearchAnalysisApi(session.sessionId)
        const data = response.data.data
        analysis.value = {
          ...data.latestAnalysis,
          fieldSources: data.fieldSources,
          teacherConfirmed: data.teacherConfirmed,
          version: data.version,
          generationStatus: data.generationStatus,
        }
        analysisGenerationStatus.value = data.generationStatus
        setReadiness(data.readiness)
      }
      return true
    } catch (requestError) {
      error.value = messageFromError(requestError, '研究解析确认失败')
      return false
    }
  }

  async function generateEvidenceCard() {
    const project = currentProject.value
    const session = activeSession.value
    if (!project || !session || !analysis.value || isGeneratingEvidence.value) return false
    const recognizedCount = [
      analysis.value.researchTopics, analysis.value.participants, analysis.value.aiLiteracyDimensions,
      analysis.value.teachingStrategies, analysis.value.intervention, analysis.value.assessmentTools,
      analysis.value.mainFindings, analysis.value.limitations, analysis.value.teachingImplications,
    ].filter((value) => Array.isArray(value) ? value.length > 0 : Boolean(value?.trim())).length
    if (recognizedCount < 6) {
      error.value = '至少完成6项研究解析后才能生成证据卡。'
      return false
    }
    isGeneratingEvidence.value = true
    error.value = ''
    try {
      evidenceDraft.value = useMock
        ? await researchMockService.generateEvidenceCard(project.projectId)
        : backendEvidence((await generateEvidenceCardApi(session.sessionId)).data.data)
      addSystemMessage('证据卡草稿已生成', 'EVIDENCE_DRAFT')
      cacheActiveWorkspace()
      return true
    } catch (requestError) {
      error.value = messageFromError(requestError, '证据卡生成失败')
      return false
    } finally {
      isGeneratingEvidence.value = false
    }
  }

  async function updateEvidence(payload: EvidenceCardEditableFields) {
    const project = currentProject.value
    const evidence = evidenceDraft.value
    if (!project || !evidence || isUpdatingEvidence.value) return false
    isUpdatingEvidence.value = true
    try {
      evidenceDraft.value = useMock
        ? await researchMockService.updateEvidenceCard(project.projectId, payload)
        : backendEvidence((await updateEvidenceCardApi(evidence.evidenceCardId, payload)).data.data)
      return true
    } catch (requestError) {
      error.value = messageFromError(requestError, '证据卡保存失败')
      return false
    } finally {
      isUpdatingEvidence.value = false
    }
  }

  async function confirmEvidence() {
    const project = currentProject.value
    const evidence = evidenceDraft.value
    if (!project || !evidence || isConfirmingEvidence.value) return false
    isConfirmingEvidence.value = true
    try {
      evidenceDraft.value = useMock
        ? await researchMockService.confirmEvidenceCard(project.projectId)
        : backendEvidence((await confirmEvidenceCardApi(evidence.evidenceCardId)).data.data)
      addSystemMessage('已保存为正式研究证据', 'EVIDENCE_DRAFT')
      return true
    } catch (requestError) {
      if (isStaleEvidenceError(requestError)) {
        evidenceDraft.value = null
        cacheActiveWorkspace()
        try {
          await refreshActiveResearchState()
        } catch {
          evidenceDraft.value = null
          cacheActiveWorkspace()
        }
        error.value = '研究解析已更新，证据卡已同步到最新版本，请重新确认。'
        return false
      }
      error.value = messageFromError(requestError, '证据卡确认失败')
      return false
    } finally {
      isConfirmingEvidence.value = false
    }
  }

  function removeSelectedResource(resourceId: number) {
    selectedResources.value = selectedResources.value.filter((id) => id !== resourceId)
    if (selectedResources.value.length === 0 && projectWorkspace.value) {
      activateWorkspace(projectWorkspace.value)
      if (currentProject.value) {
        localStorage.setItem(activeScopeStorageKey(currentProject.value.projectId), JSON.stringify({ scope: 'PROJECT' }))
      }
    }
  }

  return {
    currentProject,
    // Compatibility alias: currentSession now means the active session.
    currentSession: activeSession,
    projectSession,
    resourceSession,
    activeSession,
    activeScopeLabel,
    resources,
    selectedResources,
    selectedResourceItems,
    messages,
    analysis,
    evidenceDraft,
    readinessScore,
    readinessStatus,
    missingRequiredFields,
    missingRecommendedFields,
    analysisGenerationStatus,
    activeAnalysisScope,
    activeAnalysisSource,
    uploadStatus,
    isUploading,
    isExtracting,
    isAnalyzing,
    isSending,
    isUpdatingAnalysis,
    isGeneratingEvidence,
    isUpdatingEvidence,
    isConfirmingEvidence,
    loading,
    error,
    resourceCount,
    evidenceCount,
    initialize,
    refreshActiveResearchState,
    uploadAndProcess,
    retryResource,
    sendMessage,
    updateAnalysis,
    confirmAnalysis,
    generateEvidenceCard,
    updateEvidence,
    confirmEvidence,
    removeSelectedResource,
  }
})
