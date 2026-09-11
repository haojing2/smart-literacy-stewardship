<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { login, register } from '@/api/auth'

type AccountMode = 'login' | 'register'
const route = useRoute()
const router = useRouter()
const mode = ref<AccountMode>(route.query.mode === 'register' ? 'register' : 'login')
const loginFormRef = ref<FormInstance>()
const registerFormRef = ref<FormInstance>()
const loading = ref(false)
const loginForm = reactive({ username: '', password: '' })
const registerForm = reactive({ username: '', displayName: '', password: '', confirmPassword: '' })
const subtitle = computed(() => mode.value === 'register' ? '创建账号，开启智能教学设计' : '登录或创建账号，开始智能教学设计')
const loginRules: FormRules<typeof loginForm> = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}
const registerRules: FormRules<typeof registerForm> = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }, { min: 3, max: 30, message: '用户名长度应为 3–30 个字符', trigger: 'blur' }],
  displayName: [{ required: true, message: '请输入姓名或昵称', trigger: 'blur' }, { max: 50, message: '显示名称不能超过 50 个字符', trigger: 'blur' }],
  password: [{ required: true, message: '请设置登录密码', trigger: 'blur' }, { min: 6, message: '密码至少需要 6 位', trigger: 'blur' }],
  confirmPassword: [{ required: true, message: '请再次输入密码', trigger: 'blur' }, { validator: (_rule, value, callback) => callback(value === registerForm.password ? undefined : new Error('两次输入的密码不一致')), trigger: 'blur' }],
}
watch(() => route.query.mode, (value) => { mode.value = value === 'register' ? 'register' : 'login' })
function switchMode(next: AccountMode) {
  if (mode.value !== next) router.replace({ name: 'login', query: next === 'register' ? { mode: 'register' } : {} })
}
function saveSession(data: { access_token: string; user: { id: number; username: string; display_name: string | null; role: string } }) {
  sessionStorage.setItem('access_token', data.access_token)
  sessionStorage.setItem('current_user', JSON.stringify(data.user))
}
function requestMessage(error: any, fallback: string) {
  return error.response?.data?.message ?? (error.response ? fallback : '网络连接失败，请稍后重试')
}
async function submitLogin() {
  const valid = await loginFormRef.value?.validate().catch(() => false)
  if (!valid || loading.value) return
  loading.value = true
  try {
    const response = await login(loginForm.username.trim(), loginForm.password)
    saveSession(response.data.data)
    ElMessage.success(`欢迎回来，${response.data.data.user.display_name || response.data.data.user.username}`)
    await router.replace({ name: 'home' })
  } catch (error: any) {
    ElMessage.error(requestMessage(error, '用户名或密码错误'))
  } finally { loading.value = false }
}
async function submitRegister() {
  registerForm.username = registerForm.username.trim()
  registerForm.displayName = registerForm.displayName.trim()
  const valid = await registerFormRef.value?.validate().catch(() => false)
  if (!valid || loading.value) return
  loading.value = true
  try {
    await register(registerForm.username, registerForm.displayName, registerForm.password)
    const response = await login(registerForm.username, registerForm.password)
    saveSession(response.data.data)
    ElMessage.success('账号创建成功，欢迎使用智素领航')
    await router.replace({ name: 'home' })
  } catch (error: any) {
    ElMessage.error(requestMessage(error, '账号创建失败，请稍后重试'))
  } finally { loading.value = false }
}
</script>

<template>
  <main class="login-page">
    <section class="brand-panel" aria-label="智素领航介绍">
      <div class="brand-content">
        <div class="brand-header"><span class="brand-mark">智</span><span class="brand-name">智素领航</span></div>
        <p class="eyebrow">SMART LITERACY STEWARDSHIP</p>
        <h1>面向学生 AI 素养发展的<br />信息技术学科智能教学平台</h1>
        <span class="title-accent"></span>
        <p class="brand-positioning">研究证据 × 智能设计 × 课堂实践</p>
        <p class="brand-copy">让研究证据进入课程，让课程进入课堂。</p>
      </div>
      <div class="education-visual" aria-hidden="true"><span class="visual-halo halo-one"></span><span class="visual-halo halo-two"></span><span class="visual-orbit"></span><span class="visual-node node-one">AI</span><span class="visual-node node-two">研</span><span class="visual-node node-three">教</span><div class="visual-card card-course"><b>课程设计</b><span>智能生成</span></div><div class="visual-card card-evidence"><b>研究证据</b><span>可信依据</span></div></div>
    </section>
    <section class="form-panel">
      <div class="login-card">
        <div class="card-heading"><h2>欢迎使用智素领航</h2><p>{{ subtitle }}</p></div>
        <div class="mode-tabs" role="tablist" aria-label="账户操作"><button type="button" role="tab" :aria-selected="mode === 'login'" :class="{ active: mode === 'login' }" @click="switchMode('login')">登录</button><button type="button" role="tab" :aria-selected="mode === 'register'" :class="{ active: mode === 'register' }" @click="switchMode('register')">注册</button></div>
        <el-form v-if="mode === 'login'" ref="loginFormRef" :model="loginForm" :rules="loginRules" label-position="top" @submit.prevent="submitLogin">
          <el-form-item label="用户名 *" prop="username"><el-input v-model="loginForm.username" autocomplete="username" placeholder="请输入用户名" /></el-form-item>
          <el-form-item label="密码 *" prop="password"><el-input v-model="loginForm.password" type="password" show-password autocomplete="current-password" placeholder="请输入密码" @keyup.enter="submitLogin" /></el-form-item>
          <el-button class="submit-button" type="primary" native-type="submit" :loading="loading">登录</el-button>
          <p class="account-switch">还没有账号？<button type="button" @click="switchMode('register')">创建账号</button></p>
        </el-form>
        <el-form v-else ref="registerFormRef" :model="registerForm" :rules="registerRules" label-position="top" @submit.prevent="submitRegister">
          <el-form-item label="用户名 *" prop="username"><el-input v-model="registerForm.username" autocomplete="username" placeholder="请输入用户名" /></el-form-item>
          <el-form-item label="显示名称 *" prop="displayName"><el-input v-model="registerForm.displayName" autocomplete="name" placeholder="请输入姓名或昵称" /></el-form-item>
          <el-form-item label="密码 *" prop="password"><el-input v-model="registerForm.password" type="password" show-password autocomplete="new-password" placeholder="设置登录密码" /></el-form-item>
          <el-form-item label="确认密码 *" prop="confirmPassword"><el-input v-model="registerForm.confirmPassword" type="password" show-password autocomplete="new-password" placeholder="再次输入密码" @keyup.enter="submitRegister" /></el-form-item>
          <el-button class="submit-button" type="primary" native-type="submit" :loading="loading">创建账号</el-button>
          <p class="account-switch">已有账号？<button type="button" @click="switchMode('login')">登录</button></p>
        </el-form>
      </div>
    </section>
  </main>
</template>

<style scoped>
.login-page { display: grid; grid-template-columns: minmax(520px, 55fr) minmax(420px, 45fr); min-height: 100vh; overflow: hidden; background: #fff; }
.brand-panel { position: relative; display: flex; align-items: center; overflow: hidden; padding: clamp(56px, 8vw, 128px); background: radial-gradient(circle at 21% 10%, rgb(38 132 255 / 12%), transparent 25%), linear-gradient(135deg, #f7fbff 0%, #edf5ff 100%); }.brand-panel::before, .brand-panel::after { position: absolute; border: 1px solid rgb(38 132 255 / 11%); border-radius: 50%; content: ''; }.brand-panel::before { width: 720px; height: 720px; right: -400px; top: -330px; }.brand-panel::after { width: 560px; height: 560px; left: -430px; bottom: -390px; }
.brand-content { position: relative; z-index: 2; max-width: 610px; }.brand-header { display: flex; align-items: center; gap: 12px; margin-bottom: 50px; }.brand-mark { display: grid; width: 42px; height: 42px; place-items: center; border-radius: 12px; color: #fff; background: #1677ff; box-shadow: 0 8px 18px rgb(22 119 255 / 18%); font-size: 22px; font-weight: 700; }.brand-name { color: #1f4f86; font-size: 20px; font-weight: 700; letter-spacing: .08em; }.eyebrow { margin: 0 0 15px; color: #4d8fe9; font-size: 12px; font-weight: 700; letter-spacing: .13em; } h1 { margin: 0; color: #1f2937; font-size: clamp(32px, 3.1vw, 42px); font-weight: 700; letter-spacing: .015em; line-height: 1.42; }.title-accent { display: block; width: 48px; height: 4px; margin: 25px 0; border-radius: 5px; background: #2684ff; }.brand-positioning { margin: 0 0 13px; color: #315675; font-size: 16px; font-weight: 650; letter-spacing: .05em; }.brand-copy { margin: 0; color: #94a3b8; font-size: 15px; line-height: 1.8; }
.education-visual { position: absolute; z-index: 1; right: -52px; bottom: -30px; width: min(56vw, 660px); height: min(40vw, 500px); opacity: .8; pointer-events: none; }.visual-halo { position: absolute; border-radius: 50%; background: rgb(38 132 255 / 8%); }.halo-one { width: 330px; height: 330px; right: 70px; bottom: 30px; }.halo-two { width: 220px; height: 220px; right: 128px; bottom: 86px; background: rgb(22 119 255 / 10%); }.visual-orbit { position: absolute; width: 430px; height: 190px; right: 2px; bottom: 66px; border: 1px solid rgb(38 132 255 / 25%); border-radius: 50%; transform: rotate(-25deg); }.visual-node { position: absolute; display: grid; width: 44px; height: 44px; place-items: center; border: 1px solid rgb(38 132 255 / 18%); border-radius: 50%; color: #2684ff; background: rgb(255 255 255 / 78%); box-shadow: 0 8px 22px rgb(40 104 186 / 8%); font-size: 13px; font-weight: 700; }.node-one { right: 133px; bottom: 236px; }.node-two { right: 373px; bottom: 121px; }.node-three { right: 32px; bottom: 71px; }.visual-card { position: absolute; display: grid; gap: 5px; min-width: 108px; padding: 13px 16px; border: 1px solid rgb(255 255 255 / 86%); border-radius: 12px; color: #315675; background: rgb(255 255 255 / 75%); box-shadow: 0 10px 26px rgb(31 82 150 / 8%); }.visual-card b { font-size: 13px; }.visual-card span { color: #86a4c1; font-size: 11px; }.card-course { right: 186px; bottom: 78px; }.card-evidence { right: 50px; bottom: 181px; }
.form-panel { display: grid; padding: 40px; place-items: center; background: #fff; }.login-card { width: min(100%, 400px); padding: 40px 42px 34px; border: 1px solid #e6eef8; border-radius: 18px; background: #fff; box-shadow: 0 10px 30px rgb(31 82 150 / 7%); }.card-heading { margin-bottom: 21px; }.card-heading h2 { margin: 0 0 10px; color: #1f2937; font-size: 28px; font-weight: 700; letter-spacing: .01em; }.card-heading p { margin: 0; color: #94a3b8; font-size: 14px; }.mode-tabs { display: flex; gap: 30px; margin-bottom: 25px; border-bottom: 1px solid #e6eef8; }.mode-tabs button { position: relative; padding: 0 1px 11px; border: 0; color: #8795a5; background: transparent; cursor: pointer; font: inherit; font-size: 15px; }.mode-tabs button.active { color: #1677ff; font-weight: 600; }.mode-tabs button.active::after { position: absolute; right: 0; bottom: -1px; left: 0; height: 2px; border-radius: 2px; background: #1677ff; content: ''; }
:deep(.el-form-item) { margin-bottom: 19px; }:deep(.el-form-item__label) { height: auto; padding-bottom: 8px; color: #415366; font-size: 14px; font-weight: 600; line-height: 1.35; }:deep(.el-form-item__error) { padding-top: 5px; }:deep(.el-input__wrapper) { min-height: 46px; padding: 1px 13px; border: 1px solid #dce8f7; border-radius: 9px; box-shadow: none; transition: border-color .18s ease, box-shadow .18s ease; }:deep(.el-input__wrapper:hover) { border-color: #b9d5f7; }:deep(.el-input__wrapper.is-focus) { border-color: #1677ff; box-shadow: 0 0 0 3px rgb(22 119 255 / 8%); }:deep(.el-input__inner) { color: #1f2937; font-size: 15px; }:deep(.el-input__inner::placeholder) { color: #b1bdcb; }.submit-button { width: 100%; height: 46px; margin-top: 4px; border: 0; border-radius: 9px; background: #1677ff; box-shadow: 0 6px 14px rgb(22 119 255 / 16%); font-size: 15px; font-weight: 600; }.submit-button:hover { background: #126ae4; }.account-switch { margin: 20px 0 0; color: #8795a5; font-size: 14px; text-align: center; }.account-switch button { padding: 0; border: 0; color: #1677ff; background: transparent; cursor: pointer; font: inherit; font-weight: 600; }
@media (max-width: 900px) { .login-page { grid-template-columns: minmax(380px, 1fr) minmax(370px, 1fr); }.brand-panel { padding: 52px; }.brand-header { margin-bottom: 34px; }.education-visual { right: -125px; bottom: -63px; width: 510px; height: 350px; }.login-card { padding: 36px 32px 30px; } }
@media (max-width: 767px) { .login-page { display: block; overflow: auto; }.brand-panel { min-height: auto; padding: 32px 24px 30px; }.brand-header { margin-bottom: 26px; }.brand-mark { width: 36px; height: 36px; border-radius: 10px; font-size: 19px; }.brand-name { font-size: 18px; }.eyebrow, .education-visual { display: none; } h1 { font-size: clamp(24px, 7vw, 30px); }.title-accent { width: 36px; height: 3px; margin: 17px 0; }.brand-positioning { margin-bottom: 7px; font-size: 13px; }.brand-copy { font-size: 13px; }.form-panel { padding: 26px 20px 44px; }.login-card { width: min(100%, 400px); padding: 30px 24px; }.card-heading { margin-bottom: 20px; }.card-heading h2 { font-size: 25px; } }
</style>
