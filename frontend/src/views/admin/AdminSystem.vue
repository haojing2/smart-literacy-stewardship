<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getAdminSystemStatus, type SystemStatus } from '@/api/admin'
const status = ref<SystemStatus>()
onMounted(async () => {
  try { status.value = (await getAdminSystemStatus()).data.data }
  catch (error: any) { ElMessage.error(error.response?.data?.message ?? '无法获取系统状态') }
})
</script>
<template>
  <div class="system-page">
    <header><h1>系统状态</h1><p>查看平台基础服务运行情况</p></header>
    <section class="status-card">
      <div><span>API 服务</span><b :class="{ error: status?.api !== 'UP' }">{{ status?.api === 'UP' ? '正常' : '异常' }}</b></div>
      <div><span>数据库连接</span><b :class="{ error: status?.database !== 'UP' }">{{ status?.database === 'UP' ? '正常' : '异常' }}</b></div>
      <div><span>系统版本</span><strong>{{ status?.version ?? '—' }}</strong></div>
      <div><span>运行环境</span><strong>{{ status?.environment === 'development' ? 'Development' : 'Production' }}</strong></div>
    </section>
  </div>
</template>
<style scoped>
.system-page{max-width:900px;margin:auto}header h1{margin:0 0 9px;font-size:27px}header p{margin:0;color:#8a98aa;font-size:14px}.status-card{margin-top:28px;padding:4px 26px;border:1px solid #e6edf6;border-radius:10px;background:#fff;box-shadow:0 3px 14px #1f52960a}.status-card div{display:flex;align-items:center;justify-content:space-between;min-height:68px;border-bottom:1px solid #edf1f6}.status-card div:last-child{border:0}.status-card span{color:#526174}.status-card b{padding:5px 10px;border-radius:5px;color:#438566;background:#edf7f1;font-size:13px}.status-card b.error{color:#b45b5b;background:#fff2f2}.status-card strong{font-size:14px;font-weight:500}
</style>
