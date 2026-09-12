<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { RESEARCH_ANALYSIS_FIELDS, type ResearchAnalysis, type ResearchAnalysisContentKey } from '@/types/research'
import AnalysisFieldItem from './AnalysisFieldItem.vue'
import EvidenceReadiness from './EvidenceReadiness.vue'

const props = withDefaults(defineProps<{ analysis: ResearchAnalysis | null; readinessScore: number; readinessStatus: 'INCOMPLETE' | 'READY'; missingRequiredFields: string[]; saving: boolean; generatingEvidence?: boolean; evidenceGenerated?: boolean; generationStatus: 'PENDING' | 'READY' | 'FAILED' | null; scope: 'PROJECT' | 'RESOURCE'; sourceLabel: string }>(), { generatingEvidence: false, evidenceGenerated: false })
const emit = defineEmits<{ save: [analysis: ResearchAnalysis]; confirm: []; generateEvidence: [] }>()
const editorVisible = ref(false)
const draft = reactive<Record<ResearchAnalysisContentKey, string>>(Object.fromEntries(RESEARCH_ANALYSIS_FIELDS.map((field) => [field.key, ''])) as Record<ResearchAnalysisContentKey, string>)

function displayValue(key: ResearchAnalysisContentKey): string {
  const value = props.analysis?.[key]
  return Array.isArray(value) ? value.join('；') : value ?? ''
}
const fields = computed(() => RESEARCH_ANALYSIS_FIELDS.map((field) => ({ ...field, value: displayValue(field.key) })))
const recognizedCount = computed(() => RESEARCH_ANALYSIS_FIELDS.filter((field) => {
  const value = props.analysis?.[field.key]
  return Array.isArray(value) ? value.length > 0 : Boolean(value?.trim())
}).length)
const lines = (value: string) => value.split('\n').map((item) => item.trim()).filter(Boolean)

function syncDraft() {
  for (const field of RESEARCH_ANALYSIS_FIELDS) {
    const value = props.analysis?.[field.key]
    draft[field.key] = Array.isArray(value) ? value.join('\n') : value ?? ''
  }
}
function openEditor() { syncDraft(); editorVisible.value = true }
function save() {
  const content = Object.fromEntries(RESEARCH_ANALYSIS_FIELDS.map((field) => [field.key, field.isList ? lines(draft[field.key]) : draft[field.key].trim() || null])) as Pick<ResearchAnalysis, ResearchAnalysisContentKey>
  emit('save', { ...emptyAnalysis(), ...props.analysis, ...content })
  editorVisible.value = false
}
function emptyAnalysis(): ResearchAnalysis {
  return { participants: [], researchTopics: [], aiLiteracyDimensions: [], teachingStrategies: [], intervention: null, assessmentTools: [], mainFindings: [], limitations: [], teachingImplications: null }
}
watch(() => props.analysis, syncDraft, { deep: true, immediate: true })
</script>

<template>
  <section class="analysis-panel">
    <div class="panel-heading"><div><h2>{{ scope === 'RESOURCE' ? '单篇论文解析' : '项目综合解析' }}</h2><p>{{ scope === 'RESOURCE' ? `来源：《${sourceLabel}》` : '范围：全部已就绪研究资源' }}</p></div><span>{{ recognizedCount }}/{{ RESEARCH_ANALYSIS_FIELDS.length }} 已识别</span></div>
    <template>
      <p class="generation-status">{{ recognizedCount === 0 ? '研究解析待探索 · 可通过下方研究探索逐步完善' : '研究解析逐步完善中' }}</p>
      <EvidenceReadiness :score="readinessScore" :status="readinessStatus" :missing-required-fields="missingRequiredFields" />
      <div class="field-list"><AnalysisFieldItem v-for="field in fields" :key="field.key" :label="field.label" :value="field.value" :source="analysis?.fieldSources?.[field.key]" @edit="openEditor" /></div>
      <el-button v-if="readinessStatus === 'READY' && !analysis?.teacherConfirmed" class="confirm-analysis" plain type="success" @click="$emit('confirm')">确认当前研究解析</el-button>
      <p v-else-if="analysis?.teacherConfirmed" class="confirmed-analysis">✓ 教师已确认当前研究解析</p>
      <div class="evidence-generation">
        <template v-if="evidenceGenerated"><p>证据卡已生成 · 查看证据卡</p><el-button link type="primary" @click="$emit('generateEvidence')">查看证据卡</el-button></template>
        <template v-else><el-button type="primary" :disabled="recognizedCount < 6" :loading="generatingEvidence" @click="$emit('generateEvidence')">生成证据卡</el-button><small v-if="recognizedCount < 6">至少完成6/9项研究解析后可生成</small></template>
      </div>
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
.analysis-panel { padding: 0 18px 20px; }.panel-heading { display: flex; align-items: center; justify-content: space-between; }.panel-heading h2 { margin: 0; color: #1d2939; font-size: 15px; }.panel-heading p { margin: 4px 0 0; color: #667085; font-size: 11px; }.panel-heading span { color: #667085; font-size: 11px; }.generation-status { margin: 12px 0 0; color: #438566; font-size: 12px; }.field-list { padding-bottom: 8px; }.confirm-analysis { width: 100%; margin-top: 10px; }.confirmed-analysis { margin: 10px 0 0; color: #438566; font-size: 12px; text-align: center; }.evidence-generation { display: flex; align-items: center; justify-content: center; flex-direction: column; gap: 6px; margin-top: 14px; padding-top: 14px; border-top: 1px solid #eaecf0; }.evidence-generation p, .evidence-generation small { margin: 0; color: #667085; font-size: 12px; }.analysis-form { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0 18px; }.analysis-form .full-row { grid-column: 1 / -1; }@media (max-width: 600px) { .analysis-form { display: block; } }
</style>
