from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any

from .holidays import is_workday


def _week_start(d: date) -> str:
    return (d - timedelta(days=d.weekday())).isoformat()


def _quarter_key(d: date) -> str:
    return f"{d.year}-Q{(d.month - 1) // 3 + 1}"


def iter_workdays(date_from: str, date_to: str, holidays: set[str]) -> list[str]:
    start_date = date.fromisoformat(date_from)
    end_date = date.fromisoformat(date_to)
    if start_date > end_date:
        start_date, end_date = end_date, start_date

    workdays: list[str] = []
    current = start_date
    while current <= end_date:
        current_str = current.isoformat()
        if is_workday(current_str, holidays):
            workdays.append(current_str)
        current += timedelta(days=1)
    return workdays


def aggregate(
    issues: list[dict[str, Any]],
    member_ids: set[str],
    holidays: set[str],
) -> dict[str, dict[str, dict[str, Any]]]:
    """
    Aggregate Jira issues into daily, weekly, and quarterly worklog stats.

    Returned structure:
    {
      "daily":     { accountId: { "YYYY-MM-DD": {logged, estimated, issues, name} } },
      "weekly":    { accountId: { "YYYY-MM-DD": {...} } },
      "quarterly": { accountId: { "YYYY-QN":    {...} } },
    }
    """

    def new_slot() -> dict[str, Any]:
        return {"logged": 0, "estimated": 0, "issues": set(), "name": "", "counted": set()}

    stats: dict[str, Any] = {
        dim: defaultdict(lambda: defaultdict(new_slot))
        for dim in ("daily", "weekly", "quarterly")
    }

    for issue in issues:
        key = issue["key"]
        fields = issue.get("fields", {})
        orig_est = fields.get("timeoriginalestimate", 0) or 0
        worklogs = fields.get("worklog", {}).get("worklogs", [])

        for worklog in worklogs:
            author = worklog.get("author", {})
            aid = author.get("accountId", "")
            if aid not in member_ids:
                continue

            started = worklog.get("started", "")[:10]
            if not is_workday(started, holidays):
                continue

            ts = worklog.get("timeSpentSeconds", 0)
            name = author.get("displayName", aid)
            d_obj = date.fromisoformat(started)

            period_map = {
                "daily": started,
                "weekly": _week_start(d_obj),
                "quarterly": _quarter_key(d_obj),
            }
            for dim, pk in period_map.items():
                slot = stats[dim][aid][pk]
                slot["logged"] += ts
                slot["name"] = name
                slot["issues"].add(key)
                if dim == "daily" and key not in slot["counted"]:
                    slot["estimated"] += orig_est
                    slot["counted"].add(key)

    return stats


def build_db_rows(
    stats: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Convert aggregated stats to rows that can be written to Supabase."""
    now_ts = datetime.now(timezone.utc).isoformat()

    daily_rows = [
        {
            "account_id": aid,
            "display_name": slot["name"],
            "work_date": pk,
            "logged_sec": slot["logged"],
            "estimated_sec": slot["estimated"],
            "issue_count": len(slot["issues"]),
            "issue_keys": list(slot["issues"]),
            "updated_at": now_ts,
        }
        for aid, periods in stats["daily"].items()
        for pk, slot in periods.items()
    ]
    weekly_rows = [
        {
            "account_id": aid,
            "display_name": slot["name"],
            "week_start": pk,
            "logged_sec": slot["logged"],
            "estimated_sec": slot["estimated"],
            "issue_count": len(slot["issues"]),
            "issue_keys": list(slot["issues"]),
            "updated_at": now_ts,
        }
        for aid, periods in stats["weekly"].items()
        for pk, slot in periods.items()
    ]
    quarterly_rows = [
        {
            "account_id": aid,
            "display_name": slot["name"],
            "quarter_key": pk,
            "logged_sec": slot["logged"],
            "estimated_sec": slot["estimated"],
            "issue_count": len(slot["issues"]),
            "issue_keys": list(slot["issues"]),
            "updated_at": now_ts,
        }
        for aid, periods in stats["quarterly"].items()
        for pk, slot in periods.items()
    ]
    return daily_rows, weekly_rows, quarterly_rows


def ensure_member_rows(
    rows: list[dict[str, Any]],
    members: list[dict[str, Any]],
    period_col: str,
    period_value: str,
) -> list[dict[str, Any]]:
    """Fill missing member rows with zero values and sort by logged time."""
    now_ts = datetime.now(timezone.utc).isoformat()
    row_by_account: dict[str, dict[str, Any]] = {}

    for row in rows:
        account_id = row.get("account_id")
        if account_id:
            row_by_account[account_id] = dict(row)

    for member in members:
        account_id = member.get("accountId", "")
        if not account_id:
            continue
        display_name = member.get("displayName", account_id)

        if account_id not in row_by_account:
            row_by_account[account_id] = {
                "account_id": account_id,
                "display_name": display_name,
                period_col: period_value,
                "logged_sec": 0,
                "estimated_sec": 0,
                "issue_count": 0,
                "issue_keys": [],
                "updated_at": now_ts,
            }
            continue

        row = row_by_account[account_id]
        row.setdefault("display_name", display_name)
        row.setdefault(period_col, period_value)
        row.setdefault("logged_sec", 0)
        row.setdefault("estimated_sec", 0)
        row.setdefault("issue_count", 0)
        row.setdefault("issue_keys", [])
        if "updated_at" in row:
            row.setdefault("updated_at", now_ts)

    normalized = list(row_by_account.values())
    normalized.sort(
        key=lambda item: (
            -(item.get("logged_sec", 0) or 0),
            item.get("display_name", ""),
        )
    )
    return normalized


def ensure_daily_member_rows_for_range(
    rows: list[dict[str, Any]],
    members: list[dict[str, Any]],
    date_from: str,
    date_to: str,
    holidays: set[str],
) -> list[dict[str, Any]]:
    """Fill all workdays in the range with zero rows for every member."""
    rows_by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        work_date = row.get("work_date")
        if work_date:
            rows_by_date[work_date].append(row)

    normalized: list[dict[str, Any]] = []
    for work_date in iter_workdays(date_from, date_to, holidays):
        normalized.extend(
            ensure_member_rows(rows_by_date.get(work_date, []), members, "work_date", work_date)
        )

    normalized.sort(
        key=lambda item: (
            item.get("work_date", ""),
            item.get("display_name", ""),
        )
    )
    return normalized


def build_entry_rows(
    issues: list[dict[str, Any]],
    member_ids: set[str],
    target_date: str,
    holidays: set[str],
) -> list[dict[str, Any]]:
    """Convert a single day's Jira worklogs to worklog_entries rows."""
    return build_entry_rows_for_range(issues, member_ids, target_date, target_date, holidays)


def build_entry_rows_for_range(
    issues: list[dict[str, Any]],
    member_ids: set[str],
    date_from: str,
    date_to: str,
    holidays: set[str],
) -> list[dict[str, Any]]:
    """Convert a Jira worklog window to worklog_entries rows."""
    start_date = date.fromisoformat(date_from)
    end_date = date.fromisoformat(date_to)
    if start_date > end_date:
        return []

    now_ts = datetime.now(timezone.utc).isoformat()
    row_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}

    for issue in issues:
        issue_key = issue.get("key", "")
        if not issue_key:
            continue

        fields = issue.get("fields", {})
        issue_summary = fields.get("summary", "")
        estimated_sec = fields.get("timeoriginalestimate", 0) or 0
        worklogs = fields.get("worklog", {}).get("worklogs", [])

        for worklog in worklogs:
            author = worklog.get("author", {})
            account_id = author.get("accountId", "")
            if account_id not in member_ids:
                continue

            started = worklog.get("started", "")[:10]
            try:
                started_date = date.fromisoformat(started)
            except ValueError:
                continue

            if started_date < start_date or started_date > end_date:
                continue
            if not is_workday(started, holidays):
                continue

            map_key = (account_id, started, issue_key)
            if map_key not in row_by_key:
                row_by_key[map_key] = {
                    "account_id": account_id,
                    "display_name": author.get("displayName", account_id),
                    "work_date": started,
                    "issue_key": issue_key,
                    "issue_summary": issue_summary,
                    "time_sec": 0,
                    "estimated_sec": estimated_sec,
                    "updated_at": now_ts,
                }

            row_by_key[map_key]["time_sec"] += worklog.get("timeSpentSeconds", 0) or 0

    rows = list(row_by_key.values())
    rows.sort(
        key=lambda item: (
            -(item.get("estimated_sec", 0) or 0),
            item.get("issue_key", ""),
            item.get("account_id", ""),
        )
    )
    return rows


def aggregate_member_range_rows(
    daily_rows: list[dict[str, Any]],
    entry_rows: list[dict[str, Any]],
    members: list[dict[str, Any]],
    date_from: str,
    date_to: str,
) -> list[dict[str, Any]]:
    """Aggregate daily and entry rows into range-level member totals."""
    now_ts = datetime.now(timezone.utc).isoformat()
    row_by_account: dict[str, dict[str, Any]] = {}

    for member in members:
        account_id = member.get("accountId", "")
        if not account_id:
            continue
        row_by_account[account_id] = {
            "account_id": account_id,
            "display_name": member.get("displayName", account_id),
            "date_from": date_from,
            "date_to": date_to,
            "logged_sec": 0,
            "estimated_sec": 0,
            "issue_count": 0,
            "issue_keys": [],
            "updated_at": now_ts,
        }

    for row in daily_rows:
        account_id = row.get("account_id", "")
        if account_id in row_by_account:
            row_by_account[account_id]["logged_sec"] += row.get("logged_sec", 0) or 0

    seen_issue_by_account: dict[str, set[str]] = defaultdict(set)
    for row in entry_rows:
        account_id = row.get("account_id", "")
        issue_key = row.get("issue_key", "")
        if account_id not in row_by_account or not issue_key:
            continue
        if issue_key in seen_issue_by_account[account_id]:
            continue

        seen_issue_by_account[account_id].add(issue_key)
        row_by_account[account_id]["estimated_sec"] += row.get("estimated_sec", 0) or 0
        row_by_account[account_id]["issue_keys"].append(issue_key)

    for row in row_by_account.values():
        row["issue_count"] = len(row["issue_keys"])

    normalized = list(row_by_account.values())
    normalized.sort(
        key=lambda item: (
            -(item.get("logged_sec", 0) or 0),
            item.get("display_name", ""),
        )
    )
    return normalized


def aggregate_high_estimate_range_entries(
    entry_rows: list[dict[str, Any]],
    threshold_sec: int,
) -> list[dict[str, Any]]:
    """Aggregate range entries to one row per member and issue."""
    row_by_key: dict[tuple[str, str], dict[str, Any]] = {}

    for row in entry_rows:
        account_id = row.get("account_id", "")
        issue_key = row.get("issue_key", "")
        if not account_id or not issue_key:
            continue

        map_key = (account_id, issue_key)
        if map_key not in row_by_key:
            row_by_key[map_key] = {
                "account_id": account_id,
                "display_name": row.get("display_name", account_id),
                "issue_key": issue_key,
                "issue_summary": row.get("issue_summary", ""),
                "estimated_sec": row.get("estimated_sec", 0) or 0,
                "time_sec": 0,
            }

        row_by_key[map_key]["time_sec"] += row.get("time_sec", 0) or 0
        row_by_key[map_key]["estimated_sec"] = max(
            row_by_key[map_key]["estimated_sec"],
            row.get("estimated_sec", 0) or 0,
        )

    rows = [
        row
        for row in row_by_key.values()
        if (row.get("estimated_sec", 0) or 0) > threshold_sec
    ]
    rows.sort(
        key=lambda item: (
            -(item.get("estimated_sec", 0) or 0),
            -(item.get("time_sec", 0) or 0),
            item.get("issue_key", ""),
            item.get("account_id", ""),
        )
    )
    return rows


def aggregate_no_estimate_range_entries(
    entry_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Aggregate range entries to one row per member and issue with zero estimate."""
    row_by_key: dict[tuple[str, str], dict[str, Any]] = {}

    for row in entry_rows:
        account_id = row.get("account_id", "")
        issue_key = row.get("issue_key", "")
        if not account_id or not issue_key:
            continue

        map_key = (account_id, issue_key)
        if map_key not in row_by_key:
            row_by_key[map_key] = {
                "account_id": account_id,
                "display_name": row.get("display_name", account_id),
                "issue_key": issue_key,
                "issue_summary": row.get("issue_summary", ""),
                "estimated_sec": row.get("estimated_sec", 0) or 0,
                "time_sec": 0,
            }

        row_by_key[map_key]["time_sec"] += row.get("time_sec", 0) or 0
        row_by_key[map_key]["estimated_sec"] = max(
            row_by_key[map_key]["estimated_sec"],
            row.get("estimated_sec", 0) or 0,
        )

    rows = [row for row in row_by_key.values() if (row.get("estimated_sec", 0) or 0) == 0]
    rows.sort(
        key=lambda item: (
            -(item.get("time_sec", 0) or 0),
            item.get("issue_key", ""),
            item.get("account_id", ""),
        )
    )
    return rows


def find_under_logged(
    daily_rows: list[dict[str, Any]],
    target_date: str,
    daily_target_hours: float,
) -> list[dict[str, Any]]:
    target_sec = daily_target_hours * 3600
    return [
        {
            "accountId": row["account_id"],
            "name": row["display_name"],
            "logged_hours": round(row["logged_sec"] / 3600, 2),
        }
        for row in daily_rows
        if row["work_date"] == target_date and row["logged_sec"] < target_sec
    ]


def find_under_logged_range(
    range_rows: list[dict[str, Any]],
    required_hours: float,
) -> list[dict[str, Any]]:
    required_sec = int(required_hours * 3600)
    under_logged: list[dict[str, Any]] = []

    for row in range_rows:
        logged_sec = row.get("logged_sec", 0) or 0
        if logged_sec >= required_sec:
            continue

        logged_hours = round(logged_sec / 3600, 2)
        missing_hours = round(required_hours - logged_hours, 2)
        under_logged.append(
            {
                "accountId": row["account_id"],
                "name": row["display_name"],
                "logged_hours": logged_hours,
                "required_hours": round(required_hours, 2),
                "missing_hours": missing_hours,
            }
        )

    under_logged.sort(key=lambda item: (-item["missing_hours"], item["name"]))
    return under_logged
