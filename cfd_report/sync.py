from __future__ import annotations

from datetime import date
from typing import Any

from .aggregator import (
    aggregate,
    build_db_rows,
    build_entry_rows_for_range,
    ensure_daily_member_rows_for_range,
)
from .atlassian import search_jira_issues
from .config import Config
from .supabase_client import replace_range_window_rows, replace_sync_window_rows


def quarter_start(target_date: date) -> date:
    first_month = (target_date.month - 1) // 3 * 3 + 1
    return date(target_date.year, first_month, 1)


def sync_force_refresh_window(
    cfg: Config,
    target_date: date,
    members: list[dict[str, Any]],
    holidays: set[str],
) -> dict[str, int]:
    """Sync the quarter-to-date Jira window to Supabase during force refresh."""
    member_ids = {member["accountId"] for member in members if member.get("accountId")}
    sync_start = quarter_start(target_date).isoformat()
    sync_end = target_date.isoformat()
    quarter_key = f"{target_date.year}-Q{(target_date.month - 1) // 3 + 1}"

    issues = search_jira_issues(cfg, list(member_ids), sync_start, sync_end)
    stats = aggregate(issues, member_ids, holidays)
    daily_rows, weekly_rows, quarterly_rows = build_db_rows(stats)
    entry_rows = build_entry_rows_for_range(issues, member_ids, sync_start, sync_end, holidays)

    return replace_sync_window_rows(
        cfg,
        date_from=sync_start,
        date_to=sync_end,
        quarter_key=quarter_key,
        daily_rows=daily_rows,
        weekly_rows=weekly_rows,
        quarterly_rows=quarterly_rows,
        entry_rows=entry_rows,
    )


def sync_range_window(
    cfg: Config,
    date_from: date,
    date_to: date,
    members: list[dict[str, Any]],
    holidays: set[str],
) -> dict[str, int]:
    """Sync a custom date range to Supabase daily and entry tables."""
    start = min(date_from, date_to)
    end = max(date_from, date_to)
    member_ids = {member["accountId"] for member in members if member.get("accountId")}

    issues = search_jira_issues(cfg, list(member_ids), start.isoformat(), end.isoformat())
    stats = aggregate(issues, member_ids, holidays)
    daily_rows, _, _ = build_db_rows(stats)
    daily_rows = ensure_daily_member_rows_for_range(
        daily_rows,
        members,
        start.isoformat(),
        end.isoformat(),
        holidays,
    )
    entry_rows = build_entry_rows_for_range(
        issues,
        member_ids,
        start.isoformat(),
        end.isoformat(),
        holidays,
    )

    return replace_range_window_rows(
        cfg,
        date_from=start.isoformat(),
        date_to=end.isoformat(),
        daily_rows=daily_rows,
        entry_rows=entry_rows,
    )
