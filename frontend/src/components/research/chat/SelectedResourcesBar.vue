<script setup lang="ts">
import type { ResearchResource } from '@/types/research'

defineProps<{ resources: ResearchResource[] }>()
defineEmits<{ remove: [resourceId: number]; upload: [] }>()
</script>

<template>
  <div class="resources-bar">
    <div class="bar-heading">
      <span>当前研究依据</span>
      <el-button link type="primary" @click="$emit('upload')">上传研究资源</el-button>
    </div>
    <div v-if="resources.length" class="resource-chips">
      <span v-for="resource in resources" :key="resource.resourceId" class="resource-chip">
        <span class="file-icon">▤</span>{{ resource.fileName }}
        <button type="button" aria-label="移除研究依据" @click="$emit('remove', resource.resourceId)">×</button>
      </span>
    </div>
    <span v-else class="empty-resources">尚未添加研究资源</span>
  </div>
</template>

<style scoped>
.resources-bar { flex: none; padding: 13px 18px; border-bottom: 1px solid #eaecf0; }.bar-heading { display: flex; min-height: 24px; align-items: center; justify-content: space-between; color: #475467; font-size: 12px; font-weight: 600; }.bar-heading :deep(.el-button) { font-size: 12px; }.resource-chips { display: flex; overflow-x: auto; gap: 8px; padding-top: 8px; }.resource-chip { display: inline-flex; max-width: 240px; flex: none; align-items: center; gap: 6px; padding: 5px 8px; border: 1px solid #eaecf0; border-radius: 7px; color: #475467; background: #f8fafc; font-size: 12px; white-space: nowrap; }.resource-chip>span:not(.file-icon) { overflow: hidden; text-overflow: ellipsis; }.file-icon { color: #667085; }.resource-chip button { padding: 0; border: 0; color: #98a2b3; background: transparent; cursor: pointer; font-size: 15px; }.empty-resources { display: block; padding-top: 5px; color: #98a2b3; font-size: 12px; }
</style>
