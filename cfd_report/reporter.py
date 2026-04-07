from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from .holidays import get_cn_holidays, is_workday


def s2h(sec: int | float | None) -> float:
    return round((sec or 0) / 3600, 2)


def date_ranges(target: date) -> dict[str, str]:
    week = (target - timedelta(days=target.weekday())).isoformat()
    qkey = f"{target.year}-Q{(target.month - 1) // 3 + 1}"
    return {
        "today": target.isoformat(),
        "week_start": week,
        "quarter_key": qkey,
    }


def _holidays_for_range(start: date, end: date) -> set[str]:
    holidays: set[str] = set()
    for year in range(start.year, end.year + 1):
        holidays.update(get_cn_holidays(year))
    return holidays


def count_workdays(date_from: date, date_to: date, holidays: set[str] | None = None) -> int:
    start = min(date_from, date_to)
    end = max(date_from, date_to)
    holiday_set = holidays if holidays is not None else _holidays_for_range(start, end)

    total = 0
    current = start
    while current <= end:
        if is_workday(current.isoformat(), holiday_set):
            total += 1
        current += timedelta(days=1)
    return total


def range_meta(
    date_from: date,
    date_to: date,
    holidays: set[str] | None = None,
) -> dict[str, Any]:
    start = min(date_from, date_to)
    end = max(date_from, date_to)
    holiday_set = holidays if holidays is not None else _holidays_for_range(start, end)
    quarter_start = date(end.year, (end.month - 1) // 3 * 3 + 1, 1)

    return {
        "date_from": start,
        "date_to": end,
        "date_from_str": start.isoformat(),
        "date_to_str": end.isoformat(),
        "day_count": (end - start).days + 1,
        "workday_count": count_workdays(start, end, holiday_set),
        "week_start": (end - timedelta(days=end.weekday())).isoformat(),
        "quarter_start": quarter_start.isoformat(),
        "quarter_key": f"{end.year}-Q{(end.month - 1) // 3 + 1}",
    }


def render_markdown(
    daily_rows: list[dict[str, Any]],
    weekly_rows: list[dict[str, Any]],
    quarterly_rows: list[dict[str, Any]],
    ranges: dict[str, str],
    daily_target: float = 7.5,
    cache_hit: bool = False,
) -> str:
    source = "数据库缓存" if cache_hit else "Jira 实时"
    lines = [
        f"# CFD 团队工时统计报告（来源：{source}）",
        f"统计日期：{ranges['today']}  |  本周：{ranges['week_start']} 起  |  本季度：{ranges['quarter_key']}",
        "",
        "## 今日（日维度）",
    ]

    if daily_rows:
        lines += [
            "| 成员 | 已记录(h) | 预估(h) | Issue数 | 状态 |",
            "|------|:--------:|:------:|:------:|------|",
        ]
        for row in daily_rows:
            logged_hours = s2h(row["logged_sec"])
            ok = logged_hours >= daily_target
            lines.append(
                f"| {row['display_name']} | {logged_hours} | {s2h(row['estimated_sec'])} "
                f"| {row['issue_count']} | {'达标' if ok else '不足'} |"
            )
    else:
        lines.append("今日暂无工时记录。")

    lines += ["", "## 本周（周维度）"]
    if weekly_rows:
        lines += [
            "| 成员 | 已记录(h) | 预估(h) | Issue数 |",
            "|------|:--------:|:------:|:------:|",
        ]
        for row in weekly_rows:
            lines.append(
                f"| {row['display_name']} | {s2h(row['logged_sec'])} "
                f"| {s2h(row['estimated_sec'])} | {row['issue_count']} |"
            )
    else:
        lines.append("本周暂无数据。")

    lines += ["", f"## 本季度（{ranges['quarter_key']}）"]
    if quarterly_rows:
        lines += [
            "| 成员 | 已记录(h) | 预估(h) | Issue数 |",
            "|------|:--------:|:------:|:------:|",
        ]
        for row in quarterly_rows:
            lines.append(
                f"| {row['display_name']} | {s2h(row['logged_sec'])} "
                f"| {s2h(row['estimated_sec'])} | {row['issue_count']} |"
            )
    else:
        lines.append("本季度暂无数据。")

    under = [row for row in daily_rows if s2h(row["logged_sec"]) < daily_target]
    if under:
        lines += ["", f"⚠️ 今日工时不足 {daily_target}h 的成员（共 {len(under)} 人）："]
        for row in under:
            logged_hours = s2h(row["logged_sec"])
            lines.append(f"  - {row['display_name']}：{logged_hours}h，差 {round(daily_target - logged_hours, 2)}h")
    else:
        lines += ["", "✅ 今日所有成员工时均达标"]

    return "\n".join(lines)
