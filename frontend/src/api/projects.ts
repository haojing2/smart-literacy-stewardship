import http from './http'

export type WorkflowState =
  | 'DRAFT'
  | 'CONTEXT_READY'
  | 'RESEARCH_READY'
  | 'OBJECTIVE_PENDING'
  | 'OBJECTIVE_CONFIRMED'
  | 'PEDAGOGY_PENDING'
  | 'PEDAGOGY_CONFIRMED'
  | 'ASSESSMENT_PENDING'
  | 'ASSESSMENT_CONFIRMED'
  | 'ACTIVITY_READY'
  | 'QUALITY_READY'
  | 'QUALITY_CHECKED'
  | 'ARTIFACT_READY'
  | (string & {})
export type ProjectType = 'NEW_TOPIC' | 'OPTIMIZE_EXISTING' | 'TEXTBOOK_ADAPTATION'

export interface ProjectListItem {
  projectId: number
  title: string
  topic: string
  grade: number | null
  classHours: number | null
  studentLevel: string | null
  workflowState: WorkflowState
  updatedAt: string
}

export interface ProjectListResponse {
  code: number
  message: string
  data: {
    items: ProjectListItem[]
    total: number
    page: number
    pageSize: number
  }
  requestId: string
}

export interface ProjectListParams {
  page: number
  pageSize: number
  grade?: number
  sort?: string
}

export interface ProjectCreatePayload {
  title: string
  topic: string
  projectType: ProjectType
}

export interface ProjectCreateResponse {
  code: number
  message: string
  data: { projectId: number; workflowState: string }
  requestId: string
}

export interface ProjectDetail {
  projectId: number
  title: string
  topic: string
  projectType: string
  grade: number | null
  classHours: number | null
  studentLevel: 'BEGINNER' | 'GENERAL' | 'ADVANCED' | null
  aiAccessMode: 'TEACHER_DEMO' | 'GROUP' | 'INDIVIDUAL' | null
  devices: string[] | null
  constraints: string[] | null
  additionalRequirements: string | null
  workflowState: string
  staleSections: string[]
  createdAt: string
  updatedAt: string
}

export interface ProjectDetailResponse {
  code: number
  message: string
  data: ProjectDetail
  requestId: string
}

export interface ProjectContextPayload {
  grade: number
  classHours: number
  studentLevel: 'BEGINNER' | 'GENERAL' | 'ADVANCED'
  aiAccessMode: 'TEACHER_DEMO' | 'GROUP' | 'INDIVIDUAL'
  devices: string[]
  constraints: string[]
  additionalRequirements: string | null
}

export interface ProjectContextResponse {
  code: number
  message: string
  data: { projectId: number; workflowState: string; staleSections: string[]; updatedAt: string }
  requestId: string
}

export interface ProjectWorkflowTransitionResponse {
  code: number
  message: string
  data: { projectId: number; workflowState: WorkflowState; updatedAt: string }
  requestId: string
}

export interface ProjectUpdatePayload {
  title?: string
  topic?: string
  projectType?: ProjectType
}

export interface ProjectUpdateResponse {
  code: number
  message: string
  data: {
    projectId: number
    title: string
    topic: string
    projectType: ProjectType
    workflowState: WorkflowState
    staleSections: string[]
    updatedAt: string
  }
  requestId: string
}

export interface ProjectDeleteResponse {
  code: number
  message: string
  data: { projectId: number; deleted: true }
  requestId: string
}

export const getProjects = (params: ProjectListParams) =>
  http.get<ProjectListResponse>('/projects', { params })

export const createProject = (payload: ProjectCreatePayload) =>
  http.post<ProjectCreateResponse>('/projects', payload)

export const getProject = (projectId: string | number) =>
  http.get<ProjectDetailResponse>(`/projects/${projectId}`)

export const saveProjectContext = (projectId: string | number, payload: ProjectContextPayload) =>
  http.put<ProjectContextResponse>(`/projects/${projectId}/context`, payload)

export const completeProjectResearch = (projectId: string | number) =>
  http.post<ProjectWorkflowTransitionResponse>(`/projects/${projectId}/research/complete`)

export const updateProject = (projectId: string | number, payload: ProjectUpdatePayload) =>
  http.patch<ProjectUpdateResponse>(`/projects/${projectId}`, payload)

export const deleteProject = (projectId: string | number) =>
  http.delete<ProjectDeleteResponse>(`/projects/${projectId}`)
