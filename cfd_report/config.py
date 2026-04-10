from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


def _as_bool(raw: str, default: bool) -> bool:
    if raw is None:
        return default
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "y", "on"}:
        return True
    if value in {"0", "false", "no", "n", "off"}:
        return False
    return default


@dataclass
class Config:
    # Atlassian
    atlassian_user_email: str = ""
    atlassian_api_token: str = ""
    atlassian_cloud_url: str = "https://ddmarketinghub.atlassian.net"
    cfd_team_id: str = "3fd8537f-41c2-4c8e-b818-1e8cfea9746c"
    cfd_org_id: str = "5aka0cj1-0b28-1k26-79a4-15763431dkd2"

    # Supabase
    supabase_url: str = "https://onsxzhkogrzdwqftqsea.supabase.co"
    supabase_anon_key: str = ""

    # SMTP
    smtp_host: str = "smtp.exmail.qq.com"
    smtp_port: int = 465
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_sender: str = ""

    # Business
    daily_target_hours: float = 7.5
    member_email_map: dict[str, str] = field(default_factory=dict)
    webui_auto_sync_on_query: bool = False

    @classmethod
    def from_env(cls) -> "Config":
        email_map_raw = os.getenv("MEMBER_EMAIL_MAP", "{}")
        try:
            email_map = json.loads(email_map_raw)
        except json.JSONDecodeError:
            email_map = {}

        return cls(
            atlassian_user_email=os.getenv("ATLASSIAN_USER_EMAIL", ""),
            atlassian_api_token=os.getenv("ATLASSIAN_API_TOKEN", ""),
            atlassian_cloud_url=os.getenv("ATLASSIAN_CLOUD_URL", "https://ddmarketinghub.atlassian.net"),
            cfd_team_id=os.getenv("CFD_TEAM_ID", "3fd8537f-41c2-4c8e-b818-1e8cfea9746c"),
            cfd_org_id=os.getenv("CFD_ORG_ID", "5aka0cj1-0b28-1k26-79a4-15763431dkd2"),
            supabase_url=os.getenv("SUPABASE_URL", "https://onsxzhkogrzdwqftqsea.supabase.co"),
            supabase_anon_key=os.getenv("SUPABASE_ANON_KEY", ""),
            smtp_host=os.getenv("SMTP_HOST", "smtp.exmail.qq.com"),
            smtp_port=int(os.getenv("SMTP_PORT", "465")),
            smtp_user=os.getenv("SMTP_USER", ""),
            smtp_password=os.getenv("SMTP_PASSWORD", ""),
            smtp_sender=os.getenv("SMTP_SENDER", ""),
            daily_target_hours=float(os.getenv("DAILY_TARGET_HOURS", "7.5")),
            member_email_map=email_map,
            webui_auto_sync_on_query=_as_bool(os.getenv("WEBUI_AUTO_SYNC_ON_QUERY", "false"), False),
        )
