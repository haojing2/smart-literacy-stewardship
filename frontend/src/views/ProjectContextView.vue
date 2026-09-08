<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { getProject, saveProjectContext, type ProjectDetail } from '@/api/projects'
import { getProjectNextRoute } from '@/utils/projectNavigation'

type StudentLevel = 'BEGINNER' | 'GENERAL' | 'ADVANCED'
type AiAccessMode = 'TEACHER_DEMO' | 'GROUP' | 'INDIVIDUAL'

const route = useRoute()
const router = useRouter()
const formRef = ref<FormInstance>()
const loading = ref(true)
const saving = ref(false)
const errorMessage = ref('')
const project = ref<ProjectDetail>()
const projectId = computed(() => String(route.params.projectId))
const steps = ['基本信息', '研究证据', '课程设计', '教学智检', '资源智创']
const form = reactive({
  grade: undefined as number | undefined,
  classHours: undefined as number | undefined,
  studentLevel: 'GENERAL' as StudentLevel,
  aiAccessMode: 'GROUP' as AiAccessMode,
  devices: [] as string[],
  constraints: [] as string[],
  additionalRequirements: '',
})
const rules: FormRules<typeof form> = {
  grade: [{ required: true, message: '请选择年级', trigger: 'change' }],
  classHours: [{ required: true, type: 'number', min: 1, message: '课时必须大于 0', trigger: 'blur' }],
  studentLevel: [{ required: true, message: '请选择学生基础', trigger: 'change' }],
  aiAccessMode: [{ required: true, message: '请选择 AI 使用方式', trigger: 'change' }],
}

async function returnMissingProjectToList() {
  ElMessage.error('项目不存在或已被删除')
  await router.replace('/projects')
}

async function loadProject() {
  loading.value = true
  errorMessage.value = ''
  try {
    const { data } = await getProject(projectId.value)
    project.value = data.data
    form.grade = data.data.grade ?? undefined
    form.classHours = data.data.classHours ?? undefined
    form.studentLevel = data.data.studentLevel ?? 'GENERAL'
    form.aiAccessMode = data.data.aiAccessMode ?? 'GROUP'
    form.devices = [...(data.data.devices ?? [])]
    form.constraints = [...(data.data.constraints ?? [])]
    form.additionalRequirements = data.data.additionalRequirements ?? ''
  } catch (error: any) {
    if (error.response?.status === 404) {
      await returnMissingProjectToList()
      return
    }
    errorMessage.value = error.response?.data?.message || '项目加载失败，请返回项目列表后重试'
  } finally {
    loading.value = false
  }
}

async function saveAndContinue() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid || saving.value || form.grade === undefined || form.classHours === undefined) return

  saving.value = true
  try {
    const { data } = await saveProjectContext(projectId.value, {
      grade: form.grade,
      classHours: form.classHours,
      studentLevel: form.studentLevel,
      aiAccessMode: form.aiAccessMode,
      devices: form.devices,
      constraints: form.constraints,
      additionalRequirements: form.additionalRequirements || null,
    })
    ElMessage.success('基本信息已保存')
    await router.replace(getProjectNextRoute(data.data.workflowState, data.data.projectId))
  } catch (error: any) {
    if (error.response?.status === 404) {
      await returnMissingProjectToList()
      return
    }
    ElMessage.error(error.response?.data?.message || '保存失败，请稍后重试')
  } finally {
    saving.value = false
  }
}

function returnToProjects() {
  void router.push('/projects')
}

onMounted(() => void loadProject())
</script>

<template>
  <main class="context-page">
    <header class="context-header">
      <div>
        <el-button link type="primary" @click="returnToProjects">← 返回我的项目</el-button>
        <h1>{{ project?.title || '项目基本信息' }}</h1>
        <p>当前步骤：<strong>基本信息</strong></p>
      </div>
    </header>

    <nav class="workflow-steps" aria-label="项目流程">
      <template v-for="(step, index) in steps" :key="step">
        <span :class="['step', { current: index === 0, upcoming: index > 0 }]">{{ step }}</span>
        <span v-if="index < steps.length - 1" class="step-arrow">→</span>
      </template>
    </nav>

    <section v-if="loading" class="state-panel">正在加载项目…</section>
    <section v-else-if="errorMessage" class="state-panel error-state"><p>{{ errorMessage }}</p><el-button type="primary" plain @click="loadProject">重新加载</el-button></section>
    <section v-else class="context-card">
      <div class="card-heading"><h2>基本信息</h2><p>完善教学情境，为后续设计提供基础。</p></div>
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" class="context-form">
        <el-form-item label="年级" prop="grade">
          <el-select v-model="form.grade" placeholder="请选择年级"><el-option v-for="item in 6" :key="item" :label="`${['一', '二', '三', '四', '五', '六'][item - 1]}年级`" :value="item" /></el-select>
        </el-form-item>
        <el-form-item label="课时" prop="classHours"><el-input-number v-model="form.classHours" :min="1" :max="99" controls-position="right" /></el-form-item>
        <el-form-item label="学生基础" prop="studentLevel"><el-radio-group v-model="form.studentLevel"><el-radio value="BEGINNER">初学</el-radio><el-radio value="GENERAL">一般</el-radio><el-radio value="ADVANCED">较好</el-radio></el-radio-group></el-form-item>
        <el-form-item label="AI使用方式" prop="aiAccessMode"><el-radio-group v-model="form.aiAccessMode"><el-radio value="TEACHER_DEMO">教师演示</el-radio><el-radio value="GROUP">小组使用</el-radio><el-radio value="INDIVIDUAL">个人使用</el-radio></el-radio-group></el-form-item>
        <el-form-item label="教学设备"><el-select v-model="form.devices" multiple placeholder="请选择教学设备"><el-option label="电脑" value="COMPUTER" /><el-option label="平板" value="TABLET" /><el-option label="投影仪" value="PROJECTOR" /></el-select></el-form-item>
        <el-form-item label="教学限制"><el-select v-model="form.constraints" multiple filterable allow-create default-first-option placeholder="可选择或输入教学限制"><el-option label="网络受限" value="LIMITED_NETWORK" /><el-option label="课时有限" value="LIMITED_TIME" /><el-option label="设备有限" value="LIMITED_DEVICES" /></el-select></el-form-item>
        <el-form-item label="其他教学要求"><el-input v-model="form.additionalRequirements" type="textarea" :rows="4" maxlength="1000" show-word-limit placeholder="请输入其他教学要求（可选）" /></el-form-item>
      </el-form>
      <footer class="form-actions"><el-button @click="returnToProjects">返回我的项目</el-button><el-button type="primary" :loading="saving" @click="saveAndContinue">保存并进入下一步</el-button></footer>
    </section>
  </main>
</template>

<style scoped>
.context-page { min-height: 100vh; padding: 34px clamp(24px, 7vw, 112px) 52px; color: #101828; background: #f7f9fc; }.context-header { margin-bottom: 22px; }.context-header :deep(.el-button) { padding: 0; }.context-header h1 { margin: 15px 0 8px; font-size: 28px; }.context-header p { margin: 0; color: #667085; font-size: 14px; }.context-header strong { color: #1677ff; }.workflow-steps { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; margin-bottom: 24px; padding: 15px 20px; border: 1px solid #eaecf0; border-radius: 8px; background: #fff; box-shadow: 0 2px 10px rgb(16 24 40 / 4%); }.step { color: #98a2b3; font-size: 14px; }.step.current { color: #1677ff; font-weight: 700; }.step-arrow { color: #cbd5e1; }.state-panel { display: grid; min-height: 320px; place-items: center; border: 1px solid #eaecf0; border-radius: 8px; color: #667085; background: #fff; }.error-state { gap: 15px; color: #b54708; }.error-state p { margin: 0; }.context-card { max-width: 760px; margin: 0 auto; padding: 28px 32px 24px; border: 1px solid #eaecf0; border-radius: 8px; background: #fff; box-shadow: 0 2px 10px rgb(16 24 40 / 4%); }.card-heading { margin-bottom: 26px; }.card-heading h2 { margin: 0 0 8px; font-size: 20px; }.card-heading p { margin: 0; color: #667085; font-size: 14px; }.context-form { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); column-gap: 20px; }.context-form :deep(.el-form-item:nth-child(n + 3)) { grid-column: 1 / -1; }.context-form :deep(.el-select), .context-form :deep(.el-input-number) { width: 100%; }.form-actions { display: flex; justify-content: space-between; gap: 16px; padding-top: 22px; border-top: 1px solid #edf0f3; }@media (max-width: 640px) { .context-page { padding: 24px 16px; }.context-card { padding: 24px 20px; }.context-form { display: block; }.workflow-steps { gap: 8px; }.step { font-size: 12px; } }
</style>
