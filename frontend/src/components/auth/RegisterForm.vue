<script setup lang="ts">
import { reactive, ref } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { register } from '@/api/auth'

const emit = defineEmits<{ submitted: [] }>()
const formRef = ref<FormInstance>()
const loading = ref(false)
const form = reactive({ username: '', displayName: '', password: '', confirmPassword: '' })
const rules: FormRules<typeof form> = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }, { min: 3, max: 30, message: '用户名长度应为 3–30 个字符', trigger: 'blur' }],
  displayName: [{ required: true, message: '请输入姓名或昵称', trigger: 'blur' }, { max: 50, message: '显示名称不能超过 50 个字符', trigger: 'blur' }],
  password: [{ required: true, message: '请设置登录密码', trigger: 'blur' }, { min: 6, message: '密码至少需要 6 位', trigger: 'blur' }],
  confirmPassword: [{ required: true, message: '请再次输入密码', trigger: 'blur' }, { validator: (_rule, value, callback) => callback(value === form.password ? undefined : new Error('两次输入的密码不一致')), trigger: 'blur' }],
}

async function submit() {
  form.username = form.username.trim()
  form.displayName = form.displayName.trim()
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid || loading.value) return
  loading.value = true
  try {
    const { data } = await register(form.username, form.displayName, form.password)
    form.password = ''
    form.confirmPassword = ''
    ElMessage.success(data.data.message)
    emit('submitted')
  } catch (error: any) {
    ElMessage.error(error.response?.data?.message ?? (error.response ? '账号创建失败，请稍后重试' : '网络连接失败，请稍后重试'))
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @submit.prevent="submit">
    <el-form-item label="用户名" prop="username"><el-input v-model="form.username" autocomplete="username" placeholder="请输入用户名" /></el-form-item>
    <el-form-item label="显示名称" prop="displayName"><el-input v-model="form.displayName" autocomplete="name" placeholder="请输入姓名或昵称" /></el-form-item>
    <el-form-item label="密码" prop="password"><el-input v-model="form.password" type="password" show-password autocomplete="new-password" placeholder="设置登录密码" /></el-form-item>
    <el-form-item label="确认密码" prop="confirmPassword"><el-input v-model="form.confirmPassword" type="password" show-password autocomplete="new-password" placeholder="再次输入密码" @keyup.enter="submit" /></el-form-item>
    <el-button class="auth-primary-button" type="primary" size="large" native-type="submit" :loading="loading">创建账号</el-button>
  </el-form>
</template>

<style scoped>
:deep(.el-form-item) { margin-bottom: 20px; }
:deep(.el-form-item__label) { height: auto; padding-bottom: 8px; color: #415366; font-size: 14px; font-weight: 600; line-height: 1.35; }
:deep(.el-input__wrapper) { min-height: 44px; border: 1px solid #dce8f7; border-radius: 8px; box-shadow: none; }
:deep(.el-input__wrapper:hover) { border-color: #b9d5f7; }
:deep(.el-input__wrapper.is-focus) { border-color: #1677ff; box-shadow: 0 0 0 3px rgb(22 119 255 / 8%); }
.auth-primary-button { width: 100%; height: 46px; margin-top: 3px; border-radius: 8px; background: #1677ff; font-size: 15px; font-weight: 600; }
</style>
