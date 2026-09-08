<script setup lang="ts">
import { ref } from 'vue'
import { ElMessageBox } from 'element-plus'
import type { EvidenceCard, EvidenceCardEditableFields } from '@/types/research'
import EvidenceCardEditor from './EvidenceCardEditor.vue'

const props = defineProps<{
  evidence: EvidenceCard
  saving: boolean
  confirming: boolean
}>()
const emit = defineEmits<{ save: [payload: EvidenceCardEditableFields]; confirm: [] }>()
const editing = ref(false)

async function confirm() {
  const accepted = await ElMessageBox.confirm(
    '确认后，该证据卡将作为当前项目的正式研究证据，并可供后续课程设计使用。',
    '确认并保存证据卡',
    { confirmButtonText: '确认保存', cancelButtonText: '取消', type: 'warning' },
  ).then(() => true).catch(() => false)
  if (accepted && props.evidence.status === 'DRAFT') emit('confirm')
}
</script>

<template>
  <section class="evidence-card-panel">
    <div class="evidence-heading">
      <h2>研究证据卡</h2>
      <el-tag :type="evidence.status === 'CONFIRMED' ? 'success' : 'warning'" effect="plain" size="small">{{ evidence.status === 'CONFIRMED' ? '已确认' : '草稿' }}</el-tag>
    </div>
    <div class="evidence-content">
      <section><h3>研究发现</h3><p>{{ evidence.researchFinding || '—' }}</p></section>
      <section><h3>适用对象</h3><p>{{ evidence.applicableAudience || '—' }}</p></section>
      <section><h3>推荐策略</h3><ul><li v-for="item in evidence.recommendedStrategies" :key="item">{{ item }}</li><li v-if="!evidence.recommendedStrategies.length">—</li></ul></section>
      <section><h3>实施条件</h3><ul><li v-for="item in evidence.implementationConditions" :key="item">{{ item }}</li><li v-if="!evidence.implementationConditions.length">—</li></ul></section>
      <section><h3>教学转化建议</h3><p>{{ evidence.teachingImplications || '—' }}</p></section>
      <section><h3>研究局限</h3><p>{{ evidence.limitations || '—' }}</p></section>
      <section><h3>原始文献来源</h3><p>{{ evidence.sourceDocument }}<br><small>追溯标识：{{ evidence.sourceTraceId }}</small></p></section>
    </div>
    <footer class="evidence-actions">
      <template v-if="evidence.status === 'DRAFT'">
        <el-button @click="editing = true">编辑</el-button>
        <el-button type="primary" :loading="confirming" @click="confirm">确认并保存证据卡</el-button>
      </template>
      <span v-else>✓ 已保存为正式研究证据</span>
    </footer>
    <EvidenceCardEditor v-model:visible="editing" :evidence="evidence" :saving="saving" @save="$emit('save', $event)" />
  </section>
</template>

<style scoped>
.evidence-card-panel { display: flex; min-height: 100%; flex-direction: column; }.evidence-heading { display: flex; align-items: center; justify-content: space-between; padding: 0 18px 12px; border-bottom: 1px solid #eaecf0; }.evidence-heading h2 { margin: 0; color: #1d2939; font-size: 15px; }.evidence-content { min-height: 0; flex: 1; overflow-y: auto; padding: 2px 18px 18px; }.evidence-content section { padding: 14px 0; border-bottom: 1px solid #f0f2f5; }.evidence-content h3 { margin: 0 0 7px; color: #344054; font-size: 12px; }.evidence-content p, .evidence-content ul { margin: 0; padding-left: 0; color: #475467; font-size: 12px; line-height: 1.7; white-space: pre-wrap; }.evidence-content ul { padding-left: 17px; }.evidence-content small { color: #98a2b3; }.evidence-actions { display: flex; flex: none; justify-content: flex-end; gap: 8px; padding: 13px 18px 0; border-top: 1px solid #eaecf0; }.evidence-actions span { width: 100%; color: #438566; font-size: 12px; text-align: center; }
</style>
