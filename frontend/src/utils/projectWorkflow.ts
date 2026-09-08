/**
 * UI-only progress estimates. The persisted source of truth remains
 * course_project.workflow_state; callers must never write progress back.
 */
const workflowProgress: Record<string, number> = {
  DRAFT: 5,
  CONTEXT_READY: 15,
  RESEARCH_READY: 20,
  OBJECTIVE_PENDING: 25,
  OBJECTIVE_CONFIRMED: 35,
  PEDAGOGY_PENDING: 45,
  PEDAGOGY_CONFIRMED: 55,
  ASSESSMENT_PENDING: 65,
  ASSESSMENT_CONFIRMED: 75,
  ACTIVITY_READY: 82,
  QUALITY_READY: 88,
  QUALITY_CHECKED: 95,
  ARTIFACT_READY: 100,
}

export function getProjectProgress(workflowState: string): number {
  return workflowProgress[workflowState] ?? 0
}
