import type {
  EvidenceCard,
  EvidenceCardEditableFields,
  EvidenceReadiness,
  ResearchAnalysis,
  ResearchChatMessage,
  ResearchChatSession,
  ResearchResource,
  ResearchSessionSnapshot,
  SendResearchMessageResult,
} from '@/types/research'

interface MockWorkspaceState {
  resources: ResearchResource[]
  session: ResearchChatSession | null
  messages: ResearchChatMessage[]
  analysis: ResearchAnalysis | null
  readiness: EvidenceReadiness
  evidenceDraft: EvidenceCard | null
  nextId: number
}

const STORAGE_PREFIX = 'research-workbench-demo:'
const wait = (duration = 260) => new Promise((resolve) => window.setTimeout(resolve, duration))

function emptyReadiness(): EvidenceReadiness {
  return {
    readinessScore: 15,
    readinessStatus: 'INCOMPLETE',
    missingRequiredFields: ['participants', 'mainFindings', 'teachingStrategies'],
    missingRecommendedFields: [
      'researchTopics',
      'aiLiteracyDimensions',
      'intervention',
      'assessmentTools',
      'limitations',
    ],
  }
}

function emptyState(): MockWorkspaceState {
  return {
    resources: [],
    session: null,
    messages: [],
    analysis: null,
    readiness: emptyReadiness(),
    evidenceDraft: null,
    nextId: 1,
  }
}

function storageKey(projectId: number) {
  return `${STORAGE_PREFIX}${projectId}`
}

function load(projectId: number): MockWorkspaceState {
  const raw = localStorage.getItem(storageKey(projectId))
  if (!raw) return emptyState()
  try {
    return { ...emptyState(), ...(JSON.parse(raw) as MockWorkspaceState) }
  } catch {
    return emptyState()
  }
}

function save(projectId: number, state: MockWorkspaceState) {
  localStorage.setItem(storageKey(projectId), JSON.stringify(state))
}

function now() {
  return new Date().toISOString()
}

function nextId(state: MockWorkspaceState) {
  const value = state.nextId
  state.nextId += 1
  return value
}

function hasValues(values: string[]) {
  return values.some((value) => value.trim().length > 0)
}

function calculateReadiness(analysis: ResearchAnalysis): EvidenceReadiness {
  const required = {
    participants: hasValues(analysis.participants),
    mainFindings: hasValues(analysis.mainFindings),
    teachingStrategies: hasValues(analysis.teachingStrategies),
    sourceMetadata: true,
  }
  const recommended = {
    researchTopics: hasValues(analysis.researchTopics),
    aiLiteracyDimensions: hasValues(analysis.aiLiteracyDimensions),
    intervention: Boolean(analysis.intervention?.trim()),
    assessmentTools: hasValues(analysis.assessmentTools),
    limitations: hasValues(analysis.limitations),
  }
  const missingRequiredFields = Object.entries(required)
    .filter(([, complete]) => !complete)
    .map(([field]) => field)
  const missingRecommendedFields = Object.entries(recommended)
    .filter(([, complete]) => !complete)
    .map(([field]) => field)
  const readinessScore =
    Object.values(required).filter(Boolean).length * 15 +
    Object.values(recommended).filter(Boolean).length * 8
  return {
    readinessScore,
    readinessStatus: missingRequiredFields.length === 0 ? 'READY' : 'INCOMPLETE',
    missingRequiredFields,
    missingRecommendedFields,
  }
}

function makeDraft(
  projectId: number,
  resource: ResearchResource,
  analysis: ResearchAnalysis,
  id: number,
): EvidenceCard {
  return {
    evidenceCardId: id,
    projectId,
    resourceId: resource.resourceId,
    status: 'DRAFT',
    researchFinding: analysis.mainFindings.join('\n'),
    applicableAudience: analysis.participants.join('、'),
    recommendedStrategies: [...analysis.teachingStrategies],
    implementationConditions: analysis.intervention ? [analysis.intervention] : [],
    teachingImplications: '可结合当前项目情境，将研究策略转化为课堂活动并进行形成性评价。',
    limitations: analysis.limitations.join('\n'),
    sourceDocument: resource.fileName,
    sourceTraceId: `mock-resource-${resource.resourceId}`,
    confirmedBy: null,
    confirmedAt: null,
  }
}

function createMessage(
  state: MockWorkspaceState,
  role: ResearchChatMessage['role'],
  messageType: ResearchChatMessage['messageType'],
  content: string,
): ResearchChatMessage {
  return { messageId: nextId(state), role, messageType, content, createdAt: now(), sendStatus: 'SENT' }
}

function applyExplicitFacts(analysis: ResearchAnalysis, content: string): ResearchAnalysis {
  const updated: ResearchAnalysis = { ...analysis }
  const rules: Array<[RegExp, keyof Pick<ResearchAnalysis, 'participants' | 'mainFindings' | 'teachingStrategies'>]> = [
    [/研究对象\s*[：:]\s*(.+)/, 'participants'],
    [/主要研究(?:结果|发现)\s*[：:]\s*(.+)/, 'mainFindings'],
    [/教学策略\s*[：:]\s*(.+)/, 'teachingStrategies'],
  ]
  for (const [pattern, field] of rules) {
    const value = content.match(pattern)?.[1]?.trim()
    if (value) updated[field] = [value]
  }
  return updated
}

function stableAssistantReply(analysis: ResearchAnalysis) {
  if (!hasValues(analysis.participants)) {
    return '当前研究对象尚未确认。你可以在右侧研究解析区补充研究对象。'
  }
  if (!hasValues(analysis.mainFindings)) {
    return '当前尚未形成主要研究结果，请补充论文中的核心研究发现。'
  }
  if (!hasValues(analysis.teachingStrategies)) {
    return '当前尚未明确教学策略，请补充研究中的教学策略。'
  }
  return '当前核心研究信息已经较完整，可以进一步形成证据卡草稿。'
}

function projectKnowledgeReply() {
  return '这是基于内置研究知识库的模拟回答。我可以结合当前教学项目，协助梳理研究视角、判断证据适用性，并转化为教学设计建议。'
}

function ensureProjectSession(state: MockWorkspaceState, projectId: number) {
  if (state.session) return state.session
  const timestamp = now()
  state.session = {
    sessionId: nextId(state),
    projectId,
    resourceId: null,
    title: '项目研教对话',
    status: 'ACTIVE',
    createdAt: timestamp,
    updatedAt: timestamp,
  }
  return state.session
}

export const researchMockService = {
  async getWorkspace(projectId: number): Promise<ResearchSessionSnapshot | null> {
    await wait(120)
    const state = load(projectId)
    const projectSession = ensureProjectSession(state, projectId)
    save(projectId, state)
    return {
      session: projectSession,
      resources: state.resources,
      messages: state.messages,
      analysis: state.analysis,
      readiness: state.readiness,
      evidenceDraft: state.evidenceDraft,
    }
  },

  async uploadResource(projectId: number, file: File): Promise<ResearchResource> {
    await wait()
    const state = load(projectId)
    const resource: ResearchResource = {
      resourceId: nextId(state),
      fileName: file.name,
      mimeType: file.type || (file.name.endsWith('.docx') ? 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' : 'application/pdf'),
      fileSize: file.size,
      processingStatus: 'UPLOADED',
    }
    state.resources.push(resource)
    state.messages.push(
      createMessage(state, 'SYSTEM', 'PROCESS', '文件上传完成'),
      {
        ...createMessage(state, 'SYSTEM', 'FILE', resource.fileName),
        resourceId: resource.resourceId,
      },
    )
    save(projectId, state)
    return resource
  },

  async extractText(projectId: number, resourceId: number): Promise<ResearchResource> {
    const state = load(projectId)
    const resource = state.resources.find((item) => item.resourceId === resourceId)
    if (!resource) throw new Error('研究资源不存在')
    resource.processingStatus = 'TEXT_EXTRACTING'
    state.messages.push(createMessage(state, 'SYSTEM', 'PROCESS', '正在提取论文文本…'))
    save(projectId, state)
    await wait(520)
    resource.processingStatus = 'TEXT_EXTRACTED'
    state.messages.push(createMessage(state, 'SYSTEM', 'PROCESS', '文本提取已完成'))
    resource.indexStatus = 'indexing'
    state.messages.push(createMessage(state, 'SYSTEM', 'PROCESS', '正在进行论文向量化与建立检索索引…'))
    save(projectId, state)
    await wait(320)
    resource.indexStatus = 'ready'
    state.messages.push(createMessage(state, 'SYSTEM', 'PROCESS', '论文向量化与检索已完成'))
    save(projectId, state)
    return resource
  },

  async createSession(
    projectId: number,
    resourceId: number,
    projectTopic: string,
  ): Promise<ResearchSessionSnapshot> {
    await wait()
    const state = load(projectId)
    const resource = state.resources.find((item) => item.resourceId === resourceId)
    if (!resource) throw new Error('研究资源不存在')
    // A resource analysis is auxiliary; it must not replace the project-level
    // knowledge-base conversation session.
    ensureProjectSession(state, projectId)
    const timestamp = now()
    const resourceSession: ResearchChatSession = {
      sessionId: nextId(state),
      projectId,
      resourceId,
      title: `与 ${resource.fileName} 的研究对话`,
      status: 'ACTIVE',
      createdAt: timestamp,
      updatedAt: timestamp,
    }
    state.analysis = {
      participants: [],
      researchTopics: [],
      aiLiteracyDimensions: [],
      teachingStrategies: [],
      intervention: null,
      assessmentTools: [],
      mainFindings: [],
      limitations: [],
      teachingImplications: null,
      fieldSources: {},
      teacherConfirmed: false,
      version: 1,
    }
    state.readiness = calculateReadiness(state.analysis)
    save(projectId, state)
    return {
      session: resourceSession,
      resources: state.resources,
      messages: state.messages,
      analysis: state.analysis,
      readiness: state.readiness,
      evidenceDraft: state.evidenceDraft,
    }
  },

  async sendMessage(projectId: number, content: string): Promise<SendResearchMessageResult> {
    await wait(460)
    const state = load(projectId)
    if (!state.session) throw new Error('研教对话会话不存在')
    if (state.session.resourceId === null) {
      const userMessage = createMessage(state, 'USER', 'TEXT', content)
      const assistantMessage = createMessage(state, 'ASSISTANT', 'TEXT', projectKnowledgeReply())
      state.messages.push(userMessage, assistantMessage)
      save(projectId, state)
      return {
        userMessage,
        assistantMessage,
        updatedAnalysis: null,
        readiness: null,
        evidenceDraftGenerated: false,
        evidenceCardId: null,
      }
    }
    if (!state.analysis) throw new Error('研究资源解析尚未完成')
    const userMessage = createMessage(state, 'USER', 'TEXT', content)
    state.analysis = applyExplicitFacts(state.analysis, content)
    state.readiness = calculateReadiness(state.analysis)
    const assistantMessage = createMessage(
      state,
      'ASSISTANT',
      'TEXT',
      stableAssistantReply(state.analysis),
    )
    state.messages.push(userMessage, assistantMessage)
    save(projectId, state)
    return {
      userMessage,
      assistantMessage,
      updatedAnalysis: state.analysis,
      readiness: state.readiness,
      evidenceDraftGenerated: false,
      evidenceCardId: null,
    }
  },

  async updateAnalysis(projectId: number, analysis: ResearchAnalysis) {
    await wait()
    const state = load(projectId)
    if (!state.session) throw new Error('研究对话不存在')
    state.analysis = {
      ...analysis,
      fieldSources: Object.fromEntries(
        ['participants', 'researchTopics', 'aiLiteracyDimensions', 'teachingStrategies', 'intervention', 'assessmentTools', 'mainFindings', 'limitations', 'teachingImplications'].map((field) => [field, 'TEACHER']),
      ),
      teacherConfirmed: false,
      version: (analysis.version ?? 1) + 1,
    }
    state.readiness = calculateReadiness(state.analysis)
    state.evidenceDraft = null
    state.messages.push(createMessage(state, 'SYSTEM', 'ANALYSIS_UPDATE', '研究解析已更新'))
    save(projectId, state)
    return { analysis: state.analysis, readiness: state.readiness, evidenceDraftGenerated: false, evidenceDraft: null }
  },

  async confirmAnalysis(projectId: number) {
    await wait()
    const state = load(projectId)
    if (!state.analysis || state.readiness.readinessStatus !== 'READY') {
      throw new Error('研究信息尚未达到证据卡生成条件')
    }
    state.analysis.teacherConfirmed = true
    save(projectId, state)
    return { analysis: state.analysis, readiness: state.readiness }
  },

  async getEvidenceCard(projectId: number) {
    await wait(120)
    return load(projectId).evidenceDraft
  },

  async generateEvidenceCard(projectId: number) {
    await wait()
    const state = load(projectId)
    if (!state.analysis) throw new Error('研究解析尚未准备好')
    const recognizedCount = Object.values(state.analysis).slice(0, 9)
      .filter((value) => Array.isArray(value) ? value.length > 0 : Boolean(value?.trim())).length
    if (recognizedCount < 6) throw new Error('至少完成6项研究解析后才能生成证据卡。')
    if (!state.evidenceDraft) {
      const resource = state.resources[state.resources.length - 1]
      if (!resource) throw new Error('研究资源不存在')
      state.evidenceDraft = makeDraft(projectId, resource, state.analysis, nextId(state))
      save(projectId, state)
    }
    return state.evidenceDraft
  },

  async updateEvidenceCard(projectId: number, payload: EvidenceCardEditableFields) {
    await wait()
    const state = load(projectId)
    if (!state.evidenceDraft) throw new Error('证据卡草稿不存在')
    state.evidenceDraft = { ...state.evidenceDraft, ...payload, status: 'DRAFT' }
    save(projectId, state)
    return state.evidenceDraft
  },

  async confirmEvidenceCard(projectId: number) {
    await wait()
    const state = load(projectId)
    if (!state.evidenceDraft) throw new Error('证据卡草稿不存在')
    state.evidenceDraft.status = 'CONFIRMED'
    state.evidenceDraft.confirmedAt = now()
    state.messages.push(createMessage(state, 'SYSTEM', 'EVIDENCE_DRAFT', '已保存为正式研究证据'))
    save(projectId, state)
    return state.evidenceDraft
  },
}
