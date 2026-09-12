import http from './http'
import type {
  EvidenceCardEditableFields,
  EvidenceReadiness,
  ResearchAnalysis,
  ResearchAnalysisContentKey,
  ResearchResource,
} from '@/types/research'

interface ApiEnvelope<T> {
  code: number
  message: string
  data: T
  requestId: string
}

const RESEARCH_AGENT_TIMEOUT_MS = 130_000

export interface BackendAnalysisPayload {
  researchSubjects: string[]
  researchTopics: string[]
  aiLiteracyDimensions: string[]
  teachingStrategies: string[]
  interventionDuration: string | null
  assessmentTools: string[]
  mainFindings: string[]
  limitations: string[]
  teachingImplications: string | null
}

export interface ResearchAnalysisVersionPayload {
  sessionId: number
  analysisId: number
  version: number
  generationStatus: 'PENDING' | 'READY' | 'FAILED'
  latestAnalysis: ResearchAnalysis
  fieldSources: Record<string, 'MOCK' | 'AI_CHAT' | 'TEACHER'>
  teacherConfirmed: boolean
  teacherConfirmedAt?: string | null
  readiness: EvidenceReadiness
  evidenceDraftGenerated?: boolean
  evidenceCardId?: number | null
}

export interface BackendChatMessage {
  messageId: number
  role: 'USER' | 'ASSISTANT' | 'SYSTEM'
  sequenceNo: number
  content: string
  metadata?: Record<string, unknown> | null
  createdAt: string
}

export interface BackendSessionPayload {
  sessionId: number
  projectId: number
  resourceId: number | null
  title: string
  status: 'ACTIVE' | 'COMPLETED' | 'ARCHIVED'
  messages: BackendChatMessage[]
  latestAnalysis: BackendAnalysisPayload | null
  analysisGenerationStatus?: 'PENDING' | 'READY' | 'FAILED' | null
  fieldSources?: Record<string, 'MOCK' | 'AI_CHAT' | 'TEACHER'>
  teacherConfirmed?: boolean
  version?: number
  readiness: (EvidenceReadiness & { ready?: boolean }) | null
  evidenceCardId?: number | null
  createdAt: string
  updatedAt: string
}

export interface BackendEvidenceCard {
  evidenceCardId: number
  researchAnalysisId: number
  researchFinding: string
  applicableAudience: string
  recommendedStrategies: string[]
  implementationConditions: string[]
  teachingImplications: string
  limitations: string
  source: {
    resourceId: number | null
    projectId: number
    originalFilename: string | null
    sha256: string | null
    sourceLabel?: string
    chunkId?: string | null
  }
  cardStatus: 'DRAFT' | 'CONFIRMED'
  confirmedBy?: number | null
  confirmedAt?: string | null
}

export interface BackendMessagePayload {
  sessionId: number
  userMessage: BackendChatMessage
  assistantMessage: BackendChatMessage
  analysisPatch?: Partial<ResearchAnalysis> | null
  latestAnalysis: BackendAnalysisPayload | null
  analysisGenerationStatus?: 'PENDING' | 'READY' | 'FAILED' | null
  fieldSources?: Record<string, 'MOCK' | 'AI_CHAT' | 'TEACHER'>
  teacherConfirmed?: boolean
  version?: number
  readiness: (EvidenceReadiness & { ready?: boolean }) | null
  evidenceDraftGenerated?: boolean
  evidenceCardId?: number | null
}

export const uploadResearchResource = (projectId: number, file: File) => {
  const formData = new FormData()
  formData.append('file', file)
  return http.post<ApiEnvelope<ResearchResource>>(
    `/projects/${projectId}/research-resources/upload`,
    formData,
  )
}

export const getProjectResearchResources = (projectId: number) =>
  http.get<ApiEnvelope<ResearchResource[]>>(`/projects/${projectId}/research-resources`)

export const extractResearchText = (resourceId: number) =>
  http.post<ApiEnvelope<{ resourceId: number; processingStatus: string; extractedText: string }>>(
    `/research-resources/${resourceId}/extract-text`,
    undefined,
    { timeout: 120_000 },
  )

export const analyzeResearch = (resourceId: number) =>
  http.post<ApiEnvelope<{ analysis: ResearchAnalysis; readiness: EvidenceReadiness }>>(
    `/research-resources/${resourceId}/analyze`,
  )

export const createResearchSession = (projectId: number, resourceId: number | null = null) =>
  http.post<ApiEnvelope<BackendSessionPayload>>(`/projects/${projectId}/research-chat/sessions`, {
    resourceId,
  }, { timeout: RESEARCH_AGENT_TIMEOUT_MS })

export const getResearchSession = (sessionId: number) =>
  http.get<ApiEnvelope<BackendSessionPayload>>(`/research-chat/sessions/${sessionId}`)

export const getLatestProjectResearchSession = (projectId: number) =>
  http.get<ApiEnvelope<BackendSessionPayload>>(`/projects/${projectId}/research-chat/sessions/latest`)

export const getLatestResourceResearchSession = (projectId: number) =>
  http.get<ApiEnvelope<BackendSessionPayload>>(
    `/projects/${projectId}/research-chat/resource-sessions/latest`,
  )

export const getLatestResearchSessionForResource = (projectId: number, resourceId: number) =>
  http.get<ApiEnvelope<BackendSessionPayload>>(
    `/projects/${projectId}/research-resources/${resourceId}/session/latest`,
  )

export const getResearchMessages = async (sessionId: number) => {
  const response = await getResearchSession(sessionId)
  return response.data.data.messages
}

export const sendResearchMessage = (sessionId: number, content: string, analysisTargetField?: ResearchAnalysisContentKey) =>
  http.post<ApiEnvelope<BackendMessagePayload>>(`/research-chat/sessions/${sessionId}/messages`, {
    content,
    analysisTargetField,
  }, { timeout: RESEARCH_AGENT_TIMEOUT_MS })

export const updateResearchAnalysis = (sessionId: number, analysis: ResearchAnalysis) =>
  http.put<ApiEnvelope<ResearchAnalysisVersionPayload>>(`/research-chat/sessions/${sessionId}/analysis`, {
    participants: analysis.participants,
    researchTopics: analysis.researchTopics,
    aiLiteracyDimensions: analysis.aiLiteracyDimensions,
    teachingStrategies: analysis.teachingStrategies,
    intervention: analysis.intervention,
    assessmentTools: analysis.assessmentTools,
    mainFindings: analysis.mainFindings,
    limitations: analysis.limitations,
    teachingImplications: analysis.teachingImplications,
  })

export const confirmResearchAnalysis = (sessionId: number) =>
  http.post<ApiEnvelope<ResearchAnalysisVersionPayload>>(
    `/research-chat/sessions/${sessionId}/analysis/confirm`,
  )

export const getEvidenceCard = (evidenceCardId: number) =>
  http.get<ApiEnvelope<BackendEvidenceCard>>(`/evidence-cards/${evidenceCardId}`)

export const updateEvidenceCard = (
  evidenceCardId: number,
  payload: EvidenceCardEditableFields,
) => http.put<ApiEnvelope<BackendEvidenceCard>>(`/evidence-cards/${evidenceCardId}`, payload)

export const confirmEvidenceCard = (evidenceCardId: number) =>
  http.post<ApiEnvelope<BackendEvidenceCard>>(`/evidence-cards/${evidenceCardId}/confirm`)
