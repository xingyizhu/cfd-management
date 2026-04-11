<script setup lang="ts">
import { onMounted, computed, ref } from 'vue'
import { useWorklogStore } from '@/stores/worklog'
import MetricCard from '@/components/MetricCard.vue'
import CfdTable from '@/components/CfdTable.vue'
import DateRangePicker from '@/components/DateRangePicker.vue'
import { sendEmailReminders } from '@/api'
import type { WorklogRangeRow } from '@/types'

const store = useWorklogStore()

const forceRefresh = ref(false)
const emailEnabled = ref(false)
const emailSending = ref(false)
const emailResult = ref<{ sent: string[]; skipped: string[] } | null>(null)

onMounted(() => store.loadSummary())

const s2h = (sec: number | null | undefined) => ((sec ?? 0) / 3600).toFixed(2)

const memberCount = computed(() => store.rangeRows.length)
const totalHours = computed(() => store.rangeRows.reduce((acc, r) => acc + r.logged_sec / 3600, 0))
const avgHours = computed(() => memberCount.value ? (totalHours.value / memberCount.value).toFixed(2) : '0.00')
const requiredHours = computed(() => store.workdayCount * 7.5)
const okCount = computed(() => store.rangeRows.filter(r => r.logged_sec / 3600 >= requiredHours.value).length)
const okRate = computed(() => memberCount.value ? ((okCount.value / memberCount.value) * 100).toFixed(1) : '0.0')
const totalEstimated = computed(() => store.rangeRows.reduce((acc, r) => acc + r.estimated_sec / 3600, 0))

const tableColumns = ['成员', '已记录(h)', '预估(h)', 'Issue数', '目标(h)', '差值(h)', '达标']
const tableRows = computed(() =>
  store.rangeRows.map((r: WorklogRangeRow) => ({
    '成员': r.display_name,
    '已记录(h)': s2h(r.logged_sec),
    '预估(h)': s2h(r.estimated_sec),
    'Issue数': r.issue_count,
    '目标(h)': requiredHours.value.toFixed(2),
    '差值(h)': (r.logged_sec / 3600 - requiredHours.value).toFixed(2),
    '达标': r.logged_sec / 3600 >= requiredHours.value
  }))
)

const underLoggedColumns = ['成员', '已记录(h)', '目标(h)', '差值(h)']
const underLoggedRows = computed(() =>
  store.underLogged.map(m => ({
    '成员': m.name,
    '已记录(h)': m.logged_hours.toFixed(2),
    '目标(h)': m.required_hours.toFixed(2),
    '差值(h)': m.missing_hours.toFixed(2)
  }))
)

async function handleRefresh() {
  await store.sync(forceRefresh.value)
}

async function handleSendEmail() {
  if (!store.underLogged.length || !store.summary) return
  emailSending.value = true
  emailResult.value = null
  try {
    const result = await sendEmailReminders({
      underLogged: store.underLogged,
      context: {
        date_from: store.dateFrom,
        date_to: store.dateTo,
        workday_count: store.workdayCount,
        required_hours: requiredHours.value
      }
    })
    emailResult.value = result
  } finally {
    emailSending.value = false
  }
}
</script>

<template>
  <div class="dashboard">
    <!-- Hero -->
    <div class="hero-shell">
      <p class="hero-kicker">CFD Team Console</p>
      <h1 class="hero-title">工时范围看板</h1>
      <p class="hero-subtitle">按时间范围聚合成员工时，统一查看区间累计、风险成员与任务估时情况。</p>
      <div class="hero-chip-row" v-if="store.summary">
        <span class="hero-chip">{{ store.summary.cacheHit ? '🗄️ 数据库缓存' : '📋 Jira 实时同步' }}</span>
        <span class="hero-chip">📅 开始 {{ store.dateFrom }}</span>
        <span class="hero-chip">🗓️ 结束 {{ store.dateTo }}</span>
        <span class="hero-chip">🧮 工作日 {{ store.workdayCount }} 天</span>
      </div>
    </div>

    <!-- Controls -->
    <div class="controls-card">
      <DateRangePicker
        :model-value-from="store.dateFrom"
        :model-value-to="store.dateTo"
        @update:model-value-from="store.dateFrom = $event"
        @update:model-value-to="store.dateTo = $event"
      />
      <div class="control-actions">
        <label class="toggle-label">
          <input type="checkbox" v-model="forceRefresh" />
          强制重新拉取 Jira
        </label>
        <label class="toggle-label">
          <input type="checkbox" v-model="emailEnabled" />
          启用邮件提醒
        </label>
        <button class="btn-primary" @click="handleRefresh" :disabled="store.syncing || store.loading">
          {{ store.syncing ? '同步中...' : '🔧 刷新数据' }}
        </button>
        <button class="btn-secondary" @click="store.loadSummary" :disabled="store.loading">
          {{ store.loading ? '加载中...' : '读取缓存' }}
        </button>
      </div>
    </div>

    <!-- Error -->
    <div v-if="store.error" class="error-banner">⚠️ {{ store.error }}</div>

    <!-- Metrics Row 1 -->
    <div v-if="store.summary" class="metrics-grid">
      <MetricCard label="团队成员" :value="String(memberCount)" note="当前统计范围内成员数" />
      <MetricCard label="累计已记录" :value="totalHours.toFixed(2) + ' h'" note="所选时间范围总工时" />
      <MetricCard label="人均工时" :value="avgHours + ' h'" note="成员区间平均记录" />
      <MetricCard label="达标率" :value="okRate + '%'" :note="okCount + ' 人达到目标'" />
    </div>

    <!-- Metrics Row 2 -->
    <div v-if="store.summary" class="metrics-grid metrics-grid--3">
      <MetricCard label="目标总工时" :value="requiredHours.toFixed(2) + ' h'" :note="store.workdayCount + ' 个工作日'" />
      <MetricCard label="累计预估" :value="totalEstimated.toFixed(2) + ' h'" note="按区间内 Issue 去重" />
      <MetricCard label="待提醒成员" :value="String(store.underLogged.length)" :note="'阈值 ' + requiredHours.toFixed(2) + ' h'" />
    </div>

    <!-- Range Summary Table -->
    <template v-if="store.summary && store.rangeRows.length">
      <p class="section-title">工时范围汇总</p>
      <p class="section-desc">按成员展示所选时间范围内的累计工时、去重预估和达标状态。</p>
      <CfdTable :columns="tableColumns" :rows="tableRows" />
    </template>

    <!-- Under-logged -->
    <template v-if="store.summary">
      <div class="section-divider" />
      <p class="section-title">工时不足提醒</p>
      <p class="section-desc">按所选时间范围识别未达到目标工时的成员，并支持发送区间提醒邮件。</p>

      <div v-if="!store.underLogged.length" class="success-banner">
        ✅ 当前范围内所有成员都已达到目标工时。
      </div>
      <template v-else>
        <div class="warning-banner">
          ⚠️ 当前范围内工时不足 {{ requiredHours.toFixed(2) }}h 的成员，共 {{ store.underLogged.length }} 人。
        </div>
        <CfdTable :columns="underLoggedColumns" :rows="underLoggedRows" />

        <button
          v-if="emailEnabled"
          class="btn-primary"
          style="margin-top: 0.8rem"
          @click="handleSendEmail"
          :disabled="emailSending"
        >
          {{ emailSending ? '发送中...' : '📠 立即发送区间提醒邮件' }}
        </button>

        <div v-if="emailResult" class="success-banner" style="margin-top: 0.5rem">
          成功发送 {{ emailResult.sent.length }} 封邮件。
          <span v-if="emailResult.skipped.length">跳过：{{ emailResult.skipped.join('；') }}</span>
        </div>
      </template>
    </template>

    <!-- Empty state -->
    <div v-if="!store.loading && !store.summary" class="empty-state">
      请选择时间范围后点击"读取缓存"或"刷新数据"。
    </div>
  </div>
</template>

<style scoped>
.dashboard {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.hero-shell {
  border-radius: 20px;
  padding: 1.25rem 1.3rem 1.1rem;
  border: 1px solid var(--border);
  background:
    radial-gradient(circle at 78% -35%, rgba(109, 166, 255, 0.52), transparent 38%),
    linear-gradient(135deg, rgba(24, 40, 80, 0.86), rgba(9, 18, 40, 0.86));
  box-shadow: var(--shadow);
}

.hero-kicker {
  letter-spacing: 0.07em;
  font-size: 0.75rem;
  text-transform: uppercase;
  color: #b7dcff;
  font-weight: 600;
  margin-bottom: 0.45rem;
}

.hero-title {
  font-family: "Noto Serif SC", serif;
  font-size: 1.9rem;
  color: #f9fcff;
}

.hero-subtitle {
  margin: 0.4rem 0 0.8rem;
  color: var(--text-sub);
  font-size: 0.92rem;
}

.hero-chip-row {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.hero-chip {
  display: inline-flex;
  align-items: center;
  padding: 0.3rem 0.65rem;
  border-radius: 999px;
  border: 1px solid rgba(147, 178, 255, 0.35);
  background: rgba(13, 23, 47, 0.75);
  color: #dbe8ff;
  font-size: 0.8rem;
}

.controls-card {
  border-radius: 16px;
  padding: 1rem 1.1rem;
  border: 1px solid var(--border);
  background: rgba(12, 22, 46, 0.7);
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  align-items: flex-end;
}

.control-actions {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.toggle-label {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.88rem;
  color: var(--text-sub);
  cursor: pointer;
}

.btn-primary {
  padding: 0.45rem 1rem;
  border-radius: 10px;
  border: none;
  background: linear-gradient(135deg, #3b6bd4, #2250a8);
  color: #fff;
  font-size: 0.88rem;
  cursor: pointer;
  transition: opacity 0.15s;
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-secondary {
  padding: 0.45rem 1rem;
  border-radius: 10px;
  border: 1px solid rgba(147, 178, 255, 0.35);
  background: rgba(20, 35, 70, 0.72);
  color: #dce8ff;
  font-size: 0.88rem;
  cursor: pointer;
  transition: background 0.15s;
}

.btn-secondary:hover:not(:disabled) {
  background: rgba(56, 86, 146, 0.5);
}

.btn-secondary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 0.75rem;
}

.metrics-grid--3 {
  grid-template-columns: repeat(3, 1fr);
}

.section-title {
  font-size: 1.1rem;
  font-weight: 700;
  color: #f2f7ff;
}

.section-desc {
  color: var(--text-sub);
  font-size: 0.86rem;
  margin-top: 0.1rem;
}

.section-divider {
  border: none;
  border-top: 1px solid rgba(132, 161, 230, 0.18);
}

.error-banner {
  padding: 0.75rem 1rem;
  border-radius: 12px;
  border: 1px solid rgba(255, 120, 120, 0.4);
  background: rgba(80, 20, 20, 0.5);
  color: #ffb3b3;
  font-size: 0.9rem;
}

.success-banner {
  padding: 0.75rem 1rem;
  border-radius: 12px;
  border: 1px solid rgba(100, 220, 120, 0.4);
  background: rgba(20, 60, 30, 0.5);
  color: #a3f0b0;
  font-size: 0.9rem;
}

.warning-banner {
  padding: 0.75rem 1rem;
  border-radius: 12px;
  border: 1px solid rgba(255, 200, 80, 0.4);
  background: rgba(60, 45, 10, 0.5);
  color: #ffe0a0;
  font-size: 0.9rem;
}

.empty-state {
  text-align: center;
  color: var(--text-sub);
  font-size: 0.95rem;
  padding: 3rem;
}
</style>
