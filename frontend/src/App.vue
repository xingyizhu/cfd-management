<script setup>
import { computed, onMounted, reactive } from "vue";

const apiBase = import.meta.env.VITE_API_BASE_URL || "/api";
const jiraBaseUrl = import.meta.env.VITE_JIRA_BASE_URL || "";

function formatDate(date) {
  return date.toISOString().slice(0, 10);
}

function getWeekStart() {
  const today = new Date();
  const offset = (today.getDay() + 6) % 7;
  today.setDate(today.getDate() - offset);
  return formatDate(today);
}

function getToday() {
  return formatDate(new Date());
}

function secToHours(value) {
  return Number(((value || 0) / 3600).toFixed(2));
}

function buildIssueUrl(issueKey) {
  if (!jiraBaseUrl || !issueKey) {
    return "";
  }
  return `${jiraBaseUrl.replace(/\/$/, "")}/browse/${encodeURIComponent(issueKey)}`;
}

const state = reactive({
  filters: {
    dateFrom: getWeekStart(),
    dateTo: getToday(),
    forceRefresh: false
  },
  summary: null,
  entries: [],
  loading: false,
  syncing: false,
  sending: false,
  error: "",
  syncMessage: "",
  sendMessage: ""
});

const metrics = computed(() => {
  const rangeRows = state.summary?.range_rows || [];
  const underLogged = state.summary?.under_logged || [];
  const totalLoggedHours = rangeRows.reduce((sum, row) => sum + secToHours(row.logged_sec), 0);
  const totalEstimatedHours = rangeRows.reduce((sum, row) => sum + secToHours(row.estimated_sec), 0);

  return [
    {
      label: "成员数",
      value: rangeRows.length,
      note: "CFD 团队参与统计人数"
    },
    {
      label: "累计记录",
      value: `${totalLoggedHours.toFixed(2)} h`,
      note: "所选范围内的成员总工时"
    },
    {
      label: "累计预估",
      value: `${totalEstimatedHours.toFixed(2)} h`,
      note: "按成员去重后的预估总量"
    },
    {
      label: "风险成员",
      value: underLogged.length,
      note: "未达到范围目标工时的人数"
    }
  ];
});

const visibleEntries = computed(() => state.entries.slice(0, 80));

async function fetchJson(path, options = {}) {
  const response = await fetch(`${apiBase}${path}`, {
    headers: {
      "Content-Type": "application/json"
    },
    ...options
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed: ${response.status}`);
  }

  return response.json();
}

async function loadData() {
  state.loading = true;
  state.error = "";
  state.syncMessage = "";
  state.sendMessage = "";

  try {
    const query = `?dateFrom=${state.filters.dateFrom}&dateTo=${state.filters.dateTo}`;
    const [summary, entries] = await Promise.all([
      fetchJson(`/reports/summary${query}`),
      fetchJson(`/reports/entries${query}`)
    ]);
    state.summary = summary;
    state.entries = entries;
  } catch (error) {
    state.error = error instanceof Error ? error.message : String(error);
  } finally {
    state.loading = false;
  }
}

async function syncData() {
  state.syncing = true;
  state.error = "";
  state.syncMessage = "";

  try {
    const result = await fetchJson("/sync", {
      method: "POST",
      body: JSON.stringify({
        date_from: state.filters.dateFrom,
        date_to: state.filters.dateTo,
        force_refresh: state.filters.forceRefresh
      })
    });
    state.syncMessage = `同步完成：daily ${result.daily} / weekly ${result.weekly} / quarterly ${result.quarterly} / entries ${result.entries}`;
    await loadData();
  } catch (error) {
    state.error = error instanceof Error ? error.message : String(error);
  } finally {
    state.syncing = false;
  }
}

async function sendReminders() {
  state.sending = true;
  state.sendMessage = "";
  state.error = "";

  try {
    const query = `?dateFrom=${state.filters.dateFrom}&dateTo=${state.filters.dateTo}`;
    const result = await fetchJson(`/reminders/send${query}`, {
      method: "POST"
    });
    state.sendMessage = `发送完成：成功 ${result.sent.length} 封，跳过 ${result.skipped.length} 封`;
  } catch (error) {
    state.error = error instanceof Error ? error.message : String(error);
  } finally {
    state.sending = false;
  }
}

onMounted(loadData);
</script>

<template>
  <main class="page-shell">
    <section class="hero-panel">
      <div class="hero-copy">
        <p class="eyebrow">CFD Management Console</p>
        <h1>Worklog Command Deck</h1>
        <p class="hero-text">
          以区间视角查看 CFD 团队成员工时、周季聚合、风险提醒与 Jira 明细。
        </p>
      </div>
      <div class="hero-meta">
        <span class="meta-chip">数据源：Supabase 缓存</span>
        <span class="meta-chip">后端：Spring Boot</span>
        <span class="meta-chip">前端：Vue 3 + Vite</span>
      </div>
    </section>

    <section class="control-panel">
      <label>
        <span>开始日期</span>
        <input v-model="state.filters.dateFrom" type="date" />
      </label>
      <label>
        <span>结束日期</span>
        <input v-model="state.filters.dateTo" type="date" />
      </label>
      <label class="toggle">
        <input v-model="state.filters.forceRefresh" type="checkbox" />
        <span>强制回源 Jira</span>
      </label>
      <div class="action-row">
        <button :disabled="state.loading" class="ghost-button" @click="loadData">
          {{ state.loading ? "加载中..." : "查询报表" }}
        </button>
        <button :disabled="state.syncing" class="solid-button" @click="syncData">
          {{ state.syncing ? "同步中..." : "同步缓存" }}
        </button>
      </div>
    </section>

    <p v-if="state.error" class="status error">{{ state.error }}</p>
    <p v-if="state.syncMessage" class="status success">{{ state.syncMessage }}</p>
    <p v-if="state.sendMessage" class="status success">{{ state.sendMessage }}</p>

    <section v-if="state.summary" class="metric-grid">
      <article v-for="card in metrics" :key="card.label" class="metric-card">
        <p>{{ card.label }}</p>
        <strong>{{ card.value }}</strong>
        <span>{{ card.note }}</span>
      </article>
    </section>

    <section v-if="state.summary" class="content-grid">
      <article class="paper-card full">
        <div class="section-head">
          <div>
            <p class="section-kicker">Range Summary</p>
            <h2>区间成员汇总</h2>
          </div>
          <p class="section-note">
            {{ state.summary.meta.date_from }} 至 {{ state.summary.meta.date_to }}，
            工作日 {{ state.summary.meta.workday_count }} 天
          </p>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>成员</th>
                <th>已记录(h)</th>
                <th>预估(h)</th>
                <th>Issue 数</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in state.summary.range_rows" :key="row.account_id">
                <td>{{ row.display_name }}</td>
                <td>{{ secToHours(row.logged_sec).toFixed(2) }}</td>
                <td>{{ secToHours(row.estimated_sec).toFixed(2) }}</td>
                <td>{{ row.issue_count }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </article>

      <article class="paper-card">
        <div class="section-head compact">
          <div>
            <p class="section-kicker">Risk Desk</p>
            <h2>工时不足提醒</h2>
          </div>
          <button :disabled="state.sending || !state.summary.under_logged.length" class="solid-button small" @click="sendReminders">
            {{ state.sending ? "发送中..." : "发送提醒" }}
          </button>
        </div>
        <ul class="risk-list">
          <li v-for="member in state.summary.under_logged" :key="member.account_id">
            <strong>{{ member.name }}</strong>
            <span>已记录 {{ member.logged_hours.toFixed(2) }} h / 差 {{ member.missing_hours.toFixed(2) }} h</span>
          </li>
          <li v-if="!state.summary.under_logged.length" class="empty-inline">当前范围内无人低于目标工时。</li>
        </ul>
      </article>

      <article class="paper-card">
        <div class="section-head compact">
          <div>
            <p class="section-kicker">Today/Range</p>
            <h2>日维度</h2>
          </div>
          <p class="section-note">{{ state.summary.daily_rows.length }} 行</p>
        </div>
        <div class="table-wrap small">
          <table>
            <thead>
              <tr>
                <th>日期</th>
                <th>成员</th>
                <th>已记录(h)</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in state.summary.daily_rows.slice(0, 24)" :key="`${row.account_id}-${row.work_date}`">
                <td>{{ row.work_date }}</td>
                <td>{{ row.display_name }}</td>
                <td>{{ secToHours(row.logged_sec).toFixed(2) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </article>

      <article class="paper-card">
        <div class="section-head compact">
          <div>
            <p class="section-kicker">Weekly</p>
            <h2>周维度</h2>
          </div>
          <p class="section-note">{{ state.summary.meta.week_start }}</p>
        </div>
        <div class="table-wrap small">
          <table>
            <thead>
              <tr>
                <th>成员</th>
                <th>已记录(h)</th>
                <th>预估(h)</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in state.summary.weekly_rows" :key="`${row.account_id}-${row.week_start}`">
                <td>{{ row.display_name }}</td>
                <td>{{ secToHours(row.logged_sec).toFixed(2) }}</td>
                <td>{{ secToHours(row.estimated_sec).toFixed(2) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </article>

      <article class="paper-card">
        <div class="section-head compact">
          <div>
            <p class="section-kicker">Quarterly</p>
            <h2>季维度</h2>
          </div>
          <p class="section-note">{{ state.summary.meta.quarter_key }}</p>
        </div>
        <div class="table-wrap small">
          <table>
            <thead>
              <tr>
                <th>成员</th>
                <th>已记录(h)</th>
                <th>预估(h)</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in state.summary.quarterly_rows" :key="`${row.account_id}-${row.quarter_key}`">
                <td>{{ row.display_name }}</td>
                <td>{{ secToHours(row.logged_sec).toFixed(2) }}</td>
                <td>{{ secToHours(row.estimated_sec).toFixed(2) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </article>

      <article class="paper-card full">
        <div class="section-head">
          <div>
            <p class="section-kicker">Issue Entries</p>
            <h2>任务明细</h2>
          </div>
          <p class="section-note">当前展示前 80 条，按日期与 Issue 排序</p>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>日期</th>
                <th>成员</th>
                <th>Issue</th>
                <th>摘要</th>
                <th>状态</th>
                <th>预估(h)</th>
                <th>记录(h)</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="entry in visibleEntries" :key="`${entry.account_id}-${entry.work_date}-${entry.issue_key}`">
                <td>{{ entry.work_date }}</td>
                <td>{{ entry.display_name }}</td>
                <td>
                  <a v-if="buildIssueUrl(entry.issue_key)" :href="buildIssueUrl(entry.issue_key)" target="_blank" rel="noreferrer">
                    {{ entry.issue_key }}
                  </a>
                  <span v-else>{{ entry.issue_key }}</span>
                </td>
                <td>{{ entry.issue_summary }}</td>
                <td>{{ entry.status_name }}</td>
                <td>{{ secToHours(entry.estimated_sec).toFixed(2) }}</td>
                <td>{{ secToHours(entry.time_sec).toFixed(2) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </article>
    </section>
  </main>
</template>

<style scoped>
.page-shell {
  width: min(1400px, calc(100vw - 32px));
  margin: 0 auto;
  padding: 28px 0 48px;
}

.hero-panel {
  padding: 28px 30px;
  border: 1px solid var(--line);
  border-radius: 28px;
  background:
    radial-gradient(circle at top right, rgba(152, 95, 40, 0.16), transparent 28%),
    linear-gradient(145deg, rgba(255, 251, 245, 0.95), rgba(250, 242, 228, 0.88));
  box-shadow: var(--shadow);
}

.hero-copy h1 {
  margin: 0;
  font-size: clamp(2.4rem, 5vw, 4.5rem);
  line-height: 0.95;
  font-family: "DM Serif Display", serif;
  color: #2c2316;
}

.eyebrow,
.section-kicker {
  margin: 0 0 10px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  font-size: 0.78rem;
  color: var(--accent);
}

.hero-text {
  max-width: 720px;
  margin: 14px 0 0;
  color: var(--muted);
  font-size: 1.02rem;
}

.hero-meta {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 18px;
}

.meta-chip {
  border: 1px solid rgba(143, 78, 31, 0.22);
  border-radius: 999px;
  padding: 8px 14px;
  background: rgba(255, 249, 239, 0.84);
  color: #5b4020;
  font-size: 0.88rem;
}

.control-panel {
  margin-top: 20px;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
  padding: 18px;
  border-radius: 22px;
  background: var(--paper);
  border: 1px solid var(--line);
  box-shadow: var(--shadow);
}

.control-panel label {
  display: flex;
  flex-direction: column;
  gap: 8px;
  color: var(--muted);
  font-size: 0.9rem;
}

.control-panel input[type="date"] {
  border: 1px solid rgba(110, 83, 51, 0.18);
  background: #fffdf9;
  border-radius: 14px;
  padding: 12px 14px;
}

.toggle {
  justify-content: center;
  gap: 12px;
}

.toggle input {
  width: 18px;
  height: 18px;
}

.action-row {
  display: flex;
  align-items: flex-end;
  gap: 12px;
}

.solid-button,
.ghost-button {
  border: 0;
  border-radius: 14px;
  padding: 12px 16px;
  cursor: pointer;
  transition: transform 0.2s ease, opacity 0.2s ease;
}

.solid-button:hover,
.ghost-button:hover {
  transform: translateY(-1px);
}

.solid-button:disabled,
.ghost-button:disabled {
  cursor: wait;
  opacity: 0.7;
  transform: none;
}

.solid-button {
  background: linear-gradient(135deg, #6b3914, #9a5926);
  color: #fff8ef;
}

.ghost-button {
  background: #fffaf1;
  color: #603a1d;
  border: 1px solid rgba(143, 78, 31, 0.18);
}

.small {
  padding: 10px 14px;
}

.status {
  margin: 16px 0 0;
  padding: 12px 14px;
  border-radius: 14px;
  font-size: 0.92rem;
}

.error {
  background: rgba(165, 55, 27, 0.12);
  border: 1px solid rgba(165, 55, 27, 0.2);
  color: #8f311c;
}

.success {
  background: rgba(49, 108, 65, 0.1);
  border: 1px solid rgba(49, 108, 65, 0.18);
  color: #355d3f;
}

.metric-grid {
  margin-top: 20px;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}

.metric-card,
.paper-card {
  border: 1px solid var(--line);
  background: var(--paper);
  box-shadow: var(--shadow);
}

.metric-card {
  min-height: 160px;
  border-radius: 24px;
  padding: 22px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.metric-card p,
.metric-card span {
  margin: 0;
  color: var(--muted);
}

.metric-card strong {
  font-family: "DM Serif Display", serif;
  font-size: 2.4rem;
  color: var(--ink);
}

.content-grid {
  margin-top: 20px;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.paper-card {
  border-radius: 24px;
  padding: 22px;
}

.full {
  grid-column: 1 / -1;
}

.section-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 14px;
}

.section-head h2 {
  margin: 0;
  font-family: "DM Serif Display", serif;
  font-size: 2rem;
  color: #2f2618;
}

.compact h2 {
  font-size: 1.65rem;
}

.section-note {
  margin: 0;
  color: var(--muted);
  font-size: 0.92rem;
  text-align: right;
}

.risk-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.risk-list li {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  padding: 14px;
  border-radius: 16px;
  background: rgba(255, 250, 241, 0.82);
  border: 1px solid rgba(143, 78, 31, 0.12);
}

.risk-list strong {
  color: #2b2114;
}

.risk-list span,
.empty-inline {
  color: var(--muted);
}

.table-wrap {
  overflow: auto;
  border-radius: 18px;
  border: 1px solid rgba(120, 86, 38, 0.1);
}

.table-wrap.small {
  max-height: 420px;
}

table {
  width: 100%;
  border-collapse: collapse;
  background: rgba(255, 253, 249, 0.9);
}

th,
td {
  text-align: left;
  padding: 12px 14px;
  border-bottom: 1px solid rgba(120, 86, 38, 0.1);
  vertical-align: top;
}

thead th {
  position: sticky;
  top: 0;
  z-index: 1;
  background: #f4e8d7;
  color: #4f371f;
  font-size: 0.84rem;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

tbody tr:hover td {
  background: rgba(247, 235, 217, 0.72);
}

@media (max-width: 1100px) {
  .control-panel,
  .metric-grid,
  .content-grid {
    grid-template-columns: 1fr;
  }

  .action-row {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
