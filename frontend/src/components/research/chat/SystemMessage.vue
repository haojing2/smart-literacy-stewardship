<script setup lang="ts">
import MarkdownContent from './MarkdownContent.vue'

defineProps<{ content: string; failed?: boolean }>()
</script>

<template>
  <div class="system-message" :class="{ failed }">
    <span>{{ failed ? '!' : '✓' }}</span>
    <MarkdownContent :content="content" />
  </div>
</template>

<style scoped>
.system-message { display: flex; align-items: flex-start; gap: 7px; color: #667085; font-size: 12px; line-height: 1.5; }
.system-message>span { flex: none; color: #4f8b6c; }
.system-message.failed, .system-message.failed>span { color: #f56c6c; }
</style>
