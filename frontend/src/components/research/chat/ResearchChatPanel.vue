<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import type { ResearchAnalysis, ResearchChatMessage, ResearchResource } from '@/types/research'
import SelectedResourcesBar from './SelectedResourcesBar.vue'
import UserMessage from './UserMessage.vue'
import AssistantMessage from './AssistantMessage.vue'
import SystemMessage from './SystemMessage.vue'
import FileAttachmentCard from './FileAttachmentCard.vue'
import ChatComposer from './ChatComposer.vue'
import ScrollToBottomButton from './ScrollToBottomButton.vue'

const props = withDefaults(defineProps<{
  resources: ResearchResource[]
  selectedResources: ResearchResource[]
  activeScopeLabel?: string
  messages: ResearchChatMessage[]
  sending: boolean
  processing: boolean
  evidenceReady: boolean
  hasActiveSession: boolean
  analysis: ResearchAnalysis | null
  initializationFailed?: boolean
  sendMessage: (content: string) => Promise<boolean>
}>(), { activeScopeLabel: '项目知识库' })
const emit = defineEmits<{
  upload: [file: File]
  retryMessage: [message: ResearchChatMessage]
  retryResource: [resourceId: number]
  removeResource: [resourceId: number]
  retryInitialize: []
}>()

const composer = ref('')
const messageList = ref<HTMLElement>()
const fileInput = ref<HTMLInputElement>()
const chatComposer = ref<InstanceType<typeof ChatComposer>>()
const showScrollButton = ref(false)
const newMessageCount = ref(0)
const typingMessageId = ref<ResearchChatMessage['messageId'] | null>(null)
const displayedContent = ref('')
const followTyping = ref(true)
let typingToken = 0
let typingTimer: number | undefined
let resolveTypingDelay: (() => void) | undefined
let scrollFrame: number | undefined
let lastTypingScrollAt = 0
const empty = computed(() => props.resources.length === 0 && props.messages.length === 0)
const explorationScaffolds = computed(() => {
  const analysis = props.analysis
  return [
    { key: 'researchTopics', label: '研究问题', question: '围绕当前课程主题，已有研究主要关注哪些教学或学习问题？', complete: Boolean(analysis?.researchTopics.length) },
    { key: 'participants', label: '研究对象', question: '针对当前研究的目标对象是哪些学生群体？', complete: Boolean(analysis?.participants.length) },
    { key: 'aiLiteracyDimensions', label: '能力重点', question: '已有研究主要关注学生哪些能力或素养的发展？', complete: Boolean(analysis?.aiLiteracyDimensions.length) },
    { key: 'teachingStrategies', label: '教学策略', question: '哪些教学策略得到已有研究支持，并适合当前课程？', complete: Boolean(analysis?.teachingStrategies.length) },
    { key: 'intervention', label: '干预周期/实施时长', question: '研究中的干预或实施持续了多长时间？', complete: Boolean(analysis?.intervention) },
    { key: 'assessmentTools', label: '评价方式', question: '已有研究通常如何评价学生的学习效果？', complete: Boolean(analysis?.assessmentTools.length) },
    { key: 'mainFindings', label: '主要发现', question: '相关研究的主要研究发现是什么？', complete: Boolean(analysis?.mainFindings.length) },
    { key: 'limitations', label: '研究局限', question: '这些研究报告了哪些研究局限？', complete: Boolean(analysis?.limitations.length) },
  ].sort((left, right) => Number(left.complete) - Number(right.complete))
})

function startQuestion() {
  chatComposer.value?.focus()
}

async function send() {
  const content = composer.value.trim()
  if (!content || !props.hasActiveSession || props.sending) return
  finishTyping()
  if (await props.sendMessage(content)) {
    composer.value = ''
    const message = [...props.messages]
      .reverse()
      .find((item) => item.role === 'ASSISTANT')
    if (message) void typeMessage(message)
  }
}

function chooseFile(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (file) emit('upload', file)
  ;(event.target as HTMLInputElement).value = ''
}

function scrollToBottom(behavior: ScrollBehavior = 'smooth') {
  const element = messageList.value
  if (element) {
    if (typeof element.scrollTo === 'function') {
      element.scrollTo({ top: element.scrollHeight, behavior })
    } else {
      element.scrollTop = element.scrollHeight
    }
  }
  showScrollButton.value = false
  newMessageCount.value = 0
}

function isNearBottom() {
  const element = messageList.value
  return Boolean(element && element.scrollHeight - element.scrollTop - element.clientHeight <= 120)
}

function queueTypingScroll() {
  if (!followTyping.value || !messageList.value) return
  const now = performance.now()
  if (scrollFrame !== undefined || now - lastTypingScrollAt < 80) return
  lastTypingScrollAt = now
  scrollFrame = window.requestAnimationFrame(() => {
    scrollFrame = undefined
    if (followTyping.value && messageList.value) {
      messageList.value.scrollTop = messageList.value.scrollHeight
    }
  })
}

function typewriterSettings(length: number) {
  if (length < 500) return { chunkSize: 2, delay: 20 }
  if (length < 1500) return { chunkSize: 4, delay: 15 }
  return { chunkSize: 8, delay: 10 }
}

function waitForTypingDelay(delay: number) {
  return new Promise<void>((resolve) => {
    resolveTypingDelay = resolve
    typingTimer = window.setTimeout(() => {
      typingTimer = undefined
      resolveTypingDelay = undefined
      resolve()
    }, delay)
  })
}

function finishTyping() {
  if (typingMessageId.value !== null) {
    const message = props.messages.find((item) => item.messageId === typingMessageId.value)
    if (message) displayedContent.value = message.content
  }
  typingToken += 1
  if (typingTimer !== undefined) window.clearTimeout(typingTimer)
  typingTimer = undefined
  resolveTypingDelay?.()
  resolveTypingDelay = undefined
  typingMessageId.value = null
  if (scrollFrame !== undefined) window.cancelAnimationFrame(scrollFrame)
  scrollFrame = undefined
}

async function typeMessage(message: ResearchChatMessage) {
  finishTyping()
  const token = ++typingToken
  const { chunkSize, delay } = typewriterSettings(message.content.length)
  followTyping.value = isNearBottom()
  typingMessageId.value = message.messageId
  displayedContent.value = ''

  for (let index = 0; index < message.content.length; index += chunkSize) {
    if (token !== typingToken) return
    displayedContent.value += message.content.slice(index, index + chunkSize)
    await nextTick()
    queueTypingScroll()
    if (index + chunkSize < message.content.length) await waitForTypingDelay(delay)
  }
  if (token === typingToken) {
    typingMessageId.value = null
    displayedContent.value = ''
    queueTypingScroll()
  }
}

function assistantContent(message: ResearchChatMessage) {
  return typingMessageId.value === message.messageId
    ? displayedContent.value
    : message.content
}

function handleScroll() {
  const element = messageList.value
  if (!element) return
  followTyping.value = isNearBottom()
  showScrollButton.value = !followTyping.value
  if (!showScrollButton.value) newMessageCount.value = 0
}

function viewSource() {
  const fileCard = messageList.value?.querySelector('.file-message')
  fileCard?.scrollIntoView({ behavior: 'smooth', block: 'center' })
}

function resourceForMessage(message: ResearchChatMessage): ResearchResource {
  return props.resources.find((item) => item.resourceId === message.resourceId) ?? {
    resourceId: Number(message.resourceId ?? 0),
    fileName: message.content,
    mimeType: '',
    fileSize: 0,
    processingStatus: 'FAILED',
    errorMessage: '研究资源状态暂不可用',
  }
}

watch(
  () => props.messages.length,
  async (_, previous) => {
    await nextTick()
    if (showScrollButton.value) newMessageCount.value += Math.max(0, props.messages.length - (previous ?? 0))
    else scrollToBottom('smooth')
  },
)

watch(
  () => props.messages,
  (messages) => {
    if (
      typingMessageId.value !== null
      && !messages.some((message) => message.messageId === typingMessageId.value)
    ) {
      finishTyping()
    }
  },
)

onBeforeUnmount(finishTyping)
</script>

<template>
  <section class="chat-panel">
    <SelectedResourcesBar :resources="selectedResources" :scope-label="activeScopeLabel" @remove="$emit('removeResource', $event)" @upload="fileInput?.click()" />
    <input ref="fileInput" hidden type="file" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" @change="chooseFile" />

    <div ref="messageList" class="message-list" @scroll="handleScroll">
      <div v-if="empty" class="chat-empty">
        <div class="empty-mark">✦</div>
        <h2>开始你的研教证据探索</h2>
        <p>你可以直接向研教智联助手提问。助手将结合研究知识库和当前教学项目，为你提供研究支持。</p>
        <el-button type="primary" @click="startQuestion">开始提问</el-button>
        <el-button text :loading="processing" @click="fileInput?.click()">也可以上传论文进行专项研究分析</el-button>
      </div>

      <template v-for="message in messages" :key="message.messageId">
        <UserMessage v-if="message.role === 'USER' && message.messageType === 'TEXT'" :message="message" @retry="$emit('retryMessage', $event)" />
        <AssistantMessage v-else-if="message.role === 'ASSISTANT'" :content="assistantContent(message)" :typing="typingMessageId === message.messageId" :evidence-ready="evidenceReady" @view-source="viewSource" @reanalyze="composer = '请根据当前研究资源重新分析核心研究信息'" />
        <div v-else-if="message.messageType === 'FILE'" class="file-message">
          <FileAttachmentCard :resource="resourceForMessage(message)" @retry="$emit('retryResource', $event)" />
        </div>
        <SystemMessage v-else :content="message.content" :failed="message.content.includes('失败')" />
      </template>
      <div v-if="sending" class="assistant-typing"><span>✦</span><i></i><i></i><i></i></div>
    </div>

    <div class="composer-area">
      <ScrollToBottomButton :visible="showScrollButton" :new-count="newMessageCount" @click="scrollToBottom()" />
      <div class="composer-content">
        <div class="exploration-scaffold" aria-label="研究探索脚手架">
          <span class="scaffold-title">研究探索</span>
          <button v-for="item in explorationScaffolds" :key="item.key" type="button" class="scaffold-chip" :class="{ complete: item.complete }" @click="composer = item.question"><span v-if="item.complete">✓</span>{{ item.label }}</button>
        </div>
        <ChatComposer
          ref="chatComposer"
          v-model="composer"
          :sending="sending"
          :has-active-session="hasActiveSession"
          :initialization-failed="initializationFailed"
          @send="send"
          @select-file="$emit('upload', $event)"
          @retry-initialize="$emit('retryInitialize')"
        />
      </div>
    </div>
  </section>
</template>

<style scoped>
.chat-panel { position: relative; display: flex; min-width: 0; min-height: 590px; flex-direction: column; overflow: hidden; border: 1px solid #eaecf0; border-radius: 12px; background: #fff; box-shadow: 0 1px 3px rgb(16 24 40 / 4%); }.message-list { min-height: 0; flex: 1; overflow-y: auto; padding: 20px 24px 28px; scrollbar-gutter: stable; }.message-list>* { width: min(920px, 100%); margin-right: auto; margin-left: auto; }.message-list>*+* { margin-top: 22px; }.composer-area { position: relative; z-index: 3; flex: none; padding: 28px 0 18px; background: linear-gradient(to bottom, rgb(255 255 255 / 0%), #fff 30%); }.composer-content { width: calc(100% - 48px); max-width: 920px; margin: 0 auto; }.chat-empty { display: flex; min-height: 100%; align-items: center; justify-content: center; flex-direction: column; padding: 30px 18px; text-align: center; }.empty-mark { display: grid; width: 42px; height: 42px; place-items: center; border: 1px solid #dbe8f8; border-radius: 12px; color: #1677ff; background: #f5f9fe; }.chat-empty h2 { margin: 15px 0 7px; color: #1d2939; font-size: 18px; }.chat-empty p { max-width: 500px; margin: 0 0 18px; color: #667085; font-size: 13px; line-height: 1.7; }.quick-questions { display: flex; max-width: 620px; flex-wrap: wrap; justify-content: center; gap: 8px; margin-top: 24px; }.quick-questions button { padding: 7px 10px; border: 1px solid #e4e7ec; border-radius: 15px; color: #667085; background: #fff; cursor: pointer; font-size: 12px; }.quick-questions button:hover { border-color: #b8cff0; color: #4774a8; background: #f8fbff; }.assistant-typing { display: flex; align-items: center; gap: 5px; color: #1677ff; }.assistant-typing span { margin-right: 5px; }.assistant-typing i { width: 5px; height: 5px; border-radius: 50%; background: #98a2b3; animation: pulse 1.1s infinite alternate; }.assistant-typing i:nth-child(3) { animation-delay: .2s; }.assistant-typing i:nth-child(4) { animation-delay: .4s; }@keyframes pulse { to { opacity: .25; transform: translateY(-2px); } }@media (max-width: 760px) { .composer-content { width: calc(100% - 32px); } }@media (max-width: 480px) { .message-list { padding-right: 10px; padding-left: 10px; }.composer-content { width: calc(100% - 20px); } }@media (prefers-reduced-motion: reduce) { .assistant-typing i { animation: none; } }
.exploration-scaffold { display: flex; flex-wrap: wrap; align-items: center; gap: 7px; margin-bottom: 11px; }
.scaffold-title { width: 100%; color: #667085; font-size: 11px; font-weight: 600; }
.scaffold-chip { padding: 5px 10px; border: 1px solid #d9e2ec; border-radius: 999px; color: #52677f; background: #fff; cursor: pointer; font: inherit; font-size: 12px; line-height: 1.25; transition: border-color .15s ease, color .15s ease, background .15s ease; }
.scaffold-chip:hover { border-color: #93b8ed; color: #2563eb; background: #f2f7ff; }
.scaffold-chip.complete { border-color: #e5e7eb; color: #98a2b3; background: #f8fafc; }
.scaffold-chip.complete:hover { border-color: #cbd5e1; color: #64748b; background: #f1f5f9; }
</style>
