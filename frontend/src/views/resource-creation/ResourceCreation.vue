<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getCourseDesign } from '@/api/courseDesign'
import {
  acceptResourceSuggestion, createResourceJob, createResourceSuggestion, generateResources,
  getResourceCreation, getTeachingResource, recommendResourceSettings, regenerateResources,
  rejectResourceSuggestion, reviewTeachingResource, saveTeachingResourceVersion,
  transformTeachingResource, updateResourceJob,
} from '@/api/resourceCreation'

const route = useRoute()
const projectId = computed(() => String(route.params.projectId || route.query.projectId || ''))
const jobId = ref<number | null>(null)
const resourceRecords = ref<Record<string, { id: number; versionId?: number }>>({})
const courseInfo = ref({ title: '', grade: '', lessonMinutes: 0, objectiveCount: 0, activityCount: 0, pedagogy: '' })
const apiTypeByUi: Record<string, string> = { ppt: 'PPT', 'teacher-guide': 'TEACHER_GUIDE', worksheet: 'WORKSHEET', 'task-card': 'TASK_CARD', 'ai-case': 'AI_CASE', discussion: 'DISCUSSION', assessment: 'ASSESSMENT', reflection: 'REFLECTION' }
const uiTypeByApi: Record<string, string> = Object.fromEntries(Object.entries(apiTypeByUi).map(([key, value]) => [value, key]))

const currentMode = ref<'generate' | 'adapt' | null>(null)
const currentGenerateStep = ref(1)
const saveStatus = ref('已自动保存')
const coursePlanVisible = ref(false)
const selectedResources = ref<string[]>([])
const activeResourceId = ref('worksheet')
const isApplyingRecommendations = ref(false)
const recommendationNotice = ref(false)
const isGeneratingDraft = ref(false)
type DraftBlock = { id: string; heading: string; text: string; table?: boolean }
type ResourceDraft = { title: string; blocks: DraftBlock[] }
const resourceDrafts = ref<Record<string, ResourceDraft>>({
  worksheet: {
    title: 'AI信息核验学习单',
    blocks: [
      { id: 'worksheet-1', heading: '任务一：找出需要核验的信息', text: '阅读AI回答，圈出3条你认为需要进一步确认的信息。' },
      { id: 'worksheet-2', heading: '任务二：寻找证据', text: '与你的小组成员一起寻找两个不同的信息来源。', table: true },
      { id: 'worksheet-3', heading: '任务三：修改AI回答', text: '根据证据，修改AI回答中存在问题的内容。' },
      { id: 'worksheet-4', heading: '反思', text: '你认为以后遇到AI回答时，什么情况下需要进一步核验？' },
    ],
  },
  'task-card': {
    title: '课堂任务卡：证据核验挑战',
    blocks: [
      { id: 'task-card-1', heading: '任务目标', text: '找出AI回答中至少3条需要进一步核验的信息。' },
      { id: 'task-card-2', heading: '小组任务', text: '分工搜索两个可靠来源，比较证据并记录判断结果。' },
      { id: 'task-card-3', heading: '完成标准', text: '提交一份包含来源、证据比较和修改建议的小组任务单。' },
    ],
  },
  assessment: {
    title: '教学评价工具：证据核验观察表',
    blocks: [
      { id: 'assessment-1', heading: '观察重点', text: '学生能否识别需要核验的信息，并说明判断理由。' },
      { id: 'assessment-2', heading: '评价指标', text: '是否使用两个以上相对可靠来源；是否能够比较证据质量。', table: true },
      { id: 'assessment-3', heading: 'Exit Ticket', text: '写下你在本节课学到的一条信息核验原则。' },
    ],
  },
})
// Server state replaces the legacy design-time examples immediately on load.
resourceDrafts.value = {}
const activePreviewResourceId = ref('')
const isEditingDraft = ref(false)
const draftSnapshot = ref<Record<string, ResourceDraft> | null>(null)
const teacherModified = ref(false)
const regeneratingBlockId = ref<string | null>(null)
const isRegeneratingAll = ref(false)
type AssistantSuggestion = { id: number; text: string; status: 'pending' | 'ignored' | 'proposed' | 'applied' }
type AssistantProposal = { source: string; blockId: string; original: string; suggested: string }
const assistantVisible = ref(false)
const hasCheckedResource = ref(false)
const assistantSuggestions = ref<AssistantSuggestion[]>([
  { id: 1, text: '增加来源可信度检查表；', status: 'pending' },
  { id: 2, text: '把任务二拆成两个小步骤；', status: 'pending' },
  { id: 3, text: '增加一个示例帮助学生理解“证据”。', status: 'pending' },
])
assistantSuggestions.value = []
const assistantRequest = ref('')
const isPreparingProposal = ref(false)
const assistantProposal = ref<AssistantProposal | null>(null)
const commonSettings = reactive({
  difficulty: '适中', duration: '15分钟', format: '4人小组', lowDeviceAlternative: true, languageStyle: '适合儿童',
})
const resourceSettings = reactive({
  worksheet: { duration: '15分钟', scaffolding: '中', example: true, recordArea: true, reflection: true },
  ppt: { pages: 8, density: '适中', visualRatio: '图文均衡', speakerNotes: true, questions: true },
  'task-card': { quantity: 4, format: '小组', timeHint: true, criteria: true },
  'ai-case': { role: '学习助手', turns: 6, errorAnswer: true, judgement: true, discussionPrompt: true },
  assessment: { type: '形成性', evaluator: '教师评价', rubric: true, levels: 4, observableIndicators: true },
  'teacher-guide': { detail: '适中', timing: true, prompts: true },
  discussion: { quantity: 6, thinkingLevel: '适中', groupPrompt: true },
  reflection: { audience: '学生', questionCount: 4, actionPlan: true },
})
const resourceTypes = [
  { id: 'ppt', icon: '▤', title: '教学PPT', description: '用于课堂展示的教学内容结构与页面建议。' },
  { id: 'teacher-guide', icon: '☷', title: '教师流程卡', description: '帮助教师快速掌握每个教学环节、时间和提示语。' },
  { id: 'worksheet', icon: '▧', title: '学生学习单', description: '支持学生完成观察、核验、比较、记录和反思任务。' },
  { id: 'task-card', icon: '□', title: '课堂任务卡', description: '提供可直接发给学生的小组或个人任务。' },
  { id: 'ai-case', icon: '◌', title: 'AI对话案例', description: '提供适合课堂分析的人机对话案例。' },
  { id: 'discussion', icon: '◍', title: '讨论问题', description: '生成课堂提问、小组讨论和全班交流问题。' },
  { id: 'assessment', icon: '✓', title: '教学评价工具', description: '生成观察表、Rubric、Exit Ticket等。' },
  { id: 'reflection', icon: '↺', title: '课后反思单', description: '支持学生或教师进行课后反思。' },
]
const activeResource = computed(() => resourceTypes.find((resource) => resource.id === activeResourceId.value) ?? resourceTypes[0])
const activePreviewResource = computed(() => resourceTypes.find((resource) => resource.id === activePreviewResourceId.value) ?? resourceTypes[0])
const activeDraft = computed(() => resourceDrafts.value[activePreviewResourceId.value] ?? { title: `${activePreviewResource.value?.title ?? '教学资源'}初稿`, blocks: [{ id: 'generic-1', heading: '资源内容', text: '该资源的初稿内容将在后续版本中完善。' }] })

watch(selectedResources, (resources) => {
  if (!resources.includes(activeResourceId.value)) activeResourceId.value = resources[0] ?? ''
  if (!resources.includes(activePreviewResourceId.value)) activePreviewResourceId.value = resources[0] ?? ''
})

async function saveDraft() {
  if (!projectId.value) return ElMessage.warning('请从课程智设中的项目入口进入资源智创')
  try {
    const payload = { selectedTypes: selectedResources.value.map((item) => apiTypeByUi[item]), commonSettings: { ...commonSettings }, resourceSettings: { ...resourceSettings }, currentStep: currentGenerateStep.value }
    if (!jobId.value) {
      const response = await createResourceJob(projectId.value, { projectId: Number(projectId.value), mode: 'COURSE_GENERATE', ...payload })
      jobId.value = response.data.data.job.jobId
    } else await updateResourceJob(projectId.value, jobId.value, payload)
    saveStatus.value = '草稿已保存'
    ElMessage.success('草稿已保存')
  } catch { ElMessage.error('草稿保存失败') }
}

function toggleResource(resourceId: string) {
  selectedResources.value = selectedResources.value.includes(resourceId)
    ? selectedResources.value.filter((id) => id !== resourceId)
    : [...selectedResources.value, resourceId]
}

function selectAllResources() { selectedResources.value = resourceTypes.map((resource) => resource.id) }
function clearResources() { selectedResources.value = [] }
function returnToModeSelection() {
  currentMode.value = null
  currentGenerateStep.value = 1
}
async function applyRecommendedSettings() {
  if (!jobId.value) await saveDraft()
  if (!jobId.value) return
  isApplyingRecommendations.value = true
  recommendationNotice.value = false
  try {
    const response = await recommendResourceSettings(projectId.value, jobId.value)
    Object.assign(commonSettings, response.data.data.recommendations || {})
    isApplyingRecommendations.value = false
    recommendationNotice.value = true
  } catch { isApplyingRecommendations.value = false; ElMessage.error('推荐设置失败') }
}
async function generateDraft() {
  if (!jobId.value) await saveDraft()
  if (!jobId.value) return
  isGeneratingDraft.value = true
  try {
    await updateResourceJob(projectId.value, jobId.value, { selectedTypes: selectedResources.value.map((item) => apiTypeByUi[item]), commonSettings: { ...commonSettings }, resourceSettings: { ...resourceSettings } })
    await generateResources(projectId.value, jobId.value)
    await restoreServerState()
    isGeneratingDraft.value = false
    currentGenerateStep.value = 3
  } catch { isGeneratingDraft.value = false; ElMessage.error('资源生成失败') }
}
function startEditingDraft() {
  draftSnapshot.value = JSON.parse(JSON.stringify(resourceDrafts.value)) as Record<string, ResourceDraft>
  isEditingDraft.value = true
}
async function saveDraftEdits() {
  const record = resourceRecords.value[activePreviewResourceId.value]
  if (!record) return
  try {
    const draft = resourceDrafts.value[activePreviewResourceId.value]
    if (!draft) return
    await saveTeachingResourceVersion(projectId.value, record.id, { content: toServerContent(draft), changeSummary: 'Edited by teacher' })
    await restoreServerState()
  isEditingDraft.value = false
  teacherModified.value = true
  ElMessage.success('资源修改已保存')
  } catch { ElMessage.error('资源保存失败') }
}
function cancelDraftEdits() {
  if (draftSnapshot.value) resourceDrafts.value = draftSnapshot.value
  draftSnapshot.value = null
  isEditingDraft.value = false
}
async function applyBlockAction(block: DraftBlock, action: 'edit' | 'regenerate' | 'simplify' | 'harder' | 'scaffold') {
  if (action === 'edit') { if (!isEditingDraft.value) startEditingDraft(); return }
  const record = resourceRecords.value[activePreviewResourceId.value]
  if (!record) return
  if (action === 'regenerate') {
    regeneratingBlockId.value = block.id
    try { await transformTeachingResource(projectId.value, record.id, { action: 'REGENERATE', targetBlockKey: block.id }); await restoreServerState(); teacherModified.value = true } finally { regeneratingBlockId.value = null }
    return
  }
  const actionMap = { simplify: 'SIMPLIFY', harder: 'INCREASE_DIFFICULTY', scaffold: 'ADD_SCAFFOLD' }
  await transformTeachingResource(projectId.value, record.id, { action: actionMap[action as 'simplify' | 'harder' | 'scaffold'], targetBlockKey: block.id })
  await restoreServerState(); teacherModified.value = true
}
async function regenerateAllDrafts() {
  if (!jobId.value) return
  isRegeneratingAll.value = true
  try {
    await regenerateResources(projectId.value, jobId.value)
    await restoreServerState()
    isRegeneratingAll.value = false
    ElMessage.success('已重新生成资源初稿')
  } catch { isRegeneratingAll.value = false; ElMessage.error('重新生成失败') }
}
function targetBlockForAssistant() {
  return activeDraft.value.blocks[1] ?? activeDraft.value.blocks[0]
}
function createProposal(source: string, suggested: string) {
  const target = targetBlockForAssistant()
  if (!target) return
  assistantProposal.value = { source, blockId: target.id, original: target.text, suggested }
}
async function reviewCurrentResource() {
  const record = resourceRecords.value[activePreviewResourceId.value]
  if (!record) return
  try { await reviewTeachingResource(projectId.value, record.id); hasCheckedResource.value = true; await restoreServerState() } catch { ElMessage.error('资源检查失败') }
}
async function requestOptimizations() {
  const record = resourceRecords.value[activePreviewResourceId.value]
  if (!record) return
  try { await reviewTeachingResource(projectId.value, record.id); await restoreServerState() } catch { ElMessage.error('优化建议生成失败') }
}
function proposeSuggestion(suggestion: AssistantSuggestion) {
  const target = targetBlockForAssistant()
  if (!target) return
  if (suggestion.id > 0) {
    assistantProposal.value = { source: String(suggestion.id), blockId: target.id, original: target.text, suggested: suggestion.text }
    suggestion.status = 'proposed'
    return
  }
  const additions: Record<number, string> = {
    1: '同时提供一张来源可信度检查表，帮助学生逐项判断来源。',
    2: '先选择需要核验的信息，再分别查找和比较两个来源。',
    3: '参考示例：说明一条信息为什么需要核验，再开始小组任务。',
  }
  createProposal(suggestion.text, `${target.text} ${additions[suggestion.id]}`)
  suggestion.status = 'proposed'
}
async function ignoreSuggestion(suggestion: AssistantSuggestion) {
  await rejectResourceSuggestion(projectId.value, suggestion.id)
  suggestion.status = 'ignored'
}
async function generateRequestProposal() {
  if (!assistantRequest.value.trim()) { ElMessage.warning('请输入希望AI协助修改的要求'); return }
  const record = resourceRecords.value[activePreviewResourceId.value]
  if (!record?.versionId) return
  isPreparingProposal.value = true
  try {
    const target = targetBlockForAssistant()
    const response = await createResourceSuggestion(projectId.value, record.id, { resourceId: record.id, baseVersionId: record.versionId, suggestionType: 'AI_REVISION', userRequest: assistantRequest.value, targetBlockKey: target?.id })
    const item = response.data.data.suggestion
    assistantProposal.value = { source: String(item.suggestionId), blockId: item.targetBlockKey || target?.id || '', original: target?.text || '', suggested: item.suggestedContent || '' }
    isPreparingProposal.value = false
  } catch { isPreparingProposal.value = false; ElMessage.error('生成建议失败') }
  /*
  window.setTimeout(() => {
    const target = targetBlockForAssistant()
    if (target) createProposal('按我的要求修改', `${target.text} 建议使用更清晰的分步提示，同时保留证据比较要求。`)
    isPreparingProposal.value = false
  }, 500) */
}
async function adoptProposal() {
  const proposal = assistantProposal.value
  if (!proposal) return
  try { await acceptResourceSuggestion(projectId.value, Number(proposal.source)); await restoreServerState() } catch { return ElMessage.error('采用建议失败') }
  teacherModified.value = true
  const suggestion = assistantSuggestions.value.find((item) => item.text === proposal.source)
  if (suggestion) suggestion.status = 'applied'
  assistantProposal.value = null
  ElMessage.success('已采用AI建议版本')
}
async function editThenAdoptProposal() {
  const proposal = assistantProposal.value
  if (!proposal) return
  const record = resourceRecords.value[activePreviewResourceId.value]
  if (record && /^\d+$/.test(proposal.source)) await acceptResourceSuggestion(projectId.value, Number(proposal.source))
  await restoreServerState()
  if (!isEditingDraft.value) startEditingDraft()
  teacherModified.value = true
  assistantProposal.value = null
  ElMessage.info('AI建议已带入编辑区，请确认后保存')
}

function toServerContent(draft: ResourceDraft) {
  return { title: draft.title, blocks: draft.blocks.map((block) => ({ key: block.id, title: block.heading, content: block.text })), metadata: {} }
}
function fromServerContent(content: any): ResourceDraft {
  return { title: content?.title || '教学资源', blocks: (content?.blocks || []).map((block: any, index: number) => ({ id: block.key || `block-${index}`, heading: block.title || '资源内容', text: typeof block.content === 'string' ? block.content : JSON.stringify(block.content ?? '') })) }
}
async function restoreServerState() {
  if (!projectId.value) return
  const response = await getResourceCreation(projectId.value)
  const state = response.data.data
  const job = state.job
  jobId.value = job?.jobId || null
  if (job) {
    currentMode.value = job.mode === 'COURSE_GENERATE' ? 'generate' : 'adapt'
    currentGenerateStep.value = job.currentStep || 1
    selectedResources.value = (job.selectedTypes || []).map((item: string) => uiTypeByApi[item]).filter(Boolean)
    Object.assign(commonSettings, job.commonSettings || {})
    Object.assign(resourceSettings, job.resourceSettings || {})
  }
  resourceRecords.value = {}
  resourceDrafts.value = {}
  assistantSuggestions.value = []
  for (const resource of state.resources || []) {
    const uiType = uiTypeByApi[resource.resourceType]
    if (!uiType) continue
    const detail = (await getTeachingResource(projectId.value, resource.resourceId)).data.data
    resourceRecords.value[uiType] = { id: resource.resourceId, versionId: detail.currentVersion?.versionId }
    resourceDrafts.value[uiType] = fromServerContent(detail.currentVersion?.content)
    assistantSuggestions.value.push(...(detail.suggestions || []).map((item: any) => ({ id: item.suggestionId, text: item.suggestedContent || item.reason || '', status: item.status === 'PENDING' ? 'pending' : item.status === 'REJECTED' ? 'ignored' : 'applied' })))
  }
  activePreviewResourceId.value = selectedResources.value[0] || ''
}
async function initialize() {
  if (!projectId.value) return
  try {
    const design = (await getCourseDesign(projectId.value)).data.data
    courseInfo.value = { title: design.project?.title || '', grade: String(design.context?.grade || ''), lessonMinutes: design.context?.lessonMinutes || 0, objectiveCount: design.objectives?.length || 0, activityCount: design.activities?.length || 0, pedagogy: design.pedagogy?.customName || design.pedagogy?.name || '' }
    await restoreServerState()
  } catch { ElMessage.error('资源智创数据加载失败') }
}
onMounted(() => { void initialize() })
</script>

<template>
  <main class="resource-creation-page">
    <header class="page-header">
      <div>
        <p class="eyebrow">资源智创</p>
        <h1>资源智创</h1>
        <p class="page-description">将教学设计转化为可直接使用的课堂资源，并通过教师—AI协同持续优化。</p>
      </div>
      <div class="save-area"><el-button type="primary" @click="saveDraft">保存草稿</el-button><span>{{ saveStatus }}</span></div>
    </header>

    <section v-if="!currentMode" class="mode-section" aria-label="资源智创工作模式">
      <div class="section-intro"><h2>选择工作模式</h2><p>从已有课程生成新资源，或根据新的教学条件改编已有资源。</p></div>
      <div class="mode-grid">
        <article class="mode-card recommended">
          <header><span class="mode-icon" aria-hidden="true">▤</span><span class="recommendation-label">推荐</span></header>
          <h3>基于课程生成资源</h3>
          <p>读取已有课程设计，生成PPT、学习单、任务卡、评价工具等课堂资源。</p>
          <footer><el-button type="primary" @click="currentMode = 'generate'">开始生成资源</el-button></footer>
        </article>
        <article class="mode-card">
          <header><span class="mode-icon adapt-icon" aria-hidden="true">↺</span></header>
          <h3>智能改编已有资源</h3>
          <p>上传已有教案、PPT或学习单，根据新的年级、课时、设备条件或教学要求进行改编。</p>
          <footer><el-button @click="currentMode = 'adapt'">开始智能改编</el-button></footer>
        </article>
      </div>
    </section>

    <template v-else-if="currentMode === 'generate'">
      <nav class="creation-flow" aria-label="资源生成流程"><span :class="{ active: currentGenerateStep === 1 }">选择资源</span><i>→</i><span :class="{ active: currentGenerateStep === 2 }">生成设置</span><i>→</i><span :class="{ active: currentGenerateStep === 3 }">AI共创</span><i>→</i><span>预览导出</span></nav>

      <section v-if="currentGenerateStep === 1" class="generate-workspace">
        <article class="current-course-card">
          <header><div><p class="section-eyebrow">当前课程</p><h2>{{ courseInfo.title || '课程信息加载中' }}</h2></div><el-button link type="primary" @click="coursePlanVisible = true">查看课程方案</el-button></header>
          <div class="course-meta"><span>{{ courseInfo.grade ? `${courseInfo.grade}年级` : '—' }}</span><span>{{ courseInfo.lessonMinutes ? `${courseInfo.lessonMinutes}分钟` : '—' }}</span><span>{{ courseInfo.objectiveCount }}个学习目标</span><span>{{ courseInfo.activityCount }}个教学环节</span><span>{{ courseInfo.pedagogy || '—' }}</span></div>
          <p>已自动读取课程智设中的教学目标、教学流程和评价设计。</p>
        </article>

        <section class="resource-selection-card">
          <header class="selection-header"><div><h2>选择需要生成的教学资源</h2><p>可以一次选择一种或多种资源，系统将根据当前课程设计分别生成。</p></div><div class="batch-actions"><el-button link @click="selectAllResources">全选</el-button><el-button link @click="clearResources">清空</el-button></div></header>
          <div class="resource-grid">
            <article v-for="resource in resourceTypes" :key="resource.id" class="resource-card" :class="{ selected: selectedResources.includes(resource.id) }" @click="toggleResource(resource.id)">
              <header><span class="resource-icon" aria-hidden="true">{{ resource.icon }}</span><el-checkbox :model-value="selectedResources.includes(resource.id)" :aria-label="`选择${resource.title}`" @click.stop @change="toggleResource(resource.id)" /></header>
              <h3>{{ resource.title }}</h3><p>{{ resource.description }}</p>
            </article>
          </div>
          <footer class="selection-actions"><el-button @click="returnToModeSelection">返回模式选择</el-button><el-button type="primary" :disabled="selectedResources.length === 0" @click="currentGenerateStep = 2">下一步：设置生成条件</el-button></footer>
        </section>
      </section>

      <section v-else-if="currentGenerateStep === 2" class="settings-workspace">
        <article class="common-settings-card">
          <header><div><p class="section-eyebrow">通用设置</p><h2>生成条件</h2></div><el-button :loading="isApplyingRecommendations" @click="applyRecommendedSettings">使用AI推荐设置</el-button></header>
          <p v-if="recommendationNotice" class="recommendation-notice">已根据当前课程和学生特点应用推荐设置。</p>
          <el-form class="common-settings-form" label-position="top">
            <el-form-item label="内容难度"><el-radio-group v-model="commonSettings.difficulty"><el-radio-button label="简单" value="简单" /><el-radio-button label="适中" value="适中" /><el-radio-button label="有挑战" value="有挑战" /></el-radio-group></el-form-item>
            <el-form-item label="使用对象"><el-input :model-value="courseInfo.grade ? `${courseInfo.grade}年级` : ''" disabled /></el-form-item>
            <el-form-item label="活动时间"><el-select v-model="commonSettings.duration"><el-option label="10分钟" value="10分钟" /><el-option label="15分钟" value="15分钟" /><el-option label="20分钟" value="20分钟" /></el-select></el-form-item>
            <el-form-item label="任务方式"><el-select v-model="commonSettings.format"><el-option label="个人" value="个人" /><el-option label="两人" value="两人" /><el-option label="4人小组" value="4人小组" /><el-option label="全班" value="全班" /></el-select></el-form-item>
            <el-form-item label="低设备/无设备替代方案"><el-switch v-model="commonSettings.lowDeviceAlternative" active-text="需要" inactive-text="不需要" /></el-form-item>
            <el-form-item label="语言风格"><el-select v-model="commonSettings.languageStyle"><el-option label="简洁" value="简洁" /><el-option label="适合儿童" value="适合儿童" /><el-option label="正式" value="正式" /><el-option label="引导式" value="引导式" /></el-select></el-form-item>
          </el-form>
        </article>

        <section class="resource-settings-layout">
          <aside class="selected-resource-list"><h2>已选资源</h2><button v-for="resource in resourceTypes.filter((item) => selectedResources.includes(item.id))" :key="resource.id" :class="{ active: activeResourceId === resource.id }" @click="activeResourceId = resource.id"><span>{{ resource.icon }}</span>{{ resource.title }}</button></aside>
          <article class="exclusive-settings-card">
            <header><p class="section-eyebrow">当前资源</p><h2>{{ activeResource?.title }}</h2></header>
            <el-form v-if="activeResourceId === 'worksheet'" class="exclusive-form" label-position="top"><el-form-item label="预计完成时间"><el-select v-model="resourceSettings.worksheet.duration"><el-option label="10分钟" value="10分钟" /><el-option label="15分钟" value="15分钟" /><el-option label="20分钟" value="20分钟" /></el-select></el-form-item><el-form-item label="支架程度"><el-radio-group v-model="resourceSettings.worksheet.scaffolding"><el-radio-button label="低" value="低" /><el-radio-button label="中" value="中" /><el-radio-button label="高" value="高" /></el-radio-group></el-form-item><el-form-item label="提供示例"><el-switch v-model="resourceSettings.worksheet.example" /></el-form-item><el-form-item label="提供记录区域"><el-switch v-model="resourceSettings.worksheet.recordArea" /></el-form-item><el-form-item label="提供反思问题"><el-switch v-model="resourceSettings.worksheet.reflection" /></el-form-item></el-form>
            <el-form v-else-if="activeResourceId === 'ppt'" class="exclusive-form" label-position="top"><el-form-item label="建议页数"><el-input-number v-model="resourceSettings.ppt.pages" :min="3" :max="20" /></el-form-item><el-form-item label="每页信息密度"><el-select v-model="resourceSettings.ppt.density"><el-option label="简洁" value="简洁" /><el-option label="适中" value="适中" /><el-option label="丰富" value="丰富" /></el-select></el-form-item><el-form-item label="图文比例"><el-select v-model="resourceSettings.ppt.visualRatio"><el-option label="图文均衡" value="图文均衡" /><el-option label="以图为主" value="以图为主" /><el-option label="以文字为主" value="以文字为主" /></el-select></el-form-item><el-form-item label="包含教师讲解提示"><el-switch v-model="resourceSettings.ppt.speakerNotes" /></el-form-item><el-form-item label="包含课堂提问"><el-switch v-model="resourceSettings.ppt.questions" /></el-form-item></el-form>
            <el-form v-else-if="activeResourceId === 'task-card'" class="exclusive-form" label-position="top"><el-form-item label="任务数量"><el-input-number v-model="resourceSettings['task-card'].quantity" :min="1" :max="10" /></el-form-item><el-form-item label="个人/小组"><el-select v-model="resourceSettings['task-card'].format"><el-option label="个人" value="个人" /><el-option label="小组" value="小组" /></el-select></el-form-item><el-form-item label="包含时间提示"><el-switch v-model="resourceSettings['task-card'].timeHint" /></el-form-item><el-form-item label="包含完成标准"><el-switch v-model="resourceSettings['task-card'].criteria" /></el-form-item></el-form>
            <el-form v-else-if="activeResourceId === 'ai-case'" class="exclusive-form" label-position="top"><el-form-item label="AI角色"><el-input v-model="resourceSettings['ai-case'].role" /></el-form-item><el-form-item label="对话轮数"><el-input-number v-model="resourceSettings['ai-case'].turns" :min="2" :max="12" /></el-form-item><el-form-item label="包含错误回答"><el-switch v-model="resourceSettings['ai-case'].errorAnswer" /></el-form-item><el-form-item label="要求学生判断"><el-switch v-model="resourceSettings['ai-case'].judgement" /></el-form-item><el-form-item label="包含讨论提示"><el-switch v-model="resourceSettings['ai-case'].discussionPrompt" /></el-form-item></el-form>
            <el-form v-else-if="activeResourceId === 'assessment'" class="exclusive-form" label-position="top"><el-form-item label="评价类型"><el-radio-group v-model="resourceSettings.assessment.type"><el-radio-button label="形成性" value="形成性" /><el-radio-button label="总结性" value="总结性" /></el-radio-group></el-form-item><el-form-item label="评价主体"><el-select v-model="resourceSettings.assessment.evaluator"><el-option label="教师评价" value="教师评价" /><el-option label="自评" value="自评" /><el-option label="互评" value="互评" /></el-select></el-form-item><el-form-item label="生成Rubric"><el-switch v-model="resourceSettings.assessment.rubric" /></el-form-item><el-form-item label="Rubric等级数"><el-input-number v-model="resourceSettings.assessment.levels" :min="3" :max="5" /></el-form-item><el-form-item label="包含可观察行为指标"><el-switch v-model="resourceSettings.assessment.observableIndicators" /></el-form-item></el-form>
            <el-form v-else class="exclusive-form" label-position="top"><el-form-item label="内容详细程度"><el-radio-group v-model="resourceSettings['teacher-guide'].detail"><el-radio-button label="简洁" value="简洁" /><el-radio-button label="适中" value="适中" /><el-radio-button label="详细" value="详细" /></el-radio-group></el-form-item><el-form-item label="包含时间提示"><el-switch v-model="resourceSettings['teacher-guide'].timing" /></el-form-item><el-form-item label="包含教学提示"><el-switch v-model="resourceSettings['teacher-guide'].prompts" /></el-form-item></el-form>
          </article>
        </section>
        <footer class="settings-actions"><el-button @click="currentGenerateStep = 1">返回选择资源</el-button><div><span v-if="isGeneratingDraft">正在根据课程设计和资源要求生成初稿…</span><el-button type="primary" :loading="isGeneratingDraft" @click="generateDraft">生成资源初稿</el-button></div></footer>
      </section>

      <section v-else class="draft-stage">
        <header class="draft-header"><div><p class="section-eyebrow">资源初稿已生成</p><h2>资源预览与编辑</h2><p>3项资源 · 基于当前课程方案生成</p></div><el-button :loading="isRegeneratingAll" @click="regenerateAllDrafts">重新生成全部</el-button></header>
        <section class="draft-workspace">
          <aside class="draft-resource-list"><h2>资源列表</h2><button v-for="resource in resourceTypes.filter((item) => selectedResources.includes(item.id))" :key="resource.id" :class="{ active: activePreviewResourceId === resource.id }" @click="activePreviewResourceId = resource.id"><span>{{ resource.icon }}</span><div><strong>{{ resource.title }}</strong><small>已生成</small></div></button></aside>
          <article class="draft-editor">
            <header class="editor-header"><div><p class="section-eyebrow">当前资源</p><h2>{{ activeDraft.title }}</h2><span v-if="teacherModified" class="modified-tag">教师已修改</span></div><div class="editor-actions"><el-button @click="assistantVisible = true">AI共创助手</el-button><el-button v-if="!isEditingDraft" @click="startEditingDraft">编辑</el-button><template v-else><el-button @click="cancelDraftEdits">取消</el-button><el-button type="primary" @click="saveDraftEdits">保存修改</el-button></template></div></header>
            <section class="draft-content">
              <article v-for="block in activeDraft.blocks" :key="block.id" class="draft-block"><header><h3>{{ block.heading }}</h3><el-dropdown trigger="click"><button class="block-menu" type="button" aria-label="内容块操作">···</button><template #dropdown><el-dropdown-menu><el-dropdown-item @click="applyBlockAction(block, 'edit')">编辑本段</el-dropdown-item><el-dropdown-item @click="applyBlockAction(block, 'regenerate')">重新生成本段</el-dropdown-item><el-dropdown-item @click="applyBlockAction(block, 'simplify')">简化</el-dropdown-item><el-dropdown-item @click="applyBlockAction(block, 'harder')">增加难度</el-dropdown-item><el-dropdown-item @click="applyBlockAction(block, 'scaffold')">增加支架</el-dropdown-item></el-dropdown-menu></template></el-dropdown></header><el-input v-if="isEditingDraft" v-model="block.text" type="textarea" :rows="3" resize="none" /><p v-else>{{ block.text }}</p><span v-if="regeneratingBlockId === block.id" class="block-loading">正在重新生成本段…</span><div v-if="block.table" class="mock-table"><div><span>信息</span><span>来源1</span><span>来源2</span><span>是否一致</span></div><div><span>________________</span><span>________________</span><span>________________</span><span>□ 是　□ 否</span></div></div></article>
            </section>
          </article>
        </section>
        <footer class="settings-actions draft-footer"><el-button @click="currentGenerateStep = 2">返回生成设置</el-button><span>当前资源来自已保存的课程设计，可继续编辑或局部重新生成。</span></footer>
      </section>
    </template>

    <section v-else class="mode-placeholder">
      <div class="placeholder-icon" aria-hidden="true">↺</div>
      <h2>智能改编已有资源</h2>
      <p>已有资源智能改编将在后续步骤实现</p>
      <el-button @click="returnToModeSelection">返回模式选择</el-button>
    </section>
  </main>

  <el-dialog v-model="coursePlanVisible" title="课程方案" width="520px"><p class="course-plan-dialog">当前课程方案包含 {{ courseInfo.objectiveCount }} 个学习目标、{{ courseInfo.activityCount }} 个教学环节及对应评价设计。</p></el-dialog>
  <el-drawer v-model="assistantVisible" title="AI共创助手" size="min(420px, 92vw)">
    <div class="assistant-panel">
      <p class="assistant-intro">我可以帮助检查、提出建议和生成修改版本，最终修改由你决定。</p>
      <section class="assistant-section"><header><h3>检查当前资源</h3><el-button size="small" @click="reviewCurrentResource">检查这个资源</el-button></header><div v-if="hasCheckedResource" class="check-result"><p><span>AI检查</span><strong>已完成</strong></p><p><span>建议</span><em>请查看下方待处理建议</em></p></div></section>
      <section class="assistant-section"><header><h3>给我修改建议</h3><el-button size="small" @click="requestOptimizations">给我优化建议</el-button></header><article v-for="suggestion in assistantSuggestions" :key="suggestion.id" class="assistant-suggestion" :class="suggestion.status"><p>{{ suggestion.text }}</p><div><el-button v-if="suggestion.status === 'pending'" link type="primary" @click="proposeSuggestion(suggestion)">应用</el-button><el-button v-if="suggestion.status === 'pending'" link @click="ignoreSuggestion(suggestion)">忽略</el-button><span v-else-if="suggestion.status === 'ignored'">已忽略</span><span v-else-if="suggestion.status === 'proposed'">已生成候选版本</span><span v-else>已应用</span></div></article></section>
      <section class="assistant-section"><h3>按我的要求修改</h3><el-input v-model="assistantRequest" type="textarea" :rows="3" resize="none" placeholder="例如：第二个任务太难，请降低表述难度，但保留证据比较要求。" /><el-button class="request-button" :loading="isPreparingProposal" @click="generateRequestProposal">生成修改建议</el-button></section>
      <section v-if="assistantProposal" class="proposal-card"><p class="section-eyebrow">{{ assistantProposal.source }}</p><h3>修改建议对比</h3><div><strong>原内容</strong><p>{{ assistantProposal.original }}</p></div><div><strong>AI建议版本</strong><p>{{ assistantProposal.suggested }}</p></div><footer><el-button @click="assistantProposal = null">保留原版</el-button><el-button @click="editThenAdoptProposal">编辑后采用</el-button><el-button type="primary" @click="adoptProposal">采用修改</el-button></footer></section>
    </div>
  </el-drawer>
</template>

<style scoped>
.resource-creation-page { width: 100%; max-width: 1400px; min-height: 100%; margin: 0 auto; color: #101828; }
.page-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 28px; padding: 4px 2px 28px; }.eyebrow { margin: 0 0 7px; color: #1677ff; font-size: 13px; font-weight: 650; }h1 { margin: 0; color: #101828; font-size: 27px; font-weight: 650; letter-spacing: -.02em; }.page-description { margin: 10px 0 0; color: #667085; font-size: 14px; line-height: 1.65; }.save-area { display: flex; flex: none; align-items: center; gap: 10px; padding-top: 17px; }.save-area span { color: #98a2b3; font-size: 13px; white-space: nowrap; }
.mode-section, .mode-placeholder { border: 1px solid #eaecf0; border-radius: 12px; background: #fff; box-shadow: 0 2px 10px rgb(16 24 40 / 4%); }.mode-section { padding: 28px; }.section-intro h2, .mode-placeholder h2 { margin: 0; color: #1d2939; font-size: 18px; font-weight: 650; }.section-intro p { margin: 8px 0 0; color: #667085; font-size: 14px; }.mode-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; margin-top: 25px; }.mode-card { display: flex; min-height: 285px; flex-direction: column; padding: 24px; border: 1px solid #eaecf0; border-radius: 12px; background: #fff; transition: border-color .18s ease, box-shadow .18s ease; }.mode-card:hover { border-color: #bcd6f5; box-shadow: 0 5px 15px rgb(16 24 40 / 6%); }.mode-card.recommended { border-color: #d4e5f9; background: #fbfdff; }.mode-card header { display: flex; align-items: center; justify-content: space-between; }.mode-icon { display: grid; width: 42px; height: 42px; place-items: center; border: 1px solid #dbe8f8; border-radius: 11px; color: #1677ff; background: #edf5ff; font-size: 21px; }.adapt-icon { color: #4774a8; background: #f4f8fd; }.recommendation-label { padding: 4px 9px; border-radius: 10px; color: #4774a8; background: #edf5ff; font-size: 11px; }.mode-card h3 { margin: 22px 0 0; color: #1d2939; font-size: 18px; font-weight: 650; }.mode-card p { max-width: 470px; margin: 10px 0 0; color: #667085; font-size: 14px; line-height: 1.75; }.mode-card footer { margin-top: auto; padding-top: 24px; }.mode-placeholder { display: grid; min-height: 365px; place-content: center; padding: 34px 20px; text-align: center; }.placeholder-icon { display: grid; width: 48px; height: 48px; margin: 0 auto 16px; place-items: center; border: 1px solid #dbe8f8; border-radius: 13px; color: #1677ff; background: #edf5ff; font-size: 23px; }.mode-placeholder p { margin: 9px 0 21px; color: #667085; font-size: 14px; }
.creation-flow { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; margin-bottom: 18px; padding: 13px 17px; border: 1px solid #e6eef8; border-radius: 10px; color: #98a2b3; background: #fff; font-size: 13px; }.creation-flow span.active { color: #1677ff; font-weight: 650; }.creation-flow i { color: #c7d7e9; font-style: normal; }.generate-workspace { display: grid; gap: 18px; }.current-course-card, .resource-selection-card { border: 1px solid #eaecf0; border-radius: 12px; background: #fff; box-shadow: 0 2px 10px rgb(16 24 40 / 4%); }.current-course-card { padding: 22px 24px; }.current-course-card header, .selection-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; }.section-eyebrow { margin: 0 0 6px; color: #1677ff; font-size: 12px; font-weight: 650; }.current-course-card h2, .selection-header h2 { margin: 0; color: #1d2939; font-size: 17px; font-weight: 650; }.course-meta { display: flex; flex-wrap: wrap; gap: 7px; margin-top: 15px; }.course-meta span { padding: 4px 8px; border-radius: 5px; color: #4774a8; background: #edf5ff; font-size: 12px; }.current-course-card>p { margin: 13px 0 0; color: #667085; font-size: 13px; }.resource-selection-card { padding: 24px; }.selection-header p { margin: 8px 0 0; color: #667085; font-size: 13px; }.batch-actions { display: flex; flex: none; gap: 9px; }.batch-actions :deep(.el-button) { margin: 0; }.resource-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin-top: 22px; }.resource-card { min-height: 178px; padding: 15px; border: 1px solid #eaecf0; border-radius: 10px; background: #fff; cursor: pointer; transition: border-color .18s ease, box-shadow .18s ease; }.resource-card:hover { border-color: #bdd7f5; }.resource-card.selected { border-color: #8bbcf4; background: #f8fbff; box-shadow: 0 0 0 2px rgb(22 119 255 / 5%); }.resource-card header { display: flex; align-items: flex-start; justify-content: space-between; }.resource-icon { display: grid; width: 31px; height: 31px; place-items: center; border-radius: 8px; color: #1677ff; background: #edf5ff; font-size: 15px; }.resource-card h3 { margin: 15px 0 0; color: #344054; font-size: 14px; font-weight: 650; }.resource-card p { margin: 7px 0 0; color: #667085; font-size: 12px; line-height: 1.65; }.selection-actions { display: flex; align-items: center; justify-content: space-between; margin-top: 24px; padding-top: 18px; border-top: 1px solid #edf0f3; }.course-plan-dialog { margin: 0; color: #667085; font-size: 14px; line-height: 1.75; }
.settings-workspace { display: grid; gap: 18px; }.common-settings-card, .selected-resource-list, .exclusive-settings-card { border: 1px solid #eaecf0; border-radius: 12px; background: #fff; box-shadow: 0 2px 10px rgb(16 24 40 / 4%); }.common-settings-card { padding: 23px 24px; }.common-settings-card header { display: flex; align-items: flex-start; justify-content: space-between; gap: 18px; }.common-settings-card h2, .selected-resource-list h2, .exclusive-settings-card h2 { margin: 0; color: #1d2939; font-size: 17px; font-weight: 650; }.recommendation-notice { margin: 15px 0 0; padding: 9px 11px; border-radius: 7px; color: #4774a8; background: #f4f8fd; font-size: 13px; }.common-settings-form { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 0 18px; margin-top: 21px; }.common-settings-form :deep(.el-form-item), .exclusive-form :deep(.el-form-item) { margin-bottom: 16px; }.common-settings-form :deep(.el-form-item__label), .exclusive-form :deep(.el-form-item__label) { padding-bottom: 6px; color: #344054; font-size: 13px; font-weight: 600; }.common-settings-form :deep(.el-select), .common-settings-form :deep(.el-radio-group), .common-settings-form :deep(.el-input) { width: 100%; }.resource-settings-layout { display: grid; grid-template-columns: 220px minmax(0, 1fr); gap: 18px; }.selected-resource-list { display: grid; align-content: start; gap: 4px; padding: 19px 13px; }.selected-resource-list h2 { padding: 0 8px 10px; font-size: 15px; }.selected-resource-list button { display: flex; align-items: center; gap: 9px; padding: 10px 9px; border: 0; border-radius: 7px; color: #475467; background: transparent; cursor: pointer; font: inherit; font-size: 13px; text-align: left; }.selected-resource-list button:hover, .selected-resource-list button.active { color: #1677ff; background: #edf5ff; }.selected-resource-list button span { display: grid; width: 22px; height: 22px; place-items: center; border-radius: 6px; color: #4774a8; background: #f4f8fd; font-size: 12px; }.exclusive-settings-card { min-height: 310px; padding: 23px 24px; }.exclusive-form { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0 22px; margin-top: 20px; }.exclusive-form :deep(.el-select), .exclusive-form :deep(.el-input), .exclusive-form :deep(.el-input-number) { width: 100%; }.settings-actions { display: flex; align-items: center; justify-content: space-between; padding-top: 3px; }.settings-actions>div { display: flex; align-items: center; gap: 12px; }.settings-actions span { color: #667085; font-size: 13px; }.generate-placeholder { min-height: 420px; }
.draft-stage { display: grid; gap: 18px; }.draft-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 18px; padding: 22px 24px; border: 1px solid #eaecf0; border-radius: 12px; background: #fff; box-shadow: 0 2px 10px rgb(16 24 40 / 4%); }.draft-header h2, .draft-resource-list h2, .editor-header h2 { margin: 0; color: #1d2939; font-size: 18px; font-weight: 650; }.draft-header>div>p:last-child { margin: 7px 0 0; color: #667085; font-size: 13px; }.draft-workspace { display: grid; grid-template-columns: 210px minmax(0, 1fr); gap: 18px; min-width: 0; }.draft-resource-list, .draft-editor { border: 1px solid #eaecf0; border-radius: 12px; background: #fff; box-shadow: 0 2px 10px rgb(16 24 40 / 4%); }.draft-resource-list { display: grid; align-content: start; gap: 5px; padding: 19px 13px; }.draft-resource-list h2 { padding: 0 8px 10px; font-size: 15px; }.draft-resource-list button { display: flex; align-items: center; gap: 9px; padding: 11px 9px; border: 0; border-radius: 8px; color: #475467; background: transparent; cursor: pointer; font: inherit; text-align: left; }.draft-resource-list button:hover, .draft-resource-list button.active { color: #1677ff; background: #edf5ff; }.draft-resource-list button>span { display: grid; width: 25px; height: 25px; place-items: center; border-radius: 7px; color: #4774a8; background: #f4f8fd; font-size: 13px; }.draft-resource-list strong, .draft-resource-list small { display: block; }.draft-resource-list strong { font-size: 13px; font-weight: 600; }.draft-resource-list small { margin-top: 2px; color: #98a2b3; font-size: 11px; }.draft-editor { min-width: 0; padding: 23px 24px; }.editor-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 18px; padding-bottom: 18px; border-bottom: 1px solid #edf0f3; }.modified-tag { display: inline-block; margin-top: 8px; padding: 3px 8px; border-radius: 9px; color: #4774a8; background: #edf5ff; font-size: 11px; }.editor-actions { display: flex; align-items: center; gap: 10px; }.assistant-reserved { color: #98a2b3; font-size: 12px; white-space: nowrap; }.editor-actions :deep(.el-button) { margin: 0; }.draft-content { display: grid; gap: 13px; margin-top: 19px; }.draft-block { padding: 16px 17px; border: 1px solid #eaecf0; border-radius: 9px; }.draft-block>header { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }.draft-block h3 { margin: 0; color: #344054; font-size: 14px; font-weight: 650; }.draft-block p { margin: 9px 0 0; color: #667085; font-size: 14px; line-height: 1.7; }.draft-block :deep(.el-textarea) { display: block; margin-top: 10px; }.block-menu { width: 30px; height: 27px; border: 1px solid #eaecf0; border-radius: 6px; color: #667085; background: #fff; cursor: pointer; font: inherit; font-weight: 700; line-height: 1; }.block-menu:hover { color: #1677ff; background: #f8fbff; }.block-loading { display: block; margin-top: 8px; color: #1677ff; font-size: 12px; }.mock-table { margin-top: 13px; overflow: hidden; border: 1px solid #e6eef8; border-radius: 7px; color: #667085; font-size: 12px; }.mock-table div { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); }.mock-table div+div { border-top: 1px solid #e6eef8; }.mock-table span { padding: 8px; border-right: 1px solid #e6eef8; }.mock-table span:last-child { border-right: 0; }.mock-table div:first-child { color: #475467; background: #f8fbff; font-weight: 600; }.draft-footer { padding: 0; }
.assistant-panel { padding: 0 2px 24px; }.assistant-intro { margin: 0 0 19px; color: #667085; font-size: 13px; line-height: 1.7; }.assistant-section { padding: 17px 0; border-top: 1px solid #edf0f3; }.assistant-section:first-of-type { border-top: 0; padding-top: 0; }.assistant-section>header { display: flex; align-items: center; justify-content: space-between; gap: 12px; }.assistant-section h3, .proposal-card h3 { margin: 0; color: #344054; font-size: 15px; font-weight: 650; }.check-result { margin-top: 13px; padding: 12px; border-radius: 8px; background: #f8fbff; }.check-result p { display: flex; align-items: center; justify-content: space-between; margin: 7px 0; color: #667085; font-size: 13px; }.check-result strong { color: #438566; font-weight: 600; }.check-result em { color: #b7791f; font-style: normal; }.check-result blockquote { margin: 13px 0 0; padding: 10px 11px; border-left: 2px solid #9cc5f6; color: #475467; background: #fff; font-size: 13px; line-height: 1.65; }.assistant-suggestion { padding: 12px 0; border-bottom: 1px solid #edf0f3; }.assistant-suggestion p { margin: 0; color: #475467; font-size: 13px; line-height: 1.6; }.assistant-suggestion>div { display: flex; align-items: center; gap: 5px; margin-top: 5px; }.assistant-suggestion>div span { color: #98a2b3; font-size: 12px; }.assistant-suggestion.proposed>div span, .assistant-suggestion.applied>div span { color: #4774a8; }.assistant-section :deep(.el-textarea) { margin-top: 12px; }.request-button { margin: 10px 0 0; }.proposal-card { margin-top: 6px; padding: 16px; border: 1px solid #dbe8f8; border-radius: 10px; background: #fbfdff; }.proposal-card h3 { margin-top: 5px; }.proposal-card>div { margin-top: 14px; }.proposal-card strong { color: #475467; font-size: 12px; }.proposal-card p { margin: 6px 0 0; color: #667085; font-size: 13px; line-height: 1.65; }.proposal-card>div:last-of-type { padding: 11px; border-radius: 7px; background: #edf5ff; }.proposal-card footer { display: flex; justify-content: flex-end; gap: 8px; margin-top: 16px; }.proposal-card footer :deep(.el-button) { margin: 0; }
@media (max-width: 1100px) { .resource-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }.common-settings-form { grid-template-columns: repeat(2, minmax(0, 1fr)); } }@media (max-width: 900px) { .mode-grid { grid-template-columns: 1fr; }.mode-card { min-height: 240px; }.resource-settings-layout, .draft-workspace { grid-template-columns: 1fr; }.selected-resource-list, .draft-resource-list { grid-template-columns: repeat(3, minmax(0, 1fr)); }.selected-resource-list h2, .draft-resource-list h2 { grid-column: 1 / -1; } }@media (max-width: 620px) { .page-header, .current-course-card header, .selection-header, .common-settings-card header, .draft-header, .editor-header { flex-direction: column; gap: 16px; }.save-area { padding-top: 0; }.mode-section, .resource-selection-card, .current-course-card, .common-settings-card, .exclusive-settings-card, .draft-header, .draft-editor { padding: 21px; }.resource-grid, .common-settings-form, .exclusive-form { grid-template-columns: 1fr; }.selection-actions, .settings-actions { gap: 12px; }.selection-actions :deep(.el-button), .settings-actions :deep(.el-button) { flex: 1; margin: 0; }.settings-actions>div { width: 100%; flex-wrap: wrap; }.selected-resource-list, .draft-resource-list { grid-template-columns: 1fr; }.editor-actions { width: 100%; flex-wrap: wrap; }.assistant-reserved { width: 100%; white-space: normal; }.mock-table { overflow-x: auto; }.mock-table div { min-width: 420px; } }
</style>
