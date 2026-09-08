import { beforeEach, describe, expect, it } from 'vitest'
import { researchMockService } from '@/mocks/researchMockService'
import type { ResearchAnalysis } from '@/types/research'

describe('researchMockService', () => {
  beforeEach(() => localStorage.clear())

  async function readyWorkspace(projectId = 42) {
    const file = new File(['research'], 'study.pdf', { type: 'application/pdf' })
    const resource = await researchMockService.uploadResource(projectId, file)
    await researchMockService.extractText(projectId, resource.resourceId)
    return researchMockService.createSession(projectId, resource.resourceId, 'AI 信息核验')
  }

  it('returns stable assistant output for the same persisted input state', async () => {
    const workspace = await readyWorkspace()
    expect(workspace.session).not.toBeNull()
    expect(workspace.messages.some((message) => message.role === 'SYSTEM')).toBe(true)
    const stateBeforeMessage = localStorage.getItem('research-workbench-demo:42')
    const first = await researchMockService.sendMessage(42, '请继续分析')
    localStorage.setItem('research-workbench-demo:42', stateBeforeMessage ?? '')
    const second = await researchMockService.sendMessage(42, '请继续分析')

    expect(first.assistantMessage.content).toBe(second.assistantMessage.content)
    expect(first.userMessage.content).toBe('请继续分析')
    expect(first.updatedAnalysis).toEqual(second.updatedAnalysis)
    expect(first.readiness).toEqual(second.readiness)
  })

  it('persists a draft and confirmed evidence workflow', async () => {
    const snapshot = await readyWorkspace()
    if (!snapshot.analysis) throw new Error('Expected an analysis for a resource session')
    const complete: ResearchAnalysis = {
      ...snapshot.analysis,
      participants: ['五年级学生'],
      teachingStrategies: ['来源对照'],
      mainFindings: ['信息核验表现提升'],
    }
    const updated = await researchMockService.updateAnalysis(42, complete)
    expect(updated.readiness.readinessStatus).toBe('READY')
    expect(updated.evidenceDraftGenerated).toBe(true)

    const confirmed = await researchMockService.confirmEvidenceCard(42)
    expect(confirmed.status).toBe('CONFIRMED')
    expect((await researchMockService.getWorkspace(42))?.evidenceDraft?.status).toBe('CONFIRMED')
  })
})
