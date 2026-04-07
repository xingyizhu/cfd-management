from __future__ import annotations

import json
import urllib.request
from datetime import date, timedelta


_CN_HOLIDAYS_2026 = [
    "2026-01-01",
    "2026-02-17", "2026-02-18", "2026-02-19", "2026-02-20",
    "2026-02-21", "2026-02-22", "2026-02-23",
    "2026-04-05", "2026-04-06", "2026-04-07",
    "2026-05-01", "2026-05-02", "2026-05-03", "2026-05-04", "2026-05-05",
    "2026-05-31", "2026-06-01", "2026-06-02",
    "2026-10-01", "2026-10-02", "2026-10-03",
    "2026-10-04", "2026-10-05", "2026-10-06", "2026-10-07",
]

_CN_HOLIDAYS_2025 = [
    "2025-01-01",
    "2025-01-28", "2025-01-29", "2025-01-30", "2025-01-31",
    "2025-02-01", "2025-02-02", "2025-02-03",
    "2025-04-04", "2025-04-05", "2025-04-06",
    "2025-05-01", "2025-05-02", "2025-05-03", "2025-05-04", "2025-05-05",
    "2025-05-31", "2025-06-01", "2025-06-02",
    "2025-10-01", "2025-10-02", "2025-10-03",
    "2025-10-04", "2025-10-05", "2025-10-06", "2025-10-07",
]

_HARDCODED: dict[int, list[str]] = {
    2025: _CN_HOLIDAYS_2025,
    2026: _CN_HOLIDAYS_2026,
}


def get_cn_holidays(year: int | None = None) -> set[str]:
    if year is None:
        year = date.today().year
    try:
        url = f"https://date.nager.at/api/v3/PublicHolidays/{year}/CN"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read())
            return {h["date"] for h in data}
    except Exception:
        return set(_HARDCODED.get(year, []))


def is_workday(date_str: str, holidays: set[str]) -> bool:
    d = date.fromisoformat(date_str)
    return d.weekday() < 5 and date_str not in holidays


def latest_workday(ref_date: date | None = None) -> date:
    """若给定日期不是工作日，回退到最近一个工作日。"""
    current = ref_date or date.today()
    holidays_by_year: dict[int, set[str]] = {}

    while True:
        if current.year not in holidays_by_year:
            holidays_by_year[current.year] = get_cn_holidays(current.year)
        if is_workday(current.isoformat(), holidays_by_year[current.year]):
            return current
        current -= timedelta(days=1)
