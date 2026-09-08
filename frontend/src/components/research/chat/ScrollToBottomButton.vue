<script setup lang="ts">
defineProps<{ visible: boolean; newCount?: number }>()
defineEmits<{ click: [] }>()
</script>

<template>
  <Transition name="scroll-button">
    <button
      v-if="visible"
      type="button"
      class="scroll-to-bottom-button"
      title="回到最新消息"
      aria-label="平滑滚动到最新消息"
      @click="$emit('click')"
    >
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14m7-7-7 7-7-7" /></svg>
      <span v-if="newCount" class="new-count">{{ newCount }}</span>
    </button>
  </Transition>
</template>

<style scoped>
.scroll-to-bottom-button { position: absolute; top: -56px; left: 50%; z-index: 6; display: grid; width: 40px; height: 40px; padding: 0; place-items: center; border: 1px solid #e5e7eb; border-radius: 50%; color: #475569; background: #fff; box-shadow: 0 4px 14px rgb(15 23 42 / 10%); cursor: pointer; transform: translateX(-50%); }
.scroll-to-bottom-button:hover { color: #2563eb; background: #f8fafc; }.scroll-to-bottom-button:active { background: #f1f5f9; }
.scroll-to-bottom-button svg { width: 19px; height: 19px; fill: none; stroke: currentColor; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }
.new-count { position: absolute; top: -4px; right: -4px; display: grid; min-width: 17px; height: 17px; padding: 0 4px; place-items: center; border: 2px solid #fff; border-radius: 9px; color: #fff; background: #6b9fe6; font-size: 9px; }
.scroll-button-enter-active, .scroll-button-leave-active { transition: opacity .16s ease, transform .16s ease; }
.scroll-button-enter-from, .scroll-button-leave-to { opacity: 0; transform: translate(-50%, 7px); }
@media (prefers-reduced-motion: reduce) { .scroll-button-enter-active, .scroll-button-leave-active { transition: none; } }
</style>
