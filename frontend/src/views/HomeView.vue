<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import ProjectsContent from '@/components/ProjectsContent.vue'
import DashboardContent from '@/components/DashboardContent.vue'
import ResearchWorkbenchView from '@/views/research/ResearchWorkbenchView.vue'
import CourseDesign from '@/views/course-design/CourseDesign.vue'
import ResourceCreation from '@/views/resource-creation/ResourceCreation.vue'
import { getProjectWorkspaceRoute, type ProjectWorkspaceModule } from '@/utils/projectNavigation'
const router = useRouter()
const route = useRoute()
const sidebarCollapsed = ref(localStorage.getItem('sidebar-collapsed') === 'true')
const menuItems = [
  { name: '工作概览', icon: '▦' },
  { name: '我的项目', icon: '□' },
  { name: '研教智联', icon: '◌' },
  { name: '课程智设', icon: '▤' },
  { name: '资源智创', icon: '✦' },
]
const user = computed(() => JSON.parse(sessionStorage.getItem('current_user') ?? '{}'))
const roleLabel = computed(() => user.value.role === 'ADMIN' ? '管理员' : '普通用户')
const isResearchRoute = computed(() => ['project-research', 'research-no-project'].includes(String(route.name)))
const isCourseDesignRoute = computed(() => ['course-design', 'project-course-design'].includes(String(route.name)))
const isResourceCreationRoute = computed(() => ['resource-creation', 'project-resource-creation'].includes(String(route.name)))
const active = ref(isResearchRoute.value ? '研教智联' : isCourseDesignRoute.value ? '课程智设' : isResourceCreationRoute.value ? '资源智创' : '我的项目')
function logout() {
  sessionStorage.removeItem('access_token')
  sessionStorage.removeItem('current_user')
  router.replace({ name: 'logout' })
}
function selectMenu(name: string) {
  active.value = name
  const projectId = String(route.params.projectId || '')
  if (name === '我的项目') {
    if (route.path !== '/projects') void router.push('/projects')
    return
  }

  const moduleByMenuName: Record<string, ProjectWorkspaceModule> = {
    研教智联: 'research',
    课程智设: 'course-design',
    资源智创: 'resource-creation',
  }
  const module = moduleByMenuName[name]
  if (!module) return

  const destination = getProjectWorkspaceRoute(module, projectId)
  if (route.path !== destination) void router.push(destination)
}
function updateNavigationTooltips() {
  document.querySelectorAll<HTMLElement>('.sidebar nav button').forEach((button) => {
    button.title = sidebarCollapsed.value ? button.textContent?.trim() ?? '' : ''
  })
}
function toggleSidebar() {
  sidebarCollapsed.value = !sidebarCollapsed.value
  localStorage.setItem('sidebar-collapsed', String(sidebarCollapsed.value))
  nextTick(updateNavigationTooltips)
}
onMounted(updateNavigationTooltips)
watch(() => route.name, (name) => {
  if (name === 'project-research' || name === 'research-no-project') active.value = '研教智联'
  else if (name === 'course-design' || name === 'project-course-design') active.value = '课程智设'
  else if (name === 'resource-creation' || name === 'project-resource-creation') active.value = '资源智创'
  else if (name === 'home') active.value = '我的项目'
})
</script>

<template>
  <main class="workspace" :class="{ 'sidebar-is-collapsed': sidebarCollapsed }">
    <aside class="sidebar" :class="{ collapsed: sidebarCollapsed }">
      <div><div class="brand"><b>智</b><div><strong>智素领航</strong><small>教育管理平台</small></div></div>
        <button class="sidebar-toggle" :title="sidebarCollapsed ? '展开侧边栏' : '收起侧边栏'" :aria-label="sidebarCollapsed ? '展开侧边栏' : '收起侧边栏'" @click="toggleSidebar">
          <svg viewBox="0 0 18 18" aria-hidden="true"><rect x="1.5" y="2.5" width="15" height="13" rx="2" /><path d="M6 2.5v13" /></svg>
        </button>
        <nav><button v-for="item in menuItems" :key="item.name" :class="{active: active === item.name}" @click="selectMenu(item.name)"><span>{{ item.icon }}</span>{{ item.name }}</button></nav>
      </div>
      <div class="account-area">
        <div class="account"><i>{{ (user.display_name || user.username || '用').slice(0, 1) }}</i><div><strong>{{ user.display_name || user.username || '用户' }}</strong><small>{{ roleLabel }}</small></div><button title="退出登录" @click="logout">⇥</button></div>
        <button class="settings-button" title="系统设置" aria-label="系统设置" @click="active = '系统设置'"><span>⚙</span></button>
      </div>
    </aside>
    <ResearchWorkbenchView v-if="isResearchRoute" class="content" />
    <div v-else-if="isCourseDesignRoute" class="content course-design-content">
      <CourseDesign />
    </div>
    <div v-else-if="isResourceCreationRoute" class="content resource-creation-content">
      <ResourceCreation />
    </div>
    <DashboardContent v-else-if="active === '工作概览'" class="content" />
    <ProjectsContent v-else class="content" />
  </main>
</template>

<style scoped>
.workspace{min-height:100vh;color:#101828;background:#f7f9fc}.sidebar{position:fixed;display:flex;width:244px;height:100vh;flex-direction:column;justify-content:space-between;padding:27px 16px 22px;border-right:1px solid #eef1f5;background:#fff}.brand{display:flex;align-items:center;gap:10px;padding:0 10px}.brand>b{display:grid;width:35px;height:35px;place-items:center;border-radius:9px;color:#fff;background:#1677ff;font-size:17px}.brand strong,.brand small,.account strong,.account small{display:block}.brand strong{font-size:16px;letter-spacing:.04em}.brand small,.account small{margin-top:3px;color:#98a2b3;font-size:11px}nav{display:grid;gap:8px;margin-top:56px}nav button{display:flex;align-items:center;gap:13px;padding:11px 12px;border:0;border-radius:7px;color:#475467;background:transparent;font:inherit;font-size:14px;text-align:left;cursor:pointer}nav button:hover{color:#1677ff;background:#f2f7ff}nav button.active{color:#fff;background:#6ea8f0;box-shadow:0 3px 8px #1677ff1f}nav button span{width:18px;font-size:19px;text-align:center}.account{display:flex;align-items:center;gap:10px;padding:12px 8px;border-top:1px solid #f0f2f5}.account>i{display:grid;width:33px;height:33px;place-items:center;border-radius:50%;color:#3175cb;background:#eaf3ff;font-style:normal;font-weight:700}.account div{min-width:0;flex:1}.account strong{overflow:hidden;font-size:13px;text-overflow:ellipsis;white-space:nowrap}.account button{border:0;color:#98a2b3;background:none;font-size:22px;cursor:pointer}.account button:hover{color:#1677ff}.content{min-height:100vh;margin-left:244px;padding:34px 38px 42px}.content>header{display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:28px}.content header p{margin:0 0 11px;color:#98a2b3;font-size:13px}.content h1{margin:0;font-size:27px;font-weight:650}.content header span{display:block;margin-top:10px;color:#667085;font-size:14px}.actions{display:flex;align-items:center;gap:12px;padding-top:18px}.actions>button:not(.primary){display:grid;width:34px;height:34px;place-items:center;border:1px solid #eaecf0;border-radius:6px;color:#667085;background:#fff;font-size:16px;cursor:pointer}.primary,.filters button{height:36px;border-radius:6px;font:inherit;font-size:14px;cursor:pointer}.primary{padding:0 15px;border:1px solid #1677ff;color:#fff;background:#1677ff;box-shadow:0 2px 5px #1677ff26}.card{overflow:hidden;border:1px solid #eaecf0;border-radius:8px;background:#fff;box-shadow:0 2px 10px #1018280a}.filters{display:flex;align-items:center;gap:16px;padding:22px 24px;border-bottom:1px solid #edf0f3}.search,.select{display:flex;height:38px;align-items:center;border:1px solid #e3e7ed;border-radius:6px;color:#98a2b3;background:#fff}.search{width:min(368px,43vw);padding:0 11px;font-size:21px}.search input,.select select{width:100%;height:100%;border:0;outline:0;color:#344054;background:transparent;font:inherit;font-size:13px}.search input{padding-left:8px}.select{width:126px;padding:0 8px}.filters button{padding:0 14px;border:1px solid #e2e6ec;color:#475467;background:#fff}.table-wrap{overflow-x:auto}table{width:100%;min-width:850px;border-collapse:collapse}th{height:47px;padding:0 24px;color:#475467;background:#fafbfc;font-size:13px;font-weight:600;text-align:left}td{height:62px;padding:0 24px;border-bottom:1px solid #edf0f3;color:#344054;font-size:13px}tbody tr:hover{background:#fbfdff}.project{display:flex;align-items:center;gap:10px}.project i{display:grid;width:28px;height:28px;place-items:center;border-radius:6px;color:#4589e4;background:#edf5ff;font-style:normal;font-weight:700}.project b{color:#1d2939;font-weight:500}.muted{color:#667085}em{display:inline-flex;padding:4px 8px;border-radius:4px;font-size:12px;font-style:normal;line-height:1}em.进行中{color:#1677ff;background:#edf5ff}em.待开始{color:#b7791f;background:#fffaeb}em.已完成{color:#438566;background:#edf7f1}.op{text-align:right}.op a{margin-left:14px;color:#1677ff;cursor:pointer}.empty{height:190px;color:#98a2b3;text-align:center}footer{display:flex;align-items:center;justify-content:space-between;padding:18px 24px;color:#667085;font-size:13px}footer div{display:flex;gap:5px}footer button{display:grid;width:28px;height:28px;place-items:center;border:1px solid #e4e7ec;border-radius:5px;color:#475467;background:#fff;font:inherit;cursor:pointer}footer button.current{border-color:#1677ff;color:#fff;background:#1677ff}footer button:disabled{color:#c4cbd4;background:#fafbfc}@media(max-width:850px){.sidebar{width:70px;padding:22px 10px}.brand{justify-content:center;padding:0}.brand div,.account div,.account button{display:none}nav button{justify-content:center;padding:12px;font-size:0}nav button span{font-size:21px}.account{justify-content:center;padding:12px 0}.content{margin-left:70px;padding:28px 24px}}@media(max-width:620px){.content{padding:22px 16px}.content>header{display:block}.actions{padding-top:20px}.filters{flex-wrap:wrap;padding:17px}.search{width:100%}footer{padding:14px 17px}footer>span{display:none}}
/* Collapsible desktop sidebar */
.sidebar,
.content {
  transition: width .25s ease, margin-left .25s ease, padding .25s ease;
}
.sidebar-toggle {
  display: grid;
  width: 34px;
  height: 30px;
  margin: 14px 10px 0;
  place-items: center;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  color: #64748b;
  background: transparent;
  box-shadow: none;
  cursor: pointer;
  transition: color .2s ease, background .2s ease;
}
.sidebar-toggle svg { width: 18px; height: 18px; fill: none; stroke: currentColor; stroke-width: 1.5; stroke-linecap: round; stroke-linejoin: round; }
.sidebar-toggle:hover { color: #1677ff; background: #f2f7ff; }
.sidebar.collapsed { width: 70px; padding-right: 10px; padding-left: 10px; }
.sidebar.collapsed .brand { justify-content: center; padding: 0; }
.sidebar.collapsed .sidebar-toggle { margin-right: auto; margin-left: auto; }
.sidebar.collapsed .brand div,
.sidebar.collapsed .account div,
.sidebar.collapsed .account button { display: none; }
.sidebar.collapsed nav button { justify-content: center; padding: 12px; font-size: 0; }
.sidebar.collapsed nav button span { width: auto; font-size: 21px; }
.sidebar.collapsed .account { justify-content: center; padding: 12px 0; }
.sidebar.collapsed + .content { margin-left: 70px; }
.settings-button {
  display: grid;
  width: 34px;
  height: 30px;
  margin: 8px 8px 0;
  place-items: center;
  border: 0;
  border-radius: 6px;
  color: #64748b;
  background: transparent;
  cursor: pointer;
  font-size: 18px;
  transition: color .2s ease, background .2s ease;
}
.settings-button:hover { color: #1677ff; background: #f2f7ff; }
.sidebar.collapsed .settings-button { margin-right: auto; margin-left: auto; }

/* A fixed sidebar is outside normal flow, so reserve its exact width for content. */
.workspace { --sidebar-width: 244px; }
.workspace.sidebar-is-collapsed { --sidebar-width: 70px; }
.workspace .sidebar { width: var(--sidebar-width); }
.workspace .content {
  width: calc(100% - var(--sidebar-width));
  min-width: 0;
  margin-left: var(--sidebar-width);
}
@media (max-width: 850px) {
  .workspace { --sidebar-width: 70px; }
  .workspace .content { padding: 28px 24px; }
}
@media (max-width: 620px) {
  .workspace .content { padding: 22px 16px; }
}
</style>
