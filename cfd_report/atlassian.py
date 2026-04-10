from __future__ import annotations

import base64
import time
from typing import Any

import requests

from .config import Config


def _auth_header(cfg: Config) -> str:
    raw = f"{cfg.atlassian_user_email}:{cfg.atlassian_api_token}"
    return "Basic " + base64.b64encode(raw.encode()).decode()


def _fetch_user_profiles_bulk(
    cfg: Config,
    auth: str,
    account_ids: list[str],
) -> dict[str, dict[str, Any]]:
    """Fetch Jira users in bulk and map by accountId."""
    if not account_ids:
        return {}

    profiles: dict[str, dict[str, Any]] = {}
    batch_size = 100
    user_bulk_url = f"{cfg.atlassian_cloud_url}/rest/api/3/user/bulk"

    for idx in range(0, len(account_ids), batch_size):
        batch_ids = account_ids[idx:idx + batch_size]
        start_at = 0
        while True:
            params: list[tuple[str, Any]] = [("accountId", account_id) for account_id in batch_ids]
            params.extend([("startAt", start_at), ("maxResults", batch_size)])
            response = requests.get(
                user_bulk_url,
                params=params,
                headers={"Authorization": auth, "Accept": "application/json"},
                timeout=15,
            )
            response.raise_for_status()
            payload = response.json()
            for user in payload.get("values", []):
                account_id = user.get("accountId")
                if not account_id:
                    continue
                profiles[account_id] = {
                    "accountId": account_id,
                    "displayName": user.get("displayName", account_id),
                    "emailAddress": user.get("emailAddress", ""),
                    "active": user.get("active", True),
                }

            if payload.get("isLast", True):
                break

            start_at += int(payload.get("maxResults", batch_size))

    return profiles


def get_team_members(cfg: Config) -> list[dict[str, Any]]:
    """通过 Atlassian Teams API 获取 CFD 团队成员列表。"""
    auth = _auth_header(cfg)
    url = (
        f"https://api.atlassian.com/gateway/api/public/teams/v1"
        f"/org/{cfg.cfd_org_id}/teams/{cfg.cfd_team_id}/members"
    )
    resp = requests.post(
        url,
        json={"maxResults": 100},
        headers={"Authorization": auth, "Accept": "application/json"},
        timeout=15,
    )
    resp.raise_for_status()
    account_ids = [m["accountId"] for m in resp.json().get("results", []) if m.get("accountId")]

    if not account_ids:
        return []

    try:
        member_by_id = _fetch_user_profiles_bulk(cfg, auth, account_ids)
    except Exception:
        member_by_id = {}

    return [
        member_by_id.get(
            account_id,
            {
                "accountId": account_id,
                "displayName": account_id,
                "emailAddress": "",
                "active": True,
            },
        )
        for account_id in account_ids
    ]


def search_jira_issues(
    cfg: Config,
    account_ids: list[str],
    date_from: str,
    date_to: str,
    max_results: int = 100,
) -> list[dict[str, Any]]:
    """使用 JQL 查询指定成员在指定时间范围内的含 worklog 的 Issue。"""
    auth = _auth_header(cfg)
    ids_str = ", ".join(account_ids)
    jql = (
        f'worklogAuthor in ({ids_str}) '
        f'AND worklogDate >= "{date_from}" '
        f'AND worklogDate <= "{date_to}"'
    )
    fields = ["summary", "status", "issuetype", "assignee",
              "timespent", "timeoriginalestimate", "worklog"]

    url = f"{cfg.atlassian_cloud_url}/rest/api/3/search/jql"
    issues: list[dict[str, Any]] = []
    next_page_token: str | None = None

    while True:
        params: dict[str, Any] = {
            "jql": jql,
            "fields": fields,
            "maxResults": max_results,
        }
        if next_page_token:
            params["nextPageToken"] = next_page_token

        resp = requests.get(
            url,
            params=params,
            headers={"Authorization": auth, "Accept": "application/json"},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        batch = data.get("issues", [])
        issues.extend(batch)

        # 若 worklog 超过 20 条则分页补全
        for issue in batch:
            wl = issue.get("fields", {}).get("worklog", {})
            if wl.get("total", 0) > len(wl.get("worklogs", [])):
                issue["fields"]["worklog"]["worklogs"] = _fetch_all_worklogs(
                    cfg, issue["id"]
                )

        next_page_token = data.get("nextPageToken")
        if data.get("isLast", False) or not next_page_token:
            break
    return issues


def _fetch_all_worklogs(cfg: Config, issue_id: str) -> list[dict[str, Any]]:
    auth = _auth_header(cfg)
    url = f"{cfg.atlassian_cloud_url}/rest/api/3/issue/{issue_id}/worklog"
    worklogs: list[dict[str, Any]] = []
    start_at = 0
    while True:
        resp = requests.get(
            url,
            params={"startAt": start_at, "maxResults": 100},
            headers={"Authorization": auth, "Accept": "application/json"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        batch = data.get("worklogs", [])
        worklogs.extend(batch)
        start_at += len(batch)
        if start_at >= data.get("total", 0):
            break
        time.sleep(0.1)
    return worklogs
