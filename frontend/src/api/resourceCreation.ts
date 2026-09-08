import http from './http'
import type { ApiEnvelope } from './courseDesign'

const path = (projectId: number | string) => `/projects/${projectId}`

export const getResourceCreation = (projectId: number | string) => http.get<ApiEnvelope<any>>(`${path(projectId)}/resource-creation`)
export const createResourceJob = (projectId: number | string, payload: Record<string, any>) => http.post<ApiEnvelope<any>>(`${path(projectId)}/resource-creation/jobs`, payload)
export const updateResourceJob = (projectId: number | string, jobId: number, payload: Record<string, any>) => http.patch<ApiEnvelope<any>>(`${path(projectId)}/resource-creation/jobs/${jobId}`, payload)
export const recommendResourceSettings = (projectId: number | string, jobId: number) => http.post<ApiEnvelope<any>>(`${path(projectId)}/resource-creation/jobs/${jobId}/recommend-settings`)
export const generateResources = (projectId: number | string, jobId: number) => http.post<ApiEnvelope<any>>(`${path(projectId)}/resource-creation/jobs/${jobId}/generate`)
export const regenerateResources = (projectId: number | string, jobId: number) => http.post<ApiEnvelope<any>>(`${path(projectId)}/resource-creation/jobs/${jobId}/regenerate`)
export const getTeachingResource = (projectId: number | string, resourceId: number) => http.get<ApiEnvelope<any>>(`${path(projectId)}/teaching-resources/${resourceId}`)
export const saveTeachingResourceVersion = (projectId: number | string, resourceId: number, payload: Record<string, any>) => http.post<ApiEnvelope<any>>(`${path(projectId)}/teaching-resources/${resourceId}/versions`, payload)
export const transformTeachingResource = (projectId: number | string, resourceId: number, payload: Record<string, any>) => http.post<ApiEnvelope<any>>(`${path(projectId)}/teaching-resources/${resourceId}/transform`, payload)
export const reviewTeachingResource = (projectId: number | string, resourceId: number, payload: Record<string, any> = {}) => http.post<ApiEnvelope<any>>(`${path(projectId)}/teaching-resources/${resourceId}/review`, payload)
export const createResourceSuggestion = (projectId: number | string, resourceId: number, payload: Record<string, any>) => http.post<ApiEnvelope<any>>(`${path(projectId)}/teaching-resources/${resourceId}/suggestions`, payload)
export const acceptResourceSuggestion = (projectId: number | string, suggestionId: number) => http.post<ApiEnvelope<any>>(`${path(projectId)}/resource-suggestions/${suggestionId}/accept`)
export const reviseResourceSuggestion = (projectId: number | string, suggestionId: number, payload: Record<string, any>) => http.post<ApiEnvelope<any>>(`${path(projectId)}/resource-suggestions/${suggestionId}/revise`, payload)
export const rejectResourceSuggestion = (projectId: number | string, suggestionId: number) => http.post<ApiEnvelope<any>>(`${path(projectId)}/resource-suggestions/${suggestionId}/reject`)
