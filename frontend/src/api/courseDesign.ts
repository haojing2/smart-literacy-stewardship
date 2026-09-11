import http from './http'

export const AI_REQUEST_TIMEOUT = 260_000
const aiRequest = { timeout: AI_REQUEST_TIMEOUT }

export interface ApiEnvelope<T> { code: number; message: string; data: T; requestId: string }
export interface CourseObjective { objectiveId: number; content: string; sourceType: string; teacherAction?: string | null; confirmed: boolean; version: number }
export interface CourseAssessment { assessmentId: number; objectiveId: number; taskContent: string; studentEvidence: string[]; criteria: string[]; teacherAction?: string | null; confirmed: boolean; version: number }
export interface CourseActivity { activityId: number; sequenceNo: number; name: string; duration: number; coreTask: string; teacherAction: string; studentAction: string; aiRole: string; assessment?: string; assessmentNote?: string; scaffolds: string[]; objectiveRefs: number[]; version: number }
export interface CourseDesignState {
  project: { projectId: number; title: string; topic: string }
  context: { grade?: number; lessonMinutes?: number; classSize?: number; studentExperience?: string; deviceCondition?: string; devices?: string[]; additionalRequirements?: string }
  contextDiagnosis: { coreProblem: string; existingFoundation: string; learningDifficulties: string[]; constraints: string[] }
  objectives: CourseObjective[]
  pedagogy: Record<string, any>
  assessments: CourseAssessment[]
  activities: CourseActivity[]
  qualityChecks: QualityCheck[]
  workflowState: string
  staleSections: string[]
  currentStep: number
  completedSteps: number[]
}
export interface QualityCheck { qualityCheckId: number; checkType: string; status: string; issue?: string; reason?: string; suggestion?: string; evidence?: Record<string, any> }

const projectPath = (projectId: number | string) => '/projects/' + projectId
export const getCourseDesign = (projectId: number | string) => http.get<ApiEnvelope<CourseDesignState>>(projectPath(projectId) + '/course-design')
export const saveContext = (projectId: number | string, payload: Record<string, any>) => http.put(projectPath(projectId) + '/context', payload)
export const diagnoseContext = (projectId: number | string) => http.post(projectPath(projectId) + '/context/diagnose', undefined, aiRequest)
export const confirmContext = (projectId: number | string) => http.post(projectPath(projectId) + '/context/confirm')
export const generateObjectives = (projectId: number | string) => http.post(projectPath(projectId) + '/objectives/generate', undefined, aiRequest)
export const keepObjective = (projectId: number | string, objectiveId: number) => http.post(projectPath(projectId) + '/objectives/' + objectiveId + '/keep')
export const updateObjective = (projectId: number | string, objectiveId: number, content: string) => http.patch(projectPath(projectId) + '/objectives/' + objectiveId, { content, action: 'REVISE' })
export const deleteObjective = (projectId: number | string, objectiveId: number) => http.delete(projectPath(projectId) + '/objectives/' + objectiveId)
export const addObjective = (projectId: number | string, content: string) => http.post(projectPath(projectId) + '/objectives', { content })
export const confirmObjectives = (projectId: number | string) => http.post(projectPath(projectId) + '/objectives/confirm')
export const recommendPedagogy = (projectId: number | string) => http.post(projectPath(projectId) + '/pedagogy/recommend', undefined, aiRequest)
export const selectPedagogy = (projectId: number | string, methodId: number) => http.post(projectPath(projectId) + '/pedagogy/select', { methodId })
export const createCustomPedagogy = (projectId: number | string, name: string, description: string) => http.post(projectPath(projectId) + '/pedagogy/custom', { name, description })
export const confirmPedagogy = (projectId: number | string) => http.post(projectPath(projectId) + '/pedagogy/confirm')
export const generateAssessments = (projectId: number | string) => http.post(projectPath(projectId) + '/assessments/generate', undefined, aiRequest)
export const updateAssessment = (projectId: number | string, assessmentId: number, payload: Record<string, any>) => http.patch(projectPath(projectId) + '/assessments/' + assessmentId, payload)
export const regenerateAssessment = (projectId: number | string, assessmentId: number) => http.post(projectPath(projectId) + '/assessments/' + assessmentId + '/regenerate', undefined, aiRequest)
export const confirmAssessments = (projectId: number | string) => http.post(projectPath(projectId) + '/assessments/confirm')
export const generateBlueprint = (projectId: number | string, lessonMinutes: number) =>
  http.post(projectPath(projectId) + '/course-blueprint/generate', { lessonMinutes }, aiRequest)
export const updateActivity = (projectId: number | string, activityId: number, payload: Record<string, any>) => http.patch(projectPath(projectId) + '/activities/' + activityId, payload)
export const regenerateActivity = (projectId: number | string, activityId: number) => http.post(projectPath(projectId) + '/activities/' + activityId + '/regenerate', undefined, aiRequest)
export const transformActivity = (projectId: number | string, activityId: number, action: string) => http.post(projectPath(projectId) + '/activities/' + activityId + '/transform', { action })
export const getDesignEvidence = (projectId: number | string, bizType: string, bizId: number) => http.get(projectPath(projectId) + '/design-evidence', { params: { bizType, bizId } })
export const runQualityCheck = (projectId: number | string) => http.post(projectPath(projectId) + '/quality-check', undefined, aiRequest)
export const getQualityCheck = (projectId: number | string) => http.get(projectPath(projectId) + '/quality-check')
export const applyQualitySuggestion = (projectId: number | string, checkId: number) => http.post(projectPath(projectId) + '/quality-check/' + checkId + '/apply')
