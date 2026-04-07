from __future__ import annotations

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from .config import Config


def send_reminders(
    under_logged: list[dict[str, Any]],
    target_date: str,
    cfg: Config,
) -> tuple[list[str], list[str]]:
    """
    向工时不足的成员发送邮件提醒。

    Returns:
        (sent_names, skipped_notes) 两个列表
    """
    sent: list[str] = []
    skipped: list[str] = []

    for member in under_logged:
        name = member["name"]
        aid = member["accountId"]
        lh = member["logged_hours"]
        diff = round(cfg.daily_target_hours - lh, 2)

        email = cfg.member_email_map.get(aid)
        if not email:
            skipped.append(f"{name}（无邮箱映射）")
            continue

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"【工时提醒】{target_date} 工时记录不足提醒"
        msg["From"] = cfg.smtp_sender or cfg.smtp_user
        msg["To"] = email

        text = (
            f"Hi {name}，\n\n"
            f"系统检测到您今天（{target_date}）在 Jira 中的工时记录为 {lh} 小时，\n"
            f"距离标准工时 {cfg.daily_target_hours} 小时还差 {diff} 小时。\n\n"
            f"请及时在 Jira 中补充今日的工作记录，以确保项目进度统计的准确性。\n\n"
            f"此邮件由系统自动发送，请勿回复。\nCFD 团队管理系统"
        )
        html = (
            f"<html><body>"
            f"<p>Hi <strong>{name}</strong>，</p>"
            f"<p>系统检测到您今天（<strong>{target_date}</strong>）在 Jira 中的工时记录为"
            f"<strong>{lh} 小时</strong>，距离标准工时 {cfg.daily_target_hours} 小时还差"
            f"<strong style='color:red'>{diff} 小时</strong>。</p>"
            f"<p>请及时在 Jira 中补充今日的工作记录，以确保项目进度统计的准确性。</p>"
            f"<br><p style='color:gray;font-size:12px'>此邮件由系统自动发送，请勿回复。<br>"
            f"CFD 团队管理系统</p></body></html>"
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
        except Exception as e:
            skipped.append(f"{name}（发送失败: {e}）")

    return sent, skipped
