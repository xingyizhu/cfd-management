<script setup lang="ts">
defineProps<{
  columns: string[]
  rows: Record<string, any>[]
  issueKeyCol?: string
  cloudUrl?: string
}>()

function buildIssueUrl(issueKey: string, cloudUrl?: string): string {
  if (!cloudUrl || !issueKey) return ''
  return `${cloudUrl.replace(/\/$/, '')}/browse/${encodeURIComponent(issueKey)}`
}

function s2h(sec: number | undefined | null): string {
  return ((sec ?? 0) / 3600).toFixed(2)
}
</script>

<template>
  <div class="table-shell">
    <table class="cfd-table">
      <thead>
        <tr>
          <th v-for="col in columns" :key="col">{{ col }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(row, i) in rows" :key="i">
          <td v-for="col in columns" :key="col">
            <template v-if="col === '达标'">
              {{ row[col] ? '是' : '否' }}
            </template>
            <template v-else-if="issueKeyCol && col === issueKeyCol">
              <a
                v-if="buildIssueUrl(row[col], cloudUrl)"
                :href="buildIssueUrl(row[col], cloudUrl)"
                target="_blank"
                rel="noopener noreferrer"
              >{{ row[col] }}</a>
              <span v-else>{{ row[col] }}</span>
            </template>
            <template v-else>{{ row[col] }}</template>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.table-shell {
  width: 100%;
  overflow-x: auto;
  border: 1px solid rgba(143, 173, 253, 0.26);
  border-radius: 14px;
  background: rgba(9, 19, 40, 0.84);
  box-shadow: var(--shadow);
  margin-bottom: 0.42rem;
}

.cfd-table {
  width: 100%;
  border-collapse: collapse;
  color: var(--text-main);
  background: transparent;
  font-size: 0.9rem;
}

.cfd-table thead th {
  background: rgba(22, 40, 76, 0.86);
  color: #d9e7ff;
  font-weight: 600;
  border-bottom: 1px solid rgba(130, 161, 230, 0.3);
  padding: 0.62rem 0.75rem;
  white-space: nowrap;
  text-align: left;
}

.cfd-table tbody td {
  border-bottom: 1px solid rgba(115, 144, 210, 0.18);
  padding: 0.54rem 0.75rem;
  white-space: nowrap;
  color: #e8efff;
}

.cfd-table tbody tr:hover td {
  background: rgba(56, 86, 146, 0.22);
}

.cfd-table a {
  color: #8fd3ff;
}
</style>
