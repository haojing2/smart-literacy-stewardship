export function getCourseDesignApiErrorMessage(error: any) {
  if (error?.code === 'ECONNABORTED' || /timeout/i.test(error?.message || '')) {
    return 'AI服务响应时间较长，本次请求已超时，请稍后重试。'
  }
  const detail = error?.response?.data?.detail
  if (typeof detail?.message === 'string') return detail.message
  if (typeof error?.response?.data?.message === 'string') return error.response.data.message
  if (Array.isArray(detail)) {
    return detail.map((item: any) => item?.msg || item?.message).filter(Boolean).join('；') || '请求参数不正确，请检查后重试'
  }
  return error?.message || '操作失败，请稍后重试'
}

export function buildCourseContextPayload(context: {
  grade: number; topic: string; duration: number; classSize: number
  priorExperience: string; equipment: string; requirements: string
}) {
  return {
    grade: context.grade,
    topic: context.topic.trim(),
    lessonMinutes: context.duration,
    classSize: context.classSize,
    studentExperience: context.priorExperience.trim(),
    deviceCondition: context.equipment.trim(),
    additionalRequirements: context.requirements.trim(),
  }
}
