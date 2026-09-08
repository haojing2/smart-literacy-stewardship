<script setup lang="ts">
import type { ResearchProjectContext } from '@/types/research'

defineProps<{
  project: ResearchProjectContext
  resourceCount: number
  evidenceCount: number
  continuing: boolean
  mockMode: boolean
}>()

defineEmits<{ viewResources: []; continueCourseDesign: [] }>()

const gradeLabel = (grade: number | null) => (grade ? `${grade} 年级` : '年级未设置')
</script>

<template>
  <header class="research-context-header">
    <div>
      <p class="eyebrow">研教智联</p>
      <div class="title-row">
        <h1>让研究证据进入课程设计</h1>
        <span class="demo-badge">{{ mockMode ? 'Demo · Mock 助手' : '研教智联 Agent' }}</span>
      </div>
      <p class="project-name">{{ project.title }}</p>
      <p class="project-meta">
        {{ gradeLabel(project.grade) }} · {{ project.classHours ? `${project.classHours} 课时` : '课时未设置' }} · {{ project.topic }}
      </p>
    </div>
    <div class="header-side">
      <div class="stats">
        <span><strong>{{ resourceCount }}</strong>研究资源</span>
        <span><strong>{{ evidenceCount }}</strong>证据卡</span>
      </div>
      <el-button plain @click="$emit('viewResources')">查看研究资源</el-button>
      <el-button type="primary" :loading="continuing" :disabled="continuing" @click="$emit('continueCourseDesign')">
        进入课程智设 →
      </el-button>
    </div>
  </header>
</template>

<style scoped>
.research-context-header { display: flex; min-height: 112px; align-items: flex-end; justify-content: space-between; gap: 24px; padding: 0 2px 20px; }.eyebrow { margin: 0 0 7px; color: #1677ff; font-size: 13px; font-weight: 650; }.title-row { display: flex; align-items: center; gap: 10px; }.title-row h1 { margin: 0; color: #101828; font-size: 24px; font-weight: 650; letter-spacing: -.02em; }.demo-badge { padding: 3px 7px; border: 1px solid #dbe8f8; border-radius: 10px; color: #4774a8; background: #f4f8fd; font-size: 11px; }.project-name { margin: 13px 0 3px; color: #344054; font-size: 15px; font-weight: 600; }.project-meta { margin: 0; color: #667085; font-size: 13px; }.header-side { display: flex; align-items: center; gap: 18px; }.stats { display: flex; gap: 16px; color: #667085; font-size: 12px; }.stats span { display: grid; gap: 2px; text-align: center; }.stats strong { color: #1d2939; font-size: 18px; font-weight: 650; }@media (max-width: 760px) { .research-context-header { align-items: flex-start; flex-direction: column; }.header-side { width: 100%; justify-content: space-between; }.title-row { align-items: flex-start; flex-direction: column; } }
</style>
