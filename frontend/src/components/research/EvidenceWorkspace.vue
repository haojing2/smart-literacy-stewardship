<script setup lang="ts">
import { ref, watch } from 'vue'
import type { EvidenceCard, EvidenceCardEditableFields, ResearchAnalysis } from '@/types/research'
import ResearchAnalysisPanel from './analysis/ResearchAnalysisPanel.vue'
import EvidenceCardPanel from './evidence/EvidenceCardPanel.vue'

const props = defineProps<{
  analysis: ResearchAnalysis | null
  evidence: EvidenceCard | null
  readinessScore: number
  readinessStatus: 'INCOMPLETE' | 'READY'
  missingRequiredFields: string[]
  savingAnalysis: boolean
  generatingEvidence: boolean
  savingEvidence: boolean
  confirmingEvidence: boolean
}>()
defineEmits<{
  saveAnalysis: [analysis: ResearchAnalysis]
  confirmAnalysis: []
  saveEvidence: [payload: EvidenceCardEditableFields]
  confirmEvidence: []
}>()
const activeTab = ref('analysis')
watch(() => props.evidence, (evidence, previous) => {
  if (evidence && !previous) activeTab.value = 'evidence'
  if (!evidence && activeTab.value !== 'evidence') activeTab.value = 'analysis'
})
</script>

<template>
  <aside class="evidence-workspace">
    <el-tabs v-model="activeTab" class="workspace-tabs">
      <el-tab-pane label="研究解析" name="analysis">
        <ResearchAnalysisPanel :analysis="analysis" :readiness-score="readinessScore" :readiness-status="readinessStatus" :missing-required-fields="missingRequiredFields" :saving="savingAnalysis" @save="$emit('saveAnalysis', $event)" @confirm="$emit('confirmAnalysis')" />
      </el-tab-pane>
      <el-tab-pane name="evidence">
        <template #label><span class="evidence-tab-label">证据卡<i v-if="evidence && evidence.status === 'DRAFT'"></i></span></template>
        <div v-if="generatingEvidence" class="evidence-loading"><p>正在生成证据卡草稿……</p><el-skeleton :rows="7" animated /></div>
        <EvidenceCardPanel v-else-if="evidence" :evidence="evidence" :saving="savingEvidence" :confirming="confirmingEvidence" @save="$emit('saveEvidence', $event)" @confirm="$emit('confirmEvidence')" />
        <div v-else class="evidence-empty">
          <div>▤</div><h3>还未生成证据卡</h3><p>随着研究信息逐步完整，系统会自动形成证据卡草稿。</p><span>当前信息完整度 {{ readinessScore }}%</span>
        </div>
      </el-tab-pane>
    </el-tabs>
  </aside>
</template>

<style scoped>
.evidence-workspace { min-width: 0; min-height: 590px; overflow: hidden; border: 1px solid #eaecf0; border-radius: 12px; background: #fff; box-shadow: 0 1px 3px rgb(16 24 40 / 4%); }.workspace-tabs { display: flex; height: 100%; flex-direction: column; }.workspace-tabs :deep(.el-tabs__header) { flex: none; margin: 0 18px 16px; }.workspace-tabs :deep(.el-tabs__nav-wrap::after) { height: 1px; background: #eaecf0; }.workspace-tabs :deep(.el-tabs__item) { height: 48px; color: #667085; font-size: 13px; }.workspace-tabs :deep(.el-tabs__item.is-active) { color: #1677ff; }.workspace-tabs :deep(.el-tabs__active-bar) { height: 2px; }.workspace-tabs :deep(.el-tabs__content), .workspace-tabs :deep(.el-tab-pane) { min-height: 0; flex: 1; height: 100%; overflow-y: auto; }.evidence-tab-label { position: relative; }.evidence-tab-label i { position: absolute; top: -1px; right: -8px; width: 6px; height: 6px; border-radius: 50%; background: #1677ff; }.evidence-empty { display: flex; min-height: 420px; align-items: center; justify-content: center; flex-direction: column; padding: 30px 20px; text-align: center; }.evidence-empty>div { display: grid; width: 40px; height: 40px; place-items: center; border-radius: 10px; color: #667085; background: #f5f7fa; }.evidence-empty h3 { margin: 14px 0 7px; color: #344054; font-size: 15px; }.evidence-empty p { max-width: 250px; margin: 0; color: #98a2b3; font-size: 12px; line-height: 1.7; }.evidence-empty span { margin-top: 14px; color: #667085; font-size: 12px; }.evidence-loading { padding: 8px 18px; }.evidence-loading p { color: #667085; font-size: 12px; }
</style>
