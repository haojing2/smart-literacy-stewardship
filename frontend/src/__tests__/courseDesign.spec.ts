import { describe, expect, it, vi } from 'vitest'

vi.mock('@/api/http', () => ({
  default: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}))

import http from '@/api/http'
import { AI_REQUEST_TIMEOUT, diagnoseContext, generateObjectives } from '@/api/courseDesign'
import { buildCourseContextPayload, getCourseDesignApiErrorMessage } from '@/utils/courseDesign'

describe('course-design API boundary', () => {
  it('keeps grade and lessonMinutes numeric in the context payload', () => {
    const payload = buildCourseContextPayload({
      grade: 4, duration: 40, classSize: 42, topic: ' AI 信息核验 ',
      priorExperience: ' 已有经验 ', equipment: ' 平板 ', requirements: ' 协作 ',
    })
    expect(payload).toMatchObject({ grade: 4, lessonMinutes: 40 })
    expect(typeof payload.grade).toBe('number')
    expect(typeof payload.lessonMinutes).toBe('number')
  })

  it('uses the longer timeout only for AI requests', () => {
    diagnoseContext(12)
    generateObjectives(12)
    expect(vi.mocked(http.post).mock.calls[0]![2]).toEqual({ timeout: AI_REQUEST_TIMEOUT })
    expect(vi.mocked(http.post).mock.calls[1]![2]).toEqual({ timeout: AI_REQUEST_TIMEOUT })
  })

  it('reads FastAPI detail.message and displays a clear timeout prompt', () => {
    expect(getCourseDesignApiErrorMessage({ response: { data: { detail: { message: '教学情境尚未确认' } } } })).toBe('教学情境尚未确认')
    expect(getCourseDesignApiErrorMessage({ code: 'ECONNABORTED', message: 'timeout of 130000ms exceeded' })).toBe('AI服务响应时间较长，本次请求已超时，请稍后重试。')
  })
})
