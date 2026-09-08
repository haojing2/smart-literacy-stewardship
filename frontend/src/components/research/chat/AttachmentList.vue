<script setup lang="ts">
import type { ComposerAttachment } from '@/types/composer'

defineProps<{ attachments: ComposerAttachment[] }>()
defineEmits<{ remove: [id: string] }>()

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}
</script>

<template>
  <div class="attachment-list" aria-label="待发送附件">
    <div v-for="attachment in attachments" :key="attachment.id" class="attachment-chip">
      <span class="file-type-icon" aria-hidden="true">
        <svg viewBox="0 0 24 24">
          <path d="M7 3.75h6.7L18 8.05v12.2H7z" />
          <path d="M13.5 3.75v4.5H18" />
        </svg>
        <b>{{ attachment.extension || 'FILE' }}</b>
      </span>
      <span class="attachment-info">
        <strong :title="attachment.name">{{ attachment.name }}</strong>
        <small>{{ attachment.extension || 'FILE' }} · {{ formatSize(attachment.size) }}</small>
      </span>
      <button
        type="button"
        class="remove-attachment"
        :aria-label="`删除附件 ${attachment.name}`"
        title="删除附件"
        @click="$emit('remove', attachment.id)"
      >
        <svg viewBox="0 0 20 20" aria-hidden="true"><path d="m6 6 8 8m0-8-8 8" /></svg>
      </button>
    </div>
  </div>
</template>

<style scoped>
.attachment-list { display: flex; max-width: 920px; flex-wrap: wrap; gap: 8px; margin: 0 auto 8px; }
.attachment-chip { display: flex; min-width: 210px; max-width: 310px; align-items: center; gap: 9px; padding: 8px 9px; border: 1px solid #e5e7eb; border-radius: 10px; background: #f8fafc; }
.file-type-icon { position: relative; display: grid; width: 34px; height: 38px; flex: none; place-items: center; color: #64748b; }
.file-type-icon svg { width: 28px; height: 32px; fill: #fff; stroke: currentColor; stroke-width: 1.35; stroke-linecap: round; stroke-linejoin: round; }
.file-type-icon b { position: absolute; bottom: 2px; padding: 1px 3px; border-radius: 3px; color: #4774a8; background: #eaf2fc; font-size: 7px; line-height: 1.2; }
.attachment-info { min-width: 0; flex: 1; }
.attachment-info strong, .attachment-info small { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.attachment-info strong { color: #334155; font-size: 12px; font-weight: 600; }
.attachment-info small { margin-top: 3px; color: #94a3b8; font-size: 10px; text-transform: uppercase; }
.remove-attachment { display: grid; width: 26px; height: 26px; flex: none; padding: 0; place-items: center; border: 0; border-radius: 50%; color: #94a3b8; background: transparent; cursor: pointer; }
.remove-attachment:hover { color: #475569; background: #e9eef4; }.remove-attachment:active { background: #dfe5ec; }
.remove-attachment svg { width: 15px; height: 15px; fill: none; stroke: currentColor; stroke-width: 1.7; stroke-linecap: round; }
@media (max-width: 620px) { .attachment-chip { min-width: 0; max-width: none; flex: 1 1 100%; } }
</style>
