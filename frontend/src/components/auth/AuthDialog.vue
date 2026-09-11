<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Close } from '@element-plus/icons-vue'
import LoginForm from './LoginForm.vue'
import RegisterForm from './RegisterForm.vue'

type AuthMode = 'login' | 'register'
const props = defineProps<{ modelValue: boolean; initialMode: AuthMode }>()
const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  success: []
  'mode-change': [mode: AuthMode]
  close: []
}>()
const activeMode = ref<AuthMode>(props.initialMode)
const subtitle = computed(() => activeMode.value === 'login'
  ? '登录后继续您的教学设计与研究项目'
  : '创建账号，开启智能教学设计')

watch(() => props.initialMode, (mode) => { activeMode.value = mode })
watch(() => props.modelValue, (visible) => {
  if (visible) activeMode.value = props.initialMode
})

function switchMode(mode: AuthMode) {
  if (activeMode.value === mode) return
  activeMode.value = mode
  emit('mode-change', mode)
}

function setVisible(value: boolean) {
  emit('update:modelValue', value)
  if (!value) emit('close')
}
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    class="auth-dialog"
    width="440px"
    align-center
    destroy-on-close
    modal-class="auth-overlay"
    :show-close="false"
    :close-on-click-modal="true"
    @update:model-value="setVisible"
  >
    <button class="dialog-close" type="button" aria-label="关闭账户窗口" @click="setVisible(false)">
      <el-icon><Close /></el-icon>
    </button>

    <header class="auth-header">
      <h2>欢迎使用智素领航</h2>
      <p>{{ subtitle }}</p>
    </header>

    <div class="auth-tabs" role="tablist" aria-label="账户操作">
      <button type="button" role="tab" :aria-selected="activeMode === 'login'" :class="{ active: activeMode === 'login' }" @click="switchMode('login')">登录</button>
      <button type="button" role="tab" :aria-selected="activeMode === 'register'" :class="{ active: activeMode === 'register' }" @click="switchMode('register')">注册</button>
    </div>

    <LoginForm v-if="activeMode === 'login'" @success="emit('success')" />
    <RegisterForm v-else @submitted="switchMode('login')" />

    <p class="auth-footer">
      <span>{{ activeMode === 'login' ? '还没有账号？' : '已有账号？' }}</span>
      <button class="auth-text-link" type="button" @click="switchMode(activeMode === 'login' ? 'register' : 'login')">
        {{ activeMode === 'login' ? '创建账号' : '登录' }}
      </button>
    </p>
    <p v-if="activeMode === 'login'" class="approval-note">新注册账号需经管理员审核后方可登录</p>
  </el-dialog>
</template>

<style scoped>
.dialog-close {
  position: absolute;
  z-index: 2;
  top: 18px;
  right: 18px;
  display: grid;
  width: 32px;
  height: 32px;
  padding: 0;
  place-items: center;
  border: 0;
  border-radius: 50%;
  color: #7f8fa4;
  background: #f3f7fc;
  cursor: pointer;
  font-size: 17px;
}
.dialog-close:hover { color: #1677ff; background: #eaf3ff; }
.auth-header { padding-right: 34px; }
.auth-header h2 { margin: 0 0 9px; color: #1f2937; font-size: 27px; font-weight: 700; }
.auth-header p { margin: 0; color: #94a3b8; font-size: 14px; }
.auth-tabs { display: grid; grid-template-columns: 1fr 1fr; margin: 24px 0 25px; border-bottom: 1px solid #e6eef8; }
.auth-tabs button {
  position: relative;
  height: 42px;
  padding: 0;
  border: 0;
  outline: 0;
  color: #7f8fa4;
  background: transparent;
  cursor: pointer;
  font: inherit;
  font-size: 15px;
}
.auth-tabs button.active { color: #1677ff; font-weight: 600; }
.auth-tabs button.active::after { position: absolute; right: 28%; bottom: -1px; left: 28%; height: 2px; border-radius: 2px; background: #1677ff; content: ''; }
.auth-footer { display: flex; justify-content: center; gap: 5px; margin: 20px 0 0; color: #8795a5; font-size: 14px; }
.auth-text-link { padding: 0; border: 0; color: #1677ff; background: transparent; cursor: pointer; font: inherit; font-weight: 600; }
.approval-note { margin: 11px 0 0; color: #94a3b8; font-size: 12px; text-align: center; }

:global(.auth-dialog) { max-width: calc(100vw - 32px); overflow: hidden; border-radius: 18px; background: #fff; box-shadow: 0 18px 48px rgb(31 82 150 / 15%); }
:global(.auth-dialog .el-dialog__header) { display: none; }
:global(.auth-dialog .el-dialog__body) { padding: 32px 36px 34px; }
:global(.auth-overlay) { background-color: rgb(31 56 86 / 16%); backdrop-filter: blur(2px); }
@media (max-width: 520px) {
  :global(.auth-dialog .el-dialog__body) { max-height: calc(100vh - 32px); overflow-y: auto; padding: 29px 24px 30px; }
}
</style>
