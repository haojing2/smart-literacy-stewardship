export type ResearchMessageRole = 'USER' | 'ASSISTANT' | 'SYSTEM'
export type ResearchMessageType = 'TEXT' | 'FILE' | 'PROCESS' | 'ANALYSIS_UPDATE' | 'EVIDENCE_DRAFT'
export type ReadinessStatus = 'INCOMPLETE' | 'READY'
export type AnalysisGenerationStatus = 'PENDING' | 'READY' | 'FAILED'
export type EvidenceCardStatus = 'DRAFT' | 'CONFIRMED'
export type UploadStatus =
  | 'UPLOADING'
  | 'UPLOADED'
  | 'TEXT_EXTRACTING'
  | 'TEXT_EXTRACTED'
  | 'INDEXING'
  | 'ANALYZING'
  | 'ANALYZED'
  | 'FAILED'
  | 'REVIEWED'
  | 'CARD_READY'

export type AiLiteracyDimension =
  | 'AI_COGNITION'
  | 'HUMAN_AI_INTERACTION'
  | 'INFORMATION_VERIFICATION'
  | 'SAFETY_ETHICS'
  | 'INNOVATIVE_APPLICATION'

export interface ResearchProjectContext {
  projectId: number
  title: string
  topic: string
  grade: number | null
  classHours: number | null
}

export interface ResearchResource {
  resourceId: number
  fileName: string
  mimeType: string
  fileSize: number
  processingStatus: UploadStatus
  indexStatus?: 'pending' | 'parsing' | 'indexing' | 'ready' | 'error'
  errorMessage?: string | null
  createdAt?: string
  updatedAt?: string
}

export interface ResearchAnalysis {
  participants: string[]
  researchTopics: string[]
  aiLiteracyDimensions: string[]
  teachingStrategies: string[]
  intervention: string | null
  assessmentTools: string[]
  mainFindings: string[]
  limitations: string[]
  teachingImplications: string | null
  fieldSources?: Record<string, 'MOCK' | 'TEACHER'>
  teacherConfirmed?: boolean
  version?: number
  generationStatus?: AnalysisGenerationStatus
}

export type ResearchAnalysisContentKey =
  | 'participants'
  | 'researchTopics'
  | 'aiLiteracyDimensions'
  | 'teachingStrategies'
  | 'intervention'
  | 'assessmentTools'
  | 'mainFindings'
  | 'limitations'
  | 'teachingImplications'

export interface ResearchAnalysisFieldConfig {
  key: ResearchAnalysisContentKey
  label: string
  editorType: 'textarea'
  isList: boolean
}

export const RESEARCH_ANALYSIS_FIELDS: readonly ResearchAnalysisFieldConfig[] = [
  { key: 'participants', label: '研究对象', editorType: 'textarea', isList: true },
  { key: 'researchTopics', label: '研究问题/主题', editorType: 'textarea', isList: true },
  { key: 'aiLiteracyDimensions', label: '能力重点', editorType: 'textarea', isList: true },
  { key: 'teachingStrategies', label: '教学策略', editorType: 'textarea', isList: true },
  { key: 'intervention', label: '干预周期/实施时长', editorType: 'textarea', isList: false },
  { key: 'assessmentTools', label: '评价工具', editorType: 'textarea', isList: true },
  { key: 'mainFindings', label: '主要研究发现', editorType: 'textarea', isList: true },
  { key: 'limitations', label: '研究局限', editorType: 'textarea', isList: true },
  { key: 'teachingImplications', label: '教学启示', editorType: 'textarea', isList: false },
] as const

export interface EvidenceReadiness {
  readinessScore: number
  readinessStatus: ReadinessStatus
  missingRequiredFields: string[]
  missingRecommendedFields: string[]
}

export interface ResearchChatMessage {
  messageId: number | string
  role: ResearchMessageRole
  messageType: ResearchMessageType
  content: string
  createdAt: string
  resourceId?: number
  sendStatus?: 'SENDING' | 'SENT' | 'FAILED'
  metadata?: Record<string, unknown> | null
}

export interface ResearchChatSession {
  sessionId: number
  projectId: number
  resourceId: number | null
  title: string
  status: 'ACTIVE' | 'COMPLETED' | 'ARCHIVED'
  createdAt: string
  updatedAt: string
}

export interface EvidenceCard {
  evidenceCardId: number
  projectId: number
  resourceId: number | null
  researchAnalysisId?: number
  status: EvidenceCardStatus
  researchFinding: string
  applicableAudience: string
  recommendedStrategies: string[]
  implementationConditions: string[]
  teachingImplications: string
  limitations: string
  sourceDocument: string
  sourceTraceId: string
  confirmedBy?: number | null
  confirmedAt?: string | null
}

export type EvidenceCardEditableFields = Pick<
  EvidenceCard,
  | 'researchFinding'
  | 'applicableAudience'
  | 'recommendedStrategies'
  | 'implementationConditions'
  | 'teachingImplications'
  | 'limitations'
>

export interface ResearchSessionSnapshot {
  session: ResearchChatSession
  resources: ResearchResource[]
  messages: ResearchChatMessage[]
  analysis: ResearchAnalysis | null
  readiness: EvidenceReadiness
  evidenceDraft: EvidenceCard | null
}

export interface SendResearchMessageResult {
  userMessage: ResearchChatMessage
  assistantMessage: ResearchChatMessage
  updatedAnalysis: ResearchAnalysis | null
  readiness: EvidenceReadiness | null
  evidenceDraftGenerated: boolean
  evidenceCardId: number | null
}
