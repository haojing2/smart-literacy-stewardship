<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AuthDialog from '@/components/auth/AuthDialog.vue'

const route = useRoute()
const router = useRouter()
const authVisible = ref(route.name === 'login')
const authMode = ref<'login' | 'register'>(route.query.mode === 'register' ? 'register' : 'login')

const workflowItems = ['研究证据', '课程设计', '教学资源', '教学模式', '课堂实施']

async function openLogin(mode?: 'register') {
  await router.push({ name: 'login', query: mode ? { mode } : {} })
}

watch(() => route.fullPath, () => {
  authVisible.value = route.name === 'login'
  authMode.value = route.query.mode === 'register' ? 'register' : 'login'
}, { immediate: true })

function closeAuth() {
  authVisible.value = false
  if (route.name === 'login') router.replace({ name: 'index' })
}

function changeMode(mode: 'login' | 'register') {
  authMode.value = mode
  router.replace({ name: 'login', query: mode === 'register' ? { mode: 'register' } : {} })
}

async function enterWorkspace() {
  authVisible.value = false
  const user = JSON.parse(sessionStorage.getItem('current_user') ?? '{}')
  await router.replace({ name: user.role === 'ADMIN' ? 'admin-dashboard' : 'home' })
}
</script>

<template>
  <main class="home-page">
    <header class="brand">
      <img class="brand-mark" src="@/assets/images/icon2.png" alt="智素领航" />
      <span class="brand-name">智素领航</span>
    </header>

    <section class="hero-content" aria-labelledby="hero-title">
      <p class="eyebrow">SMART LITERACY STEWARDSHIP</p>
      <h1 id="hero-title">面向学生 AI 素养发展的<br />信息技术学科智能教学平台</h1>
      <span class="title-line"></span>
      <p class="hero-positioning">研究证据  智能设计  课堂实践</p>
      <p class="hero-description">让研究证据进入课程，让课程进入课堂。</p>
      <div class="hero-actions">
        <button class="primary-action" type="button" @click="openLogin()">开始使用</button>
        <button class="login-action" type="button" @click="openLogin('register')">未注册账号？<strong>立即注册</strong></button>
      </div>
    </section>

    <section class="workflow" aria-label="平台功能流程">
      <div class="workflow-line"></div>
      <button v-for="(item, index) in workflowItems" :key="item" class="workflow-item" type="button" :aria-label="item">
        <span class="workflow-icon">{{ index + 1 }}</span>
        <span>{{ item }}</span>
      </button>
    </section>

    <AuthDialog
      v-model="authVisible"
      :initial-mode="authMode"
      @mode-change="changeMode"
      @close="closeAuth"
      @success="enterWorkspace"
    />
  </main>
</template>

<style scoped>
.home-page { position: relative; width: 100vw; height: 100vh; min-height: 650px; overflow: hidden; background-color: #f5faff; background-image: url('@/assets/images/web_bg.png'); background-repeat: no-repeat; background-position: center right; background-size: cover; }
.brand { position: absolute; z-index: 1; top: 4%; left: 3%; display: flex; align-items: center; gap: 11px; }.brand-mark { display: block; width: 37px; height: 37px; object-fit: contain; object-position: center; }.brand-name { color: #1677ff; font-size: 26px; font-weight: 700; letter-spacing: .08em; }
.hero-content { position: absolute; z-index: 1; top: 48%; left: 7%; width: 43%; max-width: 620px; transform: translateY(-50%); }.eyebrow { margin: 0 0 15px; color: #74aaff; font-size: 12px; font-weight: 700; letter-spacing: .14em; }h1 { margin: 0; color: #1f2937; font-size: clamp(30px, 2.5vw, 44px); font-weight: 700; letter-spacing: .02em; line-height: 1.4; }.title-line { display: block; width: 44px; height: 3px; margin: 20px 0 24px; border-radius: 3px; background: #1677ff; }.hero-positioning { margin: 0; color: #4b5563; font-size: 20px; font-weight: 600; }.hero-description { margin: 12px 0 0; color: #6b7280; font-size: 15px; }.hero-actions { display: grid; width: 180px; gap: 13px; margin-top: 34px; }.hero-actions button { cursor: pointer; font-family: inherit; transition: transform .2s ease, background .2s ease, box-shadow .2s ease; }.primary-action { width: 180px; height: 48px; border: 0; border-radius: 8px; color: #fff; background: linear-gradient(135deg, #2684ff, #1677ff); box-shadow: 0 8px 20px rgb(22 119 255 / 18%); font-size: 16px; font-weight: 600; }.primary-action:hover { background: linear-gradient(135deg, #1677ff, #126ae4); transform: translateY(-1px); }.login-action { width: 180px; height: 42px; border: 1px solid rgb(22 119 255 / 35%); border-radius: 8px; color: #4b5563; background: rgb(255 255 255 / 85%); font-size: 14px; }.login-action:hover { border-color: #1677ff; box-shadow: 0 5px 14px rgb(22 119 255 / 9%); transform: translateY(-1px); }.login-action strong { margin-left: 3px; color: #1677ff; }
.workflow { position: absolute; right: 4%; bottom: 8%; left: 40%; display: flex; align-items: flex-start; justify-content: space-between; }.workflow-line { position: absolute; top: 21px; right: 7%; left: 7%; height: 3px; background: rgb(22 119 255 / 20%); }.workflow-item { position: relative; z-index: 1; display: grid; min-width: 60px; gap: 10px; padding: 0; border: 0; color: #374151; background: transparent; cursor: pointer; font-family: "Microsoft YaHei",inherit; font-size: 16px; font-weight: 700; place-items: center; transition: color .2s ease; }.workflow-icon { display: flex; width: 42px; height: 42px; align-items: center; justify-content: center; border: 1px solid rgb(22 119 255 / 22%); border-radius: 50%; color: #1677ff; background: rgb(255 255 255 / 72%); box-shadow: 0 4px 14px rgb(22 119 255 / 8%); font-size: 19px; font-weight: 700; transition: all .2s ease; }.workflow-item:hover { color: #1677ff; }.workflow-item:hover .workflow-icon { border-color: rgb(22 119 255 / 55%); box-shadow: 0 6px 18px rgb(22 119 255 / 14%); transform: translateY(-2px); }
@media (max-width: 900px) { .hero-content { left: 5%; width: 47%; }.workflow { right: 2%; left: 43%; }.workflow-item { min-width: 52px; font-size: 12px; }.workflow-icon { width: 38px; height: 38px; }.workflow-line { top: 19px; } }
@media (max-width: 767px) { .home-page { min-height: 620px; background-position: 62% center; }.home-page::before { position: absolute; inset: 0; background: linear-gradient(90deg, rgb(255 255 255 / 92%) 0%, rgb(255 255 255 / 68%) 72%, rgb(255 255 255 / 28%) 100%); content: ''; }.brand { top: 28px; left: 24px; }.brand-mark { width: 33px; height: 33px; font-size: 17px; }.brand-name { font-size: 26px; }.hero-content { top: 47%; left: 7%; width: 83%; transform: translateY(-50%); }.eyebrow { display: none; }h1 { font-size: clamp(27px, 7vw, 34px); }.hero-positioning { font-size: 14px; }.hero-description { font-size: 14px; }.workflow { display: none; } }
</style>
