"""CFD 团队工时统计 — Streamlit Web UI。"""
from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

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
from cfd_report.reporter import date_ranges, s2h
from cfd_report.supabase_client import (
    check_cache,
    check_entries_cache,
    count_high_estimate_entries,
    fetch_daily,
    fetch_high_estimate_entries,
    fetch_quarterly,
    fetch_weekly,
    upsert_entry_rows,
    upsert_rows,
)

st.set_page_config(page_title="CFD 工时统计", page_icon="🛰️", layout="wide")

cfg = Config.from_env()


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;500;700&family=Noto+Serif+SC:wght@500;700&display=swap');

        :root {
            --bg-0: #080d1b;
            --bg-1: #111b34;
            --surface: rgba(16, 28, 56, 0.74);
            --surface-soft: rgba(27, 42, 78, 0.52);
            --border: rgba(145, 175, 255, 0.28);
            --text-main: #eff5ff;
            --text-sub: #b9c8eb;
            --accent: #7ea6ff;
            --accent-2: #66e2d5;
            --danger: #ff8a9e;
            --ok: #8bf0b5;
            --shadow: 0 16px 38px rgba(2, 8, 22, 0.42);
        }

        .stApp {
            font-family: "Noto Sans SC", "PingFang SC", sans-serif;
            color: var(--text-main);
            background:
                radial-gradient(circle at 16% -10%, #3257a7 0%, transparent 40%),
                radial-gradient(circle at 88% 5%, #1f4d57 0%, transparent 30%),
                linear-gradient(160deg, var(--bg-0) 0%, #0b1730 42%, var(--bg-1) 100%);
        }

        [data-testid="stSidebar"] {
            background:
                linear-gradient(170deg, rgba(8, 14, 30, 0.95) 0%, rgba(9, 21, 45, 0.95) 100%);
            border-right: 1px solid rgba(139, 170, 255, 0.24);
        }

        [data-testid="stSidebar"] * {
            color: var(--text-main) !important;
        }

        .side-brand {
            padding: 0.65rem 0.8rem;
            border-radius: 14px;
            border: 1px solid rgba(142, 174, 255, 0.34);
            background: linear-gradient(130deg, rgba(29, 46, 90, 0.62), rgba(12, 24, 50, 0.86));
            margin-bottom: 0.8rem;
            box-shadow: var(--shadow);
        }

        .side-brand .title {
            margin: 0;
            font-family: "Noto Serif SC", serif;
            font-size: 1.1rem;
            font-weight: 700;
        }

        .side-brand .sub {
            margin: 0.25rem 0 0;
            font-size: 0.82rem;
            color: var(--text-sub) !important;
        }

        .hero-shell {
            border-radius: 20px;
            padding: 1.25rem 1.3rem 1.1rem;
            border: 1px solid var(--border);
            background:
                radial-gradient(circle at 78% -35%, rgba(109, 166, 255, 0.52), transparent 38%),
                linear-gradient(135deg, rgba(24, 40, 80, 0.86), rgba(9, 18, 40, 0.86));
            box-shadow: var(--shadow);
            margin-bottom: 0.9rem;
        }

        .hero-kicker {
            letter-spacing: 0.07em;
            font-size: 0.75rem;
            text-transform: uppercase;
            color: #b7dcff;
            margin: 0 0 0.45rem;
            font-weight: 600;
        }

        .hero-title {
            margin: 0;
            font-family: "Noto Serif SC", serif;
            font-size: 2rem;
            line-height: 1.2;
            color: #f9fcff;
        }

        .hero-subtitle {
            margin: 0.42rem 0 0.8rem;
            color: var(--text-sub);
            font-size: 0.95rem;
        }

        .hero-chip-row {
            display: flex;
            gap: 0.5rem;
            flex-wrap: wrap;
        }

        .hero-chip {
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
            padding: 0.32rem 0.68rem;
            border-radius: 999px;
            border: 1px solid rgba(147, 178, 255, 0.35);
            background: rgba(13, 23, 47, 0.75);
            color: #dbe8ff;
            font-size: 0.8rem;
        }

        .metric-card {
            border-radius: 16px;
            padding: 0.85rem 0.92rem;
            border: 1px solid rgba(139, 170, 255, 0.28);
            background: linear-gradient(160deg, rgba(20, 35, 70, 0.84), rgba(10, 22, 46, 0.84));
            box-shadow: var(--shadow);
            min-height: 102px;
            position: relative;
            overflow: hidden;
        }

        .metric-card::after {
            content: "";
            position: absolute;
            inset: auto -24px -28px auto;
            width: 120px;
            height: 120px;
            border-radius: 50%;
            background: radial-gradient(circle, rgba(120, 171, 255, 0.26), transparent 64%);
        }

        .metric-label {
            margin: 0;
            color: #c5d5fb;
            font-size: 0.82rem;
            position: relative;
            z-index: 1;
        }

        .metric-value {
            margin: 0.32rem 0 0;
            font-size: 1.45rem;
            font-weight: 700;
            color: #ffffff;
            position: relative;
            z-index: 1;
        }

        .metric-note {
            margin: 0.3rem 0 0;
            color: #a4bbec;
            font-size: 0.76rem;
            position: relative;
            z-index: 1;
        }

        .section-title {
            margin: 0.75rem 0 0.15rem;
            font-size: 1.12rem;
            color: #f2f7ff;
            font-weight: 700;
        }

        .section-desc {
            margin: 0 0 0.4rem;
            color: var(--text-sub);
            font-size: 0.86rem;
        }

        .table-shell {
            width: 100%;
            overflow-x: auto;
            border: 1px solid rgba(143, 173, 253, 0.26);
            border-radius: 14px;
            background: rgba(9, 19, 40, 0.84);
            box-shadow: var(--shadow);
            margin-bottom: 0.42rem;
        }

        table.cfd-table {
            width: 100%;
            border-collapse: collapse;
            color: var(--text-main);
            background: transparent;
            font-size: 0.9rem;
        }

        table.cfd-table thead th {
            background: rgba(22, 40, 76, 0.86);
            color: #d9e7ff;
            font-weight: 600;
            border-bottom: 1px solid rgba(130, 161, 230, 0.3);
            padding: 0.62rem 0.75rem;
            white-space: nowrap;
            text-align: left;
        }

        table.cfd-table tbody td {
            border-bottom: 1px solid rgba(115, 144, 210, 0.18);
            padding: 0.54rem 0.75rem;
            white-space: nowrap;
            color: #e8efff;
            background: transparent;
        }

        table.cfd-table tbody tr:hover td {
            background: rgba(56, 86, 146, 0.22);
        }

        .mini-note {
            color: var(--text-sub);
            font-size: 0.82rem;
            margin-top: 0.3rem;
        }

        div[data-testid="stAlert"] {
            border-radius: 12px;
            border: 1px solid rgba(143, 175, 250, 0.34);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


inject_styles()


def render_metric_card(label: str, value: str, note: str) -> None:
    st.markdown(
        f"""
        <div class="metric-card">
            <p class="metric-label">{label}</p>
            <p class="metric-value">{value}</p>
            <p class="metric-note">{note}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_bug_placeholder() -> None:
    st.markdown(
        """
        <div class="hero-shell">
            <p class="hero-kicker">CFD Team Console</p>
            <h1 class="hero-title">Bug Intelligence Center</h1>
            <p class="hero-subtitle">页面已预留，后续可接入 Jira `issuetype=Bug` 趋势与负责人维度统计。</p>
            <div class="hero-chip-row">
                <span class="hero-chip">🧭 趋势追踪</span>
                <span class="hero-chip">🛠️ 责任分布</span>
                <span class="hero-chip">⏱️ SLA 监控</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    card_cols = st.columns(3)
    with card_cols[0]:
        render_metric_card("新增 Bug", "--", "按自然日")
    with card_cols[1]:
        render_metric_card("已关闭 Bug", "--", "按自然日")
    with card_cols[2]:
        render_metric_card("未解决 Bug", "--", "实时存量")

    st.info("Bug 模块等待 Jira 数据接入后即可启用。")


def render_hero(ranges: dict[str, str], cache_hit: bool) -> None:
    source_icon = "💾" if cache_hit else "📡"
    source_label = "缓存模式" if cache_hit else "实时拉取"
    st.markdown(
        f"""
        <div class="hero-shell">
            <p class="hero-kicker">CFD Team Console</p>
            <h1 class="hero-title">工时轨道指挥台</h1>
            <p class="hero-subtitle">按日 / 周 / 季度追踪成员工时，快速识别风险成员并触发提醒。</p>
            <div class="hero-chip-row">
                <span class="hero-chip">{source_icon} {source_label}</span>
                <span class="hero-chip">📅 统计日 {ranges["today"]}</span>
                <span class="hero-chip">📆 周起始 {ranges["week_start"]}</span>
                <span class="hero-chip">🧭 季度 {ranges["quarter_key"]}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ── 侧边栏：参数选择 ─────────────────────────────────────
with st.sidebar:
    st.markdown(
        """
        <div class="side-brand">
            <p class="title">CFD 团队管理</p>
            <p class="sub">Operational cockpit for worklog rhythm</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    sub_menu = st.selectbox(
        "导航",
        ["CFD 工时看板", "Bug统计"],
        index=0,
        label_visibility="collapsed",
    )

    if sub_menu == "CFD 工时看板":
        st.divider()
        default_target_date = latest_workday(date.today())
        target_date = st.date_input(
            "统计日期",
            value=default_target_date,
            max_value=date.today(),
        )
        view = st.radio(
            "展示模式",
            ["全部（日/周/季度）", "仅日", "仅周", "仅季度"],
            index=0,
        )
        send_email_toggle = st.toggle("启用邮件提醒", value=False)
        refresh_btn = st.button("🔄 刷新数据", use_container_width=True, type="primary")
        with st.expander("高级选项", expanded=False):
            force_refresh = st.checkbox("强制重新拉取 Jira（忽略缓存）", value=False)
        st.caption(f"日工时目标：`{cfg.daily_target_hours} h`")


if sub_menu == "Bug统计":
    render_bug_placeholder()
    st.stop()


# ── 数据加载（带缓存）────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def load_data(target: date, force: bool):
    ranges = date_ranges(target)
    members = get_team_members(cfg)
    member_ids = {m["accountId"] for m in members}
    holidays = get_cn_holidays(target.year)
    issues: list[dict] | None = None

    cache = check_cache(cfg, target)
    cache_hit = cache.get("daily", False) and not force

    if not cache_hit:
        q_start = date(target.year, (target.month - 1) // 3 * 3 + 1, 1).isoformat()
        issues = search_jira_issues(cfg, list(member_ids), q_start, ranges["today"])
        stats = aggregate(issues, member_ids, holidays)
        daily_rows, weekly_rows, quarterly_rows = build_db_rows(stats)
        daily_rows = ensure_member_rows(daily_rows, members, "work_date", ranges["today"])
        weekly_rows = ensure_member_rows(weekly_rows, members, "week_start", ranges["week_start"])
        quarterly_rows = ensure_member_rows(quarterly_rows, members, "quarter_key", ranges["quarter_key"])
        upsert_rows(cfg, "worklog_daily", daily_rows)
        upsert_rows(cfg, "worklog_weekly", weekly_rows)
        upsert_rows(cfg, "worklog_quarterly", quarterly_rows)

    entries_cache_hit = check_entries_cache(cfg, ranges["today"])
    if force or not entries_cache_hit:
        if issues is None:
            issues = search_jira_issues(cfg, list(member_ids), ranges["today"], ranges["today"])
        entry_rows = build_entry_rows(issues, member_ids, ranges["today"], holidays)
        upsert_entry_rows(cfg, entry_rows)

    daily = ensure_member_rows(fetch_daily(cfg, ranges["today"]), members, "work_date", ranges["today"])
    weekly = ensure_member_rows(fetch_weekly(cfg, ranges["week_start"]), members, "week_start", ranges["week_start"])
    quarterly = ensure_member_rows(fetch_quarterly(cfg, ranges["quarter_key"]), members, "quarter_key", ranges["quarter_key"])
    return daily, weekly, quarterly, ranges, cache_hit


if refresh_btn:
    st.cache_data.clear()

with st.spinner("加载数据中..."):
    try:
        daily, weekly, quarterly, ranges, cache_hit = load_data(target_date, force_refresh)
    except Exception as error:
        st.error(f"数据加载失败：{error}")
        st.stop()

render_hero(ranges, cache_hit)


# ── 辅助函数 ─────────────────────────────────────────────
def rows_to_df(rows):
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(
        [
            {
                "成员": row["display_name"],
                "已记录(h)": s2h(row["logged_sec"]),
                "预估(h)": s2h(row["estimated_sec"]),
                "Issue数": row["issue_count"],
            }
            for row in rows
        ]
    )
    return df.sort_values(by="已记录(h)", ascending=False, kind="mergesort").reset_index(drop=True)


def render_white_table(df: pd.DataFrame) -> None:
    display_df = df.copy()
    for col in ("已记录(h)", "预估(h)", "差值(h)"):
        if col in display_df.columns:
            display_df[col] = display_df[col].map(lambda value: f"{value:.2f}")
    if "达标" in display_df.columns:
        display_df["达标"] = display_df["达标"].map(lambda value: "✅" if bool(value) else "❌")

    html = display_df.to_html(index=False, classes="cfd-table", border=0, escape=True)
    st.markdown(f'<div class="table-shell">{html}</div>', unsafe_allow_html=True)


def render_table(rows, daily_target: float | None = None):
    df = rows_to_df(rows)
    if df.empty:
        st.info("暂无数据")
        return

    if daily_target is not None:
        df["达标"] = df["已记录(h)"] >= daily_target

    render_white_table(df)
    st.bar_chart(df.set_index("成员")[["已记录(h)", "预估(h)"]], height=240)


def render_high_estimate_board(work_date: str) -> None:
    st.markdown('<p class="section-title">📌 高预估任务（当日）</p>', unsafe_allow_html=True)
    st.markdown('<p class="section-desc">聚焦预估工时偏高任务，便于任务拆解与跟进。</p>', unsafe_allow_html=True)

    control_cols = st.columns(3)
    with control_cols[0]:
        threshold_hours = st.number_input(
            "预估阈值(h)",
            min_value=0.0,
            value=5.0,
            step=0.5,
            key="high_estimate_threshold_hours",
        )
    with control_cols[1]:
        page_size = st.selectbox(
            "每页条数",
            options=[10, 20, 50],
            index=0,
            key="high_estimate_page_size",
        )

    query_signature = f"{work_date}|{threshold_hours:.2f}|{page_size}"
    if st.session_state.get("high_estimate_query_signature") != query_signature:
        st.session_state["high_estimate_query_signature"] = query_signature
        st.session_state["high_estimate_page"] = 1

    threshold_sec = int(threshold_hours * 3600)
    total_count = count_high_estimate_entries(cfg, work_date, threshold_sec)
    total_pages = max(1, (total_count + page_size - 1) // page_size)

    current_page = int(st.session_state.get("high_estimate_page", 1))
    current_page = min(max(1, current_page), total_pages)
    st.session_state["high_estimate_page"] = current_page
    page_options = list(range(1, total_pages + 1))

    with control_cols[2]:
        current_page = st.selectbox(
            "页码",
            options=page_options,
            index=page_options.index(current_page),
            key="high_estimate_page",
        )

    rows = fetch_high_estimate_entries(
        cfg=cfg,
        work_date=work_date,
        threshold_sec=threshold_sec,
        page_size=page_size,
        page_no=current_page,
    )

    if rows:
        task_df = pd.DataFrame(
            [
                {
                    "成员": row.get("display_name", ""),
                    "Issue": row.get("issue_key", ""),
                    "摘要": row.get("issue_summary", ""),
                    "预估(h)": s2h(row.get("estimated_sec", 0) or 0),
                    "当日记录(h)": s2h(row.get("time_sec", 0) or 0),
                }
                for row in rows
            ]
        )
        render_white_table(task_df)
    else:
        st.info("暂无满足条件的任务")

    if total_count == 0:
        st.caption("共 0 条任务")
        return

    start_item = (current_page - 1) * page_size + 1
    end_item = min(current_page * page_size, total_count)
    st.caption(f"共 {total_count} 条任务 · 第 {current_page}/{total_pages} 页 · 当前显示 {start_item}-{end_item} 条")


def render_period_block(title: str, description: str, rows, daily_target: float | None = None) -> None:
    st.markdown(f'<p class="section-title">{title}</p>', unsafe_allow_html=True)
    st.markdown(f'<p class="section-desc">{description}</p>', unsafe_allow_html=True)
    render_table(rows, daily_target)


# ── 主内容区 ─────────────────────────────────────────────
show_daily = view in ("全部（日/周/季度）", "仅日")
show_weekly = view in ("全部（日/周/季度）", "仅周")
show_quarterly = view in ("全部（日/周/季度）", "仅季度")

under = find_under_logged(daily, ranges["today"], cfg.daily_target_hours)
daily_count = len(daily)
daily_total_hours = sum(s2h(row["logged_sec"]) for row in daily)
daily_avg_hours = round(daily_total_hours / daily_count, 2) if daily_count else 0.0
daily_ok_count = sum(1 for row in daily if s2h(row["logged_sec"]) >= cfg.daily_target_hours)
daily_ok_rate = round((daily_ok_count / daily_count * 100), 1) if daily_count else 0.0
weekly_total_hours = sum(s2h(row["logged_sec"]) for row in weekly)
quarterly_total_hours = sum(s2h(row["logged_sec"]) for row in quarterly)

metric_row_1 = st.columns(4)
with metric_row_1[0]:
    render_metric_card("团队成员", str(daily_count), "当前统计范围成员数")
with metric_row_1[1]:
    render_metric_card("人均已记录", f"{daily_avg_hours:.2f} h", "当天平均工时")
with metric_row_1[2]:
    render_metric_card("达标率", f"{daily_ok_rate:.1f}%", f"{daily_ok_count} 人达标")
with metric_row_1[3]:
    render_metric_card("待提醒", f"{len(under)} 人", f"阈值 {cfg.daily_target_hours} h")

metric_row_2 = st.columns(2)
with metric_row_2[0]:
    render_metric_card("本周累计工时", f"{weekly_total_hours:.2f} h", f"周起始 {ranges['week_start']}")
with metric_row_2[1]:
    render_metric_card("本季度累计工时", f"{quarterly_total_hours:.2f} h", f"季度 {ranges['quarter_key']}")

if view == "全部（日/周/季度）":
    daily_tab, weekly_tab, quarterly_tab = st.tabs(["📅 今日", "📆 本周", "🛰️ 本季度"])
    with daily_tab:
        render_period_block(
            title=f"今日工时（{ranges['today']}）",
            description="按成员展示当天记录 / 预估工时与达标状态。",
            rows=daily,
            daily_target=cfg.daily_target_hours,
        )
    with weekly_tab:
        render_period_block(
            title=f"本周工时（{ranges['week_start']} 起）",
            description="周维度累计记录与预估情况。",
            rows=weekly,
        )
    with quarterly_tab:
        render_period_block(
            title=f"本季度工时（{ranges['quarter_key']}）",
            description="季度级别工作量全景。",
            rows=quarterly,
        )
else:
    if show_daily:
        render_period_block(
            title=f"今日工时（{ranges['today']}）",
            description="按成员展示当天记录 / 预估工时与达标状态。",
            rows=daily,
            daily_target=cfg.daily_target_hours,
        )
    if show_weekly:
        render_period_block(
            title=f"本周工时（{ranges['week_start']} 起）",
            description="周维度累计记录与预估情况。",
            rows=weekly,
        )
    if show_quarterly:
        render_period_block(
            title=f"本季度工时（{ranges['quarter_key']}）",
            description="季度级别工作量全景。",
            rows=quarterly,
        )

if show_daily:
    st.divider()
    render_high_estimate_board(ranges["today"])


# ── 工时不足提醒区 ────────────────────────────────────────
if show_daily:
    st.divider()
    st.markdown('<p class="section-title">🔔 工时不足提醒</p>', unsafe_allow_html=True)
    st.markdown('<p class="section-desc">自动识别未达日目标成员并支持邮件提醒。</p>', unsafe_allow_html=True)

    if under:
        st.warning(f"今日工时不足 {cfg.daily_target_hours}h 的成员（共 {len(under)} 人）")
        under_df = pd.DataFrame(
            [
                {
                    "成员": member["name"],
                    "已记录(h)": member["logged_hours"],
                    "差值(h)": round(cfg.daily_target_hours - member["logged_hours"], 2),
                }
                for member in under
            ]
        )
        render_white_table(under_df)

        if send_email_toggle and st.button("📧 立即发送提醒邮件"):
            with st.spinner("发送中..."):
                sent, skipped = send_reminders(under, ranges["today"], cfg)
            st.success(f"成功发送 {len(sent)} 封")
            if skipped:
                st.warning("跳过：" + "、".join(skipped))
    else:
        st.success("✅ 今日所有有记录成员工时均达标")

