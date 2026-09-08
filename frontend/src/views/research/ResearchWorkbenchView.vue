<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useRoute, useRouter } from 'vue-router'
import { isAxiosError } from 'axios'
import { ElMessage } from 'element-plus'
import { completeProjectResearch } from '@/api/projects'
import ResearchContextHeader from '@/components/research/ResearchContextHeader.vue'
import ResearchChatPanel from '@/components/research/chat/ResearchChatPanel.vue'
import EvidenceWorkspace from '@/components/research/EvidenceWorkspace.vue'
import { useResearchStore } from '@/stores/research'
import type { EvidenceCardEditableFields, ResearchAnalysis, ResearchChatMessage } from '@/types/research'

const route = useRoute()
const router = useRouter()
const store = useResearchStore()
const {
  currentProject, resources, selectedResourceItems, messages, analysis, evidenceDraft,
  readinessScore, readinessStatus, missingRequiredFields, isUploading, isExtracting,
  isAnalyzing, isSending, isUpdatingAnalysis, isGeneratingEvidence, isUpdatingEvidence, isConfirmingEvidence,
  loading, error, resourceCount, evidenceCount,
} = storeToRefs(store)
const invalidProject = computed(() => {
  const value = String(route.params.projectId ?? '')
  return !/^\d+$/.test(value) || Number(value) <= 0
})
const processing = computed(() => isUploading.value || isExtracting.value || isAnalyzing.value)
const hasActiveSession = computed(() => store.currentSession !== null)
const isCompletingResearch = ref(false)
const sessionInitializationFailed = ref(false)
const researchMockMode = import.meta.env.VITE_RESEARCH_USE_MOCK === 'true'

async function initialize() {
  if (invalidProject.value) return
  sessionInitializationFailed.value = false
  try {
    await store.initialize(Number(route.params.projectId))
  } catch (requestError) {
    sessionInitializationFailed.value = true
    if (isAxiosError(requestError) && requestError.response?.status === 404) {
      error.value = '项目不存在或已删除'
    }
  }
}

function upload(file: File) {
  const extension = file.name.toLowerCase().split('.').pop()
  if (!['pdf', 'docx'].includes(extension ?? '')) {
    ElMessage.error('仅支持 PDF 或 DOCX 文件')
    return
  }
  void store.uploadAndProcess(file)
}

function retryMessage(message: ResearchChatMessage) {
  void store.sendMessage(message.content, message.messageId)
}

async function sendMessage(content: string): Promise<boolean> {
  const success = await store.sendMessage(content)
  if (!success && store.error) ElMessage.warning(store.error)
  return success
}

async function saveAnalysis(value: ResearchAnalysis) {
  if (await store.updateAnalysis(value)) ElMessage.success('研究解析已保存')
  else ElMessage.error(store.error || '研究解析保存失败')
}

async function confirmAnalysis() {
  if (await store.confirmAnalysis()) ElMessage.success('研究解析已确认')
  else ElMessage.error(store.error || '研究解析确认失败')
}

async function saveEvidence(value: EvidenceCardEditableFields) {
  if (await store.updateEvidence(value)) ElMessage.success('证据卡草稿已保存')
  else ElMessage.error(store.error || '证据卡保存失败')
}

async function confirmEvidence() {
  if (await store.confirmEvidence()) ElMessage.success('已保存为正式研究证据')
  else ElMessage.error(store.error || '证据卡确认失败')
}

function viewResources() {
  document.querySelector('.resources-bar')?.scrollIntoView({ behavior: 'smooth', block: 'center' })
}

async function continueCourseDesign() {
  if (isCompletingResearch.value || invalidProject.value) return
  isCompletingResearch.value = true
  try {
    const projectId = Number(route.params.projectId)
    const { data } = await completeProjectResearch(projectId)
    if (data.data.workflowState !== 'RESEARCH_READY') {
      throw new Error(`Unexpected workflow state: ${data.data.workflowState}`)
    }
    await router.push(`/projects/${projectId}/course-design`)
  } catch (requestError) {
    const message = isAxiosError<{ message?: string }>(requestError)
      ? requestError.response?.data?.message
      : requestError instanceof Error
        ? requestError.message
        : undefined
    ElMessage.error(message || '进入课程智设失败，请稍后重试')
  } finally {
    isCompletingResearch.value = false
  }
}

onMounted(() => void initialize())
</script>

<template>
  <main class="research-page">
    <section v-if="invalidProject" class="page-state">
      <div><h1>请先选择一个教学项目</h1><p>进入研教智联前，需要先指定一个有效的教学项目。</p><el-button type="primary" @click="router.push('/projects')">前往我的项目</el-button></div>
    </section>
    <section v-else-if="loading" class="page-state"><el-skeleton :rows="8" animated /></section>
    <section v-else-if="!currentProject" class="page-state error-state">
      <div><h1>{{ error || '项目不存在或已删除' }}</h1><p>请返回项目列表选择其他教学项目，或稍后重新加载。</p><el-button @click="router.push('/projects')">前往我的项目</el-button><el-button type="primary" plain @click="initialize">重新加载</el-button></div>
    </section>
    <template v-else>
      <ResearchContextHeader :project="currentProject" :resource-count="resourceCount" :evidence-count="evidenceCount" :continuing="isCompletingResearch" :mock-mode="researchMockMode" @view-resources="viewResources" @continue-course-design="continueCourseDesign" />
      <section class="research-workspace">
        <ResearchChatPanel :resources="resources" :selected-resources="selectedResourceItems" :messages="messages" :analysis="analysis" :sending="isSending" :processing="processing" :evidence-ready="readinessStatus === 'READY'" :has-active-session="hasActiveSession" :initialization-failed="sessionInitializationFailed" :send-message="sendMessage" @upload="upload" @retry-message="retryMessage" @retry-resource="store.retryResource" @remove-resource="store.removeSelectedResource" @retry-initialize="initialize" />
        <EvidenceWorkspace :analysis="analysis" :evidence="evidenceDraft" :readiness-score="readinessScore" :readiness-status="readinessStatus" :missing-required-fields="missingRequiredFields" :saving-analysis="isUpdatingAnalysis" :generating-evidence="isGeneratingEvidence" :saving-evidence="isUpdatingEvidence" :confirming-evidence="isConfirmingEvidence" @save-analysis="saveAnalysis" @confirm-analysis="confirmAnalysis" @save-evidence="saveEvidence" @confirm-evidence="confirmEvidence" />
      </section>
    </template>
  </main>
</template>

<style scoped>
.research-page { display: flex; height: 100vh; min-height: 700px; flex-direction: column; padding: 20px 24px 22px; overflow: hidden; color: #101828; background: #f7f9fc; }.research-workspace { display: grid; min-height: 0; flex: 1; grid-template-columns: minmax(0, 2fr) minmax(320px, 1fr); gap: 18px; }.page-state { display: grid; min-height: calc(100vh - 44px); padding: 30px; place-items: center; border: 1px solid #eaecf0; border-radius: 12px; color: #667085; background: #fff; text-align: center; }.page-state>div { max-width: 520px; }.page-state h1 { margin: 0 0 10px; color: #344054; font-size: 21px; }.page-state p { margin: 0 0 20px; font-size: 13px; }.page-state :deep(.el-skeleton) { width: min(760px, 90%); }.error-state h1 { color: #b54708; }@media (max-width: 1199px) { .research-workspace { grid-template-columns: minmax(0, 1.62fr) minmax(320px, 1fr); gap: 16px; } }@media (max-width: 899px) { .research-page { height: auto; min-height: 100vh; overflow: visible; }.research-workspace { display: grid; grid-template-columns: 1fr; }.research-workspace :deep(.chat-panel), .research-workspace :deep(.evidence-workspace) { height: 720px; } }@media (max-width: 620px) { .research-page { padding: 16px; }.research-workspace :deep(.chat-panel), .research-workspace :deep(.evidence-workspace) { height: 650px; min-height: 0; } }
</style>
