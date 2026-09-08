export type MutableFlag = { value: boolean }

export async function runCourseDesignConfirmation({
  confirming,
  confirm,
  refresh,
  onConfirmed,
  onRefreshFailed,
  onFailed,
  onStart = () => undefined,
  onEnd = () => undefined,
}: {
  confirming: MutableFlag
  confirm: () => Promise<unknown>
  refresh: () => Promise<void>
  onConfirmed: () => void
  onRefreshFailed: () => void
  onFailed: (error: unknown) => void
  onStart?: () => void
  onEnd?: () => void
}) {
  if (confirming.value) return false
  confirming.value = true
  onStart()
  let persisted = false
  try {
    await confirm()
    persisted = true
    await refresh()
    onConfirmed()
    return true
  } catch (error) {
    if (persisted) onRefreshFailed()
    else onFailed(error)
    return false
  } finally {
    confirming.value = false
    onEnd()
  }
}
