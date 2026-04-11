// ── Team ──────────────────────────────────────────────────────────────────

export interface TeamMember {
  accountId: string
  displayName: string
  emailAddress: string
  active: boolean
}

// ── Worklog ───────────────────────────────────────────────────────────────

export interface WorklogRangeRow {
  account_id: string
  display_name: string
  logged_sec: number
  estimated_sec: number
  issue_count: number
  issue_keys: string[]
}

export interface WorklogEntry {
  account_id: string
  display_name: string
  work_date: string
  issue_key: string
  issue_summary: string
  time_sec: number
  estimated_sec: number
  project_key: string
  project_name: string
  status_name: string
}

export interface RangeMeta {
  date_from: string
  date_to: string
  workday_count: number
}

export interface UnderLoggedMember {
  accountId: string
  name: string
  logged_hours: number
  required_hours: number
  missing_hours: number
}

export interface RangeSummary {
  meta: RangeMeta
  rangeRows: WorklogRangeRow[]
  underLogged: UnderLoggedMember[]
  cacheHit: boolean
}

// ── Sync ──────────────────────────────────────────────────────────────────

export interface SyncRequest {
  dateFrom: string
  dateTo: string
  forceRefresh?: boolean
}

export interface SyncResult {
  entries: number
  daily: number
  weekly: number
  quarterly: number
}

// ── Email ─────────────────────────────────────────────────────────────────

export interface EmailReminderRequest {
  underLogged: UnderLoggedMember[]
  context: {
    date_from: string
    date_to: string
    workday_count: number
    required_hours: number
  }
}

export interface EmailReminderResult {
  sent: string[]
  skipped: string[]
  sent_count: number
}

// ── Holidays ──────────────────────────────────────────────────────────────

export interface HolidayInfo {
  holidays: string[]
  workdays: string[]
  workday_count: number
}

// ── Estimate board ────────────────────────────────────────────────────────

export interface EstimateEntry {
  account_id: string
  display_name: string
  issue_key: string
  issue_summary: string
  estimated_sec: number
  time_sec: number
}
