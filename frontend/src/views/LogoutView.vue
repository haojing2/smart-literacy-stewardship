<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()
</script>

<template>
  <main class="logout-page">
    <button class="brand" type="button" aria-label="返回平台首页" @click="router.push('/')">
      <img src="@/assets/images/icon2.png" alt="" />
      <span>智素领航</span>
    </button>

    <span class="orbit orbit-one" aria-hidden="true"></span>
    <span class="orbit orbit-two" aria-hidden="true"></span>

    <section class="logout-card" aria-labelledby="logout-title">
      <div class="success-icon" aria-hidden="true">✓</div>
      <h1 id="logout-title">已安全退出</h1>
      <p>您已退出当前账号，登录状态已安全结束。</p>
      <button class="login-button" type="button" @click="router.push('/login')">重新登录</button>
      <button class="home-button" type="button" @click="router.push('/')">返回平台首页</button>
    </section>
  </main>
</template>

<style scoped>
.logout-page {
  position: relative;
  display: grid;
  min-height: 100vh;
  overflow: hidden;
  place-items: center;
  background: linear-gradient(145deg, #fff 0%, #f7fbff 56%, #eef7ff 100%);
}

.brand {
  position: absolute;
  z-index: 1;
  top: 40px;
  left: 48px;
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 0;
  border: 0;
  color: #1677ff;
  background: transparent;
  cursor: pointer;
  font: inherit;
  font-size: 24px;
  font-weight: 700;
  letter-spacing: .08em;
}

.brand img { width: 37px; height: 37px; object-fit: contain; }
.orbit { position: absolute; border: 1px solid rgb(38 132 255 / 9%); border-radius: 50%; pointer-events: none; }
.orbit-one { width: 720px; height: 720px; right: -390px; top: -400px; }
.orbit-two { width: 550px; height: 550px; left: -355px; bottom: -385px; border-color: rgb(38 132 255 / 7%); }

.logout-card {
  position: relative;
  z-index: 1;
  width: min(calc(100vw - 40px), 400px);
  margin-top: -7vh;
  padding: 42px 40px 34px;
  border: 1px solid #e6eef8;
  border-radius: 19px;
  background: #fff;
  box-shadow: 0 12px 32px rgb(31 82 150 / 8%);
  text-align: center;
}

.success-icon {
  display: grid;
  width: 64px;
  height: 64px;
  margin: 0 auto 23px;
  place-items: center;
  border-radius: 50%;
  color: #1677ff;
  background: #eaf4ff;
  font-size: 34px;
  font-weight: 600;
}

h1 { margin: 0 0 13px; color: #1f3550; font-size: 28px; font-weight: 650; letter-spacing: .01em; }
p { margin: 0 0 29px; color: #7d8da6; font-size: 15px; line-height: 1.7; }
.login-button { width: min(100%, 280px); height: 46px; border: 0; border-radius: 9px; color: #fff; background: #1677ff; box-shadow: 0 6px 14px rgb(22 119 255 / 16%); cursor: pointer; font: inherit; font-size: 15px; font-weight: 600; }
.login-button:hover { background: #126ae4; }
.home-button { display: block; margin: 18px auto 0; padding: 4px; border: 0; color: #5087c6; background: transparent; cursor: pointer; font: inherit; font-size: 14px; }
.home-button:hover { color: #1677ff; }

@media (max-width: 767px) {
  .brand { top: 28px; left: 24px; font-size: 22px; }
  .brand img { width: 33px; height: 33px; }
  .logout-card { margin-top: -3vh; padding: 38px 26px 30px; }
}
</style>
