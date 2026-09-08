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
const stateLabel = computed(() => ({
  UPLOADING: '正在上传…', UPLOADED: '上传完成', TEXT_EXTRACTING: '正在解析研究内容…', TEXT_EXTRACTED: '文本解析完成', ANALYZING: '正在形成研究解析…', ANALYZED: '研究解析完成', REVIEWED: '已完成教师确认', CARD_READY: '证据卡已就绪', FAILED: '解析失败',
}[props.resource.processingStatus]))
</script>

<template>
  <article class="file-card" :class="{ failed: resource.processingStatus === 'FAILED' }">
    <div class="file-symbol">PDF</div>
    <div class="file-info">
      <strong>{{ resource.fileName }}</strong>
      <span>{{ typeLabel }} · {{ sizeLabel }}</span>
      <small>{{ resource.processingStatus === 'FAILED' ? '!' : '✓' }} {{ stateLabel }}</small>
      <p v-if="resource.errorMessage">{{ resource.errorMessage }}</p>
    </div>
    <el-button v-if="resource.processingStatus === 'FAILED'" link type="danger" @click="$emit('retry', resource.resourceId)">重新解析</el-button>
  </article>
</template>

<style scoped>
.file-card { display: grid; width: min(430px, 90%); grid-template-columns: 38px minmax(0, 1fr) auto; align-items: center; gap: 11px; padding: 12px 14px; border: 1px solid #eaecf0; border-radius: 9px; background: #fafbfc; }.file-symbol { display: grid; width: 38px; height: 42px; place-items:center; border-radius: 6px; color: #4774a8; background: #edf4fc; font-size: 9px; font-weight: 700; }.file-info { min-width: 0; }.file-info strong, .file-info span, .file-info small { display: block; }.file-info strong { overflow: hidden; color: #344054; font-size: 13px; text-overflow: ellipsis; white-space: nowrap; }.file-info span { margin-top: 3px; color: #98a2b3; font-size: 11px; }.file-info small { margin-top: 6px; color: #4f8b6c; font-size: 11px; }.file-card.failed .file-info small { color: #f56c6c; }.file-info p { margin: 4px 0 0; color: #f56c6c; font-size: 11px; }
</style>
