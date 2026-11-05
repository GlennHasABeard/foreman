#!/usr/bin/env python3
"""Home "Due today" calendar (v1.2). Separate from the bot health panel.

schedule.json:
  {"rules": [{"name": "Follow Audit", "due": [0, 6]}], "off": ["2026-11-05"]}

`due` entries are weekday numbers (Monday is 0) or names (mon, sunday).
A date in `off` clears the whole day.
"""
from datetime import date, datetime

_NAMES = {
    "mon": 0, "monday": 0, "tue": 1, "tues": 1, "tuesday": 1,
    "wed": 2, "wednesday": 2, "thu": 3, "thur": 3, "thurs": 3, "thursday": 3,
    "fri": 4, "friday": 4, "sat": 5, "saturday": 5, "sun": 6, "sunday": 6,
}


def _weekday(value):
    if isinstance(value, int):
        return value
    raw = str(value).strip().lower()
    if raw.isdigit():
        return int(raw)
    return _NAMES.get(raw)


def due_today(schedule, today=None):
    """Names whose `due` rule includes today and whose date is not in `off`."""
    schedule = schedule or {}
    if today is None:
        today = date.today()
    if isinstance(today, datetime):
        today = today.date()
    off = {str(d)[:10] for d in (schedule.get("off") or [])}
    if today.isoformat() in off:
        return []
    names = []
    rules = schedule.get("rules") or schedule.get("items") or []
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        dues = [_weekday(d) for d in (rule.get("due") or [])]
        if today.weekday() in dues:
            names.append(rule.get("name") or rule.get("title") or "Untitled")
    return names


def due_html_items(names):
    return list(names or [])
