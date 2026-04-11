<script setup lang="ts">
defineProps<{
  label: string
  value: string
  note: string
}>()
</script>

<template>
  <div class="metric-card">
    <p class="metric-label">{{ label }}</p>
    <p class="metric-value">{{ value }}</p>
    <p class="metric-note">{{ note }}</p>
  </div>
</template>

<style scoped>
.metric-card {
  border-radius: 16px;
  padding: 0.85rem 0.92rem;
  border: 1px solid rgba(139, 170, 255, 0.28);
  background: linear-gradient(160deg, rgba(20, 35, 70, 0.84), rgba(10, 22, 46, 0.84));
  box-shadow: var(--shadow);
  min-height: 102px;
  position: relative;
  overflow: hidden;
}

.metric-card::after {
  content: "";
  position: absolute;
  inset: auto -24px -28px auto;
  width: 120px;
  height: 120px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(120, 171, 255, 0.26), transparent 64%);
}

.metric-label {
  color: #c5d5fb;
  font-size: 0.82rem;
  position: relative;
  z-index: 1;
}

.metric-value {
  margin: 0.32rem 0 0;
  font-size: 1.45rem;
  font-weight: 700;
  color: #ffffff;
  position: relative;
  z-index: 1;
}

.metric-note {
  margin: 0.3rem 0 0;
  color: #a4bbec;
  font-size: 0.76rem;
  position: relative;
  z-index: 1;
}
</style>
