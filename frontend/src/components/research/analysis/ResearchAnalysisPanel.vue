<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import type { ResearchAnalysis } from '@/types/research'
import AnalysisFieldItem from './AnalysisFieldItem.vue'
import EvidenceReadiness from './EvidenceReadiness.vue'

const props = defineProps<{
  analysis: ResearchAnalysis | null
  readinessScore: number
  readinessStatus: 'INCOMPLETE' | 'READY'
  missingRequiredFields: string[]
  saving: boolean
}>()
const emit = defineEmits<{ save: [analysis: ResearchAnalysis]; confirm: [] }>()
const editorVisible = ref(false)
const dimensions = [
  { value: 'AI_COGNITION', label: 'AI认知' },
  { value: 'HUMAN_AI_INTERACTION', label: '有效交互' },
  { value: 'INFORMATION_VERIFICATION', label: '信息核验' },
  { value: 'SAFETY_ETHICS', label: '安全伦理' },
  { value: 'INNOVATIVE_APPLICATION', label: '创新应用' },
]
const draft = reactive({
  participants: '', researchTopic: '', aiLiteracyDimensions: [] as string[], teachingStrategies: '', intervention: '', assessmentTools: '', mainFindings: '', limitations: '',
})

const fields = computed(() => {
  const value = props.analysis
  return [
    { key: 'participants', label: '学习者/适用对象', value: value?.participants.join('；') ?? '' },
    { key: 'researchTopic', label: '研究问题/主题', value: value?.researchTopic ?? '' },
    { key: 'aiLiteracyDimensions', label: '能力重点', value: value?.aiLiteracyDimensions.map(dimensionLabel).join('、') ?? '' },
    { key: 'teachingStrategies', label: '教学策略', value: value?.teachingStrategies.join('；') ?? '' },
    { key: 'intervention', label: '实施条件', value: value?.intervention ?? '' },
    { key: 'assessmentTools', label: '评价方式', value: value?.assessmentTools.join('；') ?? '' },
    { key: 'mainFindings', label: '主要研究发现', value: value?.mainFindings.join('；') ?? '' },
    { key: 'limitations', label: '局限与迁移边界', value: value?.limitations.join('；') ?? '' },
  ]
})
const recognizedCount = computed(() => fields.value.filter((field) => field.value.trim()).length)

function dimensionLabel(value: string) {
  return dimensions.find((dimension) => dimension.value === value)?.label ?? value
}

function lines(value: string) {
  return value.split('\n').map((item) => item.trim()).filter(Boolean)
}

function syncDraft() {
  const value = props.analysis
  if (!value) return
  draft.participants = value.participants.join('\n')
  draft.researchTopic = value.researchTopic ?? ''
  draft.aiLiteracyDimensions = [...value.aiLiteracyDimensions]
  draft.teachingStrategies = value.teachingStrategies.join('\n')
  draft.intervention = value.intervention ?? ''
  draft.assessmentTools = value.assessmentTools.join('\n')
  draft.mainFindings = value.mainFindings.join('\n')
  draft.limitations = value.limitations.join('\n')
}

function openEditor() {
  syncDraft()
  editorVisible.value = true
}

function save() {
  if (!props.analysis) return
  emit('save', {
    ...props.analysis,
    participants: lines(draft.participants),
    researchTopic: draft.researchTopic.trim() || null,
    aiLiteracyDimensions: [...draft.aiLiteracyDimensions],
    teachingStrategies: lines(draft.teachingStrategies),
    intervention: draft.intervention.trim() || null,
    assessmentTools: lines(draft.assessmentTools),
    mainFindings: lines(draft.mainFindings),
    limitations: lines(draft.limitations),
  })
  editorVisible.value = false
}

watch(() => props.analysis, syncDraft, { deep: true })
</script>

<template>
  <section class="analysis-panel">
    <div class="panel-heading"><h2>研究解析</h2><span>{{ recognizedCount }}/8 已识别</span></div>
    <EvidenceReadiness :score="readinessScore" :status="readinessStatus" :missing-required-fields="missingRequiredFields" />
    <el-skeleton v-if="!analysis" :rows="7" animated class="analysis-skeleton" />
    <div v-else class="field-list">
      <AnalysisFieldItem v-for="field in fields" :key="field.key" :label="field.label" :value="field.value" :source="analysis.fieldSources?.[field.key]" @edit="openEditor" />
    </div>
    <el-button v-if="readinessStatus === 'READY' && !analysis?.teacherConfirmed" class="confirm-analysis" plain type="success" @click="$emit('confirm')">确认当前研究解析</el-button>
    <p v-else-if="analysis?.teacherConfirmed" class="confirmed-analysis">✓ 教师已确认当前研究解析</p>

    <el-dialog v-model="editorVisible" title="编辑研究解析" width="min(680px, 92vw)" append-to-body>
      <el-form label-position="top" class="analysis-form">
        <el-form-item label="研究对象"><el-input v-model="draft.participants" type="textarea" :rows="2" placeholder="每行一项" /></el-form-item>
        <el-form-item label="研究主题"><el-input v-model="draft.researchTopic" /></el-form-item>
        <el-form-item label="AI素养维度" class="full-row"><el-checkbox-group v-model="draft.aiLiteracyDimensions"><el-checkbox v-for="item in dimensions" :key="item.value" :value="item.value">{{ item.label }}</el-checkbox></el-checkbox-group></el-form-item>
        <el-form-item label="教学策略"><el-input v-model="draft.teachingStrategies" type="textarea" :rows="3" placeholder="每行一项" /></el-form-item>
        <el-form-item label="干预时间"><el-input v-model="draft.intervention" /></el-form-item>
        <el-form-item label="评价工具"><el-input v-model="draft.assessmentTools" type="textarea" :rows="2" placeholder="每行一项" /></el-form-item>
        <el-form-item label="主要研究结果"><el-input v-model="draft.mainFindings" type="textarea" :rows="3" placeholder="每行一项" /></el-form-item>
        <el-form-item label="研究局限" class="full-row"><el-input v-model="draft.limitations" type="textarea" :rows="3" placeholder="每行一项" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="editorVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="save">保存解析</el-button></template>
    </el-dialog>
  </section>
</template>

<style scoped>
.analysis-panel { padding: 0 18px 20px; }.panel-heading { display: flex; align-items: center; justify-content: space-between; }.panel-heading h2 { margin: 0; color: #1d2939; font-size: 15px; }.panel-heading span { color: #667085; font-size: 11px; }.analysis-skeleton { padding-top: 18px; }.field-list { padding-bottom: 8px; }.confirm-analysis { width: 100%; margin-top: 10px; }.confirmed-analysis { margin: 10px 0 0; color: #438566; font-size: 12px; text-align: center; }.analysis-form { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0 18px; }.analysis-form .full-row { grid-column: 1 / -1; }.analysis-form :deep(.el-checkbox) { margin-right: 18px; }@media (max-width: 600px) { .analysis-form { display: block; } }
</style>
