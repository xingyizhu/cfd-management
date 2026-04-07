from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import requests

from .config import Config


def _headers(cfg: Config) -> dict[str, str]:
    return {
        "apikey": cfg.supabase_anon_key,
        "Authorization": f"Bearer {cfg.supabase_anon_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _upsert_headers(cfg: Config) -> dict[str, str]:
    h = _headers(cfg)
    h["Prefer"] = "resolution=merge-duplicates,return=minimal"
    return h


def check_cache(cfg: Config, target_date: date) -> dict[str, bool]:
    """检查 Supabase 中是否已有当日数据。"""
    today = target_date.isoformat()
    week = (target_date - timedelta(days=target_date.weekday())).isoformat()
    qkey = f"{target_date.year}-Q{(target_date.month - 1) // 3 + 1}"

    results: dict[str, bool] = {}
    for table, param in [
        ("worklog_daily", f"work_date=eq.{today}"),
        ("worklog_weekly", f"week_start=eq.{week}"),
        ("worklog_quarterly", f"quarter_key=eq.{qkey}"),
    ]:
        try:
            url = f"{cfg.supabase_url}/rest/v1/{table}?{param}&limit=1"
            r = requests.get(url, headers=_headers(cfg), timeout=10)
            r.raise_for_status()
            results[table.replace("worklog_", "")] = len(r.json()) > 0
        except Exception:
            results[table.replace("worklog_", "")] = False
    return results


def check_entries_cache(cfg: Config, work_date: str) -> bool:
    """检查 worklog_entries 是否已有指定日期数据。"""
    try:
        url = f"{cfg.supabase_url}/rest/v1/worklog_entries?work_date=eq.{work_date}&limit=1"
        response = requests.get(url, headers=_headers(cfg), timeout=10)
        response.raise_for_status()
        return len(response.json()) > 0
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
    resp = requests.post(
        url,
        params=params,
        json=rows,
        headers=_upsert_headers(cfg),
        timeout=20,
    )
    resp.raise_for_status()
    return len(rows)


def upsert_entry_rows(cfg: Config, rows: list[dict[str, Any]]) -> int:
    """upsert worklog_entries 行数据。"""
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


def fetch_daily(cfg: Config, work_date: str) -> list[dict[str, Any]]:
    url = f"{cfg.supabase_url}/rest/v1/worklog_daily?work_date=eq.{work_date}&order=display_name"
    r = requests.get(url, headers=_headers(cfg), timeout=10)
    r.raise_for_status()
    return r.json()


def fetch_weekly(cfg: Config, week_start: str) -> list[dict[str, Any]]:
    url = f"{cfg.supabase_url}/rest/v1/worklog_weekly?week_start=eq.{week_start}&order=display_name"
    r = requests.get(url, headers=_headers(cfg), timeout=10)
    r.raise_for_status()
    return r.json()


def fetch_quarterly(cfg: Config, quarter_key: str) -> list[dict[str, Any]]:
    url = f"{cfg.supabase_url}/rest/v1/worklog_quarterly?quarter_key=eq.{quarter_key}&order=display_name"
    r = requests.get(url, headers=_headers(cfg), timeout=10)
    r.raise_for_status()
    return r.json()


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
    """统计指定日期内预估时长大于阈值的任务条数。"""
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
    """分页查询指定日期内预估时长大于阈值的任务。"""
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
