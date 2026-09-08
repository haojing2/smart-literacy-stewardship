import http from './http'
import type {
  EvidenceCardEditableFields,
  EvidenceReadiness,
  ResearchAnalysis,
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
}

export interface BackendChatMessage {
  messageId: number
  role: 'USER' | 'ASSISTANT' | 'SYSTEM'
  sequenceNo: number
  content: string
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

export const extractResearchText = (resourceId: number) =>
  http.post<ApiEnvelope<{ resourceId: number; processingStatus: string; extractedText: string }>>(
    `/research-resources/${resourceId}/extract-text`,
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

export const getResearchMessages = async (sessionId: number) => {
  const response = await getResearchSession(sessionId)
  return response.data.data.messages
}

export const sendResearchMessage = (sessionId: number, content: string) =>
  http.post<ApiEnvelope<BackendMessagePayload>>(`/research-chat/sessions/${sessionId}/messages`, {
    content,
  }, { timeout: RESEARCH_AGENT_TIMEOUT_MS })

export const updateResearchAnalysis = (sessionId: number, analysis: ResearchAnalysis) =>
  http.put<
    ApiEnvelope<{
      sessionId: number
      analysisId: number
      version: number
      latestAnalysis: ResearchAnalysis
      readiness: EvidenceReadiness
      evidenceDraftGenerated?: boolean
      evidenceCardId?: number | null
    }>
  >(`/research-chat/sessions/${sessionId}/analysis`, {
    participants: analysis.participants,
    researchTopic: analysis.researchTopic,
    aiLiteracyDimensions: analysis.aiLiteracyDimensions,
    teachingStrategies: analysis.teachingStrategies,
    intervention: analysis.intervention,
    assessmentTools: analysis.assessmentTools,
    mainFindings: analysis.mainFindings,
    limitations: analysis.limitations,
  })

export const confirmResearchAnalysis = (sessionId: number) =>
  http.post<ApiEnvelope<{ latestAnalysis: ResearchAnalysis; readiness: EvidenceReadiness }>>(
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
