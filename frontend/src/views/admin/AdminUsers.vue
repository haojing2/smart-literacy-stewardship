<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { approveUser, disableUser, enableUser, getAdminUsers, rejectUser, type AdminUser, type UserStatus } from '@/api/admin'
const route = useRoute()
const router = useRouter()
const items = ref<AdminUser[]>([])
const total = ref(0)
const loading = ref(false)
const query = reactive<{ page: number; pageSize: number; status?: UserStatus; keyword: string }>({ page: 1, pageSize: 20, status: route.query.status as UserStatus | undefined, keyword: '' })
const tabs: { label: string; value?: UserStatus }[] = [{ label: '全部' }, { label: '待审批', value: 'PENDING' }, { label: '正常', value: 'ACTIVE' }, { label: '未通过', value: 'REJECTED' }, { label: '已停用', value: 'DISABLED' }]
const statusLabel = (value: UserStatus) => ({ PENDING: '待审批', ACTIVE: '正常', REJECTED: '未通过', DISABLED: '已停用' }[value])
async function load() {
  loading.value = true
  try {
    const { data } = await getAdminUsers({ page: query.page, pageSize: query.pageSize, status: query.status, keyword: query.keyword || undefined })
    items.value = data.data.items
    total.value = data.data.total
  } finally { loading.value = false }
}
function selectStatus(value?: UserStatus) {
  query.status = value
  query.page = 1
  router.replace({ query: value ? { status: value } : {} })
  load()
}
async function act(item: AdminUser, action: 'approve' | 'reject' | 'disable' | 'enable') {
  const config = {
    approve: ['确认通过该用户的注册申请吗？', '已通过注册申请', approveUser],
    reject: ['确认拒绝该用户的注册申请吗？', '已拒绝注册申请', rejectUser],
    disable: ['确认停用该用户账号吗？', '账号已停用', disableUser],
    enable: ['确认恢复该用户账号吗？', '账号已恢复', enableUser],
  } as const
  const [prompt, success, request] = config[action]
  await ElMessageBox.confirm(prompt, '操作确认', { type: 'warning', confirmButtonText: '确认', cancelButtonText: '取消' })
  await request(item.id)
  ElMessage.success(success)
  await load()
}
watch(() => route.query.status, value => {
  const next = value as UserStatus | undefined
  if (next !== query.status) { query.status = next; query.page = 1; load() }
})
onMounted(load)
</script>
<template>
  <div class="admin-users">
    <header><h1>用户管理</h1><p>审核注册申请并管理平台用户状态</p></header>
    <section class="panel">
      <div class="toolbar"><div class="tabs"><button v-for="tab in tabs" :key="tab.label" :class="{ active: query.status === tab.value }" @click="selectStatus(tab.value)">{{ tab.label }}</button></div><el-input v-model="query.keyword" clearable placeholder="搜索用户名或显示名称" @keyup.enter="query.page = 1; load()" /></div>
      <el-table v-loading="loading" :data="items">
        <el-table-column label="用户" prop="username" min-width="140" />
        <el-table-column label="显示名称" min-width="140"><template #default="{ row }">{{ row.displayName || '—' }}</template></el-table-column>
        <el-table-column label="注册时间" min-width="180"><template #default="{ row }">{{ new Date(row.createdAt).toLocaleString() }}</template></el-table-column>
        <el-table-column label="状态" width="100"><template #default="{ row }"><el-tag :class="'status-' + row.status" effect="light">{{ statusLabel(row.status) }}</el-tag></template></el-table-column>
        <el-table-column label="角色" width="100"><template #default="{ row }">{{ row.role === 'ADMIN' ? '管理员' : '普通用户' }}</template></el-table-column>
        <el-table-column label="操作" width="180" fixed="right"><template #default="{ row }">
          <template v-if="row.role !== 'ADMIN'">
            <el-button v-if="row.status === 'PENDING' || row.status === 'REJECTED'" link type="primary" @click="act(row, 'approve')">通过</el-button>
            <el-button v-if="row.status === 'PENDING'" link type="danger" @click="act(row, 'reject')">拒绝</el-button>
            <el-button v-if="row.status === 'ACTIVE'" link type="danger" @click="act(row, 'disable')">停用账号</el-button>
            <el-button v-if="row.status === 'DISABLED'" link type="primary" @click="act(row, 'enable')">恢复账号</el-button>
          </template>
          <span v-else class="protected">受保护</span>
        </template></el-table-column>
      </el-table>
      <el-pagination v-model:current-page="query.page" v-model:page-size="query.pageSize" layout="total, prev, pager, next" :total="total" @current-change="load" />
    </section>
  </div>
</template>
<style scoped>
.admin-users{max-width:1280px;margin:auto}header h1{margin:0 0 9px;font-size:27px}header p{margin:0;color:#8a98aa;font-size:14px}.panel{margin-top:28px;overflow:hidden;border:1px solid #e6edf6;border-radius:10px;background:#fff;box-shadow:0 3px 14px #1f52960a}.toolbar{display:flex;align-items:center;justify-content:space-between;gap:20px;padding:18px 22px;border-bottom:1px solid #edf1f6}.tabs{display:flex;gap:20px}.tabs button{padding:9px 1px;border:0;border-bottom:2px solid transparent;color:#718096;background:transparent;cursor:pointer;font:inherit}.tabs button.active{border-color:#1677ff;color:#1677ff;font-weight:600}.toolbar :deep(.el-input){width:260px}.panel :deep(.el-pagination){justify-content:flex-end;padding:18px 22px}.status-PENDING{color:#b7791f;background:#fff6e5;border-color:#f4dfbd}.status-ACTIVE{color:#438566;background:#edf7f1;border-color:#d3eadc}.status-REJECTED{color:#b45b5b;background:#fff2f2;border-color:#f3d6d6}.status-DISABLED{color:#667085;background:#f2f4f7;border-color:#e4e7ec}.protected{color:#98a2b3;font-size:13px}@media(max-width:850px){.toolbar{align-items:stretch;flex-direction:column}.tabs{overflow-x:auto}.toolbar :deep(.el-input){width:100%}}
</style>
