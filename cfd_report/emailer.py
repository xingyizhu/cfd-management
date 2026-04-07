from __future__ import annotations

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from .config import Config


def _build_range_label(range_context: dict[str, Any]) -> str:
    date_from = range_context["date_from"]
    date_to = range_context["date_to"]
    if date_from == date_to:
        return date_from
    return f"{date_from} 至 {date_to}"


def send_reminders(
    under_logged: list[dict[str, Any]],
    range_context: dict[str, Any],
    cfg: Config,
) -> tuple[list[str], list[str]]:
    """
    向工时不足的成员发送邮件提醒。

    Returns:
        (sent_names, skipped_notes) 两个列表
    """
    sent: list[str] = []
    skipped: list[str] = []
    range_label = _build_range_label(range_context)
    required_hours = float(range_context.get("required_hours", cfg.daily_target_hours))
    workday_count = int(range_context.get("workday_count", 1))

    for member in under_logged:
        name = member["name"]
        aid = member["accountId"]
        logged_hours = float(member["logged_hours"])
        missing_hours = float(member.get("missing_hours", round(required_hours - logged_hours, 2)))

        email = cfg.member_email_map.get(aid)
        if not email:
            skipped.append(f"{name}（无邮箱映射）")
            continue

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"【工时提醒】{range_label} 工时记录不足提醒"
        msg["From"] = cfg.smtp_sender or cfg.smtp_user
        msg["To"] = email

        text = (
            f"Hi {name}，\n\n"
            f"系统检测到您在 {range_label} 的 Jira 工时记录为 {logged_hours} 小时。\n"
            f"当前统计范围共有 {workday_count} 个工作日，目标工时为 {required_hours} 小时，"
            f"仍差 {missing_hours} 小时。\n\n"
            "请及时在 Jira 中补充对应时间范围内的工作记录，"
            "以确保项目进度统计的准确性。\n\n"
            "此邮件由系统自动发送，请勿回复。\n"
            "CFD 团队管理系统"
        )
        html = (
            "<html><body>"
            f"<p>Hi <strong>{name}</strong>，</p>"
            f"<p>系统检测到您在 <strong>{range_label}</strong> 的 Jira 工时记录为 "
            f"<strong>{logged_hours} 小时</strong>。</p>"
            f"<p>当前统计范围共有 <strong>{workday_count}</strong> 个工作日，"
            f"目标工时为 <strong>{required_hours} 小时</strong>，"
            f"仍差 <strong style='color:red'>{missing_hours} 小时</strong>。</p>"
            "<p>请及时在 Jira 中补充对应时间范围内的工作记录，以确保项目进度统计的准确性。</p>"
            "<br><p style='color:gray;font-size:12px'>此邮件由系统自动发送，请勿回复。<br>"
            "CFD 团队管理系统</p></body></html>"
        )
        msg.attach(MIMEText(text, "plain", "utf-8"))
        msg.attach(MIMEText(html, "html", "utf-8"))

        try:
            if cfg.smtp_port == 465:
                with smtplib.SMTP_SSL(cfg.smtp_host, cfg.smtp_port) as srv:
                    srv.login(cfg.smtp_user, cfg.smtp_password)
                    srv.sendmail(msg["From"], [email], msg.as_string())
            else:
                with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port) as srv:
                    srv.starttls()
                    srv.login(cfg.smtp_user, cfg.smtp_password)
                    srv.sendmail(msg["From"], [email], msg.as_string())
            sent.append(name)
        except Exception as error:
            skipped.append(f"{name}（发送失败: {error}）")

    return sent, skipped
