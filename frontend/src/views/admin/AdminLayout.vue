<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
const route = useRoute()
const router = useRouter()
const user = computed(() => {
  try { return JSON.parse(sessionStorage.getItem('current_user') ?? '{}') } catch { return {} }
})
const menus = [
  { name: 'admin-dashboard', label: '管理概览', icon: '▦' },
  { name: 'admin-users', label: '用户管理', icon: '♙' },
  { name: 'admin-system', label: '系统状态', icon: '◌' },
]
function logout() {
  sessionStorage.removeItem('access_token')
  sessionStorage.removeItem('current_user')
  router.replace({ name: 'logout' })
}
</script>
<template>
  <main class="admin-shell">
    <aside>
      <div>
        <div class="brand"><b>智</b><div><strong>智素领航</strong><small>管理端</small></div></div>
        <nav><button v-for="item in menus" :key="item.name" :class="{ active: route.name === item.name }" @click="router.push({ name: item.name })"><i>{{ item.icon }}</i>{{ item.label }}</button></nav>
      </div>
      <div class="sidebar-bottom">
        <button class="teaching-link" @click="router.push('/projects')">进入教学平台</button>
        <div class="account"><i>{{ (user.display_name || user.username || '管').slice(0, 1) }}</i><div><strong>{{ user.display_name || user.username || '管理员' }}</strong><small>管理员</small></div><button title="退出登录" @click="logout">⇥</button></div>
      </div>
    </aside>
    <section class="admin-content"><router-view /></section>
  </main>
</template>
<style scoped>
.admin-shell{min-height:100vh;color:#1d2939;background:#f6f9fd}.admin-shell>aside{position:fixed;display:flex;width:224px;height:100vh;box-sizing:border-box;flex-direction:column;justify-content:space-between;padding:28px 16px 20px;border-right:1px solid #e8eef6;background:#fff}.brand{display:flex;align-items:center;gap:11px;padding:0 10px}.brand>b{display:grid;width:36px;height:36px;place-items:center;border-radius:9px;color:#fff;background:#1677ff}.brand strong,.brand small,.account strong,.account small{display:block}.brand small,.account small{margin-top:3px;color:#98a2b3;font-size:11px}nav{display:grid;gap:7px;margin-top:48px}nav button{display:flex;align-items:center;gap:12px;height:42px;padding:0 13px;border:0;border-radius:8px;color:#526174;background:transparent;cursor:pointer;font:inherit;text-align:left}nav button.active,nav button:hover{color:#1677ff;background:#edf5ff}nav i{width:18px;font-size:18px;font-style:normal;text-align:center}.teaching-link{width:100%;height:38px;margin-bottom:12px;border:1px solid #cfe1f7;border-radius:7px;color:#1677ff;background:#f7fbff;cursor:pointer}.account{display:flex;align-items:center;gap:9px;padding:13px 7px 0;border-top:1px solid #edf1f6}.account>i{display:grid;width:32px;height:32px;place-items:center;border-radius:50%;color:#1677ff;background:#eaf3ff;font-style:normal;font-weight:700}.account div{min-width:0;flex:1}.account strong{overflow:hidden;font-size:13px;text-overflow:ellipsis;white-space:nowrap}.account>button{border:0;color:#98a2b3;background:transparent;cursor:pointer;font-size:20px}.admin-content{min-height:100vh;margin-left:224px;padding:36px 40px;box-sizing:border-box}@media(max-width:720px){.admin-shell>aside{position:static;width:100%;height:auto}.admin-shell>aside>div:first-child{display:flex;align-items:center;justify-content:space-between}nav{display:flex;margin:0}.sidebar-bottom{display:none}.admin-content{margin-left:0;padding:24px 18px}}
</style>
