<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import CourseTimeline from '@/components/course-design/CourseTimeline.vue'
import * as courseDesignApi from '@/api/courseDesign'
import { buildCourseContextPayload, getCourseDesignApiErrorMessage } from '@/utils/courseDesign'
import { runCourseDesignConfirmation } from '@/utils/courseDesignConfirmation'

const route = useRoute()
const projectId = String(route.params.projectId ?? route.query.projectId ?? '')
const currentProject = reactive({
  name: 'AI信息可信度与证据核验',
})
const saveStatus = ref('已自动保存')
const steps = [
  { id: 1, title: '教学情境' },
  { id: 2, title: '教学目标' },
  { id: 3, title: '教学策略' },
  { id: 4, title: '评价设计' },
  { id: 5, title: '课程生成' },
  { id: 6, title: '优化完善' },
]
const currentStep = ref(1)
const completedSteps = ref<number[]>([])
const workflowState = ref('RESEARCH_READY')
const contextForm = reactive({
  grade: 4,
  topic: 'AI信息可信度与证据核验',
  duration: 40,
  priorExperience: '学生已经使用过生成式AI进行简单问答，但缺乏系统的信息核验经验。',
  classSize: 42,
  equipment: '每4名学生共用1台平板，可访问校园网络。',
  requirements: '希望增加小组协作和真实任务。',
})
const isDiagnosing = ref(false)
const isConfirmingContext = ref(false)
const isGeneratingObjectives = ref(false)
const isConfirmingObjectives = ref(false)
const isGeneratingPedagogy = ref(false)
const isConfirmingPedagogy = ref(false)
const isGeneratingAssessments = ref(false)
const isConfirmingAssessments = ref(false)
const isGeneratingBlueprint = ref(false)
const isRunningQualityCheck = ref(false)
const hasDiagnosis = ref(false)
const diagnosis = ref({ coreProblem: '', existingFoundation: '', learningDifficulties: [] as string[], constraints: [] as string[] })
const qualityResult = ref<{ completionChecks: any[]; qualitySummary: any; suggestions: any[] }>({ completionChecks: [], qualitySummary: {}, suggestions: [] })
const qualityCheckLabels: Record<string, string> = {
  CONTEXT_COMPLETE: '教学情境完整',
  OBJECTIVE_CONFIRMED: '教学目标已确认',
  PEDAGOGY_CONFIRMED: '教学策略已确认',
  OBJECTIVE_ASSESSMENT_ALIGNMENT: '目标与评价一致',
  OBJECTIVE_ACTIVITY_ALIGNMENT: '目标与活动一致',
  ACTIVITY_DURATION: '活动时长合理',
  AI_ROLE_DEFINED: 'AI角色明确',
  ADD_SCAFFOLD: '增加学习支架',
  ADD_PROCESS_EVIDENCE: '补充过程性评价证据',
}
const qualityCheckLabel = (checkType: string) => qualityCheckLabels[checkType] ?? '课程质量检查'
type LearningGoal = {
  id: number
  text: string
  source: 'ai' | 'teacher'
  status: 'pending' | 'kept' | 'edited'
  isNew?: boolean
}
const learningGoals = ref<LearningGoal[]>([
  { id: 1, text: '能够识别AI回答中需要进一步核验的事实性信息。', source: 'ai', status: 'pending' },
  { id: 2, text: '能够使用至少两个相对可靠的信息来源核验AI生成内容。', source: 'ai', status: 'pending' },
  { id: 3, text: '能够根据核验获得的证据修改或纠正AI回答。', source: 'ai', status: 'pending' },
])
const editingGoalId = ref<number | null>(null)
const nextGoalId = ref(4)
type TeachingStrategy = {
  id: string
  name: string
  description: string
  source: 'ai' | 'teacher'
}
const recommendedStrategy: TeachingStrategy = {
  id: 'evidence-inquiry',
  name: '证据驱动的问题探究',
  description: '当前课程不仅要求学生认识AI可能出现错误，还要求学生主动寻找证据、比较来源，并据此修订AI回答，因此适合采用真实问题驱动、证据核验与协作讨论相结合的教学策略。',
  source: 'ai',
}
const alternativeStrategies: TeachingStrategy[] = [
  { id: 'case-analysis', name: '案例分析', description: '适合通过典型AI错误案例帮助学生识别问题。', source: 'ai' },
  { id: 'collaborative-inquiry', name: '协作探究', description: '强调小组共同搜索、比较和解释证据。', source: 'ai' },
  { id: 'task-based-learning', name: '任务驱动学习', description: '围绕完成真实的信息核验任务组织课堂。', source: 'ai' },
]
const selectedStrategy = ref<TeachingStrategy | null>(null)
const showAlternatives = ref(false)
const isCustomizingStrategy = ref(false)
const customStrategy = reactive({ name: '', description: '' })
type EvaluationTask = {
  objectiveId: number
  assessmentId?: number
  text: string
  status: 'pending' | 'kept' | 'edited'
  variant: number
}
const evaluationTasks = ref<EvaluationTask[]>([])
const editingEvaluationId = ref<number | null>(null)
const regeneratingEvaluationId = ref<number | null>(null)
const supplementaryRequirement = ref('')
const isPreparingCourse = ref(false)
type BlueprintStage = {
  id: number
  name: string
  duration: string
  task: string
  teacher: string
  student: string
  aiRole: string
  evaluation: string
  scaffolds: string[]
}
const baseBlueprintStages: BlueprintStage[] = [
  { id: 1, name: '发现问题', duration: '5分钟', task: '观察一段看起来可信但包含错误信息的AI回答。', teacher: '展示AI回答，引导学生判断：这段回答可以直接相信吗？', student: '先独立判断，再与小组成员交流判断依据。', aiRole: '情境生成者', evaluation: '记录学生对AI信息可信度的初始判断。', scaffolds: [] },
  { id: 2, name: '证据核验', duration: '15分钟', task: '寻找并比较证据，验证AI回答中的关键信息。', teacher: '提供信息来源可信度判断支架，引导学生比较不同来源。', student: '小组搜索两个以上来源，记录并比较证据。', aiRole: '信息比较助手', evaluation: '来源选择与证据质量。', scaffolds: [] },
  { id: 3, name: '基于证据修订', duration: '15分钟', task: '根据核验结果修改AI回答。', teacher: '引导学生解释修改理由和证据依据。', student: '完成小组修订版AI回答。', aiRole: '反馈伙伴', evaluation: '修订准确性与证据使用质量。', scaffolds: [] },
  { id: 4, name: '反思总结', duration: '5分钟', task: '总结什么时候不能直接相信AI，以及如何进行核验。', teacher: '组织全班提炼信息核验原则。', student: '完成简短Exit Ticket。', aiRole: '总结辅助', evaluation: '形成性反思。', scaffolds: [] },
]
const blueprintStages = reactive<BlueprintStage[]>(baseBlueprintStages.map((stage) => ({ ...stage, scaffolds: [...stage.scaffolds] })))
const editingBlueprintStageId = ref<number | null>(null)
const regeneratingBlueprintStageId = ref<number | null>(null)
const evidenceStage = ref<BlueprintStage | null>(null)
const evidenceDrawerVisible = ref(false)
const evidenceData = ref<any>({ aiLiteracy: [], learningObjectives: [], researchEvidence: [], resources: [], applicableConditions: [], designRationale: '' })
const blueprintStale = ref(false)
const regeneratePromptVisible = ref(false)
const designPreviewVisible = ref(false)
const confirmedObjectives = computed(() => learningGoals.value.filter((goal) => goal.status === 'kept' && goal.text.trim()))
function workflowDebug(event: string, details?: Record<string, unknown>) {
  if (import.meta.env.DEV) console.info('[CourseDesign]', event, details ?? '')
}
function showApiError(error: any) {
  ElMessage.error(getCourseDesignApiErrorMessage(error))
}
function syncState(state: courseDesignApi.CourseDesignState) {
  workflowState.value = state.workflowState
  currentProject.name = state.project.title
  currentStep.value = state.currentStep
  completedSteps.value = state.completedSteps
  contextForm.grade = state.context.grade ?? 4
  contextForm.topic = state.project.topic || contextForm.topic
  contextForm.duration = state.context.lessonMinutes ?? 40
  contextForm.classSize = state.context.classSize ?? contextForm.classSize
  contextForm.priorExperience = state.context.studentExperience ?? ''
  contextForm.equipment = state.context.deviceCondition ?? state.context.devices?.[0] ?? ''
  contextForm.requirements = state.context.additionalRequirements ?? ''
  diagnosis.value = state.contextDiagnosis || diagnosis.value
  hasDiagnosis.value = Boolean(diagnosis.value.coreProblem)
  learningGoals.value = state.objectives.map((item) => ({ id: item.objectiveId, text: item.content, source: item.sourceType === 'TEACHER' ? 'teacher' : 'ai', status: item.teacherAction === 'ACCEPT' ? 'kept' : item.teacherAction === 'REVISE' ? 'edited' : 'pending' }))
  evaluationTasks.value = state.assessments.map((item) => ({ objectiveId: item.objectiveId, assessmentId: item.assessmentId, text: item.taskContent, status: item.confirmed ? 'kept' : item.teacherAction === 'REVISE' ? 'edited' : 'pending', variant: 0 }))
  blueprintStages.splice(0, blueprintStages.length, ...state.activities.map((item) => ({ id: item.activityId, name: item.name, duration: `${item.duration}分钟`, task: item.coreTask, teacher: item.teacherAction, student: item.studentAction, aiRole: item.aiRole, evaluation: item.assessment ?? item.assessmentNote ?? '', scaffolds: item.scaffolds || [] })))
  blueprintStale.value = state.staleSections.includes('ACTIVITY')
  if (state.pedagogy?.pedagogyId) {
    selectedStrategy.value = { id: String(state.pedagogy.primaryMethodId ?? 'custom'), name: state.pedagogy.customName || recommendedStrategy.name, description: state.pedagogy.customDescription || state.pedagogy.rationale || '', source: state.pedagogy.sourceType === 'TEACHER' ? 'teacher' : 'ai' }
  }
  const alternatives = state.pedagogy?.alternatives
  if (alternatives?.recommended) {
    recommendedStrategy.id = String(alternatives.recommended.methodId ?? 'custom')
    recommendedStrategy.name = alternatives.recommended.name
    recommendedStrategy.description = alternatives.recommended.rationale
    alternativeStrategies.splice(0, alternativeStrategies.length, ...(alternatives.alternatives || []).map((item: any) => ({ id: String(item.methodId ?? 'custom'), name: item.name, description: item.rationale, source: 'ai' })))
  }
}
let refreshRequestVersion = 0
async function reloadDesign() {
  if (!projectId) { ElMessage.error('缺少项目编号，请从“我的项目”进入课程智设'); return }
  const requestVersion = ++refreshRequestVersion
  workflowDebug('refresh:start', { requestVersion })
  const { data } = await courseDesignApi.getCourseDesign(projectId)
  if (requestVersion !== refreshRequestVersion) { workflowDebug('refresh:stale', { requestVersion }); return }
  syncState(data.data)
  workflowDebug('refresh:success', { workflowState: data.data.workflowState, currentStep: data.data.currentStep })
}
async function announceConfirmed(message: string) {
  await nextTick()
  document.querySelector('.workspace-card')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  ElMessage.success(message)
}
function saveDraft() {
  saveStatus.value = '已自动保存'
  ElMessage.success('课程状态已保存在服务器')
}

function handleStepChange(step: { id: number }) {
  currentStep.value = step.id
}

async function diagnoseContext() {
  if (!contextForm.topic.trim()) { ElMessage.warning('请补充教学主题'); return }
  if (!contextForm.priorExperience.trim()) { ElMessage.warning('请补充学生已有经验'); return }
  if (!contextForm.equipment.trim()) { ElMessage.warning('请补充设备条件'); return }
  isDiagnosing.value = true
  try {
    await courseDesignApi.saveContext(projectId, buildCourseContextPayload(contextForm))
    await courseDesignApi.diagnoseContext(projectId)
    await reloadDesign()
  } catch (error) { showApiError(error) } finally { isDiagnosing.value = false }
}

async function confirmContext() {
  await runCourseDesignConfirmation({
    confirming: isConfirmingContext,
    confirm: () => courseDesignApi.confirmContext(projectId),
    refresh: reloadDesign,
    onConfirmed: () => { void announceConfirmed('教学情境已确认，请生成学习目标') },
    onRefreshFailed: () => ElMessage.warning('教学情境已确认，但页面状态同步失败，请点击重新加载。'),
    onFailed: showApiError,
    onStart: () => workflowDebug('confirmContext:start'),
    onEnd: () => workflowDebug('confirmContext:end'),
  })
}

async function generateObjectives() {
  if (isGeneratingObjectives.value) return
  isGeneratingObjectives.value = true
  try { await courseDesignApi.generateObjectives(projectId); await reloadDesign(); ElMessage.success('学习目标已生成，请确认采用的目标') } catch (error) { showApiError(error) } finally { isGeneratingObjectives.value = false }
}

function markBlueprintStale() {
  if (!completedSteps.value.includes(5) || blueprintStale.value) return
  blueprintStale.value = true
  regeneratePromptVisible.value = true
}
async function keepGoal(goal: LearningGoal) { try { await courseDesignApi.keepObjective(projectId, goal.id); await reloadDesign() } catch (error) { showApiError(error) } }
function editGoal(goal: LearningGoal) { editingGoalId.value = goal.id }
async function saveGoal(goal: LearningGoal) {
  if (!goal.text.trim()) { ElMessage.warning('请先填写学习目标'); return }
  goal.text = goal.text.trim()
  try {
    if (goal.isNew) await courseDesignApi.addObjective(projectId, goal.text)
    else await courseDesignApi.updateObjective(projectId, goal.id, goal.text)
    editingGoalId.value = null
    await reloadDesign()
  } catch (error) { showApiError(error) }
}
async function deleteGoal(goal: LearningGoal) {
  try {
    await ElMessageBox.confirm('删除后，该学习目标将不再参与后续课程设计。', '删除学习目标', { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' })
    await courseDesignApi.deleteObjective(projectId, goal.id)
    learningGoals.value = learningGoals.value.filter((item) => item.id !== goal.id)
    if (editingGoalId.value === goal.id) editingGoalId.value = null
    markBlueprintStale()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error('删除学习目标失败')
  }
}
function addGoal() {
  const goal: LearningGoal = { id: nextGoalId.value++, text: '', source: 'teacher', status: 'pending', isNew: true }
  learningGoals.value.push(goal)
  editingGoalId.value = goal.id
  markBlueprintStale()
}
function goalTag(goal: LearningGoal) {
  if (goal.isNew && goal.source === 'teacher') return goal.text.trim() ? '教师新增' : '新增目标'
  if (goal.source === 'teacher') return '教师已修改'
  return 'AI推荐'
}
async function confirmGoals() {
  if (!learningGoals.value.some((goal) => goal.status === 'kept' && goal.text.trim())) return
  await runCourseDesignConfirmation({
    confirming: isConfirmingObjectives,
    confirm: () => courseDesignApi.confirmObjectives(projectId),
    refresh: reloadDesign,
    onConfirmed: () => { void announceConfirmed('学习目标已确认，进入教学策略') },
    onRefreshFailed: () => ElMessage.warning('学习目标已确认，但页面状态同步失败，请点击重新加载。'),
    onFailed: showApiError,
    onStart: () => workflowDebug('confirmObjectives:start'),
    onEnd: () => workflowDebug('confirmObjectives:end', { workflowState: workflowState.value, currentStep: currentStep.value }),
  })
}
async function generatePedagogy() {
  if (isGeneratingPedagogy.value) return
  isGeneratingPedagogy.value = true
  try { await courseDesignApi.recommendPedagogy(projectId); await reloadDesign(); ElMessage.success('教学策略已生成，请选择并确认') } catch (error) { showApiError(error) } finally { isGeneratingPedagogy.value = false }
}
async function selectStrategy(strategy: TeachingStrategy) {
  if (!Number.isInteger(Number(strategy.id))) { ElMessage.warning('当前策略不能作为系统教学法选择'); return }
  try { await courseDesignApi.selectPedagogy(projectId, Number(strategy.id)); selectedStrategy.value = { ...strategy }; await reloadDesign() } catch (error) { showApiError(error) }
}
async function saveCustomStrategy() {
  if (!customStrategy.name.trim() || !customStrategy.description.trim()) {
    ElMessage.warning('请填写策略名称和策略说明')
    return
  }
  try { await courseDesignApi.createCustomPedagogy(projectId, customStrategy.name.trim(), customStrategy.description.trim()); isCustomizingStrategy.value = false; await reloadDesign() } catch (error) { showApiError(error) }
}
async function confirmStrategy() {
  if (!selectedStrategy.value) return
  await runCourseDesignConfirmation({
    confirming: isConfirmingPedagogy,
    confirm: () => courseDesignApi.confirmPedagogy(projectId),
    refresh: reloadDesign,
    onConfirmed: () => { void announceConfirmed('教学策略已确认，进入评价设计') },
    onRefreshFailed: () => ElMessage.warning('教学策略已确认，但页面状态同步失败，请点击重新加载。'),
    onFailed: showApiError,
    onStart: () => workflowDebug('confirmPedagogy:start'),
    onEnd: () => workflowDebug('confirmPedagogy:end', { workflowState: workflowState.value, currentStep: currentStep.value }),
  })
}
async function generateAssessments() {
  if (isGeneratingAssessments.value) return
  isGeneratingAssessments.value = true
  try { await courseDesignApi.generateAssessments(projectId); await reloadDesign(); ElMessage.success('评价任务已生成，请确认评价设计') } catch (error) { showApiError(error) } finally { isGeneratingAssessments.value = false }
}
function taskFor(objectiveId: number) {
  return evaluationTasks.value.find((task) => task.objectiveId === objectiveId)
}
function keepEvaluation(task: EvaluationTask) { task.status = 'kept' }
async function saveEvaluation(task: EvaluationTask) {
  if (!task.text.trim()) { ElMessage.warning('请填写评价任务'); return }
  if (!task.assessmentId) return
  try { await courseDesignApi.updateAssessment(projectId, task.assessmentId, { taskContent: task.text.trim() }); editingEvaluationId.value = null; await reloadDesign() } catch (error) { showApiError(error) }
}
async function regenerateEvaluation(task: EvaluationTask) {
  if (!task.assessmentId) return
  regeneratingEvaluationId.value = task.objectiveId
  try { await courseDesignApi.regenerateAssessment(projectId, task.assessmentId); await reloadDesign() } catch (error) { showApiError(error) } finally { regeneratingEvaluationId.value = null }
}
const allObjectivesEvaluated = computed(() => confirmedObjectives.value.length > 0 && confirmedObjectives.value.every((goal) => Boolean(taskFor(goal.id)?.text.trim())))
async function confirmEvaluation() {
  if (!allObjectivesEvaluated.value) return
  await runCourseDesignConfirmation({
    confirming: isConfirmingAssessments,
    confirm: () => courseDesignApi.confirmAssessments(projectId),
    refresh: reloadDesign,
    onConfirmed: () => { void announceConfirmed('评价设计已确认，请生成课程蓝图') },
    onRefreshFailed: () => ElMessage.warning('评价设计已确认，但页面状态同步失败，请点击重新加载。'),
    onFailed: showApiError,
    onStart: () => workflowDebug('confirmAssessments:start'),
    onEnd: () => workflowDebug('confirmAssessments:end', { workflowState: workflowState.value, currentStep: currentStep.value }),
  })
}
async function generateBlueprint() {
  if (isGeneratingBlueprint.value) return
  isGeneratingBlueprint.value = true
  isPreparingCourse.value = true
  try { await courseDesignApi.generateBlueprint(projectId, contextForm.duration); await reloadDesign(); ElMessage.success('课程蓝图已生成') } catch (error) { showApiError(error) } finally { isPreparingCourse.value = false; isGeneratingBlueprint.value = false }
}
async function confirmBlueprint() {
  if (isRunningQualityCheck.value) return
  isRunningQualityCheck.value = true
  try { const { data } = await courseDesignApi.runQualityCheck(projectId); qualityResult.value = data.data; await reloadDesign(); await announceConfirmed('质量检查已完成') } catch (error) { showApiError(error) } finally { isRunningQualityCheck.value = false }
}
async function openEvidence(stage: BlueprintStage) {
  evidenceStage.value = stage
  evidenceDrawerVisible.value = true
  try { const { data } = await courseDesignApi.getDesignEvidence(projectId, 'ACTIVITY', stage.id); evidenceData.value = data.data } catch (error) { showApiError(error) }
}
async function saveBlueprintStage() {
  const stage = blueprintStages.find((item) => item.id === editingBlueprintStageId.value)
  if (!stage) return
  try { await courseDesignApi.updateActivity(projectId, stage.id, { name: stage.name, duration: Number.parseInt(stage.duration, 10), coreTask: stage.task, teacherAction: stage.teacher, studentAction: stage.student, aiRole: stage.aiRole, assessment: stage.evaluation, scaffolds: stage.scaffolds }); editingBlueprintStageId.value = null; await reloadDesign(); ElMessage.success('教学环节已更新') } catch (error) { showApiError(error) }
}
async function regenerateBlueprintStage(stage: BlueprintStage) {
  regeneratingBlueprintStageId.value = stage.id
  try { await courseDesignApi.regenerateActivity(projectId, stage.id); await reloadDesign(); ElMessage.success('教学环节已重新生成') } catch (error) { showApiError(error) } finally { regeneratingBlueprintStageId.value = null }
}
async function transformStage(stage: BlueprintStage, action: string) {
  try { await courseDesignApi.transformActivity(projectId, stage.id, action); await reloadDesign(); ElMessage.success('教学环节已更新') } catch (error) { showApiError(error) }
}
function regenerateWholeBlueprint() {
  regeneratePromptVisible.value = false
  isPreparingCourse.value = true
  courseDesignApi.generateBlueprint(projectId, contextForm.duration).then(reloadDesign).catch(showApiError).finally(() => { isPreparingCourse.value = false })
}
async function applySuggestion(checkId: number) {
  try { await courseDesignApi.applyQualitySuggestion(projectId, checkId); await reloadDesign(); const { data } = await courseDesignApi.getQualityCheck(projectId); qualityResult.value = data.data } catch (error) { showApiError(error) }
}
function saveToProjects() { ElMessage.success('课程设计已保存到“我的项目”') }
onMounted(async () => {
  try {
    await reloadDesign()
    if (currentStep.value === 6) {
      const { data } = await courseDesignApi.getQualityCheck(projectId)
      qualityResult.value = data.data
    }
  } catch (error) { showApiError(error) }
})
</script>

<template>
  <main class="course-design-page">
    <header class="page-header">
      <div>
        <p class="eyebrow">课程智设</p>
        <h1>课程智设</h1>
        <p class="page-description">基于教学情境、研究证据与教师专业判断，共同生成可实施的课程方案</p>
        <p class="project-name">当前项目：{{ currentProject.name }}</p>
      </div>
      <div class="save-area">
        <el-button type="primary" @click="saveDraft">保存草稿</el-button>
        <span>{{ saveStatus }}</span>
      </div>
    </header>

    <CourseTimeline :steps="steps" :current-step="currentStep" :completed-steps="completedSteps" @step-change="handleStepChange" />

    <section v-if="currentStep === 1" class="workspace-card context-workspace">
      <h2>教学情境</h2>
      <p class="workspace-description">告诉智素领航这节课面对什么学生、准备解决什么问题。</p>
      <el-form class="context-form" label-position="top">
        <div class="form-column basics-column">
          <el-form-item label="年级">
            <el-select v-model="contextForm.grade" @change="markBlueprintStale"><el-option label="小学四年级" :value="4" /><el-option label="小学五年级" :value="5" /><el-option label="小学六年级" :value="6" /></el-select>
          </el-form-item>
          <el-form-item label="教学主题"><el-input v-model="contextForm.topic" @input="markBlueprintStale" /></el-form-item>
          <el-form-item label="课时长度"><el-select v-model="contextForm.duration" @change="markBlueprintStale"><el-option label="40分钟" :value="40" /><el-option label="45分钟" :value="45" /><el-option label="80分钟" :value="80" /></el-select></el-form-item>
          <el-form-item label="班级人数"><el-input-number v-model="contextForm.classSize" :min="1" :max="100" controls-position="right" @change="markBlueprintStale" /></el-form-item>
        </div>
        <div class="form-column">
          <el-form-item label="学生已有经验"><el-input v-model="contextForm.priorExperience" type="textarea" :rows="3" resize="none" @input="markBlueprintStale" /></el-form-item>
          <el-form-item label="设备条件"><el-input v-model="contextForm.equipment" type="textarea" :rows="3" resize="none" @input="markBlueprintStale" /></el-form-item>
          <el-form-item label="其他教学要求"><el-input v-model="contextForm.requirements" type="textarea" :rows="3" resize="none" @input="markBlueprintStale" /></el-form-item>
        </div>
      </el-form>

      <div class="diagnosis-action">
        <el-button type="primary" :loading="isDiagnosing" @click="diagnoseContext">AI诊断教学情境</el-button>
        <span v-if="isDiagnosing">正在分析教学需求…</span>
      </div>

      <article v-if="hasDiagnosis" class="diagnosis-card">
        <header><div><h3>教学情境诊断</h3><p>基于当前教学需求的辅助分析</p></div><span>AI分析</span></header>
        <div class="diagnosis-grid">
          <section><h4>核心教学问题</h4><p>{{ diagnosis.coreProblem }}</p></section>
          <section><h4>已有基础</h4><p>{{ diagnosis.existingFoundation }}</p></section>
          <section><h4>潜在学习困难</h4><ul><li v-for="item in diagnosis.learningDifficulties" :key="item">{{ item }}</li></ul></section>
          <section><h4>教学约束</h4><div class="constraint-tags"><span v-for="item in diagnosis.constraints" :key="item">{{ item }}</span></div></section>
        </div>
        <footer><el-button :disabled="isConfirmingContext" @click="diagnoseContext">重新诊断</el-button><el-button type="primary" :loading="isConfirmingContext" :disabled="isConfirmingContext" @click="confirmContext">确认教学情境</el-button><el-button v-if="workflowState === 'RESEARCH_READY'" type="primary" :loading="isGeneratingObjectives" :disabled="isGeneratingObjectives" @click="generateObjectives">生成学习目标</el-button></footer>
      </article>
    </section>

    <section v-else-if="currentStep === 2" class="workspace-card goals-workspace">
      <h2>教学目标</h2>
      <p class="workspace-description">AI根据教学情境和已有研究证据推荐可观察、可评价的学习目标，由教师决定最终采用哪些目标。</p>
      <div class="evidence-bar">
        <div><strong>推荐依据</strong><span>教学情境 · 已选研究证据 · AI素养能力框架</span></div>
        <el-button link type="primary" @click="ElMessageBox.alert('详细研究依据将在后续证据关联功能中完善。', '推荐依据')">查看依据</el-button>
      </div>
      <p class="teacher-note">AI提供建议，最终教学目标由教师确认。</p>
      <div class="goal-list">
        <article v-for="(goal, index) in learningGoals" :key="goal.id" class="goal-card" :class="{ kept: goal.status === 'kept' }">
          <header><span class="goal-index">目标 {{ index + 1 }}</span><span class="goal-tag">{{ goalTag(goal) }}</span></header>
          <el-input v-if="editingGoalId === goal.id" v-model="goal.text" type="textarea" :rows="3" resize="none" placeholder="请输入学习目标" />
          <p v-else class="goal-text">{{ goal.text || '尚未填写学习目标' }}</p>
          <footer>
            <span v-if="goal.status === 'kept'" class="kept-status">已保留</span><span v-else></span>
            <div>
              <el-button v-if="editingGoalId === goal.id" type="primary" link @click="saveGoal(goal)">保存</el-button>
              <el-button v-else link type="primary" @click="keepGoal(goal)">保留</el-button>
              <el-button v-if="editingGoalId !== goal.id" link @click="editGoal(goal)">编辑</el-button>
              <el-button link class="delete-button" @click="deleteGoal(goal)">删除</el-button>
            </div>
          </footer>
        </article>
      </div>
      <el-button class="add-goal" text @click="addGoal">＋ 添加学习目标</el-button>
      <footer class="goal-actions">
        <el-button @click="currentStep = 1">返回教学情境</el-button>
        <el-button type="primary" :loading="isConfirmingObjectives" :disabled="isConfirmingObjectives || !learningGoals.some((goal) => goal.status === 'kept' && goal.text.trim())" @click="confirmGoals">确认学习目标</el-button>
      </footer>
    </section>

    <section v-else-if="currentStep === 3" class="workspace-card strategy-workspace">
      <h2>教学策略</h2>
      <p class="workspace-description">根据教学目标、学生特点和研究证据，AI推荐适合当前课程的教学策略，最终由教师确定。</p>
      <article class="recommended-strategy" :class="{ selected: selectedStrategy?.id === recommendedStrategy.id }">
        <header><div><span class="recommendation-label">重点推荐</span><h3>{{ recommendedStrategy.name }}</h3></div><span class="goal-tag">AI推荐</span></header>
        <p>{{ recommendedStrategy.description }}</p>
        <div class="strategy-elements"><span>真实问题情境</span><span>小组协作</span><span>多来源核验</span><span>证据比较</span><span>反思修订</span></div>
        <footer><span v-if="selectedStrategy?.id === recommendedStrategy.id" class="kept-status">教师已确认</span><span v-else></span><div><el-button link type="primary" @click="ElMessageBox.alert('• 与当前学习目标匹配\n• 与学生已有AI使用经验匹配\n• 支持形成证据核验与修订过程', '推荐依据')">为什么推荐？</el-button><el-button type="primary" @click="selectStrategy(recommendedStrategy)">采用此策略</el-button></div></footer>
      </article>
      <div class="strategy-tools"><el-button @click="showAlternatives = !showAlternatives">{{ showAlternatives ? '收起其他策略' : '查看其他策略' }}</el-button><el-button @click="isCustomizingStrategy = !isCustomizingStrategy">自定义策略</el-button></div>
      <section v-if="showAlternatives" class="alternative-strategies" aria-label="其他推荐策略">
        <article v-for="strategy in alternativeStrategies" :key="strategy.id" :class="{ selected: selectedStrategy?.id === strategy.id }"><div><h3>{{ strategy.name }}</h3><p>{{ strategy.description }}</p></div><el-button link type="primary" @click="selectStrategy(strategy)">{{ selectedStrategy?.id === strategy.id ? '已选择' : '选择' }}</el-button></article>
      </section>
      <section v-if="isCustomizingStrategy" class="custom-strategy">
        <h3>自定义策略</h3><p>由教师补充适合本课的教学策略。</p>
        <el-form label-position="top"><el-form-item label="策略名称"><el-input v-model="customStrategy.name" placeholder="请输入策略名称" /></el-form-item><el-form-item label="策略说明"><el-input v-model="customStrategy.description" type="textarea" :rows="3" resize="none" placeholder="说明该策略如何组织课堂" /></el-form-item></el-form>
        <footer><el-button @click="isCustomizingStrategy = false">取消</el-button><el-button type="primary" @click="saveCustomStrategy">保存策略</el-button></footer>
      </section>
      <div v-if="selectedStrategy?.source === 'teacher'" class="selected-strategy-summary"><span>教师自定义</span><strong>{{ selectedStrategy.name }}</strong></div>
      <footer class="goal-actions strategy-actions"><el-button @click="currentStep = 2">返回教学目标</el-button><el-button v-if="workflowState === 'OBJECTIVE_CONFIRMED'" type="primary" :loading="isGeneratingPedagogy" :disabled="isGeneratingPedagogy" @click="generatePedagogy">AI推荐教学策略</el-button><el-button type="primary" :loading="isConfirmingPedagogy" :disabled="isConfirmingPedagogy || !selectedStrategy || workflowState !== 'PEDAGOGY_PENDING'" @click="confirmStrategy">确认教学策略</el-button></footer>
    </section>

    <section v-else-if="currentStep === 4" class="workspace-card evaluation-workspace">
      <h2>评价设计</h2>
      <p class="workspace-description">为已经确认的学习目标设计可观察、可评价的学习任务，确保目标与评价保持一致。</p>
      <p class="alignment-heading">目标 <span>—</span> 活动 <span>—</span> 评价一致性</p>
      <div class="evaluation-list">
        <article v-for="(objective, index) in confirmedObjectives" :key="objective.id" class="evaluation-card">
          <header><span>目标 {{ index + 1 }}</span><em :class="{ incomplete: !taskFor(objective.id)?.text.trim() }">{{ taskFor(objective.id)?.text.trim() ? '目标 ✓ 评价 ✓' : '待完善' }}</em></header>
          <p class="objective-text">{{ objective.text }}</p>
          <div class="task-area"><strong>评价任务</strong><el-input v-if="editingEvaluationId === objective.id" v-model="taskFor(objective.id)!.text" type="textarea" :rows="3" resize="none" /><p v-else>{{ taskFor(objective.id)?.text || '尚未设置评价任务' }}</p></div>
          <footer><span v-if="taskFor(objective.id)?.status === 'kept'" class="kept-status">已保留</span><span v-else></span><div><el-button v-if="editingEvaluationId === objective.id" type="primary" link @click="saveEvaluation(taskFor(objective.id)!)">保存</el-button><el-button v-else link type="primary" @click="keepEvaluation(taskFor(objective.id)!)">保留</el-button><el-button v-if="editingEvaluationId !== objective.id" link @click="editingEvaluationId = objective.id">修改</el-button><el-button link :loading="regeneratingEvaluationId === objective.id" @click="regenerateEvaluation(taskFor(objective.id)!)">重新生成</el-button></div></footer>
        </article>
      </div>
      <el-form class="supplementary-form" label-position="top"><el-form-item label="补充评价要求（可选）"><el-input v-model="supplementaryRequirement" type="textarea" :rows="2" resize="none" placeholder="例如：希望增加对小组合作过程的观察。" /></el-form-item></el-form>
      <footer class="goal-actions"><el-button @click="currentStep = 3">返回教学策略</el-button><el-button v-if="workflowState === 'PEDAGOGY_CONFIRMED'" type="primary" :loading="isGeneratingAssessments" :disabled="isGeneratingAssessments" @click="generateAssessments">AI生成评价任务</el-button><el-button type="primary" :loading="isConfirmingAssessments" :disabled="isConfirmingAssessments || workflowState !== 'ASSESSMENT_PENDING' || !allObjectivesEvaluated" @click="confirmEvaluation">确认评价设计</el-button></footer>
    </section>

    <section v-else-if="currentStep === 5" class="workspace-card blueprint-workspace">
      <template v-if="isPreparingCourse">
        <div class="blueprint-loading"><span class="course-loading" aria-hidden="true"></span><h2>正在生成课程蓝图</h2><p>正在结合教学情境、学习目标、教学策略与评价设计生成课程方案…</p></div>
      </template>
      <template v-else>
        <header class="blueprint-header"><div><h2>课程蓝图</h2><p>先查看课程整体结构，再对具体教学环节进行调整。</p></div><div class="blueprint-meta"><span>小学{{ contextForm.grade }}年级</span><span>{{ contextForm.duration }}分钟</span><span>{{ contextForm.topic }}</span><span>{{ selectedStrategy?.name }}</span></div><el-button v-if="workflowState === 'ASSESSMENT_CONFIRMED'" type="primary" :loading="isGeneratingBlueprint" :disabled="isGeneratingBlueprint" @click="generateBlueprint">生成课程蓝图</el-button></header>
        <p class="blueprint-stats">{{ blueprintStages.length }}个教学环节 · {{ contextForm.duration }}分钟 · {{ confirmedObjectives.length }}个学习目标 · {{ evaluationTasks.filter((task) => task.text.trim()).length }}项核心评价</p>
        <section class="blueprint-flow" aria-label="课程教学环节">
          <article v-for="stage in blueprintStages" :key="stage.id" class="blueprint-stage">
            <header><div class="stage-title"><span>{{ stage.id }}</span><div><h3>{{ stage.name }}</h3><small>{{ stage.duration }}</small></div></div><el-dropdown trigger="click"><button class="stage-menu" type="button" aria-label="环节操作">···</button><template #dropdown><el-dropdown-menu><el-dropdown-item @click="editingBlueprintStageId = stage.id">编辑</el-dropdown-item><el-dropdown-item @click="regenerateBlueprintStage(stage)">重新生成</el-dropdown-item><el-dropdown-item @click="transformStage(stage, 'SHORTEN')">缩短时间</el-dropdown-item><el-dropdown-item @click="transformStage(stage, 'INCREASE_DIFFICULTY')">增加难度</el-dropdown-item><el-dropdown-item @click="transformStage(stage, 'DECREASE_DIFFICULTY')">降低难度</el-dropdown-item><el-dropdown-item @click="transformStage(stage, 'ADD_SCAFFOLD')">增加支架</el-dropdown-item><el-dropdown-item divided @click="openEvidence(stage)">查看设计依据</el-dropdown-item></el-dropdown-menu></template></el-dropdown></header>
            <template v-if="editingBlueprintStageId === stage.id">
              <el-form class="stage-edit-form" label-position="top"><el-form-item label="核心任务"><el-input v-model="stage.task" type="textarea" :rows="2" resize="none" /></el-form-item><el-form-item label="教师活动"><el-input v-model="stage.teacher" type="textarea" :rows="2" resize="none" /></el-form-item><el-form-item label="学生活动"><el-input v-model="stage.student" type="textarea" :rows="2" resize="none" /></el-form-item><el-form-item label="AI角色"><el-input v-model="stage.aiRole" /></el-form-item><el-form-item label="评价"><el-input v-model="stage.evaluation" type="textarea" :rows="2" resize="none" /></el-form-item></el-form><footer class="stage-edit-actions"><el-button @click="editingBlueprintStageId = null">取消</el-button><el-button type="primary" @click="saveBlueprintStage">保存</el-button></footer>
            </template>
            <template v-else>
              <div class="stage-task"><strong>核心任务</strong><p>{{ stage.task }}</p></div>
              <p v-if="regeneratingBlueprintStageId === stage.id" class="stage-regenerating">正在重新生成该教学环节…</p>
              <dl><div><dt>教师活动</dt><dd>{{ stage.teacher }}</dd></div><div><dt>学生活动</dt><dd>{{ stage.student }}</dd></div><div><dt>AI角色</dt><dd>{{ stage.aiRole }}</dd></div><div><dt>评价</dt><dd>{{ stage.evaluation }}</dd></div></dl>
              <div v-if="stage.scaffolds.length" class="stage-scaffolds"><strong>学习支架</strong><span v-for="scaffold in stage.scaffolds" :key="scaffold">{{ scaffold }}</span></div>
            </template>
          </article>
        </section>
        <footer class="goal-actions blueprint-actions"><el-button @click="currentStep = 4">返回评价设计</el-button><el-button type="primary" :loading="isRunningQualityCheck" :disabled="workflowState !== 'ACTIVITY_READY' || isRunningQualityCheck" @click="confirmBlueprint">开始质量检查</el-button></footer>
      </template>
    </section>

    <section v-else class="workspace-card next-step-placeholder">
      <div class="optimization-header"><h2>优化完善</h2><p>检查课程整体一致性，并完成最后调整。</p></div>
      <section class="optimization-section"><h3>课程完整性检查</h3><ul class="completion-checklist"><li v-for="check in qualityResult.completionChecks" :key="check.qualityCheckId">{{ qualityCheckLabel(check.checkType) }}：{{ check.status === 'PASS' ? '通过' : check.issue }}</li></ul></section>
      <section class="optimization-section suggestions"><h3>智能检查建议</h3><p class="quality-label">整体设计质量：<strong>{{ qualityResult.qualitySummary.warnings ? '需优化' : '良好' }}</strong></p><article v-for="suggestion in qualityResult.suggestions" :key="suggestion.qualityCheckId"><h4>{{ qualityCheckLabel(suggestion.checkType) }}</h4><p>{{ suggestion.issue || suggestion.reason }}</p><div><span>{{ suggestion.suggestion }}</span><el-button @click="applySuggestion(suggestion.qualityCheckId)">应用建议</el-button></div></article></section>
      <section class="optimization-section final-status"><h3>课程设计已完成</h3><p>{{ blueprintStages.length }}个教学环节 · {{ contextForm.duration }}分钟 · {{ confirmedObjectives.length }}个学习目标 · {{ evaluationTasks.filter((task) => task.text.trim()).length }}项核心评价任务 · 已关联研究依据</p></section>
      <footer class="goal-actions final-actions"><el-button @click="currentStep = 5">返回课程蓝图</el-button><div><el-button @click="designPreviewVisible = true">生成完整教学设计</el-button><el-button type="primary" @click="saveToProjects">保存到我的项目</el-button></div></footer>
    </section>
  </main>

  <el-drawer v-model="evidenceDrawerVisible" title="设计依据" size="420px">
    <template v-if="evidenceStage"><section class="evidence-section"><h3>对应AI素养能力</h3><p v-for="item in evidenceData.aiLiteracy" :key="item.id">{{ item.dimension }}：{{ item.performance }}</p></section><section class="evidence-section"><h3>对应学习目标</h3><p v-for="item in evidenceData.learningObjectives" :key="item.objectiveId">{{ item.content }}</p></section><section v-for="item in evidenceData.researchEvidence" :key="item.id" class="evidence-section research-evidence"><h3>研究证据</h3><strong>{{ item.authors }} · {{ item.year }}</strong><p>{{ item.title }}</p><small>{{ item.mainFinding }}（{{ item.sourceDocument }} {{ item.sourcePage }}）</small></section><section class="evidence-section"><h3>课程资源</h3><p>{{ evidenceData.resources.join('、') || '暂无' }}</p></section><section class="evidence-section"><h3>适用条件</h3><ul><li v-for="item in evidenceData.applicableConditions" :key="item">{{ item }}</li></ul></section><section class="evidence-section"><h3>设计理由</h3><p>{{ evidenceData.designRationale }}</p></section></template>
  </el-drawer>

  <el-dialog v-model="regeneratePromptVisible" title="上游设计已发生变化" width="440px"><p>当前课程蓝图基于之前的教学决策生成。是否根据最新内容重新生成？</p><template #footer><el-button @click="regeneratePromptVisible = false">稍后处理</el-button><el-button type="primary" @click="regenerateWholeBlueprint">重新生成课程</el-button></template></el-dialog>
  <el-dialog v-model="designPreviewVisible" title="完整教学设计预览" width="720px"><div class="design-preview"><section><h3>学情分析</h3><p>{{ contextForm.priorExperience }}</p></section><section><h3>教学目标</h3><ul><li v-for="objective in confirmedObjectives" :key="objective.id">{{ objective.text }}</li></ul></section><section><h3>教学重点与难点</h3><p>重点：信息判断与证据核验。难点：比较证据并说明修改理由。</p></section><section><h3>教学流程</h3><p>{{ blueprintStages.map((stage) => `${stage.name}（${stage.duration}）`).join(' → ') }}</p></section><section><h3>评价设计</h3><ul><li v-for="task in evaluationTasks" :key="task.objectiveId">{{ task.text }}</li></ul></section></div></el-dialog>
</template>

<style scoped>
.course-design-page { width: min(1280px, 100%); min-height: 100%; margin: 0 auto; color: #101828; }
.page-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 32px; padding: 4px 2px 26px; }
.eyebrow { margin: 0 0 7px; color: #1677ff; font-size: 13px; font-weight: 650; }
h1 { margin: 0; color: #101828; font-size: 27px; font-weight: 650; letter-spacing: -.02em; }
.page-description { margin: 10px 0 0; color: #667085; font-size: 14px; line-height: 1.65; }
.project-name { margin: 10px 0 0; color: #98a2b3; font-size: 13px; }
.save-area { display: flex; flex: none; align-items: center; gap: 10px; padding-top: 17px; }.save-area span { color: #98a2b3; font-size: 13px; white-space: nowrap; }
.workspace-card { border: 1px solid #eaecf0; border-radius: 12px; background: #fff; box-shadow: 0 2px 10px rgb(16 24 40 / 4%); }.workspace-card h2 { margin: 0; color: #1d2939; font-size: 17px; font-weight: 650; }
.workspace-card { min-height: 390px; margin-top: 18px; padding: 26px 28px; }.workspace-description { margin: 8px 0 0; color: #667085; font-size: 14px; }
.context-form { display: grid; grid-template-columns: minmax(250px, .82fr) minmax(340px, 1.18fr); gap: 28px; margin-top: 26px; }.form-column { display: grid; align-content: start; gap: 1px; }.context-form :deep(.el-form-item) { margin-bottom: 17px; }.context-form :deep(.el-form-item__label) { padding-bottom: 7px; color: #344054; font-size: 13px; font-weight: 600; line-height: 1.35; }.context-form :deep(.el-select), .context-form :deep(.el-input-number) { width: 100%; }.context-form :deep(.el-textarea__inner) { line-height: 1.65; }
.diagnosis-action { display: flex; align-items: center; gap: 12px; margin-top: 3px; padding-top: 22px; border-top: 1px solid #edf0f3; }.diagnosis-action span { color: #667085; font-size: 13px; }
.diagnosis-card { margin-top: 24px; overflow: hidden; border: 1px solid #dbe8f8; border-radius: 12px; background: #fbfdff; }.diagnosis-card>header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; padding: 19px 21px 16px; border-bottom: 1px solid #e6eef8; }.diagnosis-card h3 { margin: 0; color: #1d2939; font-size: 16px; font-weight: 650; }.diagnosis-card header p { margin: 5px 0 0; color: #667085; font-size: 12px; }.diagnosis-card header span { padding: 3px 8px; border: 1px solid #dbe8f8; border-radius: 10px; color: #4774a8; background: #f4f8fd; font-size: 11px; }.diagnosis-grid { display: grid; grid-template-columns: 1fr 1fr; }.diagnosis-grid section { min-height: 126px; padding: 18px 21px; border-right: 1px solid #e6eef8; border-bottom: 1px solid #e6eef8; }.diagnosis-grid section:nth-child(2n) { border-right: 0; }.diagnosis-grid section:nth-last-child(-n+2) { border-bottom: 0; }.diagnosis-grid h4 { margin: 0; color: #344054; font-size: 13px; font-weight: 650; }.diagnosis-grid p, .diagnosis-grid ul { margin: 8px 0 0; color: #667085; font-size: 13px; line-height: 1.7; }.diagnosis-grid ul { padding-left: 18px; }.diagnosis-grid li+li { margin-top: 3px; }.constraint-tags { display: flex; flex-wrap: wrap; gap: 7px; margin-top: 10px; }.constraint-tags span { padding: 4px 8px; border-radius: 5px; color: #4774a8; background: #edf5ff; font-size: 12px; }.diagnosis-card footer { display: flex; justify-content: flex-end; gap: 10px; padding: 16px 21px; border-top: 1px solid #e6eef8; background: #fff; }
.next-step-placeholder { display: grid; min-height: 340px; place-content: center; text-align: center; }.next-step-placeholder p { margin: 9px 0 0; color: #98a2b3; font-size: 14px; }
.goals-workspace { min-height: 480px; }.evidence-bar { display: flex; align-items: center; justify-content: space-between; gap: 18px; margin-top: 22px; padding: 13px 15px; border: 1px solid #e6eef8; border-radius: 8px; background: #f8fbff; }.evidence-bar>div { display: flex; align-items: center; gap: 12px; min-width: 0; }.evidence-bar strong { color: #344054; font-size: 13px; font-weight: 650; }.evidence-bar span { overflow: hidden; color: #667085; font-size: 13px; text-overflow: ellipsis; white-space: nowrap; }.teacher-note { margin: 15px 0 0; color: #667085; font-size: 13px; }.goal-list { display: grid; gap: 12px; margin-top: 20px; }.goal-card { padding: 17px 18px; border: 1px solid #eaecf0; border-radius: 10px; background: #fff; transition: border-color .18s ease, box-shadow .18s ease; }.goal-card:hover { border-color: #c9dcef; box-shadow: 0 2px 7px rgb(16 24 40 / 4%); }.goal-card.kept { border-color: #cfe2f8; background: #fbfdff; }.goal-card header, .goal-card footer { display: flex; align-items: center; justify-content: space-between; gap: 12px; }.goal-index { color: #475467; font-size: 12px; font-weight: 650; }.goal-tag { padding: 3px 8px; border-radius: 10px; color: #4774a8; background: #edf5ff; font-size: 11px; }.goal-text { min-height: 22px; margin: 12px 0 15px; color: #344054; font-size: 14px; line-height: 1.65; }.goal-card :deep(.el-textarea) { margin: 12px 0 14px; }.goal-card footer>div { display: flex; gap: 3px; }.goal-card footer :deep(.el-button) { margin: 0; }.kept-status { color: #1677ff; font-size: 12px; }.delete-button { color: #98a2b3; }.delete-button:hover { color: #d92d20; }.add-goal { margin-top: 8px; color: #1677ff; }.goal-actions { display: flex; justify-content: space-between; margin-top: 24px; padding-top: 18px; border-top: 1px solid #edf0f3; }
.strategy-workspace { min-height: 530px; }.recommended-strategy { margin-top: 23px; padding: 21px 22px; border: 1px solid #dbe8f8; border-radius: 12px; background: #fbfdff; }.recommended-strategy.selected, .alternative-strategies article.selected { border-color: #9cc5f6; box-shadow: 0 0 0 2px rgb(22 119 255 / 6%); }.recommended-strategy header, .recommended-strategy footer { display: flex; align-items: flex-start; justify-content: space-between; gap: 14px; }.recommendation-label { color: #1677ff; font-size: 12px; font-weight: 650; }.recommended-strategy h3, .alternative-strategies h3, .custom-strategy h3 { margin: 6px 0 0; color: #1d2939; font-size: 17px; font-weight: 650; }.recommended-strategy>p { max-width: 880px; margin: 13px 0 0; color: #667085; font-size: 14px; line-height: 1.75; }.strategy-elements { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 16px; }.strategy-elements span { padding: 5px 9px; border-radius: 5px; color: #4774a8; background: #edf5ff; font-size: 12px; }.recommended-strategy footer { align-items: center; margin-top: 20px; }.recommended-strategy footer>div { display: flex; gap: 10px; }.recommended-strategy footer :deep(.el-button) { margin: 0; }.strategy-tools { display: flex; gap: 10px; margin-top: 16px; }.strategy-tools :deep(.el-button) { margin: 0; }.alternative-strategies { display: grid; gap: 10px; margin-top: 14px; }.alternative-strategies article { display: flex; align-items: center; justify-content: space-between; gap: 18px; padding: 15px 17px; border: 1px solid #eaecf0; border-radius: 9px; background: #fff; }.alternative-strategies h3 { margin: 0; font-size: 14px; }.alternative-strategies p { margin: 6px 0 0; color: #667085; font-size: 13px; }.alternative-strategies :deep(.el-button) { flex: none; margin: 0; }.custom-strategy { margin-top: 14px; padding: 19px; border: 1px solid #e6eef8; border-radius: 10px; background: #f8fbff; }.custom-strategy h3 { margin: 0; font-size: 15px; }.custom-strategy>p { margin: 7px 0 17px; color: #667085; font-size: 13px; }.custom-strategy :deep(.el-form-item) { margin-bottom: 15px; }.custom-strategy :deep(.el-form-item__label) { padding-bottom: 6px; color: #344054; font-size: 13px; font-weight: 600; }.custom-strategy footer { display: flex; justify-content: flex-end; gap: 10px; }.custom-strategy footer :deep(.el-button) { margin: 0; }.strategy-actions { margin-top: 26px; }
.selected-strategy-summary { display: flex; align-items: center; gap: 9px; margin-top: 14px; padding: 11px 13px; border: 1px solid #dbe8f8; border-radius: 8px; background: #f8fbff; }.selected-strategy-summary span { padding: 3px 7px; border-radius: 9px; color: #4774a8; background: #edf5ff; font-size: 11px; }.selected-strategy-summary strong { color: #344054; font-size: 13px; font-weight: 600; }
.evaluation-workspace { min-height: 570px; }.alignment-heading { margin: 19px 0 0; color: #344054; font-size: 14px; font-weight: 650; }.alignment-heading span { margin: 0 7px; color: #1677ff; }.evaluation-list { display: grid; gap: 13px; margin-top: 16px; }.evaluation-card { padding: 18px 19px; border: 1px solid #eaecf0; border-radius: 10px; background: #fff; }.evaluation-card header, .evaluation-card footer { display: flex; align-items: center; justify-content: space-between; gap: 12px; }.evaluation-card header>span { color: #475467; font-size: 12px; font-weight: 650; }.evaluation-card em { padding: 3px 8px; border-radius: 10px; color: #4774a8; background: #edf5ff; font-size: 11px; font-style: normal; }.evaluation-card em.incomplete { color: #98a2b3; background: #f2f4f7; }.objective-text { margin: 11px 0 14px; color: #344054; font-size: 14px; line-height: 1.65; }.task-area { padding: 13px 14px; border-radius: 8px; background: #f8fbff; }.task-area strong { color: #475467; font-size: 12px; font-weight: 650; }.task-area p { margin: 7px 0 0; color: #667085; font-size: 13px; line-height: 1.7; }.task-area :deep(.el-textarea) { display: block; margin-top: 8px; }.evaluation-card footer { margin-top: 14px; }.evaluation-card footer>div { display: flex; gap: 3px; }.evaluation-card footer :deep(.el-button) { margin: 0; }.supplementary-form { margin-top: 19px; padding: 17px 18px 2px; border: 1px solid #edf0f3; border-radius: 9px; background: #fbfcfe; }.supplementary-form :deep(.el-form-item__label) { padding-bottom: 6px; color: #344054; font-size: 13px; font-weight: 600; }.course-loading { display: inline-block; width: 28px; height: 28px; margin: 0 auto 10px; border: 2px solid #dbe8f8; border-top-color: #1677ff; border-radius: 50%; animation: course-spin .8s linear infinite; }@keyframes course-spin { to { transform: rotate(360deg); } }
.blueprint-workspace { min-height: 560px; }.blueprint-loading { display: grid; min-height: 360px; place-content: center; text-align: center; }.blueprint-loading h2 { margin: 0; font-size: 18px; }.blueprint-loading p { margin: 9px 0 0; color: #667085; font-size: 13px; }.blueprint-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 22px; }.blueprint-header h2 { font-size: 20px; }.blueprint-header>div>p { margin: 8px 0 0; color: #667085; font-size: 13px; }.blueprint-meta { display: flex; max-width: 570px; flex-wrap: wrap; justify-content: flex-end; gap: 7px; }.blueprint-meta span { padding: 4px 8px; border-radius: 5px; color: #4774a8; background: #edf5ff; font-size: 12px; }.blueprint-stats { margin: 19px 0 0; padding: 11px 13px; border: 1px solid #e6eef8; border-radius: 8px; color: #475467; background: #f8fbff; font-size: 13px; }.blueprint-flow { display: grid; gap: 13px; margin-top: 17px; }.blueprint-stage { position: relative; padding: 18px 19px; border: 1px solid #eaecf0; border-radius: 10px; background: #fff; }.blueprint-stage>header { display: flex; align-items: flex-start; justify-content: space-between; gap: 14px; }.stage-title { display: flex; align-items: center; gap: 10px; }.stage-title>span { display: grid; width: 27px; height: 27px; place-items: center; border-radius: 8px; color: #1677ff; background: #edf5ff; font-size: 12px; font-weight: 700; }.stage-title h3 { margin: 0; color: #1d2939; font-size: 16px; font-weight: 650; }.stage-title small { display: block; margin-top: 3px; color: #98a2b3; font-size: 12px; }.stage-menu { width: 30px; height: 28px; border: 1px solid #eaecf0; border-radius: 6px; color: #667085; background: #fff; cursor: pointer; font: inherit; font-weight: 700; line-height: 1; }.stage-menu:hover { color: #1677ff; background: #f8fbff; }.stage-task { margin-top: 15px; padding: 11px 13px; border-radius: 8px; background: #f8fbff; }.stage-task strong, .blueprint-stage dt { color: #475467; font-size: 12px; font-weight: 650; }.stage-task p { margin: 5px 0 0; color: #344054; font-size: 14px; line-height: 1.6; }.blueprint-stage dl { display: grid; grid-template-columns: 1fr 1fr; gap: 12px 28px; margin: 15px 0 0; }.blueprint-stage dl div { min-width: 0; }.blueprint-stage dt { margin: 0; }.blueprint-stage dd { margin: 5px 0 0; color: #667085; font-size: 13px; line-height: 1.65; }.blueprint-actions { margin-top: 22px; }
.stage-edit-form { display: grid; grid-template-columns: 1fr 1fr; gap: 0 15px; margin-top: 17px; }.stage-edit-form :deep(.el-form-item) { margin-bottom: 14px; }.stage-edit-form :deep(.el-form-item:first-child), .stage-edit-form :deep(.el-form-item:last-child) { grid-column: 1 / -1; }.stage-edit-form :deep(.el-form-item__label) { padding-bottom: 5px; color: #475467; font-size: 12px; font-weight: 650; }.stage-edit-actions { display: flex; justify-content: flex-end; gap: 9px; }.stage-edit-actions :deep(.el-button) { margin: 0; }.stage-regenerating { margin: 11px 0 -3px; color: #1677ff; font-size: 12px; }.stage-scaffolds { display: flex; align-items: center; flex-wrap: wrap; gap: 7px; margin-top: 14px; }.stage-scaffolds strong { margin-right: 2px; color: #475467; font-size: 12px; }.stage-scaffolds span { padding: 4px 8px; border-radius: 5px; color: #4774a8; background: #edf5ff; font-size: 12px; }
.optimization-header h2 { font-size: 20px; }.optimization-header>p { margin: 8px 0 0; color: #667085; font-size: 14px; }.optimization-section { margin-top: 20px; padding: 19px 20px; border: 1px solid #eaecf0; border-radius: 10px; background: #fff; }.optimization-section h3 { margin: 0; color: #1d2939; font-size: 16px; font-weight: 650; }.completion-checklist { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 11px 20px; margin: 15px 0 0; padding: 0; list-style: none; }.completion-checklist li { color: #475467; font-size: 13px; }.completion-checklist li::before { margin-right: 7px; color: #1677ff; content: '✓'; font-weight: 700; }.quality-label { margin: 8px 0 14px; color: #667085; font-size: 13px; }.quality-label strong { color: #1677ff; }.suggestions article { padding: 14px 0; border-top: 1px solid #edf0f3; }.suggestions article:first-of-type { border-top: 0; }.suggestions h4 { margin: 0; color: #344054; font-size: 13px; }.suggestions article>p { margin: 7px 0 10px; color: #667085; font-size: 13px; line-height: 1.65; }.suggestions article>div { display: flex; align-items: center; justify-content: space-between; gap: 15px; color: #475467; font-size: 13px; }.suggestions article :deep(.el-button) { flex: none; margin: 0; }.final-status { border-color: #dbe8f8; background: #f8fbff; }.final-status p { margin: 8px 0 0; color: #667085; font-size: 13px; }.final-actions { margin-top: 22px; }.final-actions>div { display: flex; gap: 10px; }.final-actions :deep(.el-button) { margin: 0; }
.evidence-section { padding: 0 0 18px; margin-bottom: 18px; border-bottom: 1px solid #edf0f3; }.evidence-section:last-child { border-bottom: 0; }.evidence-section h3 { margin: 0; color: #344054; font-size: 14px; }.evidence-section p, .evidence-section li, .evidence-section small { color: #667085; font-size: 13px; line-height: 1.7; }.evidence-section p { margin: 8px 0 0; }.evidence-section ul { margin: 8px 0 0; padding-left: 18px; }.research-evidence { padding: 15px; border: 1px solid #e6eef8; border-radius: 9px; background: #f8fbff; }.research-evidence strong { display: block; margin-top: 10px; color: #344054; font-size: 13px; }.research-evidence small { display: block; margin-top: 8px; }.research-evidence :deep(.el-button) { margin: 8px 0 0; padding: 0; }.design-preview section+section { margin-top: 17px; }.design-preview h3 { margin: 0; color: #344054; font-size: 14px; }.design-preview p, .design-preview li { color: #667085; font-size: 13px; line-height: 1.7; }.design-preview p, .design-preview ul { margin: 7px 0 0; }.design-preview ul { padding-left: 18px; }
@media (max-width: 760px) { .page-header { flex-direction: column; gap: 16px; }.save-area { padding-top: 0; }.workspace-card { padding: 22px; }.context-form, .diagnosis-grid, .blueprint-stage dl { grid-template-columns: 1fr; }.diagnosis-grid section, .diagnosis-grid section:nth-child(2n), .diagnosis-grid section:nth-last-child(-n+2) { min-height: 0; border-right: 0; border-bottom: 1px solid #e6eef8; }.diagnosis-grid section:last-child { border-bottom: 0; }.diagnosis-card footer { flex-wrap: wrap; }.diagnosis-card footer :deep(.el-button) { flex: 1; margin: 0; }.evidence-bar { align-items: flex-start; flex-direction: column; gap: 6px; }.evidence-bar>div { align-items: flex-start; flex-direction: column; gap: 5px; }.evidence-bar span { white-space: normal; }.goal-card footer { align-items: flex-start; flex-direction: column; }.goal-card footer>div { width: 100%; }.goal-actions { gap: 12px; }.goal-actions :deep(.el-button) { flex: 1; margin: 0; }.blueprint-header { flex-direction: column; }.blueprint-meta { justify-content: flex-start; }.blueprint-stage dl { gap: 11px; } }
@media (max-width: 1000px) { .context-form { grid-template-columns: 1fr; } }
</style>
