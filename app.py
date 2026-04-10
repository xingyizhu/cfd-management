"""CFD 团队工时统计 - Streamlit Web UI."""
from __future__ import annotations

import html
import json
from datetime import date, timedelta
from math import ceil
from textwrap import dedent
from urllib.parse import quote

import pandas as pd
import streamlit as st

from cfd_report.ai_summary import (
    build_rule_member_summary,
    is_ai_summary_enabled,
    summarize_member_task_cards,
)
from cfd_report.aggregator import (
    aggregate_high_estimate_range_entries,
    aggregate_member_task_summary_cards,
    aggregate_no_estimate_range_entries,
    aggregate_member_range_rows,
    find_under_logged_range,
    iter_workdays,
)
from cfd_report.atlassian import get_team_members
from cfd_report.config import Config
from cfd_report.emailer import send_reminders
from cfd_report.holidays import get_cn_holidays
from cfd_report.reporter import range_meta, s2h
from cfd_report.supabase_client import (
    fetch_daily_range,
    fetch_entries_range,
    fetch_entries_range_for_member_aggregate,
)
from cfd_report.sync import sync_range_window

st.set_page_config(page_title="CFD 工时统计", page_icon="📊", layout="wide")

cfg = Config.from_env()
auto_sync_on_query = bool(getattr(cfg, "webui_auto_sync_on_query", False))


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;500;700&family=Noto+Serif+SC:wght@500;700&display=swap');

        :root {
            --bg-0: #080d1b;
            --bg-1: #111b34;
            --border: rgba(145, 175, 255, 0.28);
            --text-main: #eff5ff;
            --text-sub: #b9c8eb;
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

        table.cfd-table a {
            color: #8fd3ff;
            text-decoration: none;
        }

        table.cfd-table a:hover {
            text-decoration: underline;
        }

        .member-card-shell {
            border: 1px solid rgba(143, 173, 253, 0.26);
            border-radius: 18px;
            background: linear-gradient(160deg, rgba(15, 28, 58, 0.92), rgba(8, 18, 38, 0.92));
            box-shadow: var(--shadow);
            padding: 1rem 1.05rem;
            margin-bottom: 1rem;
        }

        .member-card-head {
            display: flex;
            justify-content: space-between;
            gap: 1rem;
            flex-wrap: wrap;
            align-items: flex-start;
        }

        .member-card-name {
            margin: 0;
            font-size: 1.08rem;
            color: #f5f8ff;
            font-weight: 700;
        }

        .member-card-summary {
            margin: 0.32rem 0 0;
            color: var(--text-sub);
            font-size: 0.9rem;
            line-height: 1.55;
        }

        .member-chip-row {
            display: flex;
            gap: 0.45rem;
            flex-wrap: wrap;
            justify-content: flex-end;
        }

        .member-chip {
            display: inline-flex;
            align-items: center;
            padding: 0.3rem 0.65rem;
            border-radius: 999px;
            border: 1px solid rgba(147, 178, 255, 0.28);
            background: rgba(20, 35, 70, 0.72);
            color: #dce8ff;
            font-size: 0.8rem;
            white-space: nowrap;
        }

        .project-block {
            margin-top: 0.95rem;
            padding-top: 0.9rem;
            border-top: 1px solid rgba(132, 161, 230, 0.18);
        }

        .project-title {
            margin: 0;
            font-size: 0.98rem;
            font-weight: 700;
            color: #eef4ff;
        }

        .project-note {
            margin: 0.18rem 0 0.45rem;
            font-size: 0.82rem;
            color: #a9bbe4;
        }

        div[data-testid="stAlert"] {
            border-radius: 12px;
            border: 1px solid rgba(143, 175, 250, 0.34);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


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
            <p class="hero-subtitle">页面已预留，后续可接入 Jira Bug 趋势与责任人维度统计。</p>
            <div class="hero-chip-row">
                <span class="hero-chip">📈 趋势追踪</span>
                <span class="hero-chip">👥 责任分布</span>
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

def render_hero(meta: dict[str, object], cache_hit: bool) -> None:
    source_icon = "🗄️" if cache_hit else "📋"
    source_label = "数据库缓存" if cache_hit else "Jira 实时同步"
    st.markdown(
        f"""
        <div class="hero-shell">
            <p class="hero-kicker">CFD Team Console</p>
            <h1 class="hero-title">工时范围看板</h1>
            <p class="hero-subtitle">按时间范围聚合成员工时，统一查看区间累计、风险成员与任务估时情况。</p>
            <div class="hero-chip-row">
                <span class="hero-chip">{source_icon} {source_label}</span>
                <span class="hero-chip">📅 开始 {meta['date_from_str']}</span>
                <span class="hero-chip">🗓️ 结束 {meta['date_to_str']}</span>
                <span class="hero-chip">🧮 工作日 {meta['workday_count']} 天</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

def rows_to_df(rows: list[dict[str, object]], required_hours: float | None = None) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()

    data: list[dict[str, object]] = []
    for row in rows:
        record = {
            "成员": row["display_name"],
            "已记录(h)": s2h(row.get("logged_sec")),
            "预估(h)": s2h(row.get("estimated_sec")),
            "Issue数": row.get("issue_count", 0),
        }
        if required_hours is not None:
            record["目标(h)"] = round(required_hours, 2)
            record["差值(h)"] = round(record["已记录(h)"] - required_hours, 2)
            record["达标"] = bool(record["已记录(h)"] >= required_hours)
        data.append(record)

    return pd.DataFrame(data)

def render_white_table(df: pd.DataFrame) -> None:
    display_df = df.copy()
    for col in ("已记录(h)", "预估(h)", "目标(h)", "差值(h)", "区间记录(h)"):
        if col in display_df.columns:
            display_df[col] = display_df[col].map(lambda value: f"{value:.2f}")
    if "达标" in display_df.columns:
        display_df["达标"] = display_df["达标"].map(lambda value: "是" if bool(value) else "否")

    table_html = display_df.to_html(index=False, classes="cfd-table", border=0, escape=True)
    st.markdown(f'<div class="table-shell">{table_html}</div>', unsafe_allow_html=True)

def render_range_summary(range_rows: list[dict[str, object]], required_hours: float) -> None:
    st.markdown('<p class="section-title">工时范围汇总</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="section-desc">按成员展示所选时间范围内的累计工时、去重预估和达标状态。</p>',
        unsafe_allow_html=True,
    )

    df = rows_to_df(range_rows, required_hours=required_hours)
    if df.empty:
        st.info("当前范围暂无数据。")
        return

    render_white_table(df)
    st.bar_chart(df.set_index("成员")[["已记录(h)", "预估(h)"]], height=260)

def _build_issue_url(issue_key: str) -> str:
    if not issue_key:
        return ""
    base_url = (cfg.atlassian_cloud_url or "").rstrip("/")
    if not base_url:
        return ""
    return f"{base_url}/browse/{quote(issue_key, safe='-')}"


def _build_issue_link_html(issue_key: str) -> str:
    issue_url = _build_issue_url(issue_key)
    issue_cell = html.escape(issue_key)
    if issue_url:
        issue_cell = (
            f'<a href="{html.escape(issue_url, quote=True)}" '
            f'target="_blank" rel="noopener noreferrer">{html.escape(issue_key)}</a>'
        )
    return issue_cell


def _format_project_label(project_key: str, project_name: str) -> str:
    safe_key = (project_key or "").strip()
    safe_name = (project_name or "").strip()
    if safe_key and safe_name and safe_name != safe_key:
        return f"{safe_key} · {safe_name}"
    return safe_key or safe_name or "未识别项目"


def _build_table_html(df: pd.DataFrame, *, escape: bool) -> str:
    return df.to_html(index=False, classes="cfd-table", border=0, escape=escape)


def render_issue_task_table(rows: list[dict[str, object]]) -> None:
    table_rows: list[dict[str, str]] = []

    for row in rows:
        issue_key = str(row.get("issue_key", ""))
        table_rows.append(
            {
                "成员": html.escape(str(row.get("display_name", ""))),
                "Issue": _build_issue_link_html(issue_key),
                "摘要": html.escape(str(row.get("issue_summary", ""))),
                "预估(h)": f"{s2h(row.get('estimated_sec')):.2f}",
                "区间记录(h)": f"{s2h(row.get('time_sec')):.2f}",
            }
        )

    table_df = pd.DataFrame(table_rows)
    table_html = _build_table_html(table_df, escape=False)
    st.markdown(f'<div class="table-shell">{table_html}</div>', unsafe_allow_html=True)


def _build_project_task_table_html(tasks: list[dict[str, object]]) -> str:
    table_rows: list[dict[str, str]] = []
    for task in tasks:
        issue_key = str(task.get("issue_key", ""))
        table_rows.append(
            {
                "Issue": _build_issue_link_html(issue_key),
                "摘要": html.escape(str(task.get("issue_summary", ""))),
                "进度": html.escape(str(task.get("status_name", "") or "未知")),
                "预估(h)": f"{s2h(task.get('estimated_sec')):.2f}",
                "区间记录(h)": f"{s2h(task.get('time_sec')):.2f}",
            }
        )

    if not table_rows:
        return ""

    table_df = pd.DataFrame(table_rows)
    return _build_table_html(table_df, escape=False)


def _build_member_task_card_html(member: dict[str, object]) -> str:
    chip_items = [
        f"已记录 {s2h(member.get('total_time_sec')):.2f} h",
        f"任务 {int(member.get('task_count', 0) or 0)} 个",
        f"项目 {int(member.get('project_count', 0) or 0)} 个",
        f"Done {int(member.get('done_task_count', 0) or 0)} 个",
    ]
    chip_html = "".join(
        f'<span class="member-chip">{html.escape(item)}</span>'
        for item in chip_items
    )

    project_sections: list[str] = []
    for project in member.get("projects", []):
        project_label = _format_project_label(
            str(project.get("project_key", "")),
            str(project.get("project_name", "")),
        )
        table_html = _build_project_task_table_html(project.get("tasks", []))
        project_sections.append(
            dedent(
                f"""
                <div class="project-block">
                    <p class="project-title">{html.escape(project_label)}</p>
                    <p class="project-note">
                        任务 {int(project.get("task_count", 0) or 0)} 个 ·
                        已记录 {s2h(project.get("total_time_sec")):.2f} h
                    </p>
                    <div class="table-shell">{table_html}</div>
                </div>
                """
            ).strip()
        )

    return dedent(
        f"""
        <div class="member-card-shell">
            <div class="member-card-head">
                <div>
                    <p class="member-card-name">{html.escape(str(member.get("display_name", "")))}</p>
                    <p class="member-card-summary">{html.escape(str(member.get("summary_text", "")))}</p>
                </div>
                <div class="member-chip-row">{chip_html}</div>
            </div>
            {''.join(project_sections)}
        </div>
        """
    ).strip()


def render_estimate_task_board(meta: dict[str, object]) -> None:
    st.markdown('<p class="section-title">任务估时看板</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="section-desc">在同一区块切换查看“无预估任务”和“高预估任务”，Issue 支持直接跳转 Jira 详情。</p>',
        unsafe_allow_html=True,
    )

    if not st.session_state.get("estimate_board_loaded", False):
        if st.button("加载任务明细", key="estimate_board_load_btn", use_container_width=True):
            st.session_state["estimate_board_loaded"] = True
            st.rerun()
        st.caption("未加载时仅展示摘要，点击后再查询任务明细数据。")
        return

    with st.spinner("加载任务明细中..."):
        entry_rows = load_estimate_entries(meta["date_from_str"], meta["date_to_str"])

    st.session_state.setdefault("estimate_board_view", "no_estimate")
    st.session_state.setdefault("estimate_board_threshold_hours", 5.0)

    control_cols = st.columns(4)
    with control_cols[0]:
        selected_view = st.radio(
            "任务视图",
            options=["no_estimate", "high_estimate"],
            format_func=lambda item: "无预估任务" if item == "no_estimate" else "高预估任务",
            horizontal=True,
            key="estimate_board_view",
        )

    with control_cols[1]:
        page_size = st.selectbox(
            "每页条数",
            options=[10, 20, 50],
            index=0,
            key="estimate_board_page_size",
        )

    threshold_hours = float(st.session_state.get("estimate_board_threshold_hours", 5.0))
    if selected_view == "high_estimate":
        with control_cols[2]:
            threshold_hours = st.number_input(
                "预估阈值(h)",
                min_value=0.0,
                value=threshold_hours,
                step=0.5,
                key="estimate_board_threshold_hours",
            )

    if selected_view == "high_estimate":
        threshold_sec = int(threshold_hours * 3600)
        aggregated_rows = aggregate_high_estimate_range_entries(entry_rows, threshold_sec)
        query_signature = (
            f"high|{meta['date_from_str']}|{meta['date_to_str']}|{threshold_hours:.2f}|{page_size}"
        )
        query_signature_key = "estimate_board_high_query_signature"
        page_key = "estimate_board_page_high"
    else:
        aggregated_rows = aggregate_no_estimate_range_entries(entry_rows)
        query_signature = f"no|{meta['date_from_str']}|{meta['date_to_str']}|{page_size}"
        query_signature_key = "estimate_board_no_estimate_query_signature"
        page_key = "estimate_board_page_no_estimate"

    total_count = len(aggregated_rows)
    total_pages = max(1, ceil(total_count / page_size)) if total_count else 1
    if st.session_state.get(query_signature_key) != query_signature:
        st.session_state[query_signature_key] = query_signature
        st.session_state[page_key] = 1

    current_page = int(st.session_state.get(page_key, 1))
    current_page = min(max(1, current_page), total_pages)
    st.session_state[page_key] = current_page
    page_options = list(range(1, total_pages + 1))

    with control_cols[3]:
        current_page = st.selectbox(
            "页码",
            options=page_options,
            index=page_options.index(current_page),
            key=page_key,
        )

    start_idx = (current_page - 1) * page_size
    page_rows = aggregated_rows[start_idx:start_idx + page_size]
    if not page_rows:
        st.info("暂无满足条件的任务。")
        st.caption(f"共 {total_count} 条任务")
        return

    render_issue_task_table(page_rows)
    end_idx = min(start_idx + page_size, total_count)
    if selected_view == "high_estimate":
        st.caption(
            f"高预估任务共 {total_count} 条（阈值 {threshold_hours:.2f}h），当前显示 {start_idx + 1}-{end_idx} 条"
        )
    else:
        st.caption(f"无预估任务共 {total_count} 条，当前显示 {start_idx + 1}-{end_idx} 条")


def render_member_task_summary_board(meta: dict[str, object]) -> None:
    st.markdown('<p class="section-title">成员任务归纳</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="section-desc">展示成员在所选时间范围内登记过时间追踪的任务，并按 Jira 项目空间 - 事项 - 进度 归纳。</p>',
        unsafe_allow_html=True,
    )

    if not st.session_state.get("member_task_board_loaded", False):
        if st.button("加载成员任务归纳", key="member_task_board_load_btn", use_container_width=True):
            st.session_state["member_task_board_loaded"] = True
            st.rerun()
        st.caption("未加载时不查询任务明细，点击后再按成员生成任务归纳。")
        return

    with st.spinner("归纳成员任务中..."):
        entry_rows = load_estimate_entries(meta["date_from_str"], meta["date_to_str"])

    member_cards = aggregate_member_task_summary_cards(entry_rows)
    if not member_cards:
        st.info("当前范围内暂无成员登记时间追踪任务。")
        return

    ai_summary_result: dict[str, object] = {"summaries": {}, "used_ai": False, "error": None}
    if is_ai_summary_enabled(cfg):
        member_cards_signature = json.dumps(member_cards, ensure_ascii=False, sort_keys=True)
        with st.spinner("生成 AI 汇报话术中..."):
            ai_summary_result = load_member_ai_summaries(member_cards_signature)

    summaries = ai_summary_result.get("summaries", {}) or {}
    if isinstance(summaries, dict):
        for member in member_cards:
            account_id = str(member.get("account_id", "") or "").strip()
            summary_text = str(summaries.get(account_id, "") or "").strip()
            if summary_text:
                member["summary_text"] = summary_text
            else:
                member["summary_text"] = build_rule_member_summary(member)

    has_missing_detail = _has_missing_entry_detail(entry_rows)
    if has_missing_detail:
        st.info("系统已尝试自动补同步 Jira。若仍有任务缺少项目或状态字段，请执行一次“强制重新拉取 Jira”并确认 Supabase 已新增相关列。")

    if not ai_summary_result.get("used_ai", False):
        error_hint = str(ai_summary_result.get("error", "") or "").strip()
        if is_ai_summary_enabled(cfg):
            if error_hint:
                st.caption(f"AI 汇报话术生成失败（{error_hint}），当前显示规则摘要。")
            else:
                st.caption("AI 汇报话术生成失败，当前显示规则摘要。")
        else:
            st.caption("未配置 OpenAI API，当前显示规则摘要。")

    total_tasks = sum(int(card.get("task_count", 0) or 0) for card in member_cards)
    st.caption(f"共 {len(member_cards)} 名成员，登记了 {total_tasks} 个任务。")

    for member in member_cards:
        st.markdown(_build_member_task_card_html(member), unsafe_allow_html=True)


def render_under_logged_section(
    under_logged: list[dict[str, object]],
    meta: dict[str, object],
    send_email_toggle: bool,
    required_hours: float,
) -> None:
    st.markdown('<p class="section-title">工时不足提醒</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="section-desc">按所选时间范围识别未达到目标工时的成员，并支持发送区间提醒邮件。</p>',
        unsafe_allow_html=True,
    )

    if not under_logged:
        st.success("当前范围内所有成员都已达到目标工时。")
        return

    st.warning(f"当前范围内工时不足 {required_hours:.2f}h 的成员，共 {len(under_logged)} 人。")
    under_df = pd.DataFrame(
        [
            {
                "成员": member["name"],
                "已记录(h)": member["logged_hours"],
                "目标(h)": member["required_hours"],
                "差值(h)": member["missing_hours"],
            }
            for member in under_logged
        ]
    )
    render_white_table(under_df)

    if send_email_toggle and st.button("📠 立即发送区间提醒邮件"):
        reminder_context = {
            "date_from": meta["date_from_str"],
            "date_to": meta["date_to_str"],
            "workday_count": meta["workday_count"],
            "required_hours": required_hours,
        }
        with st.spinner("发送中..."):
            sent, skipped = send_reminders(under_logged, reminder_context, cfg)
        st.success(f"成功发送 {len(sent)} 封邮件。")
        if skipped:
            st.warning("跳过：" + "；".join(skipped))

def get_holidays_for_range(start: date, end: date) -> set[str]:
    holidays: set[str] = set()
    for year in range(start.year, end.year + 1):
        holidays.update(get_cn_holidays(year))
    return holidays


def _normalize_date_range(date_from: str, date_to: str) -> tuple[date, date]:
    start = date.fromisoformat(date_from)
    end = date.fromisoformat(date_to)
    if start > end:
        start, end = end, start
    return start, end


@st.cache_data(ttl=14400, show_spinner=False)
def load_team_members() -> list[dict[str, object]]:
    return get_team_members(cfg)


def _has_daily_coverage(meta: dict[str, object], holidays: set[str], daily_rows: list[dict[str, object]]) -> bool:
    expected_dates = set(iter_workdays(meta["date_from_str"], meta["date_to_str"], holidays))
    if not expected_dates:
        return True
    cached_dates = {row.get("work_date") for row in daily_rows if row.get("work_date")}
    return expected_dates.issubset(cached_dates)


def _has_entry_coverage(
    daily_rows: list[dict[str, object]],
    entry_rows: list[dict[str, object]],
) -> bool:
    logged_dates = {
        row.get("work_date")
        for row in daily_rows
        if (row.get("logged_sec", 0) or 0) > 0 and row.get("work_date")
    }
    entry_dates = {row.get("work_date") for row in entry_rows if row.get("work_date")}
    return logged_dates.issubset(entry_dates)


def _has_missing_entry_detail(entry_rows: list[dict[str, object]]) -> bool:
    for row in entry_rows:
        issue_key = str(row.get("issue_key", "") or "").strip()
        if not issue_key:
            continue

        project_key = str(row.get("project_key", "") or "").strip()
        project_name = str(row.get("project_name", "") or "").strip()
        status_name = str(row.get("status_name", "") or "").strip()

        if not project_key or project_key.upper() == "UNKNOWN":
            return True
        if not project_name:
            return True
        if not status_name or status_name == "未知" or status_name.casefold() == "unknown":
            return True
    return False


@st.cache_data(ttl=300, show_spinner=False)
def load_base_data(date_from: str, date_to: str, force_refresh: bool) -> dict[str, object]:
    start, end = _normalize_date_range(date_from, date_to)
    holidays = get_holidays_for_range(start, end)
    meta = range_meta(start, end, holidays)
    members = load_team_members()
    synced = False

    if force_refresh:
        sync_range_window(cfg, start, end, members, holidays)
        synced = True
        daily_rows = fetch_daily_range(cfg, meta["date_from_str"], meta["date_to_str"])
        entry_rows = fetch_entries_range_for_member_aggregate(cfg, meta["date_from_str"], meta["date_to_str"])
    elif auto_sync_on_query:
        daily_rows = fetch_daily_range(cfg, meta["date_from_str"], meta["date_to_str"])
        entry_rows = fetch_entries_range_for_member_aggregate(cfg, meta["date_from_str"], meta["date_to_str"])
        if not (_has_daily_coverage(meta, holidays, daily_rows) and _has_entry_coverage(daily_rows, entry_rows)):
            sync_range_window(cfg, start, end, members, holidays)
            synced = True
            daily_rows = fetch_daily_range(cfg, meta["date_from_str"], meta["date_to_str"])
            entry_rows = fetch_entries_range_for_member_aggregate(cfg, meta["date_from_str"], meta["date_to_str"])
    else:
        # 极速读取模式：默认仅读取 Supabase 缓存，不自动回源 Jira。
        daily_rows = fetch_daily_range(cfg, meta["date_from_str"], meta["date_to_str"])
        entry_rows = fetch_entries_range_for_member_aggregate(cfg, meta["date_from_str"], meta["date_to_str"])

    range_rows = aggregate_member_range_rows(
        daily_rows,
        entry_rows,
        members,
        meta["date_from_str"],
        meta["date_to_str"],
    )

    return {
        "daily_rows": daily_rows,
        "range_rows": range_rows,
        "meta": meta,
        "cache_hit": not synced,
    }


@st.cache_data(ttl=300, show_spinner=False)
def load_estimate_entries(date_from: str, date_to: str) -> list[dict[str, object]]:
    start, end = _normalize_date_range(date_from, date_to)
    date_from_str = start.isoformat()
    date_to_str = end.isoformat()
    entry_rows = fetch_entries_range(cfg, date_from_str, date_to_str)

    if not entry_rows or not _has_missing_entry_detail(entry_rows):
        return entry_rows

    holidays = get_holidays_for_range(start, end)
    members = load_team_members()
    try:
        sync_range_window(cfg, start, end, members, holidays)
    except Exception:
        return entry_rows
    return fetch_entries_range(cfg, date_from_str, date_to_str)


@st.cache_data(ttl=900, show_spinner=False)
def load_member_ai_summaries(member_cards_signature: str) -> dict[str, object]:
    member_cards = json.loads(member_cards_signature)
    result = summarize_member_task_cards(cfg, member_cards)
    return {
        "summaries": result.summaries,
        "used_ai": result.used_ai,
        "error": result.error,
    }


inject_styles()

today = date.today()
week_start = today - timedelta(days=today.weekday())
quarter_start = date(today.year, (today.month - 1) // 3 * 3 + 1, 1)
st.session_state.setdefault("selected_range", (today, today))

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
        st.caption("统计范围")
        quick_cols = st.columns(2)
        with quick_cols[0]:
            if st.button("当周", use_container_width=True):
                st.session_state["selected_range"] = (week_start, today)
        with quick_cols[1]:
            if st.button("当季度", use_container_width=True):
                st.session_state["selected_range"] = (quarter_start, today)

        selected_range = st.date_input(
            "时间范围",
            key="selected_range",
            max_value=today,
        )
        send_email_toggle = st.toggle("启用邮件提醒", value=False)
        refresh_btn = st.button("🔧 刷新数据", use_container_width=True, type="primary")
        with st.expander("高级选项", expanded=False):
            force_refresh = st.checkbox("强制重新拉取 Jira（忽略缓存）", value=False)
        strategy_label = "平衡模式（查询时自动补同步）" if auto_sync_on_query else "极速读取（仅读缓存，缺失明细时补同步）"
        st.caption(f"查询策略：`{strategy_label}`")
        st.caption(f"日工时目标：`{cfg.daily_target_hours} h`")
    else:
        selected_range = (today, today)
        send_email_toggle = False
        refresh_btn = False
        force_refresh = False

if sub_menu == "Bug统计":
    render_bug_placeholder()
    st.stop()

if isinstance(selected_range, (list, tuple)):
    range_start = selected_range[0]
    range_end = selected_range[1] if len(selected_range) > 1 else selected_range[0]
else:
    range_start = selected_range
    range_end = selected_range

if refresh_btn:
    load_base_data.clear()
    load_estimate_entries.clear()

with st.spinner("加载数据中..."):
    try:
        data_bundle = load_base_data(range_start.isoformat(), range_end.isoformat(), force_refresh)
    except Exception as error:
        st.error(f"数据加载失败：{error}")
        st.stop()

meta = data_bundle["meta"]
range_rows = data_bundle["range_rows"]
cache_hit = bool(data_bundle["cache_hit"])
required_hours = meta["workday_count"] * cfg.daily_target_hours
under_logged = find_under_logged_range(range_rows, required_hours)

range_signature = f"{meta['date_from_str']}|{meta['date_to_str']}"
if st.session_state.get("estimate_board_range_signature") != range_signature:
    st.session_state["estimate_board_range_signature"] = range_signature
    st.session_state["estimate_board_loaded"] = False
    st.session_state["member_task_board_loaded"] = False
    st.session_state["estimate_board_view"] = "no_estimate"
    st.session_state["estimate_board_high_query_signature"] = ""
    st.session_state["estimate_board_no_estimate_query_signature"] = ""
    st.session_state["estimate_board_page_high"] = 1
    st.session_state["estimate_board_page_no_estimate"] = 1

render_hero(meta, cache_hit)
if auto_sync_on_query:
    st.caption("当前策略：平衡模式（仅在缓存覆盖不足时自动补同步）。")
else:
    st.caption("当前策略：极速读取（默认只读 Supabase 缓存；任务明细缺少项目或状态字段时会自动补同步，勾选“强制重新拉取 Jira”可全量刷新）。")

member_count = len(range_rows)
total_hours = sum(s2h(row.get("logged_sec")) for row in range_rows)
avg_hours = round(total_hours / member_count, 2) if member_count else 0.0
ok_count = sum(1 for row in range_rows if s2h(row.get("logged_sec")) >= required_hours)
ok_rate = round((ok_count / member_count) * 100, 1) if member_count else 0.0
total_estimated = sum(s2h(row.get("estimated_sec")) for row in range_rows)

metric_row_1 = st.columns(4)
with metric_row_1[0]:
    render_metric_card("团队成员", str(member_count), "当前统计范围内成员数")
with metric_row_1[1]:
    render_metric_card("累计已记录", f"{total_hours:.2f} h", "所选时间范围总工时")
with metric_row_1[2]:
    render_metric_card("人均工时", f"{avg_hours:.2f} h", "成员区间平均记录")
with metric_row_1[3]:
    render_metric_card("达标率", f"{ok_rate:.1f}%", f"{ok_count} 人达到目标")

metric_row_2 = st.columns(3)
with metric_row_2[0]:
    render_metric_card("目标总工时", f"{required_hours:.2f} h", f"{meta['workday_count']} 个工作日")
with metric_row_2[1]:
    render_metric_card("累计预估", f"{total_estimated:.2f} h", "按区间内 Issue 去重")
with metric_row_2[2]:
    render_metric_card("待提醒成员", str(len(under_logged)), f"阈值 {required_hours:.2f} h")

if meta["workday_count"] == 0:
    st.info("所选时间范围内没有工作日，工时目标按 0 小时处理。")

render_range_summary(range_rows, required_hours)

st.divider()
render_estimate_task_board(meta)

st.divider()
render_member_task_summary_board(meta)

st.divider()
render_under_logged_section(under_logged, meta, send_email_toggle, required_hours)


