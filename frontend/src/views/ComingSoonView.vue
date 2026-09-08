<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()
</script>

<template>
  <main class="coming-soon-page">
    <section>
      <p>项目设计流程</p>
      <h1>功能开发中</h1>
      <span>该项目的下一步能力即将开放，当前项目信息已安全保存。</span>
      <el-button type="primary" @click="router.push('/projects')">返回我的项目</el-button>
    </section>
  </main>
</template>

<style scoped>
.coming-soon-page { display: grid; min-height: 100vh; padding: 24px; place-items: center; color: #101828; background: #f7f9fc; }.coming-soon-page section { width: min(100%, 480px); padding: 48px; border: 1px solid #eaecf0; border-radius: 10px; background: #fff; box-shadow: 0 2px 12px rgb(16 24 40 / 5%); text-align: center; }.coming-soon-page p { margin: 0 0 14px; color: #1677ff; font-size: 14px; font-weight: 600; }.coming-soon-page h1 { margin: 0; font-size: 27px; }.coming-soon-page span { display: block; margin: 14px 0 26px; color: #667085; font-size: 14px; line-height: 1.7; }
</style>
