#!/usr/bin/env python3
"""CFD 团队工时统计 CLI 入口。"""
from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta

from cfd_report.aggregator import (
    aggregate,
    build_db_rows,
    build_entry_rows,
    ensure_member_rows,
    find_under_logged,
)
from cfd_report.atlassian import get_team_members, search_jira_issues
from cfd_report.config import Config
from cfd_report.emailer import send_reminders
from cfd_report.holidays import get_cn_holidays, latest_workday
from cfd_report.reporter import date_ranges, range_meta, render_markdown
from cfd_report.supabase_client import (
    check_cache,
    check_entries_cache,
    fetch_daily,
    fetch_quarterly,
    fetch_weekly,
    upsert_entry_rows,
    upsert_rows,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="CFD 团队工时统计")
    p.add_argument("--date", metavar="YYYY-MM-DD", help="统计日期（默认今天）")
    p.add_argument("--no-email", action="store_true", help="不发送邮件提醒")
    p.add_argument("--week-only", action="store_true", help="只输出本周数据")
    p.add_argument("--quarter-only", action="store_true", help="只输出本季度数据")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    cfg = Config.from_env()

    target = date.fromisoformat(args.date) if args.date else latest_workday(date.today())
    ranges = date_ranges(target)

    print(f"📊 CFD 工时统计 — {ranges['today']}")
    print("─" * 50)

    # ── 1. 获取团队成员 ──────────────────────────────────
    print("🔍 获取 CFD 团队成员...")
    members = get_team_members(cfg)
    member_ids = {m["accountId"] for m in members}
    print(f"  共 {len(members)} 名成员")

    # ── 2. 检查 Supabase 缓存 ─────────────────────────────
    print("💾 检查数据库缓存...")
    cache = check_cache(cfg, target)
    cache_hit = cache.get("daily", False)
    print(f"  今日缓存：{'命中 ✅' if cache_hit else '未命中，将从 Jira 拉取'}")

    # ── 3. 若缓存未命中，查询 Jira 并入库 ──────────────────
    holidays = get_cn_holidays(target.year)
    issues: list[dict] | None = None
    if not cache_hit:
        q_start = date(target.year, (target.month - 1) // 3 * 3 + 1, 1).isoformat()
        print(f"📡 查询 Jira worklog（{q_start} ~ {ranges['today']}）...")
        issues = search_jira_issues(cfg, list(member_ids), q_start, ranges["today"])
        print(f"  获取 {len(issues)} 个 Issue")

        stats = aggregate(issues, member_ids, holidays)
        daily_rows, weekly_rows, quarterly_rows = build_db_rows(stats)
        daily_rows = ensure_member_rows(daily_rows, members, "work_date", ranges["today"])
        weekly_rows = ensure_member_rows(weekly_rows, members, "week_start", ranges["week_start"])
        quarterly_rows = ensure_member_rows(quarterly_rows, members, "quarter_key", ranges["quarter_key"])

        print("📥 写入 Supabase...")
        n1 = upsert_rows(cfg, "worklog_daily", daily_rows)
        n2 = upsert_rows(cfg, "worklog_weekly", weekly_rows)
        n3 = upsert_rows(cfg, "worklog_quarterly", quarterly_rows)
        print(f"  daily={n1} 条，weekly={n2} 条，quarterly={n3} 条")

    entries_cache_hit = check_entries_cache(cfg, ranges["today"])
    if not entries_cache_hit:
        if issues is None:
            print(f"📡 查询 Jira 任务明细（{ranges['today']}）...")
            issues = search_jira_issues(cfg, list(member_ids), ranges["today"], ranges["today"])
        entry_rows = build_entry_rows(issues, member_ids, ranges["today"], holidays)
        entry_count = upsert_entry_rows(cfg, entry_rows)
        print(f"  worklog_entries={entry_count} 条")

    # ── 4. 从数据库读取展示 ──────────────────────────────
    daily = fetch_daily(cfg, ranges["today"])
    weekly = fetch_weekly(cfg, ranges["week_start"])
    quarterly = fetch_quarterly(cfg, ranges["quarter_key"])
    daily = ensure_member_rows(daily, members, "work_date", ranges["today"])
    weekly = ensure_member_rows(weekly, members, "week_start", ranges["week_start"])
    quarterly = ensure_member_rows(quarterly, members, "quarter_key", ranges["quarter_key"])

    if not args.week_only and not args.quarter_only:
        report = render_markdown(daily, weekly, quarterly, ranges, cfg.daily_target_hours, cache_hit)
    elif args.week_only:
        report = render_markdown([], weekly, [], ranges, cfg.daily_target_hours, cache_hit)
    else:
        report = render_markdown([], [], quarterly, ranges, cfg.daily_target_hours, cache_hit)

    print("\n" + report)

    # ── 5. 发送邮件 ──────────────────────────────────────
    if not args.no_email:
        under = find_under_logged(daily, ranges["today"], cfg.daily_target_hours)
        if under:
            print(f"\n📧 发送邮件提醒（{len(under)} 人）...")
            reminder_context = range_meta(target, target, holidays)
            reminder_context["required_hours"] = cfg.daily_target_hours
            sent, skipped = send_reminders(under, reminder_context, cfg)
            print(f"  成功 {len(sent)} 封，跳过 {len(skipped)} 封")
            if skipped:
                print("  跳过：" + "、".join(skipped))
        else:
            print("\n✅ 今日所有成员工时达标，无需发送提醒")
    else:
        print("\n（--no-email 模式，跳过邮件发送）")


if __name__ == "__main__":
    main()
