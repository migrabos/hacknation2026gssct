"""Shared date helpers: one notion of "today" (Polish local time) and leap-safe year shifts.

Servers usually run in UTC while farmers pick dates in Polish time; between 00:00 and
01:00/02:00 PL the two disagree on what "today" is. Use `today_pl()` everywhere.
"""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Warsaw")


def today_pl() -> date:
    return datetime.now(TZ).date()


def shift_years(d: date, years: int) -> date:
    """Same calendar day `years` later/earlier; 29 Feb -> 28 Feb in non-leap years."""
    try:
        return d.replace(year=d.year + years)
    except ValueError:
        return d.replace(year=d.year + years, day=28)
