import { describe, expect, it, vi } from 'vitest'
import { runCourseDesignConfirmation } from '@/utils/courseDesignConfirmation'

describe('course-design confirmation synchronization', () => {
  it.each([
    'OBJECTIVE_CONFIRMED',
    'PEDAGOGY_CONFIRMED',
    'ASSESSMENT_CONFIRMED',
  ])('refreshes the server state after confirmation (%s)', async (workflowState) => {
    const confirming = { value: false }
    const confirm = vi.fn().mockResolvedValue({ data: { workflowState } })
    const refresh = vi.fn().mockResolvedValue(undefined)
    const confirmed = vi.fn()
    await runCourseDesignConfirmation({ confirming, confirm, refresh, onConfirmed: confirmed, onRefreshFailed: vi.fn(), onFailed: vi.fn() })
    expect(confirm).toHaveBeenCalledOnce()
    expect(refresh).toHaveBeenCalledOnce()
    expect(confirmed).toHaveBeenCalledOnce()
    expect(confirming.value).toBe(false)
  })

  it('always releases loading when confirmation fails', async () => {
    const confirming = { value: false }
    const failed = vi.fn()
    await runCourseDesignConfirmation({ confirming, confirm: vi.fn().mockRejectedValue(new Error('failed')), refresh: vi.fn(), onConfirmed: vi.fn(), onRefreshFailed: vi.fn(), onFailed: failed })
    expect(failed).toHaveBeenCalledOnce()
    expect(confirming.value).toBe(false)
  })

  it('does not report a persisted confirmation as a confirmation failure when refresh fails', async () => {
    const confirming = { value: false }
    const refreshFailed = vi.fn()
    const failed = vi.fn()
    await runCourseDesignConfirmation({ confirming, confirm: vi.fn().mockResolvedValue(undefined), refresh: vi.fn().mockRejectedValue(new Error('offline')), onConfirmed: vi.fn(), onRefreshFailed: refreshFailed, onFailed: failed })
    expect(refreshFailed).toHaveBeenCalledOnce()
    expect(failed).not.toHaveBeenCalled()
    expect(confirming.value).toBe(false)
  })

  it('ignores a fast double click while confirmation is in flight', async () => {
    const confirming = { value: false }
    let resolveConfirm: (() => void) | undefined
    const confirm = vi.fn(() => new Promise<void>((resolve) => { resolveConfirm = resolve }))
    const refresh = vi.fn().mockResolvedValue(undefined)
    const first = runCourseDesignConfirmation({ confirming, confirm, refresh, onConfirmed: vi.fn(), onRefreshFailed: vi.fn(), onFailed: vi.fn() })
    const second = await runCourseDesignConfirmation({ confirming, confirm, refresh, onConfirmed: vi.fn(), onRefreshFailed: vi.fn(), onFailed: vi.fn() })
    expect(second).toBe(false)
    expect(confirm).toHaveBeenCalledOnce()
    resolveConfirm?.()
    await first
  })
})
