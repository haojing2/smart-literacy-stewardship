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
    ElMessage.error(error.response?.data?.message ?? (error.response ? '用户名或密码错误' : '网络连接失败，请稍后重试'))
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @submit.prevent="submit">
    <el-form-item label="用户名" prop="username"><el-input v-model="form.username" autocomplete="username" placeholder="请输入用户名" /></el-form-item>
    <el-form-item label="密码" prop="password"><el-input v-model="form.password" type="password" show-password autocomplete="current-password" placeholder="请输入密码" @keyup.enter="submit" /></el-form-item>
    <el-button class="auth-primary-button" type="primary" size="large" native-type="submit" :loading="loading">登录</el-button>
  </el-form>
</template>

<style scoped>
:deep(.el-form-item) { margin-bottom: 21px; }
:deep(.el-form-item__label) { height: auto; padding-bottom: 8px; color: #415366; font-size: 14px; font-weight: 600; line-height: 1.35; }
:deep(.el-input__wrapper) { min-height: 44px; border: 1px solid #dce8f7; border-radius: 8px; box-shadow: none; }
:deep(.el-input__wrapper:hover) { border-color: #b9d5f7; }
:deep(.el-input__wrapper.is-focus) { border-color: #1677ff; box-shadow: 0 0 0 3px rgb(22 119 255 / 8%); }
.auth-primary-button { width: 100%; height: 46px; margin-top: 3px; border-radius: 8px; background: #1677ff; font-size: 15px; font-weight: 600; }
</style>
