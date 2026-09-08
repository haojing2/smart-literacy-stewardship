<script setup lang="ts">
import { computed, ref } from 'vue'
import type { ResearchChatMessage } from '@/types/research'
import MarkdownContent from './MarkdownContent.vue'

const props = defineProps<{ message: ResearchChatMessage }>()
defineEmits<{ retry: [message: ResearchChatMessage] }>()
const expanded = ref(false)
const isLong = computed(() => props.message.content.length > 600 || props.message.content.split('\n').length > 8)
</script>

<template>
  <div class="user-message-wrap">
    <article class="user-message" :class="{ collapsed: isLong && !expanded }">
      <MarkdownContent class="message-markdown" :content="message.content" />
      <button v-if="isLong" type="button" class="expand-button" @click="expanded = !expanded">
        {{ expanded ? '收起 ↑' : '展开全文 ↓' }}
      </button>
    </article>
    <div v-if="message.sendStatus === 'SENDING'" class="message-state">发送中…</div>
    <div v-else-if="message.sendStatus === 'FAILED'" class="message-state error">
      消息发送失败 <button type="button" @click="$emit('retry', message)">重新发送</button>
    </div>
  </div>
</template>

<style scoped>
.message-markdown { margin: 0; }
.user-message.collapsed .message-markdown { display: -webkit-box; overflow: hidden; -webkit-box-orient: vertical; -webkit-line-clamp: 8; }
.user-message-wrap { display: flex; align-items: flex-end; flex-direction: column; }.user-message { max-width: 76%; padding: 13px 17px; border-radius: 17px; color: #1d2939; background: #f1f7ff; font-size: 14px; line-height: 1.72; }.user-message p { margin: 0; white-space: pre-wrap; overflow-wrap: anywhere; }.user-message.collapsed p { display: -webkit-box; overflow: hidden; -webkit-box-orient: vertical; -webkit-line-clamp: 8; }.expand-button { margin-top: 7px; padding: 0; border: 0; color: #4774a8; background: transparent; cursor: pointer; font-size: 12px; }.message-state { margin-top: 5px; color: #98a2b3; font-size: 11px; }.message-state.error { color: #f56c6c; }.message-state button { padding: 0; border: 0; color: inherit; background: transparent; cursor: pointer; text-decoration: underline; }
</style>
