<script setup lang="ts">
import { reactive, ref } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { login } from '@/api/auth'

const emit = defineEmits<{ success: [] }>()

const formRef = ref<FormInstance>()
const loading = ref(false)
const form = reactive({ username: '', password: '' })

const rules: FormRules<typeof form> = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

async function submit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid || loading.value) return

  loading.value = true
  try {
    const { data } = await login(form.username.trim(), form.password)
    sessionStorage.setItem('access_token', data.data.access_token)
    sessionStorage.setItem('current_user', JSON.stringify(data.data.user))
    ElMessage.success(`欢迎回来，${data.data.user.display_name || data.data.user.username}`)
    emit('success')
  } catch (error: any) {
    console.error('登录请求失败：', error)
    const status = error.response?.status
    const message = !error.response
      ? '网络连接失败，请稍后重试'
      : status >= 500
        ? '服务暂时不可用，请稍后重试'
        : '用户名或密码错误'
    ElMessage.error(message)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @submit.prevent="submit">
    <el-form-item label="用户名" prop="username">
      <el-input v-model="form.username" size="large" autocomplete="username" placeholder="请输入用户名" />
    </el-form-item>
    <el-form-item label="密码" prop="password">
      <el-input v-model="form.password" size="large" type="password" show-password autocomplete="current-password" placeholder="请输入密码" @keyup.enter="submit" />
    </el-form-item>
    <el-button class="submit-button" type="primary" size="large" native-type="submit" :loading="loading" :disabled="loading">
      {{ loading ? '登录中...' : '登录' }}
    </el-button>
  </el-form>
</template>

<style scoped>
:deep(.el-form-item) { margin-bottom: 23px; }
:deep(.el-form-item__label) { height: auto; padding-bottom: 8px; color: #415366; font-size: 14px; font-weight: 600; line-height: 1.35; }
:deep(.el-input__wrapper) { min-height: 46px; padding: 1px 13px; border: 1px solid #dce8f7; border-radius: 9px; box-shadow: none; transition: border-color .18s ease, box-shadow .18s ease; }
:deep(.el-input__wrapper:hover) { border-color: #b9d5f7; box-shadow: none; }
:deep(.el-input__wrapper.is-focus) { border-color: #1677ff; box-shadow: 0 0 0 3px rgb(22 119 255 / 8%); }
:deep(.el-input__inner) { color: #1f2937; font-size: 15px; }
:deep(.el-input__inner::placeholder) { color: #b1bdcb; }
.submit-button { width: 100%; height: 47px; margin-top: 5px; border: 0; border-radius: 9px; background: linear-gradient(135deg, #2684ff, #1677ff); box-shadow: 0 8px 16px rgb(22 119 255 / 18%); font-size: 15px; font-weight: 600; transition: transform .18s ease, box-shadow .18s ease, background .18s ease; }
.submit-button:hover { background: linear-gradient(135deg, #1677ff, #126ae4); box-shadow: 0 10px 19px rgb(22 119 255 / 22%); transform: translateY(-1px); }
.submit-button:active { transform: translateY(0); }
:deep(.submit-button.is-disabled) { box-shadow: none; }
</style>
