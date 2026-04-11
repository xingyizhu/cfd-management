<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  modelValueFrom: string
  modelValueTo: string
}>()

const emit = defineEmits<{
  'update:modelValueFrom': [val: string]
  'update:modelValueTo': [val: string]
}>()

const today = new Date().toISOString().slice(0, 10)

const mondayOfThisWeek = computed(() => {
  const d = new Date()
  d.setDate(d.getDate() - d.getDay() + 1)
  return d.toISOString().slice(0, 10)
})

const quarterStart = computed(() => {
  const now = new Date()
  const month = now.getMonth()
  const qMonth = Math.floor(month / 3) * 3
  return new Date(now.getFullYear(), qMonth, 1).toISOString().slice(0, 10)
})

function setThisWeek() {
  emit('update:modelValueFrom', mondayOfThisWeek.value)
  emit('update:modelValueTo', today)
}

function setThisQuarter() {
  emit('update:modelValueFrom', quarterStart.value)
  emit('update:modelValueTo', today)
}
</script>

<template>
  <div class="date-range-picker">
    <div class="quick-btns">
      <button class="quick-btn" @click="setThisWeek">当周</button>
      <button class="quick-btn" @click="setThisQuarter">当季度</button>
    </div>
    <div class="date-inputs">
      <div class="date-field">
        <label>开始日期</label>
        <input
          type="date"
          :value="modelValueFrom"
          :max="today"
          @input="emit('update:modelValueFrom', ($event.target as HTMLInputElement).value)"
        />
      </div>
      <span class="separator">至</span>
      <div class="date-field">
        <label>结束日期</label>
        <input
          type="date"
          :value="modelValueTo"
          :max="today"
          @input="emit('update:modelValueTo', ($event.target as HTMLInputElement).value)"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.date-range-picker {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.quick-btns {
  display: flex;
  gap: 0.5rem;
}

.quick-btn {
  padding: 0.3rem 0.8rem;
  border-radius: 8px;
  border: 1px solid rgba(147, 178, 255, 0.35);
  background: rgba(20, 35, 70, 0.72);
  color: #dce8ff;
  font-size: 0.85rem;
  cursor: pointer;
  transition: background 0.15s;
}

.quick-btn:hover {
  background: rgba(56, 86, 146, 0.5);
}

.date-inputs {
  display: flex;
  align-items: flex-end;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.date-field {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.date-field label {
  font-size: 0.78rem;
  color: var(--text-sub);
}

.date-field input {
  padding: 0.4rem 0.6rem;
  border-radius: 8px;
  border: 1px solid rgba(147, 178, 255, 0.35);
  background: rgba(9, 19, 40, 0.7);
  color: var(--text-main);
  font-size: 0.9rem;
  font-family: inherit;
}

.separator {
  color: var(--text-sub);
  font-size: 0.85rem;
  padding-bottom: 0.4rem;
}
</style>
