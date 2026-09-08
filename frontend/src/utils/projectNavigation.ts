export type ProjectWorkspaceModule = 'research' | 'course-design' | 'resource-creation'

export function getProjectWorkspaceRoute(
  module: ProjectWorkspaceModule,
  projectId?: number | string | null,
): string {
  const normalizedProjectId = String(projectId ?? '').trim()
  return normalizedProjectId
    ? `/projects/${normalizedProjectId}/${module}`
    : `/${module}`
}

export function getProjectNextRoute(workflowState: string, projectId: number | string): string {
  const routes: Record<string, string> = {
    DRAFT: `/projects/${projectId}/context`,
    CONTEXT_READY: `/projects/${projectId}/research`,
    RESEARCH_READY: `/projects/${projectId}/course-design`,
    OBJECTIVE_PENDING: `/projects/${projectId}/course-design`,
    OBJECTIVE_CONFIRMED: `/projects/${projectId}/course-design`,
    PEDAGOGY_PENDING: `/projects/${projectId}/course-design`,
    PEDAGOGY_CONFIRMED: `/projects/${projectId}/course-design`,
    ASSESSMENT_PENDING: `/projects/${projectId}/course-design`,
    ASSESSMENT_CONFIRMED: `/projects/${projectId}/course-design`,
    ACTIVITY_READY: `/projects/${projectId}/course-design`,
    QUALITY_READY: `/projects/${projectId}/course-design`,
    QUALITY_CHECKED: `/projects/${projectId}/course-design`,
    ARTIFACT_READY: `/projects/${projectId}/course-design`,
  }

  const route = routes[workflowState]
  if (route) return route

  if (import.meta.env.DEV) {
    console.warn(`Unknown project workflow state: ${workflowState}`)
  }
  return `/projects/${projectId}/context`
}
