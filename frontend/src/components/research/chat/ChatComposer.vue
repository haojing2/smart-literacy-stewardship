<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import MarkdownContent from './MarkdownContent.vue'

const props = defineProps<{
  modelValue: string
  sending: boolean
  hasActiveSession: boolean
  initializationFailed?: boolean
}>()
const emit = defineEmits<{
  'update:modelValue': [value: string]
  send: []
  selectFile: [file: File]
  retryInitialize: []
}>()

const ACCEPTED_FILES = '.pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document'
const textarea = ref<HTMLTextAreaElement>()
const fileInput = ref<HTMLInputElement>()
const previewing = ref(false)

function resizeTextarea() {
  nextTick(() => {
    const element = textarea.value
    if (!element) return
    element.style.height = 'auto'
    element.style.height = `${Math.min(element.scrollHeight, 160)}px`
  })
}

function selectAttachments(event: Event) {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  if (file) emit('selectFile', file)
  target.value = ''
}

function openFilePicker() {
  fileInput.value?.click()
}

function onInput(event: Event) {
  emit('update:modelValue', (event.target as HTMLTextAreaElement).value)
  resizeTextarea()
}

function onKeydown(event: KeyboardEvent) {
  if (event.key !== 'Enter' || event.shiftKey || event.isComposing) return
  event.preventDefault()
  if (props.modelValue.trim() && props.hasActiveSession && !props.sending) emit('send')
}

function togglePreview() {
  previewing.value = !previewing.value
  if (!previewing.value) resizeTextarea()
}

function focus() {
  previewing.value = false
  nextTick(() => textarea.value?.focus())
}

defineExpose({ focus })

watch(
  () => props.modelValue,
  (value) => {
    if (!value) previewing.value = false
    resizeTextarea()
  },
)
</script>

<template>
  <div class="chat-composer">
    <button
      type="button"
      class="add-file-button"
      title="添加文件"
      aria-label="添加文件"
      @click="openFilePicker"
    >
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14M5 12h14" /></svg>
    </button>
    <input ref="fileInput" hidden type="file" :accept="ACCEPTED_FILES" @change="selectAttachments" />

    <div class="input-shell">
      <MarkdownContent
        v-if="previewing"
        class="markdown-preview"
        :content="modelValue || '*暂无可预览内容*'"
      />
      <textarea
        v-else
        ref="textarea"
        :value="modelValue"
        rows="1"
        :placeholder="hasActiveSession ? '输入问题，与研教智联助手一起探索研究证据……' : initializationFailed ? '研教对话初始化失败，请重试' : '正在准备研教对话会话……'"
        aria-label="对话输入框"
        @input="onInput"
        @keydown="onKeydown"
      />
    </div>

    <button
      type="button"
      class="send-button"
      :disabled="!modelValue.trim() || !hasActiveSession || sending"
      :title="hasActiveSession ? '发送' : '正在准备研教对话会话'"
      aria-label="发送消息"
      @click="$emit('send')"
    >
      <span v-if="sending">…</span>
      <svg v-else viewBox="0 0 24 24" aria-hidden="true"><path d="M12 19V5m-6 6 6-6 6 6" /></svg>
    </button>
  </div>

  <div class="composer-status">
    <button v-if="initializationFailed" type="button" class="retry-initialize" @click="$emit('retryInitialize')">研教对话初始化失败，请重试</button>
    <span v-else>{{ hasActiveSession ? '内容由AI生成，请注意核实' : '正在准备研教对话会话' }}</span>
    <button
      type="button"
      :class="{ active: previewing }"
      :aria-pressed="previewing"
      @click="togglePreview"
    >
      {{ previewing ? '返回编辑' : '发送前预览' }}
      <svg viewBox="0 0 16 16" aria-hidden="true"><path d="m4 6 4 4 4-4" /></svg>
    </button>
  </div>
</template>

<style scoped>
.chat-composer {
  display: flex;
  width: 100%;
  min-height: 64px;
  align-items: flex-end;
  gap: 10px;
  padding: 12px 14px;
  border: 1px solid #e5e7eb;
  border-radius: 28px;
  background: #fff;
  box-shadow: 0 6px 24px rgb(15 23 42 / 8%);
  transition: border-color .16s ease, box-shadow .16s ease;
}
.chat-composer:focus-within { border-color: #bfdbfe; box-shadow: 0 6px 24px rgb(15 23 42 / 8%), 0 0 0 3px rgb(59 130 246 / 6%); }
.add-file-button, .send-button { display: grid; width: 38px; height: 38px; flex: none; padding: 0; place-items: center; border: 0; cursor: pointer; }
.add-file-button { border-radius: 50%; color: #374151; background: transparent; }
.add-file-button:hover { background: #f3f4f6; }.add-file-button:active { background: #e5e7eb; }
.add-file-button svg { width: 21px; height: 21px; fill: none; stroke: currentColor; stroke-width: 1.6; stroke-linecap: round; }
.input-shell { min-width: 0; flex: 1; align-self: center; }
.input-shell textarea { display: block; width: 100%; height: 24px; min-height: 24px; max-height: 160px; padding: 1px 0; overflow-y: auto; border: 0; outline: 0; color: #111827; background: #fff; resize: none; font: inherit; font-size: 15px; line-height: 1.55; }
.input-shell textarea::placeholder { color: #9ca3af; }
.markdown-preview { max-height: 160px; padding: 1px 0; overflow-y: auto; color: #111827; font-size: 15px; line-height: 1.55; }
.send-button { border-radius: 50%; color: #fff; background: #2563eb; }
.send-button:hover:not(:disabled) { background: #1d4ed8; }.send-button:active:not(:disabled) { transform: translateY(1px); }
.send-button:disabled { color: #9ca3af; background: #e5e7eb; cursor: not-allowed; }
.send-button svg { width: 19px; height: 19px; fill: none; stroke: currentColor; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }
.composer-status { display: flex; min-height: 25px; align-items: center; justify-content: center; gap: 22px; color: #9ca3af; font-size: 10px; }
.composer-status button { display: inline-flex; align-items: center; gap: 3px; padding: 0; border: 0; color: #9ca3af; background: transparent; cursor: pointer; font: inherit; }
.composer-status button:hover, .composer-status button.active { color: #6b83a6; }
.composer-status svg { width: 12px; height: 12px; fill: none; stroke: currentColor; stroke-width: 1.4; stroke-linecap: round; stroke-linejoin: round; transition: transform .15s ease; }
.composer-status button.active svg { transform: rotate(180deg); }
@media (max-width: 620px) {
  .chat-composer { gap: 6px; padding-right: 10px; padding-left: 10px; }
  .composer-status { justify-content: space-between; gap: 8px; }
}
</style>
