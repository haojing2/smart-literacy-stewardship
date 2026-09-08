import { describe, expect, it, vi } from 'vitest'
import { getProjectNextRoute, getProjectWorkspaceRoute } from '@/utils/projectNavigation'

describe('getProjectNextRoute', () => {
  it('routes a DRAFT project to basic context', () => {
    expect(getProjectNextRoute('DRAFT', 12)).toBe('/projects/12/context')
  })

  it('routes a context-ready project to research', () => {
    expect(getProjectNextRoute('CONTEXT_READY', 12)).toBe('/projects/12/research')
  })

  it('routes a research-ready project to course design', () => {
    expect(getProjectNextRoute('RESEARCH_READY', 12)).toBe('/projects/12/course-design')
  })

  it('routes pending and confirmed course-design states to course design', () => {
    const courseDesignStates = [
      'OBJECTIVE_PENDING',
      'OBJECTIVE_CONFIRMED',
      'PEDAGOGY_PENDING',
      'PEDAGOGY_CONFIRMED',
      'ASSESSMENT_PENDING',
      'ASSESSMENT_CONFIRMED',
      'ACTIVITY_READY',
      'QUALITY_READY',
      'QUALITY_CHECKED',
      'ARTIFACT_READY',
    ]
    for (const state of courseDesignStates) {
      expect(getProjectNextRoute(state, 12)).toBe('/projects/12/course-design')
    }
  })

  it('uses the safe context fallback for an unknown state', () => {
    const warning = vi.spyOn(console, 'warn').mockImplementation(() => undefined)
    expect(getProjectNextRoute('UNRECOGNISED_STATE', 12)).toBe('/projects/12/context')
    warning.mockRestore()
  })
})

describe('getProjectWorkspaceRoute', () => {
  it('retains the project id when switching workspace modules', () => {
    expect(getProjectWorkspaceRoute('research', 27)).toBe('/projects/27/research')
    expect(getProjectWorkspaceRoute('course-design', 27)).toBe('/projects/27/course-design')
    expect(getProjectWorkspaceRoute('resource-creation', 27)).toBe('/projects/27/resource-creation')
  })

  it('uses no-project routes when no project is selected', () => {
    expect(getProjectWorkspaceRoute('research')).toBe('/research')
    expect(getProjectWorkspaceRoute('course-design', '')).toBe('/course-design')
    expect(getProjectWorkspaceRoute('resource-creation', null)).toBe('/resource-creation')
  })
})
