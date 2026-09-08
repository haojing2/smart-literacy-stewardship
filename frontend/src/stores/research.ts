import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { isAxiosError } from 'axios'
import { getProject } from '@/api/projects'
import {
  confirmEvidenceCard as confirmEvidenceCardApi,
  confirmResearchAnalysis as confirmResearchAnalysisApi,
  createResearchSession as createResearchSessionApi,
  extractResearchText as extractResearchTextApi,
  getEvidenceCard as getEvidenceCardApi,
  getLatestProjectResearchSession as getLatestProjectResearchSessionApi,
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
  EvidenceCard,
  EvidenceCardEditableFields,
  ReadinessStatus,
  ResearchAnalysis,
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

function backendAnalysis(payload: BackendAnalysisPayload | null): ResearchAnalysis | null {
  if (!payload) return null
  return {
    participants: payload.researchSubjects,
    researchTopic: payload.researchTopics[0] ?? null,
    aiLiteracyDimensions: payload.aiLiteracyDimensions,
    teachingStrategies: payload.teachingStrategies,
    intervention: payload.interventionDuration,
    assessmentTools: payload.assessmentTools,
    mainFindings: payload.mainFindings,
    limitations: payload.limitations,
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

export const useResearchStore = defineStore('research', () => {
  const currentProject = ref<ResearchProjectContext | null>(null)
  const currentSession = ref<ResearchChatSession | null>(null)
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

  const selectedResourceItems = computed(() =>
    resources.value.filter((resource) => selectedResources.value.includes(resource.resourceId)),
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
    currentSession.value = null
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
    uploadStatus.value = 'IDLE'
    error.value = ''
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

  function applySnapshot(snapshot: {
    session: ResearchChatSession
    resources?: ResearchResource[]
    messages: ResearchChatMessage[]
    analysis?: ResearchAnalysis | null
    readiness?: Parameters<typeof setReadiness>[0] | null
    evidenceDraft?: EvidenceCard | null
  }) {
    currentSession.value = snapshot.session
    if (snapshot.resources) resources.value = snapshot.resources
    selectedResources.value = snapshot.session.resourceId === null ? [] : [snapshot.session.resourceId]
    messages.value = snapshot.messages
    analysis.value = snapshot.analysis ?? null
    if (snapshot.readiness) setReadiness(snapshot.readiness)
    evidenceDraft.value = snapshot.evidenceDraft ?? null
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

      const savedResources = localStorage.getItem(resourcesStorageKey(projectId))
      if (savedResources) resources.value = JSON.parse(savedResources) as ResearchResource[]
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
      if (payload.resourceId !== null && !resources.value.some((resource) => resource.resourceId === payload.resourceId)) {
        resources.value.push({
          resourceId: payload.resourceId,
          fileName: '研究资源',
          mimeType: 'application/pdf',
          fileSize: 0,
          processingStatus: 'ANALYZED',
        })
      }
      applySnapshot({
        session: backendSession(payload),
        messages: payload.messages.map(backendMessage),
        analysis: backendAnalysis(payload.latestAnalysis),
        readiness: payload.readiness,
      })
      if (payload.evidenceCardId) {
        evidenceDraft.value = backendEvidence((await getEvidenceCardApi(payload.evidenceCardId)).data.data)
        const selectedResource = resources.value.find(
          (resource) => resource.resourceId === payload.resourceId,
        )
        if (selectedResource && evidenceDraft.value) {
          selectedResource.fileName = evidenceDraft.value.sourceDocument
          selectedResource.processingStatus = 'REVIEWED'
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
    let processingStage: 'upload' | 'text-extraction' | 'ai-analysis' = 'upload'
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
      selectedResources.value = [uploaded.resourceId]
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
      addSystemMessage('正在解析研究资源……')
      const extracted = useMock
        ? await researchMockService.extractText(project.projectId, uploaded.resourceId)
        : {
            ...uploaded,
            processingStatus: (await extractResearchTextApi(uploaded.resourceId)).data.data
              .processingStatus as UploadStatus,
          }
      Object.assign(uploaded, extracted)
      uploadStatus.value = 'TEXT_EXTRACTED'
      addSystemMessage('研究资源解析完成')

      isAnalyzing.value = true
      processingStage = 'ai-analysis'
      uploadStatus.value = 'ANALYZING'
      if (useMock) {
        const snapshot = await researchMockService.createSession(
          project.projectId,
          uploaded.resourceId,
          project.topic,
        )
        resourceSession.value = snapshot.session
        analysis.value = snapshot.analysis
        setReadiness(snapshot.readiness)
        evidenceDraft.value = snapshot.evidenceDraft
      } else {
        const sessionResponse = await createResearchSessionApi(project.projectId, uploaded.resourceId)
        const payload = sessionResponse.data.data
        resourceSession.value = backendSession(payload)
        analysis.value = backendAnalysis(payload.latestAnalysis)
        if (payload.readiness) setReadiness(payload.readiness)
        evidenceDraft.value = null
        if (payload.evidenceCardId) {
          evidenceDraft.value = backendEvidence((await getEvidenceCardApi(payload.evidenceCardId)).data.data)
        }
        localStorage.setItem(resourcesStorageKey(project.projectId), JSON.stringify(resources.value))
        addSystemMessage('论文解析完成，可在右侧查看研究解析与证据卡。')
      }
      const completedResource = resources.value.find((item) => item.resourceId === uploaded.resourceId)
      if (completedResource) completedResource.processingStatus = 'ANALYZED'
      uploadStatus.value = 'ANALYZED'
    } catch (requestError) {
      const resource = uploadedResource
        ?? resources.value.find((item) => item.resourceId === placeholderId)
      if (resource) {
        resource.processingStatus = processingStage === 'ai-analysis' ? 'TEXT_EXTRACTED' : 'FAILED'
        resource.errorMessage = messageFromError(
          requestError,
          processingStage === 'upload'
            ? '文件上传失败'
            : processingStage === 'text-extraction'
              ? '文本提取失败'
              : 'AI研究解析失败',
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
    if (!project || !resource || isExtracting.value) return
    if (resourceId < 0) {
      error.value = '上传未完成，请重新选择原始文件'
      return
    }
    isExtracting.value = true
    error.value = ''
    resource.processingStatus = 'TEXT_EXTRACTING'
    let processingStage: 'text-extraction' | 'ai-analysis' = 'text-extraction'
    addSystemMessage('正在重新解析研究资源……')
    try {
      const extracted = useMock
        ? await researchMockService.extractText(project.projectId, resourceId)
        : {
            ...resource,
            processingStatus: (await extractResearchTextApi(resourceId)).data.data
              .processingStatus as UploadStatus,
          }
      Object.assign(resource, extracted)
      isAnalyzing.value = true
      processingStage = 'ai-analysis'
      if (useMock) {
        const snapshot = await researchMockService.createSession(project.projectId, resourceId, project.topic)
        resourceSession.value = snapshot.session
        analysis.value = snapshot.analysis
        setReadiness(snapshot.readiness)
        evidenceDraft.value = snapshot.evidenceDraft
      } else {
        const payload = (await createResearchSessionApi(project.projectId, resourceId)).data.data
        resourceSession.value = backendSession(payload)
        analysis.value = backendAnalysis(payload.latestAnalysis)
        if (payload.readiness) setReadiness(payload.readiness)
        if (payload.evidenceCardId) {
          evidenceDraft.value = backendEvidence((await getEvidenceCardApi(payload.evidenceCardId)).data.data)
        }
      }
      addSystemMessage('研究资源重新解析完成')
    } catch (requestError) {
      resource.processingStatus = processingStage === 'ai-analysis' ? 'TEXT_EXTRACTED' : 'FAILED'
      resource.errorMessage = messageFromError(
        requestError,
        processingStage === 'ai-analysis' ? 'AI研究解析失败' : '文本提取失败',
      )
      error.value = resource.errorMessage
    } finally {
      isExtracting.value = false
      isAnalyzing.value = false
    }
  }

  async function sendMessage(content: string, retryMessageId?: number | string): Promise<boolean> {
    const project = currentProject.value
    const normalizedContent = content.trim()
    if (!project) {
      error.value = '当前教学项目不可用，请先选择项目'
      return false
    }
    if (!currentSession.value) {
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
        const response = await sendResearchMessageApi(currentSession.value.sessionId, normalizedContent)
        const payload = response.data.data
        normalized = {
          userMessage: backendMessage(payload.userMessage),
          assistantMessage: backendMessage(payload.assistantMessage),
          updatedAnalysis: backendAnalysis(payload.latestAnalysis),
          readiness: payload.readiness,
          evidenceDraftGenerated: payload.evidenceDraftGenerated ?? false,
          evidenceCardId: payload.evidenceCardId ?? null,
        }
      }
      const pendingIndex = messages.value.findIndex((message) => message.messageId === temporaryId)
      if (pendingIndex >= 0) messages.value.splice(pendingIndex, 1, normalized.userMessage)
      messages.value.push(normalized.assistantMessage)
      if (normalized.updatedAnalysis) analysis.value = normalized.updatedAnalysis
      if (normalized.readiness) setReadiness(normalized.readiness)
      if (normalized.evidenceDraftGenerated) {
        addSystemMessage('当前核心研究信息已完整，系统已生成证据卡草稿。', 'EVIDENCE_DRAFT')
        isGeneratingEvidence.value = true
        evidenceDraft.value = useMock
          ? await researchMockService.getEvidenceCard(project.projectId)
          : normalized.evidenceCardId
            ? backendEvidence((await getEvidenceCardApi(normalized.evidenceCardId)).data.data)
            : null
      }
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
    const session = resourceSession.value
    if (!project || !session || isUpdatingAnalysis.value) return false
    isUpdatingAnalysis.value = true
    error.value = ''
    try {
      if (useMock) {
        const result = await researchMockService.updateAnalysis(project.projectId, updated)
        analysis.value = result.analysis
        setReadiness(result.readiness)
        if (result.evidenceDraftGenerated) {
          evidenceDraft.value = result.evidenceDraft
          addSystemMessage('当前核心研究信息已完整，系统已生成证据卡草稿。', 'EVIDENCE_DRAFT')
        }
      } else {
        const response = await updateResearchAnalysisApi(session.sessionId, updated)
        analysis.value = { ...response.data.data.latestAnalysis, version: response.data.data.version }
        setReadiness(response.data.data.readiness)
        if (response.data.data.evidenceDraftGenerated && response.data.data.evidenceCardId) {
          evidenceDraft.value = backendEvidence((await getEvidenceCardApi(response.data.data.evidenceCardId)).data.data)
          addSystemMessage('当前核心研究信息已经完整，系统已生成证据卡草稿。', 'EVIDENCE_DRAFT')
        }
      }
      addSystemMessage('研究解析已更新', 'ANALYSIS_UPDATE')
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
    const session = resourceSession.value
    if (!project || !session || readinessStatus.value !== 'READY') return false
    try {
      if (useMock) {
        const result = await researchMockService.confirmAnalysis(project.projectId)
        analysis.value = result.analysis
        setReadiness(result.readiness)
      } else {
        const response = await confirmResearchAnalysisApi(session.sessionId)
        analysis.value = response.data.data.latestAnalysis
        setReadiness(response.data.data.readiness)
      }
      return true
    } catch (requestError) {
      error.value = messageFromError(requestError, '研究解析确认失败')
      return false
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
      error.value = messageFromError(requestError, '证据卡确认失败')
      return false
    } finally {
      isConfirmingEvidence.value = false
    }
  }

  function removeSelectedResource(resourceId: number) {
    selectedResources.value = selectedResources.value.filter((id) => id !== resourceId)
  }

  return {
    currentProject,
    currentSession,
    resourceSession,
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
    uploadAndProcess,
    retryResource,
    sendMessage,
    updateAnalysis,
    confirmAnalysis,
    updateEvidence,
    confirmEvidence,
    removeSelectedResource,
  }
})
