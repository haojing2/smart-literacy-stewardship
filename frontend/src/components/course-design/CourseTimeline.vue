<script setup lang="ts">
import { computed } from 'vue'

type CourseStep = {
  id: number
  title: string
}

const props = withDefaults(defineProps<{
  steps: CourseStep[]
  currentStep: number
  completedSteps?: number[]
}>(), {
  completedSteps: () => [],
})

const emit = defineEmits<{
  'step-change': [step: CourseStep]
}>()

const completedSet = computed(() => new Set(props.completedSteps))

function stepState(step: CourseStep) {
  if (step.id === props.currentStep) return 'active'
  if (completedSet.value.has(step.id)) return 'completed'
  return 'pending'
}

function isAvailable(step: CourseStep) {
  const lastCompletedStep = Math.max(0, ...props.completedSteps)
  return stepState(step) !== 'pending' || step.id <= lastCompletedStep + 1
}

function selectStep(step: CourseStep) {
  if (isAvailable(step)) emit('step-change', step)
}
</script>

<template>
  <nav class="course-timeline" aria-label="课程设计流程">
    <ol>
      <li v-for="(step, index) in steps" :key="step.id" :class="`is-${stepState(step)}`">
        <button
          type="button"
          :disabled="!isAvailable(step)"
          :aria-current="stepState(step) === 'active' ? 'step' : undefined"
          @click="selectStep(step)"
        >
          <span class="node" aria-hidden="true">{{ stepState(step) === 'completed' ? '✓' : step.id }}</span>
          <span class="step-copy"><strong>{{ step.title }}</strong><small v-if="stepState(step) === 'active'">当前</small></span>
        </button>
        <span v-if="index < steps.length - 1" class="connector" aria-hidden="true"></span>
      </li>
    </ol>
  </nav>
</template>

<style scoped>
.course-timeline { min-height: 108px; padding: 18px 24px 14px; border: 1px solid #eaecf0; border-radius: 12px; background: #fff; box-shadow: 0 2px 10px rgb(16 24 40 / 4%); }
ol { display: flex; align-items: flex-start; width: 100%; margin: 0; padding: 0; list-style: none; }
li { display: flex; min-width: 0; flex: 1; align-items: flex-start; }
button { display: flex; min-width: 0; flex: none; align-items: center; flex-direction: column; gap: 7px; border: 0; color: #98a2b3; background: transparent; cursor: pointer; font: inherit; }
button:disabled { cursor: not-allowed; }.node { display: grid; width: 30px; height: 30px; place-items: center; border: 1.5px solid #d0d5dd; border-radius: 50%; color: #98a2b3; background: #fff; font-size: 12px; font-weight: 650; transition: transform .18s ease, border-color .18s ease, background .18s ease; }
.step-copy { display: grid; gap: 2px; min-width: 0; text-align: center; }.step-copy strong { overflow: hidden; max-width: 82px; color: inherit; font-size: 13px; font-weight: 500; line-height: 1.3; text-overflow: ellipsis; white-space: nowrap; }.step-copy small { color: #1677ff; font-size: 11px; line-height: 1; }
.connector { height: 2px; min-width: 10px; flex: 1; margin: 14px 8px 0; border-radius: 999px; background: #eaecf0; }
.is-completed .node { border-color: #1677ff; color: #fff; background: #1677ff; }.is-completed .step-copy strong { color: #344054; font-weight: 600; }.is-completed .connector { background: #1677ff; }
.is-active .node { width: 36px; height: 36px; margin: -3px; border: 2px solid #1677ff; color: #1677ff; background: #edf5ff; box-shadow: 0 0 0 3px rgb(22 119 255 / 7%); }.is-active .step-copy strong { color: #1d2939; font-weight: 650; }.is-active .connector { margin-top: 14px; }
button:not(:disabled):hover .node { transform: translateY(-1px); }button:not(:disabled):hover .step-copy strong { color: #1677ff; }
@media (max-width: 1100px) { .course-timeline { padding-right: 14px; padding-left: 14px; }.connector { min-width: 4px; margin-right: 4px; margin-left: 4px; }.step-copy strong { max-width: 58px; font-size: 12px; white-space: normal; }.node { width: 28px; height: 28px; }.is-active .node { width: 32px; height: 32px; }.is-active .connector { margin-top: 13px; } }
</style>
