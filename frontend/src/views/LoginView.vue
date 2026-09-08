<script setup lang="ts">
import { useRouter } from 'vue-router'
import LoginForm from '@/components/LoginForm.vue'

const router = useRouter()

async function enterWorkspace() {
  await router.replace({ name: 'home' })
}
</script>

<template>
  <main class="login-page">
    <section class="brand-panel" aria-label="智素领航介绍">
      <div class="brand-content">
        <div class="brand-header">
          <span class="brand-mark">智</span>
          <span class="brand-name">智素领航</span>
        </div>
        <p class="eyebrow">SMART LITERACY STEWARDSHIP</p>
        <h1>面向学生 AI 素养发展的<br />信息技术学科智能教学平台</h1>
        <span class="title-accent"></span>
        <p class="brand-positioning">研究证据 × 智能设计 × 课堂实践</p>
        <p class="brand-copy">让研究证据进入课程，让课程进入课堂。</p>
      </div>

      <div class="education-visual" aria-hidden="true">
        <span class="visual-halo halo-one"></span>
        <span class="visual-halo halo-two"></span>
        <span class="visual-orbit"></span>
        <span class="visual-node node-one">AI</span>
        <span class="visual-node node-two">研</span>
        <span class="visual-node node-three">教</span>
        <div class="visual-card card-course"><b>课程设计</b><span>智能生成</span></div>
        <div class="visual-card card-evidence"><b>研究证据</b><span>可信依据</span></div>
      </div>
    </section>

    <section class="form-panel">
      <div class="login-card">
        <div class="card-heading">
          <h2>欢迎登录</h2>
          <p>登录智素领航，开始智能教学设计</p>
        </div>
        <LoginForm @success="enterWorkspace" />
        <p class="notice">账号信息由系统管理员维护</p>
      </div>
    </section>
  </main>
</template>

<style scoped>
.login-page {
  display: grid;
  grid-template-columns: minmax(520px, 55fr) minmax(420px, 45fr);
  min-height: 100vh;
  overflow: hidden;
  background: #fff;
}

.brand-panel {
  position: relative;
  display: flex;
  align-items: center;
  overflow: hidden;
  padding: clamp(56px, 8vw, 128px);
  background:
    radial-gradient(circle at 21% 10%, rgb(38 132 255 / 12%), transparent 25%),
    linear-gradient(135deg, #f7fbff 0%, #edf5ff 100%);
}

.brand-panel::before,
.brand-panel::after {
  position: absolute;
  border: 1px solid rgb(38 132 255 / 11%);
  border-radius: 50%;
  content: '';
}

.brand-panel::before { width: 720px; height: 720px; right: -400px; top: -330px; }
.brand-panel::after { width: 560px; height: 560px; left: -430px; bottom: -390px; }

.brand-content { position: relative; z-index: 2; max-width: 610px; }
.brand-header { display: flex; align-items: center; gap: 12px; margin-bottom: 50px; }
.brand-mark { display: grid; width: 42px; height: 42px; place-items: center; border-radius: 12px; color: #fff; background: linear-gradient(135deg, #2684ff, #1677ff); box-shadow: 0 8px 18px rgb(22 119 255 / 18%); font-size: 22px; font-weight: 700; }
.brand-name { color: #1f4f86; font-size: 20px; font-weight: 700; letter-spacing: .08em; }
.eyebrow { margin: 0 0 15px; color: #4d8fe9; font-size: 12px; font-weight: 700; letter-spacing: .13em; }
h1 { margin: 0; color: #1f2937; font-size: clamp(32px, 3.1vw, 42px); font-weight: 700; letter-spacing: .015em; line-height: 1.42; }
.title-accent { display: block; width: 48px; height: 4px; margin: 25px 0; border-radius: 5px; background: #2684ff; }
.brand-positioning { margin: 0 0 13px; color: #315675; font-size: 16px; font-weight: 650; letter-spacing: .05em; }
.brand-copy { margin: 0; color: #94a3b8; font-size: 15px; line-height: 1.8; }

.education-visual { position: absolute; z-index: 1; right: -52px; bottom: -30px; width: min(56vw, 660px); height: min(40vw, 500px); opacity: .8; pointer-events: none; }
.visual-halo { position: absolute; border-radius: 50%; background: rgb(38 132 255 / 8%); }.halo-one { width: 330px; height: 330px; right: 70px; bottom: 30px; }.halo-two { width: 220px; height: 220px; right: 128px; bottom: 86px; background: rgb(22 119 255 / 10%); }
.visual-orbit { position: absolute; width: 430px; height: 190px; right: 2px; bottom: 66px; border: 1px solid rgb(38 132 255 / 25%); border-radius: 50%; transform: rotate(-25deg); }
.visual-node { position: absolute; display: grid; width: 44px; height: 44px; place-items: center; border: 1px solid rgb(38 132 255 / 18%); border-radius: 50%; color: #2684ff; background: rgb(255 255 255 / 78%); box-shadow: 0 8px 22px rgb(40 104 186 / 8%); font-size: 13px; font-weight: 700; }.node-one { right: 133px; bottom: 236px; }.node-two { right: 373px; bottom: 121px; }.node-three { right: 32px; bottom: 71px; }
.visual-card { position: absolute; display: grid; gap: 5px; min-width: 108px; padding: 13px 16px; border: 1px solid rgb(255 255 255 / 86%); border-radius: 12px; color: #315675; background: rgb(255 255 255 / 75%); box-shadow: 0 10px 26px rgb(31 82 150 / 8%); }.visual-card b { font-size: 13px; }.visual-card span { color: #86a4c1; font-size: 11px; }.card-course { right: 186px; bottom: 78px; }.card-evidence { right: 50px; bottom: 181px; }

.form-panel { display: grid; padding: 40px; place-items: center; background: #fff; }
.login-card { width: min(100%, 400px); padding: 44px; border: 1px solid #edf3fa; border-radius: 16px; background: #fff; box-shadow: 0 12px 40px rgb(31 82 150 / 8%); }
.card-heading { margin-bottom: 31px; }.card-heading h2 { margin: 0 0 10px; color: #1f2937; font-size: 29px; font-weight: 700; letter-spacing: .01em; }.card-heading p { margin: 0; color: #94a3b8; font-size: 14px; }
.notice { margin: 24px 0 0; color: #a5b2c0; font-size: 12px; text-align: center; }

@media (max-width: 900px) { .login-page { grid-template-columns: minmax(380px, 1fr) minmax(370px, 1fr); }.brand-panel { padding: 52px; }.brand-header { margin-bottom: 34px; }.education-visual { right: -125px; bottom: -63px; width: 510px; height: 350px; }.login-card { padding: 40px 34px; } }
@media (max-width: 767px) { .login-page { display: block; overflow: auto; }.brand-panel { min-height: auto; padding: 32px 24px 30px; }.brand-header { margin-bottom: 26px; }.brand-mark { width: 36px; height: 36px; border-radius: 10px; font-size: 19px; }.brand-name { font-size: 18px; }.eyebrow, .education-visual { display: none; } h1 { font-size: clamp(24px, 7vw, 30px); }.title-accent { width: 36px; height: 3px; margin: 17px 0; }.brand-positioning { margin-bottom: 7px; font-size: 13px; }.brand-copy { font-size: 13px; }.form-panel { padding: 26px 20px 44px; }.login-card { width: min(100%, 400px); padding: 30px 24px; }.card-heading { margin-bottom: 26px; }.card-heading h2 { font-size: 26px; } }
</style>
