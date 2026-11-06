#!/usr/bin/env python3
"""Fan Finder backlog copy and expiry (v1.2). Saved data only."""
from datetime import date, datetime, timedelta


def backlog_copy(count, previous):
    """'N people still engaging who don't follow you yet (±D vs last week)'."""
    count = int(count or 0)
    if previous is None:
        delta = "±0"
    else:
        diff = count - int(previous)
        if diff > 0:
            delta = f"+{diff}"
        elif diff < 0:
            delta = f"{diff}"
        else:
            delta = "±0"
    return f"{count} people still engaging who don't follow you yet ({delta} vs last week)"


def likes_off_line(stored_likes, days=14):
    return (f"New like pulls are off to save money; {int(stored_likes)} stored likes from the last "
            f"{int(days)} days still count.")


def _day(value):
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def expire_backlog(people, today, expire_days=30, still_engaging=()):
    """Drop people with no engagement since `expire_days`. Returns (kept, dropped_count).

    people: {id: {username, last}}. still_engaging: ids seen in this run (their last refreshes).
    """
    if isinstance(today, datetime):
        today = today.date()
    fresh = {str(i) for i in (still_engaging or [])}
    kept, dropped = {}, 0
    for uid, rec in (people or {}).items():
        if str(uid) in fresh:
            kept[uid] = rec
            continue
        last = _day((rec or {}).get("last"))
        if last and (today - last).days > int(expire_days):
            dropped += 1
            continue
        kept[uid] = rec
    return kept, dropped


def track_leads_seen(seen, leads, today):
    """Record every qualified lead this run, shown or not.

    seen: {id: {username, first, last, times}}. Dates are ISO days.
    """
    if isinstance(today, datetime):
        today = today.date()
    day = today.isoformat()
    seen = dict(seen or {})
    for lead in leads or []:
        uid = str(lead.get("id"))
        name = ""
        user = lead.get("u") or lead.get("user") or {}
        if isinstance(user, dict):
            name = user.get("username") or ""
        name = name or lead.get("username") or ""
        rec = seen.get(uid) or {"username": name, "first": day, "times": 0}
        rec["username"] = name or rec.get("username") or ""
        rec["first"] = rec.get("first") or day
        rec["last"] = day
        rec["times"] = int(rec.get("times") or 0) + 1
        seen[uid] = rec
    return seen


def previous_week_count(history, today):
    """Count stored about 7 days ago, if one was saved."""
    if isinstance(today, datetime):
        today = today.date()
    weeks = (history or {}).get("by_week") or {}
    target = (today - timedelta(days=7)).isoformat()
    if target in weeks:
        return int(weeks[target])
    older = sorted(k for k in weeks if k <= target)
    if not older:
        return None
    return int(weeks[older[-1]])
