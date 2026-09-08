<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { deleteProject, getProject, getProjects, type ProjectDetail, type ProjectListItem } from '@/api/projects'
import ProjectFormDialog from '@/components/ProjectFormDialog.vue'
import { getProjectNextRoute } from '@/utils/projectNavigation'
import { getProjectProgress } from '@/utils/projectWorkflow'

const router = useRouter()
const items = ref<ProjectListItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)
const grade = ref<number | undefined>()
const sort = ref('updated_at_desc')
const loading = ref(false)
const errorMessage = ref('')
const projectDialogVisible = ref(false)
const projectDialogMode = ref<'create' | 'edit'>('create')
const editingProject = ref<Pick<ProjectDetail, 'projectId' | 'title' | 'topic' | 'projectType'>>()

const isEmpty = computed(() => !loading.value && !errorMessage.value && items.value.length === 0)

function workflowLabel(state: string) {
  return state === 'DRAFT' ? '待完善情境' : state === 'CONTEXT_READY' ? '情境已完成' : state
}

function formatUpdatedAt(value: string) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN', { hour12: false })
}

async function loadProjects() {
  loading.value = true
  errorMessage.value = ''
  try {
    const { data } = await getProjects({
      page: page.value,
      pageSize: pageSize.value,
      grade: grade.value,
      sort: sort.value || undefined,
    })
    items.value = data.data.items
    total.value = data.data.total
  } catch {
    items.value = []
    total.value = 0
    errorMessage.value = '项目列表加载失败，请检查网络后重试'
  } finally {
    loading.value = false
  }
}

function handleFilterChange() {
  page.value = 1
  void loadProjects()
}

function handlePageChange(nextPage: number) {
  page.value = nextPage
  void loadProjects()
}

function handleSizeChange(nextPageSize: number) {
  pageSize.value = nextPageSize
  page.value = 1
  void loadProjects()
}

function continueDesign(project: ProjectListItem) {
  void router.push(getProjectNextRoute(project.workflowState, project.projectId))
}

function openCreateDialog() {
  projectDialogMode.value = 'create'
  editingProject.value = undefined
  projectDialogVisible.value = true
}

async function openEditDialog(project: ProjectListItem) {
  try {
    const { data } = await getProject(project.projectId)
    editingProject.value = data.data
    projectDialogMode.value = 'edit'
    projectDialogVisible.value = true
  } catch (error: any) {
    ElMessage.error(error.response?.data?.message || '无法读取项目详情，请稍后重试')
  }
}

async function handleProjectCommand(command: string, project: ProjectListItem) {
  if (command === 'edit') {
    await openEditDialog(project)
    return
  }
  if (command !== 'delete') return

  try {
    await ElMessageBox.confirm(
      `确定删除项目“${project.title}”吗？\n\n删除后该项目将不再出现在“我的项目”中。`,
      '删除项目',
      {
        confirmButtonText: '删除项目',
        cancelButtonText: '取消',
        type: 'warning',
        confirmButtonClass: 'el-button--danger',
      },
    )
    await deleteProject(project.projectId)
    ElMessage.success('项目已删除')
    if (items.value.length === 1 && page.value > 1) page.value -= 1
    await loadProjects()
  } catch (error: any) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(error.response?.data?.message || '删除失败，请稍后重试')
    }
  }
}

onMounted(() => void loadProjects())
</script>

<template>
  <section class="projects-content">
    <header class="projects-header">
      <div>
        <p class="breadcrumb">工作台 / 我的项目</p>
        <h1>我的项目</h1>
        <span>管理你的所有教学设计项目</span>
      </div>
      <div class="header-actions">
        <span class="project-overview">项目总览</span>
        <el-button type="primary" @click="openCreateDialog">新建项目</el-button>
      </div>
    </header>

    <section class="projects-card">
      <div class="filters" aria-label="项目筛选">
        <el-select model-value="all" class="filter-select" disabled aria-label="项目范围">
          <el-option label="全部项目" value="all" />
        </el-select>
        <el-select v-model="sort" class="filter-select" aria-label="时间筛选" @change="handleFilterChange">
          <el-option label="按时间筛选" value="updated_at_desc" />
          <el-option label="最早更新" value="updated_at_asc" />
        </el-select>
        <el-select v-model="grade" class="filter-select" clearable placeholder="全部年级" aria-label="年级筛选" @change="handleFilterChange">
          <el-option v-for="item in 12" :key="item" :label="`${item} 年级`" :value="item" />
        </el-select>
      </div>

      <div v-if="errorMessage" class="state-panel error-state">
        <p>{{ errorMessage }}</p>
        <el-button plain type="primary" @click="loadProjects">重新加载</el-button>
      </div>
      <div v-else-if="isEmpty" class="state-panel empty-state">
        <p>还没有教学项目，创建第一个项目开始设计吧</p>
      </div>
      <el-table v-else v-loading="loading" :data="items" class="projects-table" empty-text="" table-layout="fixed">
        <el-table-column prop="title" label="项目名称" min-width="190">
          <template #default="{ row }"><strong class="project-title">{{ row.title }}</strong></template>
        </el-table-column>
        <el-table-column label="年级/对象" min-width="125">
          <template #default="{ row }">{{ row.grade ? `${row.grade} 年级` : '未设置' }}{{ row.studentLevel ? ` · ${row.studentLevel}` : '' }}</template>
        </el-table-column>
        <el-table-column prop="topic" label="主题" min-width="180" show-overflow-tooltip />
        <el-table-column label="课时" width="90">
          <template #default="{ row }">{{ row.classHours ? `${row.classHours} 课时` : '—' }}</template>
        </el-table-column>
        <el-table-column label="更新时间" width="180">
          <template #default="{ row }">{{ formatUpdatedAt(row.updatedAt) }}</template>
        </el-table-column>
        <el-table-column label="进度" width="150">
          <template #default="{ row }"><div class="progress-cell"><el-progress :percentage="getProjectProgress(row.workflowState)" :stroke-width="6" :show-text="false" /><span>{{ getProjectProgress(row.workflowState) }}%</span></div><el-tag size="small" effect="plain" type="primary">{{ workflowLabel(row.workflowState) }}</el-tag></template>
        </el-table-column>
        <el-table-column label="操作" width="135" align="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="continueDesign(row)">继续设计</el-button>
            <el-dropdown trigger="click" @command="handleProjectCommand($event, row)">
              <el-button class="more-actions" link aria-label="更多项目操作">···</el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="edit">编辑项目</el-dropdown-item>
                  <el-dropdown-item command="delete" divided>删除项目</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </template>
        </el-table-column>
      </el-table>

      <footer v-if="!errorMessage && !isEmpty" class="pagination-bar">
        <span>共 {{ total }} 个项目</span>
        <el-pagination v-model:current-page="page" v-model:page-size="pageSize" :page-sizes="[10, 20, 50]" :total="total" layout="sizes, prev, pager, next" @current-change="handlePageChange" @size-change="handleSizeChange" />
      </footer>
    </section>
    <ProjectFormDialog v-model:visible="projectDialogVisible" :mode="projectDialogMode" :project="editingProject" @saved="loadProjects" />
  </section>
</template>

<style scoped>
.projects-content { min-height: 100vh; padding: 34px 38px 42px; }.projects-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; margin-bottom: 28px; }.breadcrumb { margin: 0 0 11px; color: #98a2b3; font-size: 13px; }.projects-header h1 { margin: 0; color: #101828; font-size: 27px; font-weight: 650; }.projects-header span { display: block; margin-top: 10px; color: #667085; font-size: 14px; }.header-actions { display: flex; align-items: center; gap: 14px; padding-top: 18px; }.header-actions .project-overview { margin: 0; color: #667085; font-size: 14px; }.header-actions :deep(.el-button) { height: 36px; padding: 0 16px; border-radius: 6px; box-shadow: 0 2px 5px rgb(22 119 255 / 15%); }.projects-card { overflow: hidden; border: 1px solid #eaecf0; border-radius: 8px; background: #fff; box-shadow: 0 2px 10px rgb(16 24 40 / 4%); }.filters { display: flex; gap: 12px; padding: 18px 22px; border-bottom: 1px solid #edf0f3; }.filter-select { width: 142px; }.projects-table { width: 100%; }.projects-table :deep(th.el-table__cell) { height: 47px; color: #475467; background: #fafbfc; font-size: 13px; font-weight: 600; }.projects-table :deep(td.el-table__cell) { height: 62px; color: #475467; font-size: 13px; }.project-title { color: #1d2939; font-weight: 600; }.progress-cell { display: flex; width: 100%; align-items: center; gap: 7px; }.progress-cell :deep(.el-progress) { flex: 1; }.progress-cell span { width: 32px; color: #667085; font-size: 12px; }.more-actions { min-width: 28px; margin-left: 4px; padding: 0 4px; color: #667085; font-size: 18px; letter-spacing: 1px; }.state-panel { display: grid; min-height: 270px; padding: 36px; color: #667085; place-items: center; text-align: center; }.state-panel p { margin: 0; }.error-state { gap: 16px; color: #b54708; }.pagination-bar { display: flex; align-items: center; justify-content: space-between; min-height: 68px; padding: 12px 22px; border-top: 1px solid #edf0f3; color: #667085; font-size: 13px; }@media (max-width: 850px) { .projects-content { padding: 28px 24px; } }@media (max-width: 620px) { .projects-content { padding: 22px 16px; }.projects-header { display: block; }.header-actions { padding-top: 20px; }.filters { flex-wrap: wrap; }.filter-select { flex: 1 1 130px; }.pagination-bar { align-items: flex-start; gap: 12px; flex-direction: column; } }
</style>
