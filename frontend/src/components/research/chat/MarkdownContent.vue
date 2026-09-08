<script setup lang="ts">
import { computed } from 'vue'
import { renderMarkdown } from '@/utils/markdown'

const props = defineProps<{ content: string }>()
const html = computed(() => renderMarkdown(props.content))
</script>

<template>
  <div class="markdown-content" v-html="html" />
</template>

<style scoped>
.markdown-content { overflow-wrap: anywhere; }
.markdown-content :deep(> :first-child) { margin-top: 0; }
.markdown-content :deep(> :last-child) { margin-bottom: 0; }
.markdown-content :deep(p) { margin: .55em 0; }
.markdown-content :deep(h1), .markdown-content :deep(h2), .markdown-content :deep(h3), .markdown-content :deep(h4), .markdown-content :deep(h5), .markdown-content :deep(h6) { margin: .9em 0 .45em; color: inherit; line-height: 1.35; }
.markdown-content :deep(h1) { font-size: 1.35em; }.markdown-content :deep(h2) { font-size: 1.22em; }.markdown-content :deep(h3) { font-size: 1.12em; }
.markdown-content :deep(ul), .markdown-content :deep(ol) { margin: .55em 0; padding-left: 1.55em; }
.markdown-content :deep(li + li) { margin-top: .24em; }
.markdown-content :deep(blockquote) { margin: .7em 0; padding: .45em .8em; border-left: 3px solid #9fbce1; color: #667085; background: rgb(255 255 255 / 58%); }
.markdown-content :deep(code) { padding: .12em .35em; border-radius: 4px; background: rgb(16 24 40 / 7%); font-family: Consolas, Monaco, monospace; font-size: .9em; }
.markdown-content :deep(pre) { overflow-x: auto; margin: .7em 0; padding: .75em .9em; border-radius: 7px; color: #e6edf3; background: #1f2937; }
.markdown-content :deep(pre code) { padding: 0; color: inherit; background: transparent; white-space: pre; }
.markdown-content :deep(a) { color: #1677ff; text-decoration: underline; text-underline-offset: 2px; }
.markdown-content :deep(hr) { margin: .9em 0; border: 0; border-top: 1px solid #d9e1ea; }
.markdown-content :deep(.markdown-table-wrap) { overflow-x: auto; margin: .7em 0; }
.markdown-content :deep(table) { width: 100%; border-collapse: collapse; font-size: .94em; }
.markdown-content :deep(th), .markdown-content :deep(td) { padding: .45em .6em; border: 1px solid #dce3ec; text-align: left; }
.markdown-content :deep(th) { background: rgb(16 24 40 / 5%); font-weight: 650; }
</style>
