<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import {
  createProject,
  updateProject,
  type ProjectCreatePayload,
  type ProjectDetail,
  type ProjectType,
} from '@/api/projects'
import { getProjectNextRoute } from '@/utils/projectNavigation'

const props = defineProps<{
  visible: boolean
  mode: 'create' | 'edit'
  project?: Pick<ProjectDetail, 'projectId' | 'title' | 'topic' | 'projectType'>
}>()
const emit = defineEmits<{ 'update:visible': [value: boolean]; saved: [] }>()

const router = useRouter()
const formRef = ref<FormInstance>()
const submitting = ref(false)
const isEdit = computed(() => props.mode === 'edit')
const form = reactive<ProjectCreatePayload>({
  title: '',
  topic: '',
  projectType: 'NEW_TOPIC',
})
const rules: FormRules<typeof form> = {
  title: [{ required: true, message: '请输入项目名称', trigger: 'blur' }],
  topic: [{ required: true, message: '请输入教学主题', trigger: 'blur' }],
  projectType: [{ required: true, message: '请选择项目类型', trigger: 'change' }],
}

function resetForm() {
  form.title = props.project?.title ?? ''
  form.topic = props.project?.topic ?? ''
  form.projectType = (props.project?.projectType ?? 'NEW_TOPIC') as ProjectType
  formRef.value?.clearValidate()
}

watch(
  () => [props.visible, props.mode, props.project] as const,
  ([visible]) => {
    if (visible) resetForm()
  },
)

function close() {
  if (!submitting.value) emit('update:visible', false)
}

async function submit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid || submitting.value) return

  submitting.value = true
  try {
    if (isEdit.value) {
      if (!props.project) return
      await updateProject(props.project.projectId, {
        title: form.title.trim(),
        topic: form.topic.trim(),
        projectType: form.projectType,
      })
      emit('update:visible', false)
      ElMessage.success('修改成功')
      emit('saved')
      return
    }

    const { data } = await createProject({
      title: form.title.trim(),
      topic: form.topic.trim(),
      projectType: form.projectType,
    })
    emit('update:visible', false)
    ElMessage.success('项目创建成功')
    emit('saved')
    await router.push(getProjectNextRoute(data.data.workflowState, data.data.projectId))
  } catch (error: any) {
    ElMessage.error(error.response?.data?.message || (isEdit.value ? '修改失败，请稍后重试' : '项目创建失败，请稍后重试'))
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <el-dialog
    :model-value="visible"
    :title="isEdit ? '编辑项目' : '新建项目'"
    width="480px"
    :close-on-click-modal="false"
    @close="close"
  >
    <p class="dialog-description">
      {{ isEdit ? '修改项目基础信息会根据当前设计进度自动处理后续内容。' : '先创建项目基础信息，教学情境将在下一步填写。' }}
    </p>
    <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @submit.prevent="submit">
      <el-form-item label="项目名称" prop="title">
        <el-input v-model="form.title" maxlength="255" placeholder="例如：AI回答可信吗？" />
      </el-form-item>
      <el-form-item label="教学主题" prop="topic">
        <el-input v-model="form.topic" maxlength="255" placeholder="例如：生成式AI信息核验" />
      </el-form-item>
      <el-form-item label="项目类型" prop="projectType">
        <el-radio-group v-model="form.projectType">
          <el-radio value="NEW_TOPIC">新主题</el-radio>
          <el-radio value="OPTIMIZE_EXISTING">优化已有课程</el-radio>
          <el-radio value="TEXTBOOK_ADAPTATION">教材适配</el-radio>
        </el-radio-group>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button :disabled="submitting" @click="close">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="submit">
        {{ isEdit ? '保存修改' : '创建项目' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.dialog-description { margin: -4px 0 23px; color: #667085; font-size: 14px; }
.el-radio-group { display: grid; gap: 12px; }
.el-radio { margin-right: 0; }
</style>
