import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { fetchRangeSummary, triggerSync, fetchEntries } from '@/api'
import type { RangeSummary, WorklogEntry, SyncResult } from '@/types'

export const useWorklogStore = defineStore('worklog', () => {
  const today = new Date().toISOString().slice(0, 10)
  const mondayOfThisWeek = (() => {
    const d = new Date()
    d.setDate(d.getDate() - d.getDay() + 1)
    return d.toISOString().slice(0, 10)
  })()

  const dateFrom = ref<string>(mondayOfThisWeek)
  const dateTo = ref<string>(today)

  const summary = ref<RangeSummary | null>(null)
  const entries = ref<WorklogEntry[]>([])
  const loading = ref(false)
  const syncing = ref(false)
  const error = ref<string | null>(null)

  const workdayCount = computed(() => summary.value?.meta.workday_count ?? 0)
  const rangeRows = computed(() => summary.value?.rangeRows ?? [])
  const underLogged = computed(() => summary.value?.underLogged ?? [])

  async function loadSummary() {
    loading.value = true
    error.value = null
    try {
      summary.value = await fetchRangeSummary(dateFrom.value, dateTo.value)
    } catch (e: any) {
      error.value = e.message ?? '加载失败'
    } finally {
      loading.value = false
    }
  }

  async function loadEntries() {
    loading.value = true
    error.value = null
    try {
      entries.value = await fetchEntries(dateFrom.value, dateTo.value)
    } catch (e: any) {
      error.value = e.message ?? '加载失败'
    } finally {
      loading.value = false
    }
  }

  async function sync(forceRefresh = false): Promise<SyncResult | null> {
    syncing.value = true
    error.value = null
    try {
      const result = await triggerSync({ dateFrom: dateFrom.value, dateTo: dateTo.value, forceRefresh })
      await loadSummary()
      return result
    } catch (e: any) {
      error.value = e.message ?? '同步失败'
      return null
    } finally {
      syncing.value = false
    }
  }

  function setDateRange(from: string, to: string) {
    dateFrom.value = from
    dateTo.value = to
    summary.value = null
    entries.value = []
  }

  return {
    dateFrom, dateTo,
    summary, entries,
    loading, syncing, error,
    workdayCount, rangeRows, underLogged,
    loadSummary, loadEntries, sync, setDateRange
  }
})
