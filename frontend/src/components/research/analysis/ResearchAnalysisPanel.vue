<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { RESEARCH_ANALYSIS_FIELDS, type ResearchAnalysis, type ResearchAnalysisContentKey } from '@/types/research'
import AnalysisFieldItem from './AnalysisFieldItem.vue'
import EvidenceReadiness from './EvidenceReadiness.vue'

const props = defineProps<{ analysis: ResearchAnalysis | null; readinessScore: number; readinessStatus: 'INCOMPLETE' | 'READY'; missingRequiredFields: string[]; saving: boolean; generationStatus: 'PENDING' | 'READY' | 'FAILED' | null; scope: 'PROJECT' | 'RESOURCE'; sourceLabel: string }>()
const emit = defineEmits<{ save: [analysis: ResearchAnalysis]; confirm: []; reanalyze: [] }>()
const editorVisible = ref(false)
const draft = reactive<Record<ResearchAnalysisContentKey, string>>(Object.fromEntries(RESEARCH_ANALYSIS_FIELDS.map((field) => [field.key, ''])) as Record<ResearchAnalysisContentKey, string>)

function displayValue(key: ResearchAnalysisContentKey): string {
  const value = props.analysis?.[key]
  return Array.isArray(value) ? value.join('；') : value ?? ''
}
const fields = computed(() => RESEARCH_ANALYSIS_FIELDS.map((field) => ({ ...field, value: displayValue(field.key) })))
const recognizedCount = computed(() => fields.value.filter((field) => field.value.trim()).length)
const lines = (value: string) => value.split('\n').map((item) => item.trim()).filter(Boolean)

function syncDraft() {
  for (const field of RESEARCH_ANALYSIS_FIELDS) {
    const value = props.analysis?.[field.key]
    draft[field.key] = Array.isArray(value) ? value.join('\n') : value ?? ''
  }
}
function openEditor() { syncDraft(); editorVisible.value = true }
function save() {
  if (!props.analysis) return
  const content = Object.fromEntries(RESEARCH_ANALYSIS_FIELDS.map((field) => [field.key, field.isList ? lines(draft[field.key]) : draft[field.key].trim() || null])) as Pick<ResearchAnalysis, ResearchAnalysisContentKey>
  emit('save', { ...props.analysis, ...content })
  editorVisible.value = false
}
watch(() => props.analysis, syncDraft, { deep: true, immediate: true })
</script>

<template>
  <section class="analysis-panel">
    <div class="panel-heading"><div><h2>{{ scope === 'RESOURCE' ? '单篇论文解析' : '项目综合解析' }}</h2><p>{{ scope === 'RESOURCE' ? `来源：《${sourceLabel}》` : '范围：全部已就绪研究资源' }}</p></div><span v-if="generationStatus !== 'FAILED'">{{ recognizedCount }}/{{ RESEARCH_ANALYSIS_FIELDS.length }} 已识别</span></div>
    <div v-if="generationStatus === 'FAILED'" class="analysis-failed"><strong>论文文档与知识索引已就绪 · AI结构化解析失败，可重新分析</strong><el-button type="primary" plain @click="$emit('reanalyze')">重新分析</el-button></div>
    <template v-else>
      <p class="generation-status">{{ generationStatus === 'PENDING' ? '解析中' : generationStatus === 'READY' ? '解析完成' : '' }}</p>
      <EvidenceReadiness :score="readinessScore" :status="readinessStatus" :missing-required-fields="missingRequiredFields" />
      <el-skeleton v-if="!analysis" :rows="7" animated class="analysis-skeleton" />
      <div v-else class="field-list"><AnalysisFieldItem v-for="field in fields" :key="field.key" :label="field.label" :value="field.value" :source="analysis.fieldSources?.[field.key]" @edit="openEditor" /></div>
      <el-button v-if="readinessStatus === 'READY' && !analysis?.teacherConfirmed" class="confirm-analysis" plain type="success" @click="$emit('confirm')">确认当前研究解析</el-button>
      <p v-else-if="analysis?.teacherConfirmed" class="confirmed-analysis">✓ 教师已确认当前研究解析</p>
    </template>
    <el-dialog v-model="editorVisible" title="编辑研究解析" width="min(680px, 92vw)" append-to-body>
      <el-form label-position="top" class="analysis-form">
        <el-form-item v-for="field in RESEARCH_ANALYSIS_FIELDS" :key="field.key" :label="field.label" :class="{ 'full-row': field.key === 'aiLiteracyDimensions' || field.key === 'limitations' || field.key === 'teachingImplications' }"><el-input v-model="draft[field.key]" :type="field.editorType" :rows="field.isList ? 3 : 2" :placeholder="field.isList ? '每行一项' : undefined" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="editorVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="save">保存解析</el-button></template>
    </el-dialog>
  </section>
</template>

<style scoped>
.analysis-panel { padding: 0 18px 20px; }.panel-heading { display: flex; align-items: center; justify-content: space-between; }.panel-heading h2 { margin: 0; color: #1d2939; font-size: 15px; }.panel-heading p { margin: 4px 0 0; color: #667085; font-size: 11px; }.panel-heading span { color: #667085; font-size: 11px; }.generation-status { margin: 12px 0 0; color: #438566; font-size: 12px; }.analysis-failed { margin-top: 16px; padding: 16px; border: 1px solid #fecdca; border-radius: 8px; color: #b42318; background: #fffbfa; }.analysis-skeleton { padding-top: 18px; }.field-list { padding-bottom: 8px; }.confirm-analysis { width: 100%; margin-top: 10px; }.confirmed-analysis { margin: 10px 0 0; color: #438566; font-size: 12px; text-align: center; }.analysis-form { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0 18px; }.analysis-form .full-row { grid-column: 1 / -1; }@media (max-width: 600px) { .analysis-form { display: block; } }
</style>
