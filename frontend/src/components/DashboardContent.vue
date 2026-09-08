<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getProjects, type ProjectListItem } from '@/api/projects'
import ProjectFormDialog from '@/components/ProjectFormDialog.vue'
import { getProjectNextRoute } from '@/utils/projectNavigation'
import { getProjectProgress } from '@/utils/projectWorkflow'

const router = useRouter()
const projects = ref<ProjectListItem[]>([])
const loading = ref(false)
const errorMessage = ref('')
const createDialogVisible = ref(false)
const isEmpty = computed(() => !loading.value && !errorMessage.value && projects.value.length === 0)

async function loadRecentProjects() {
  loading.value = true
  errorMessage.value = ''
  try {
    const { data } = await getProjects({ page: 1, pageSize: 3 })
    projects.value = data.data.items
  } catch {
    projects.value = []
    errorMessage.value = '项目数据加载失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

function continueDesign(project: ProjectListItem) {
  void router.push(getProjectNextRoute(project.workflowState, project.projectId))
}

onMounted(() => void loadRecentProjects())
</script>

<template>
  <section class="dashboard-content">
    <header class="dashboard-header"><div><p>工作台</p><h1>工作概览</h1><span>快速查看最近的教学设计项目</span></div></header>
    <section class="recent-projects"><div class="section-heading"><div><h2>最近项目</h2><p>继续推进你的教学设计</p></div><el-button link type="primary" @click="router.push('/projects')">查看全部</el-button></div>
      <div v-if="loading" class="state-panel">正在加载项目…</div>
      <div v-else-if="errorMessage" class="state-panel error-state"><p>{{ errorMessage }}</p><el-button type="primary" plain @click="loadRecentProjects">重新加载</el-button></div>
      <div v-else-if="isEmpty" class="state-panel empty-state"><p>创建你的第一个教学项目</p><el-button type="primary" @click="createDialogVisible = true">新建项目</el-button></div>
      <div v-else class="project-grid"><button v-for="project in projects" :key="project.projectId" class="project-card" type="button" @click="continueDesign(project)"><div class="card-top"><span class="project-grade">{{ project.grade ? `${project.grade} 年级` : '未设置年级' }}</span><span>{{ getProjectProgress(project.workflowState) }}%</span></div><h3>{{ project.title }}</h3><p>{{ project.topic }}</p><div class="card-meta"><span>{{ project.classHours ? `${project.classHours} 课时` : '未设置课时' }}</span><el-progress :percentage="getProjectProgress(project.workflowState)" :stroke-width="5" :show-text="false" /></div></button></div>
    </section>
    <ProjectFormDialog v-model:visible="createDialogVisible" mode="create" @saved="loadRecentProjects" />
  </section>
</template>

<style scoped>
.dashboard-content { min-height: 100vh; padding: 34px 38px 42px; }.dashboard-header { margin-bottom: 28px; }.dashboard-header p { margin: 0 0 11px; color: #98a2b3; font-size: 13px; }.dashboard-header h1 { margin: 0; color: #101828; font-size: 27px; font-weight: 650; }.dashboard-header span { display: block; margin-top: 10px; color: #667085; font-size: 14px; }.recent-projects { padding: 24px; border: 1px solid #eaecf0; border-radius: 8px; background: #fff; box-shadow: 0 2px 10px rgb(16 24 40 / 4%); }.section-heading { display: flex; align-items: center; justify-content: space-between; margin-bottom: 21px; }.section-heading h2 { margin: 0 0 6px; color: #1d2939; font-size: 18px; }.section-heading p { margin: 0; color: #98a2b3; font-size: 13px; }.project-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; }.project-card { display: block; min-height: 174px; padding: 18px; border: 1px solid #eaecf0; border-radius: 8px; color: inherit; background: #fff; cursor: pointer; font: inherit; text-align: left; transition: border-color .2s ease, box-shadow .2s ease, transform .2s ease; }.project-card:hover { border-color: #b9d5f7; box-shadow: 0 7px 18px rgb(22 119 255 / 9%); transform: translateY(-2px); }.card-top { display: flex; align-items: center; justify-content: space-between; color: #667085; font-size: 12px; }.project-grade { padding: 3px 7px; border-radius: 4px; color: #1677ff; background: #eff6ff; }.project-card h3 { overflow: hidden; margin: 18px 0 8px; color: #1d2939; font-size: 15px; text-overflow: ellipsis; white-space: nowrap; }.project-card p { overflow: hidden; margin: 0; color: #667085; font-size: 13px; text-overflow: ellipsis; white-space: nowrap; }.card-meta { display: grid; grid-template-columns: auto 1fr; align-items: center; gap: 10px; margin-top: 22px; color: #98a2b3; font-size: 12px; }.state-panel { display: grid; min-height: 196px; place-items: center; color: #667085; text-align: center; }.error-state { gap: 14px; color: #b54708; }.error-state p, .empty-state p { margin: 0; }.empty-state { gap: 15px; color: #667085; }@media (max-width: 850px) { .dashboard-content { padding: 28px 24px; }.project-grid { grid-template-columns: 1fr; } }@media (max-width: 620px) { .dashboard-content { padding: 22px 16px; }.recent-projects { padding: 19px; } }
</style>
