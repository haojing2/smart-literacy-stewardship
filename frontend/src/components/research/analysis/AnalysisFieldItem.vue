<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  label: string
  value: string
  source?: 'MOCK' | 'AI_CHAT' | 'TEACHER'
}>()
defineEmits<{ edit: [] }>()

const status = computed(() => {
  if (!props.value.trim()) return { label: '未识别', className: 'empty', icon: '○' }
  if (props.source === 'TEACHER') return { label: '已识别', className: 'identified', icon: '✓' }
  return { label: '待确认', className: 'pending', icon: '!' }
})
</script>

<template>
  <section class="field-item">
    <div class="field-heading">
      <strong>{{ label }}</strong>
      <span :class="status.className">{{ status.icon }} {{ status.label }}</span>
    </div>
    <div class="field-value">
      <p :class="{ placeholder: !value }">{{ value || '尚未识别' }}</p>
      <button type="button" @click="$emit('edit')">编辑</button>
    </div>
  </section>
</template>

<style scoped>
.field-item { padding: 13px 0; border-bottom: 1px solid #f0f2f5; }.field-heading, .field-value { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; }.field-heading strong { color: #344054; font-size: 12px; font-weight: 650; }.field-heading span { font-size: 10px; white-space: nowrap; }.identified { color: #438566; }.pending { color: #b7791f; }.empty { color: #98a2b3; }.field-value { margin-top: 7px; }.field-value p { min-width: 0; margin: 0; color: #475467; font-size: 12px; line-height: 1.6; white-space: pre-wrap; }.field-value p.placeholder { color: #98a2b3; }.field-value button { flex: none; padding: 0; border: 0; color: #1677ff; background: transparent; cursor: pointer; font-size: 11px; }
</style>
