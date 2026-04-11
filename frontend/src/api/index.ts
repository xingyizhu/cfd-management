import axios from 'axios'
import type {
  TeamMember,
  RangeSummary,
  WorklogEntry,
  SyncRequest,
  SyncResult,
  EmailReminderRequest,
  EmailReminderResult,
  HolidayInfo
} from '@/types'

const api = axios.create({
  baseURL: '/api',
  timeout: 60000
})

// ── Team ──────────────────────────────────────────────────────────────────

export function fetchTeamMembers(): Promise<TeamMember[]> {
  return api.get<TeamMember[]>('/team/members').then(r => r.data)
}

// ── Worklog ───────────────────────────────────────────────────────────────

export function fetchRangeSummary(dateFrom: string, dateTo: string): Promise<RangeSummary> {
  return api.get<RangeSummary>('/worklog/range', { params: { dateFrom, dateTo } }).then(r => r.data)
}

export function fetchEntries(dateFrom: string, dateTo: string): Promise<WorklogEntry[]> {
  return api.get<WorklogEntry[]>('/worklog/entries', { params: { dateFrom, dateTo } }).then(r => r.data)
}

// ── Sync ──────────────────────────────────────────────────────────────────

export function triggerSync(req: SyncRequest): Promise<SyncResult> {
  return api.post<SyncResult>('/sync', req).then(r => r.data)
}

// ── Email ─────────────────────────────────────────────────────────────────

export function sendEmailReminders(req: EmailReminderRequest): Promise<EmailReminderResult> {
  return api.post<EmailReminderResult>('/email/remind', req).then(r => r.data)
}

// ── Holidays ──────────────────────────────────────────────────────────────

export function fetchHolidays(dateFrom: string, dateTo: string): Promise<HolidayInfo> {
  return api.get<HolidayInfo>('/holidays', { params: { dateFrom, dateTo } }).then(r => r.data)
}
