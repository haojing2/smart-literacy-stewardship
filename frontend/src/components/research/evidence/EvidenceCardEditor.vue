<script setup lang="ts">
import { reactive, watch } from 'vue'
import type { EvidenceCard, EvidenceCardEditableFields } from '@/types/research'

const props = defineProps<{ visible: boolean; evidence: EvidenceCard; saving: boolean }>()
const emit = defineEmits<{ 'update:visible': [visible: boolean]; save: [payload: EvidenceCardEditableFields] }>()
const form = reactive({
  researchFinding: '', applicableAudience: '', recommendedStrategies: '', implementationConditions: '', teachingImplications: '', limitations: '',
})

function sync() {
  form.researchFinding = props.evidence.researchFinding
  form.applicableAudience = props.evidence.applicableAudience
  form.recommendedStrategies = props.evidence.recommendedStrategies.join('\n')
  form.implementationConditions = props.evidence.implementationConditions.join('\n')
  form.teachingImplications = props.evidence.teachingImplications
  form.limitations = props.evidence.limitations
}

function list(value: string) {
  return value.split('\n').map((item) => item.trim()).filter(Boolean)
}

function save() {
  emit('save', {
    researchFinding: form.researchFinding.trim(),
    applicableAudience: form.applicableAudience.trim(),
    recommendedStrategies: list(form.recommendedStrategies),
    implementationConditions: list(form.implementationConditions),
    teachingImplications: form.teachingImplications.trim(),
    limitations: form.limitations.trim(),
  })
  emit('update:visible', false)
}

watch(() => props.visible, (visible) => { if (visible) sync() }, { immediate: true })
</script>

<template>
  <el-dialog :model-value="visible" title="编辑研究证据卡" width="min(680px, 92vw)" append-to-body @update:model-value="$emit('update:visible', $event)">
    <el-form label-position="top" class="evidence-form">
      <el-form-item label="研究发现"><el-input v-model="form.researchFinding" type="textarea" :rows="3" /></el-form-item>
      <el-form-item label="适用对象"><el-input v-model="form.applicableAudience" /></el-form-item>
      <el-form-item label="推荐策略"><el-input v-model="form.recommendedStrategies" type="textarea" :rows="3" placeholder="每行一项" /></el-form-item>
      <el-form-item label="实施条件"><el-input v-model="form.implementationConditions" type="textarea" :rows="3" placeholder="每行一项" /></el-form-item>
      <el-form-item label="教学转化建议"><el-input v-model="form.teachingImplications" type="textarea" :rows="3" /></el-form-item>
      <el-form-item label="研究局限"><el-input v-model="form.limitations" type="textarea" :rows="3" /></el-form-item>
    </el-form>
    <template #footer><el-button @click="$emit('update:visible', false)">取消</el-button><el-button type="primary" :loading="saving" @click="save">保存修改</el-button></template>
  </el-dialog>
</template>

<style scoped>
.evidence-form :deep(.el-form-item) { margin-bottom: 18px; }
</style>
