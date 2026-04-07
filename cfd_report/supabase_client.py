from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import requests

from .config import Config
from .holidays import get_cn_holidays, is_workday


def _headers(cfg: Config) -> dict[str, str]:
    return {
        "apikey": cfg.supabase_anon_key,
        "Authorization": f"Bearer {cfg.supabase_anon_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _upsert_headers(cfg: Config) -> dict[str, str]:
    headers = _headers(cfg)
    headers["Prefer"] = "resolution=merge-duplicates,return=minimal"
    return headers


def _delete_headers(cfg: Config) -> dict[str, str]:
    headers = _headers(cfg)
    headers["Prefer"] = "return=minimal"
    return headers


def _quarter_key(target_date: date) -> str:
    return f"{target_date.year}-Q{(target_date.month - 1) // 3 + 1}"


def _week_starts_in_range(date_from: str, date_to: str) -> list[str]:
    start_date = date.fromisoformat(date_from)
    end_date = date.fromisoformat(date_to)
    if start_date > end_date:
        return []

    current = start_date - timedelta(days=start_date.weekday())
    week_starts: list[str] = []
    while current <= end_date:
        week_starts.append(current.isoformat())
        current += timedelta(days=7)
    return week_starts


def _delete_with_filters(
    cfg: Config,
    table: str,
    filters: list[tuple[str, str]],
) -> None:
    if not filters:
        return

    url = f"{cfg.supabase_url}/rest/v1/{table}"
    response = requests.delete(
        url,
        params=filters,
        headers=_delete_headers(cfg),
        timeout=20,
    )
    response.raise_for_status()


def check_cache(cfg: Config, target_date: date) -> dict[str, bool]:
    """Check whether Supabase already has target daily/weekly/quarterly rows."""
    today = target_date.isoformat()
    week = (target_date - timedelta(days=target_date.weekday())).isoformat()
    qkey = _quarter_key(target_date)

    results: dict[str, bool] = {}
    for table, param in [
        ("worklog_daily", f"work_date=eq.{today}"),
        ("worklog_weekly", f"week_start=eq.{week}"),
        ("worklog_quarterly", f"quarter_key=eq.{qkey}"),
    ]:
        try:
            url = f"{cfg.supabase_url}/rest/v1/{table}?{param}&limit=1"
            response = requests.get(url, headers=_headers(cfg), timeout=10)
            response.raise_for_status()
            results[table.replace("worklog_", "")] = len(response.json()) > 0
        except Exception:
            results[table.replace("worklog_", "")] = False
    return results


def check_entries_cache(cfg: Config, work_date: str) -> bool:
    """Check whether worklog_entries already has rows for the target date."""
    try:
        url = f"{cfg.supabase_url}/rest/v1/worklog_entries?work_date=eq.{work_date}&limit=1"
        response = requests.get(url, headers=_headers(cfg), timeout=10)
        response.raise_for_status()
        return len(response.json()) > 0
    except Exception:
        return False


def check_daily_range_cache(cfg: Config, date_from: str, date_to: str) -> bool:
    """Check whether all workdays in the range exist in worklog_daily."""
    start_date = date.fromisoformat(date_from)
    end_date = date.fromisoformat(date_to)
    if start_date > end_date:
        start_date, end_date = end_date, start_date

    holidays: set[str] = set()
    for year in range(start_date.year, end_date.year + 1):
        holidays.update(get_cn_holidays(year))

    expected_dates: set[str] = set()
    current = start_date
    while current <= end_date:
        current_str = current.isoformat()
        if is_workday(current_str, holidays):
            expected_dates.add(current_str)
        current += timedelta(days=1)

    if not expected_dates:
        return True

    try:
        url = (
            f"{cfg.supabase_url}/rest/v1/worklog_daily"
            f"?select=work_date"
            f"&work_date=gte.{start_date.isoformat()}"
            f"&work_date=lte.{end_date.isoformat()}"
            f"&limit=5000"
        )
        response = requests.get(url, headers=_headers(cfg), timeout=15)
        response.raise_for_status()
        cached_dates = {row.get("work_date") for row in response.json() if row.get("work_date")}
        return expected_dates.issubset(cached_dates)
    except Exception:
        return False


def check_entries_range_cache(cfg: Config, date_from: str, date_to: str) -> bool:
    """Check whether worklog_entries is readable for the target range."""
    try:
        url = (
            f"{cfg.supabase_url}/rest/v1/worklog_entries"
            f"?select=work_date"
            f"&work_date=gte.{date_from}"
            f"&work_date=lte.{date_to}"
            f"&limit=1"
        )
        response = requests.get(url, headers=_headers(cfg), timeout=15)
        response.raise_for_status()
        return True
    except Exception:
        return False


def upsert_rows(cfg: Config, table: str, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0

    conflict_keys = {
        "worklog_daily": "account_id,work_date",
        "worklog_weekly": "account_id,week_start",
        "worklog_quarterly": "account_id,quarter_key",
    }
    url = f"{cfg.supabase_url}/rest/v1/{table}"
    params = {"on_conflict": conflict_keys[table]} if table in conflict_keys else None
    response = requests.post(
        url,
        params=params,
        json=rows,
        headers=_upsert_headers(cfg),
        timeout=20,
    )
    response.raise_for_status()
    return len(rows)


def upsert_entry_rows(cfg: Config, rows: list[dict[str, Any]]) -> int:
    """Upsert worklog_entries rows."""
    if not rows:
        return 0

    url = f"{cfg.supabase_url}/rest/v1/worklog_entries"
    response = requests.post(
        url,
        params={"on_conflict": "account_id,work_date,issue_key"},
        json=rows,
        headers=_upsert_headers(cfg),
        timeout=20,
    )
    response.raise_for_status()
    return len(rows)


def replace_sync_window_rows(
    cfg: Config,
    *,
    date_from: str,
    date_to: str,
    quarter_key: str,
    daily_rows: list[dict[str, Any]],
    weekly_rows: list[dict[str, Any]],
    quarterly_rows: list[dict[str, Any]],
    entry_rows: list[dict[str, Any]],
) -> dict[str, int]:
    """Replace all rows in the sync window so Supabase matches Jira exactly."""
    week_starts = _week_starts_in_range(date_from, date_to)

    _delete_with_filters(
        cfg,
        "worklog_entries",
        [("work_date", f"gte.{date_from}"), ("work_date", f"lte.{date_to}")],
    )
    _delete_with_filters(
        cfg,
        "worklog_daily",
        [("work_date", f"gte.{date_from}"), ("work_date", f"lte.{date_to}")],
    )
    if week_starts:
        _delete_with_filters(
            cfg,
            "worklog_weekly",
            [("week_start", f"in.({','.join(week_starts)})")],
        )
    _delete_with_filters(
        cfg,
        "worklog_quarterly",
        [("quarter_key", f"eq.{quarter_key}")],
    )

    return {
        "entries": upsert_entry_rows(cfg, entry_rows),
        "daily": upsert_rows(cfg, "worklog_daily", daily_rows),
        "weekly": upsert_rows(cfg, "worklog_weekly", weekly_rows),
        "quarterly": upsert_rows(cfg, "worklog_quarterly", quarterly_rows),
    }


def replace_range_window_rows(
    cfg: Config,
    *,
    date_from: str,
    date_to: str,
    daily_rows: list[dict[str, Any]],
    entry_rows: list[dict[str, Any]],
) -> dict[str, int]:
    """Replace daily and entry rows in a custom date range."""
    _delete_with_filters(
        cfg,
        "worklog_entries",
        [("work_date", f"gte.{date_from}"), ("work_date", f"lte.{date_to}")],
    )
    _delete_with_filters(
        cfg,
        "worklog_daily",
        [("work_date", f"gte.{date_from}"), ("work_date", f"lte.{date_to}")],
    )

    return {
        "entries": upsert_entry_rows(cfg, entry_rows),
        "daily": upsert_rows(cfg, "worklog_daily", daily_rows),
    }


def fetch_daily(cfg: Config, work_date: str) -> list[dict[str, Any]]:
    url = f"{cfg.supabase_url}/rest/v1/worklog_daily?work_date=eq.{work_date}&order=display_name"
    response = requests.get(url, headers=_headers(cfg), timeout=10)
    response.raise_for_status()
    return response.json()


def fetch_daily_range(cfg: Config, date_from: str, date_to: str) -> list[dict[str, Any]]:
    url = (
        f"{cfg.supabase_url}/rest/v1/worklog_daily"
        f"?work_date=gte.{date_from}"
        f"&work_date=lte.{date_to}"
        f"&order=work_date.asc,display_name.asc"
        f"&limit=5000"
    )
    response = requests.get(url, headers=_headers(cfg), timeout=15)
    response.raise_for_status()
    return response.json()


def fetch_entries_range(cfg: Config, date_from: str, date_to: str) -> list[dict[str, Any]]:
    url = (
        f"{cfg.supabase_url}/rest/v1/worklog_entries"
        f"?work_date=gte.{date_from}"
        f"&work_date=lte.{date_to}"
        f"&order=work_date.asc,issue_key.asc,account_id.asc"
        f"&limit=10000"
    )
    response = requests.get(url, headers=_headers(cfg), timeout=20)
    response.raise_for_status()
    return response.json()


def fetch_weekly(cfg: Config, week_start: str) -> list[dict[str, Any]]:
    url = f"{cfg.supabase_url}/rest/v1/worklog_weekly?week_start=eq.{week_start}&order=display_name"
    response = requests.get(url, headers=_headers(cfg), timeout=10)
    response.raise_for_status()
    return response.json()


def fetch_quarterly(cfg: Config, quarter_key: str) -> list[dict[str, Any]]:
    url = f"{cfg.supabase_url}/rest/v1/worklog_quarterly?quarter_key=eq.{quarter_key}&order=display_name"
    response = requests.get(url, headers=_headers(cfg), timeout=10)
    response.raise_for_status()
    return response.json()


def _parse_total_count(content_range: str) -> int:
    if "/" not in content_range:
        return 0

    tail = content_range.rsplit("/", 1)[-1].strip()
    if tail == "*":
        return 0
    try:
        return int(tail)
    except ValueError:
        return 0


def count_high_estimate_entries(cfg: Config, work_date: str, threshold_sec: int) -> int:
    """Count tasks whose original estimate exceeds the threshold on one day."""
    url = (
        f"{cfg.supabase_url}/rest/v1/worklog_entries"
        f"?select=account_id"
        f"&work_date=eq.{work_date}"
        f"&estimated_sec=gt.{threshold_sec}"
        f"&limit=1"
    )
    headers = _headers(cfg)
    headers["Prefer"] = "count=exact"
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()
    return _parse_total_count(response.headers.get("Content-Range", ""))


def fetch_high_estimate_entries(
    cfg: Config,
    work_date: str,
    threshold_sec: int,
    page_size: int,
    page_no: int,
) -> list[dict[str, Any]]:
    """Fetch high-estimate tasks for one day with pagination."""
    safe_page_size = max(1, int(page_size))
    safe_page_no = max(1, int(page_no))
    offset = (safe_page_no - 1) * safe_page_size

    url = (
        f"{cfg.supabase_url}/rest/v1/worklog_entries"
        f"?select=account_id,display_name,work_date,issue_key,issue_summary,time_sec,estimated_sec"
        f"&work_date=eq.{work_date}"
        f"&estimated_sec=gt.{threshold_sec}"
        f"&order=estimated_sec.desc,issue_key.asc,account_id.asc"
        f"&limit={safe_page_size}"
        f"&offset={offset}"
    )
    response = requests.get(url, headers=_headers(cfg), timeout=10)
    response.raise_for_status()
    return response.json()
