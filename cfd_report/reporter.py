from __future__ import annotations

from datetime import date, timedelta
from typing import Any


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
        for r in daily_rows:
            lh = s2h(r["logged_sec"])
            ok = lh >= daily_target
            lines.append(
                f"| {r['display_name']} | {lh} | {s2h(r['estimated_sec'])} "
                f"| {r['issue_count']} | {'✅ 达标' if ok else '⚠️ 不足'} |"
            )
    else:
        lines.append("今日暂无工时记录。")

    lines += ["", "## 本周（周维度）"]
    if weekly_rows:
        lines += [
            "| 成员 | 已记录(h) | 预估(h) | Issue数 |",
            "|------|:--------:|:------:|:------:|",
        ]
        for r in weekly_rows:
            lines.append(
                f"| {r['display_name']} | {s2h(r['logged_sec'])} "
                f"| {s2h(r['estimated_sec'])} | {r['issue_count']} |"
            )
    else:
        lines.append("本周暂无数据。")

    lines += ["", f"## 本季度（{ranges['quarter_key']}）"]
    if quarterly_rows:
        lines += [
            "| 成员 | 已记录(h) | 预估(h) | Issue数 |",
            "|------|:--------:|:------:|:------:|",
        ]
        for r in quarterly_rows:
            lines.append(
                f"| {r['display_name']} | {s2h(r['logged_sec'])} "
                f"| {s2h(r['estimated_sec'])} | {r['issue_count']} |"
            )
    else:
        lines.append("本季度暂无数据。")

    under = [r for r in daily_rows if s2h(r["logged_sec"]) < daily_target]
    if under:
        lines += ["", f"⚠️ 今日工时不足 {daily_target}h 的成员（共 {len(under)} 人）："]
        for r in under:
            lh = s2h(r["logged_sec"])
            lines.append(f"  - {r['display_name']}：{lh}h，差 {round(daily_target - lh, 2)}h")
    else:
        lines += ["", "✅ 今日所有成员工时均达标"]

    return "\n".join(lines)
