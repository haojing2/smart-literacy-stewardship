<script setup lang="ts">
defineProps<{
  score: number
  status: 'INCOMPLETE' | 'READY'
  missingRequiredFields: string[]
}>()
</script>

<template>
  <section class="readiness">
    <div class="readiness-heading">
      <span>研究信息完整度</span>
      <strong>{{ score }}%</strong>
    </div>
    <el-progress :percentage="score" :stroke-width="6" :show-text="false" :status="status === 'READY' ? 'success' : undefined" />
    <p v-if="status === 'READY'" class="ready-message">✓ 已具备生成证据卡的条件</p>
    <p v-else class="incomplete-message">
      仍需补充 {{ missingRequiredFields.length }} 项必填信息
      <el-tag size="small" effect="plain">INCOMPLETE</el-tag>
    </p>
  </section>
</template>

<style scoped>
.readiness { padding: 13px 0 16px; border-bottom: 1px solid #eaecf0; }.readiness-heading { display: flex; align-items: center; justify-content: space-between; margin-bottom: 9px; color: #667085; font-size: 12px; }.readiness-heading strong { color: #344054; font-size: 13px; }.readiness p { margin: 9px 0 0; font-size: 12px; }.ready-message { color: #438566; }.incomplete-message { display: flex; align-items: center; justify-content: space-between; color: #667085; }.incomplete-message :deep(.el-tag) { height: 20px; color: #667085; border-color: #dfe3e8; background: #f9fafb; font-size: 10px; }
</style>
