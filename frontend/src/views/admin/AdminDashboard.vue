<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getAdminSystemStatus, getAdminUsers, type AdminUser, type SystemStatus } from '@/api/admin'
const router = useRouter()
const stats = ref<SystemStatus>()
const recent = ref<AdminUser[]>([])
onMounted(async () => {
  const [status, users] = await Promise.all([getAdminSystemStatus(), getAdminUsers({ page: 1, pageSize: 5 })])
  stats.value = status.data.data
  recent.value = users.data.data.items
})
const statusLabel = (value: string) => ({ PENDING: '待审批', ACTIVE: '正常', REJECTED: '未通过', DISABLED: '已停用' }[value] ?? value)
</script>
<template>
  <div class="admin-page">
    <header><h1>管理概览</h1><p>查看平台用户与系统运行情况</p></header>
    <div class="stats">
      <article><span>用户总数</span><b>{{ stats?.registeredUsers ?? '—' }}</b></article>
      <article class="pending"><span>待审批</span><b>{{ stats?.pendingUsers ?? '—' }}</b></article>
      <article><span>正常用户</span><b>{{ stats?.activeUsers ?? '—' }}</b></article>
      <article><span>项目总数</span><b>{{ stats?.projectCount ?? '—' }}</b></article>
    </div>
    <section class="panel"><div class="panel-head"><h2>最近注册申请</h2><button @click="router.push({ name: 'admin-users', query: { status: 'PENDING' } })">查看全部</button></div>
      <div v-if="recent.length" class="recent-row" v-for="item in recent" :key="item.id"><span><b>{{ item.username }}</b><small>{{ item.displayName || '—' }}</small></span><time>{{ new Date(item.createdAt).toLocaleString() }}</time><em :class="item.status">{{ statusLabel(item.status) }}</em></div>
      <p v-else class="empty">暂无注册申请</p>
    </section>
  </div>
</template>
<style scoped>
.admin-page{max-width:1180px;margin:auto}header h1{margin:0 0 9px;font-size:27px}header p{margin:0;color:#8a98aa;font-size:14px}.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:18px;margin:28px 0}.stats article,.panel{border:1px solid #e6edf6;border-radius:10px;background:#fff;box-shadow:0 3px 14px #1f52960a}.stats article{padding:22px}.stats span{color:#718096;font-size:13px}.stats b{display:block;margin-top:12px;font-size:28px}.stats .pending{border-color:#f1dbb7;background:#fffcf6}.stats .pending b{color:#bd7a1b}.panel{padding:0 24px}.panel-head{display:flex;align-items:center;justify-content:space-between;height:64px;border-bottom:1px solid #edf1f6}.panel-head h2{font-size:17px}.panel-head button{border:0;color:#1677ff;background:transparent;cursor:pointer}.recent-row{display:grid;grid-template-columns:1fr 180px 80px;align-items:center;padding:15px 0;border-bottom:1px solid #f0f3f7;font-size:13px}.recent-row span b,.recent-row span small{display:block}.recent-row small,time{margin-top:4px;color:#98a2b3}.recent-row em{justify-self:end;padding:5px 9px;border-radius:5px;background:#eef2f6;color:#667085;font-style:normal}.recent-row em.PENDING{color:#b7791f;background:#fff6e5}.recent-row em.ACTIVE{color:#438566;background:#edf7f1}.empty{padding:32px;color:#98a2b3;text-align:center}@media(max-width:900px){.stats{grid-template-columns:repeat(2,1fr)}}@media(max-width:540px){.recent-row{grid-template-columns:1fr 70px}.recent-row time{display:none}}
</style>
