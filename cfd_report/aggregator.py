from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any

from .holidays import is_workday


def _week_start(d: date) -> str:
    return (d - timedelta(days=d.weekday())).isoformat()


def _quarter_key(d: date) -> str:
    return f"{d.year}-Q{(d.month - 1) // 3 + 1}"


def aggregate(
    issues: list[dict[str, Any]],
    member_ids: set[str],
    holidays: set[str],
) -> dict[str, dict[str, dict[str, Any]]]:
    """
    将 Jira issues 聚合为三个维度的统计数据。

    返回结构：
    {
      "daily":     { accountId: { "YYYY-MM-DD": {logged, estimated, issues, name} } },
      "weekly":    { accountId: { "YYYY-MM-DD": {...} } },
      "quarterly": { accountId: { "YYYY-QN":    {...} } },
    }
    """
    def new_slot():
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

        for wl in worklogs:
            author = wl.get("author", {})
            aid = author.get("accountId", "")
            if aid not in member_ids:
                continue
            started = wl.get("started", "")[:10]
            if not is_workday(started, holidays):
                continue

            ts = wl.get("timeSpentSeconds", 0)
            name = author.get("displayName", aid)
            d_obj = date.fromisoformat(started)

            period_map = {
                "daily": started,
                "weekly": _week_start(d_obj),
                "quarterly": _quarter_key(d_obj),
            }
            for dim, pk in period_map.items():
                s = stats[dim][aid][pk]
                s["logged"] += ts
                s["name"] = name
                s["issues"].add(key)
                if dim == "daily" and key not in s["counted"]:
                    s["estimated"] += orig_est
                    s["counted"].add(key)

    return stats


def build_db_rows(
    stats: dict[str, Any],
) -> tuple[list[dict], list[dict], list[dict]]:
    """将聚合结果转为可直接 upsert 到 Supabase 的行列表。"""
    now_ts = datetime.now(timezone.utc).isoformat()

    daily_rows = [
        {
            "account_id": aid,
            "display_name": s["name"],
            "work_date": pk,
            "logged_sec": s["logged"],
            "estimated_sec": s["estimated"],
            "issue_count": len(s["issues"]),
            "issue_keys": list(s["issues"]),
            "updated_at": now_ts,
        }
        for aid, periods in stats["daily"].items()
        for pk, s in periods.items()
    ]
    weekly_rows = [
        {
            "account_id": aid,
            "display_name": s["name"],
            "week_start": pk,
            "logged_sec": s["logged"],
            "estimated_sec": s["estimated"],
            "issue_count": len(s["issues"]),
            "issue_keys": list(s["issues"]),
            "updated_at": now_ts,
        }
        for aid, periods in stats["weekly"].items()
        for pk, s in periods.items()
    ]
    quarterly_rows = [
        {
            "account_id": aid,
            "display_name": s["name"],
            "quarter_key": pk,
            "logged_sec": s["logged"],
            "estimated_sec": s["estimated"],
            "issue_count": len(s["issues"]),
            "issue_keys": list(s["issues"]),
            "updated_at": now_ts,
        }
        for aid, periods in stats["quarterly"].items()
        for pk, s in periods.items()
    ]
    return daily_rows, weekly_rows, quarterly_rows


def ensure_member_rows(
    rows: list[dict[str, Any]],
    members: list[dict[str, Any]],
    period_col: str,
    period_value: str,
) -> list[dict[str, Any]]:
    """按团队成员补齐缺失行（无工时成员补 0），并按 logged_sec 倒序。"""
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


def build_entry_rows(
    issues: list[dict[str, Any]],
    member_ids: set[str],
    target_date: str,
    holidays: set[str],
) -> list[dict[str, Any]]:
    """将 Jira issue/worklog 明细转为 worklog_entries 的 upsert 行。"""
    if not is_workday(target_date, holidays):
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
            if started != target_date or not is_workday(started, holidays):
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


def find_under_logged(
    daily_rows: list[dict[str, Any]],
    target_date: str,
    daily_target_hours: float,
) -> list[dict[str, Any]]:
    target_sec = daily_target_hours * 3600
    return [
        {
            "accountId": r["account_id"],
            "name": r["display_name"],
            "logged_hours": round(r["logged_sec"] / 3600, 2),
        }
        for r in daily_rows
        if r["work_date"] == target_date and r["logged_sec"] < target_sec
    ]
