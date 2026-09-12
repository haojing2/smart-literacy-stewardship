<script setup lang="ts">
import MarkdownContent from './MarkdownContent.vue'

defineProps<{ content: string; evidenceReady: boolean; typing?: boolean }>()
defineEmits<{ viewSource: [] }>()
</script>

<template>
  <article class="assistant-message">
    <div class="assistant-mark">✦</div>
    <div class="assistant-body">
      <strong>研教智联助手</strong>
      <MarkdownContent class="assistant-markdown" :content="content" />
      <span v-if="typing" class="typing-cursor" aria-label="正在输入" />
      <div class="assistant-actions">
        <el-button link @click="$emit('viewSource')">查看依据</el-button>
        <el-button link :disabled="!evidenceReady" title="达到 READY 后自动生成证据卡">加入证据卡</el-button>
      </div>
    </div>
  </article>
</template>

<style scoped>
.assistant-markdown { margin-top: 8px; color: #344054; font-size: 14px; line-height: 1.78; }
.assistant-message { display: grid; grid-template-columns: 28px minmax(0, 1fr); gap: 10px; max-width: 94%; color: #344054; }.assistant-mark { display: grid; width: 27px; height: 27px; place-items: center; border: 1px solid #dce8f6; border-radius: 8px; color: #1677ff; background: #f6f9fd; font-size: 13px; }.assistant-body>strong { color: #1d2939; font-size: 13px; }.assistant-body p { margin: 8px 0 0; color: #344054; font-size: 14px; line-height: 1.78; white-space: pre-wrap; overflow-wrap: anywhere; }.assistant-actions { display: flex; gap: 4px; margin-top: 9px; }.assistant-actions :deep(.el-button) { margin: 0; padding: 0 6px 0 0; color: #667085; font-size: 12px; }.assistant-actions :deep(.el-button:hover) { color: #1677ff; }
.typing-cursor { display: inline-block; width: 2px; height: 1em; margin-left: 2px; vertical-align: -2px; background: #1677ff; animation: cursor-blink .8s steps(1, end) infinite; }
@keyframes cursor-blink { 0%, 50% { opacity: 1; } 51%, 100% { opacity: 0; } }
@media (prefers-reduced-motion: reduce) { .typing-cursor { animation: none; } }
</style>
