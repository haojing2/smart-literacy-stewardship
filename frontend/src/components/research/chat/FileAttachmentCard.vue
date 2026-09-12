<script setup lang="ts">
import { computed } from 'vue'
import type { ResearchResource } from '@/types/research'

const props = defineProps<{ resource: ResearchResource }>()
defineEmits<{ retry: [resourceId: number] }>()
const sizeLabel = computed(() => {
  const bytes = props.resource.fileSize
  return bytes >= 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`
})
const typeLabel = computed(() => (props.resource.fileName.toLowerCase().endsWith('.docx') ? 'DOCX' : 'PDF'))
const hasProcessingError = computed(() =>
  props.resource.processingStatus === 'FAILED' || props.resource.indexStatus === 'error',
)
const stateLabel = computed(() => {
  const { processingStatus, indexStatus } = props.resource
  if (processingStatus === 'UPLOADING') return '正在上传…'
  if (processingStatus === 'TEXT_EXTRACTING') return '正在提取论文文本…'
  if (processingStatus === 'TEXT_EXTRACTED') {
    if (indexStatus === 'error') return '文本提取已完成 · 向量化与检索索引失败'
    if (indexStatus === 'ready') return '文本提取已完成 · 论文向量化与检索已完成'
    return '文本提取已完成 · 正在向量化与建立检索索引…'
  }
  if (processingStatus === 'UPLOADED') return '上传完成，等待文本提取'
  if (processingStatus === 'FAILED') return '处理失败'
  if (processingStatus === 'REVIEWED') return '已完成教师确认'
  if (processingStatus === 'CARD_READY') return '证据卡已就绪'
  return '研究资源处理中'
})
</script>

<template>
  <article class="file-card" :class="{ failed: hasProcessingError }">
    <div class="file-symbol">PDF</div>
    <div class="file-info">
      <strong>{{ resource.fileName }}</strong>
      <span>{{ typeLabel }} · {{ sizeLabel }}</span>
      <small>{{ hasProcessingError ? '!' : '✓' }} {{ stateLabel }}</small>
      <p v-if="resource.errorMessage">{{ resource.errorMessage }}</p>
    </div>
    <el-button v-if="hasProcessingError" link type="danger" @click="$emit('retry', resource.resourceId)">重新处理</el-button>
  </article>
</template>

<style scoped>
.file-card { display: grid; width: min(430px, 90%); grid-template-columns: 38px minmax(0, 1fr) auto; align-items: center; gap: 11px; padding: 12px 14px; border: 1px solid #eaecf0; border-radius: 9px; background: #fafbfc; }.file-symbol { display: grid; width: 38px; height: 42px; place-items:center; border-radius: 6px; color: #4774a8; background: #edf4fc; font-size: 9px; font-weight: 700; }.file-info { min-width: 0; }.file-info strong, .file-info span, .file-info small { display: block; }.file-info strong { overflow: hidden; color: #344054; font-size: 13px; text-overflow: ellipsis; white-space: nowrap; }.file-info span { margin-top: 3px; color: #98a2b3; font-size: 11px; }.file-info small { margin-top: 6px; color: #4f8b6c; font-size: 11px; }.file-card.failed .file-info small { color: #f56c6c; }.file-info p { margin: 4px 0 0; color: #f56c6c; font-size: 11px; }
</style>
