#!/usr/bin/env python3
"""Saved-data helpers for Follow Audit (v1.2). No X API calls.

  new_follower_headline   the headline count equals the named rows
  skip_newest_read        skip the daily newest-followers read when few were lost
  seven_night_line        threshold plus a 7-night replay
  sunday_rollup           named unfollows for the week, plus the pending unnamed count
"""
from datetime import date, datetime, timedelta


def new_follower_headline(named, followed_back=0, seen_not_listed=0):
    """Headline number is the named new-follower rows. Extras are labelled, not added in."""
    bits = []
    if followed_back:
        bits.append(f"+{int(followed_back)} in Followed you back")
    if seen_not_listed:
        bits.append(f"+{int(seen_not_listed)} seen but not listed")
    text = str(int(named or 0))
    if bits:
        text += " (" + ", ".join(bits) + ")"
    return text


def skip_newest_read(est_lost, threshold=5, force=False):
    """True when the daily newest-followers read should be skipped ($0 for that read).

    Skips when the estimate is `threshold` lost or fewer. A missing estimate does not skip.
    `--force` overrides. The monthly full scan is unchanged.
    """
    if force or est_lost is None:
        return False
    return int(est_lost) <= int(threshold)


def _est(night):
    if night.get("est_lost_before") is not None:
        return night.get("est_lost_before")
    return night.get("est_unfollows")


def seven_night_line(log, threshold=5):
    """Chat and report line: the threshold, and how many of the last 7 nights would have read."""
    nights = list(log or [])[-7:]
    n = len(nights)
    base = (f"Newest-followers read is skipped when the estimate is {int(threshold)} lost or fewer "
            "(--force overrides).")
    if not n:
        return base + " No nights logged yet. The monthly full scan is unchanged."
    would, named, total = 0, 0, 0
    for night in nights:
        got = int(night.get("new_followers") or 0)
        total += got
        est = _est(night)
        if est is None or int(est) > int(threshold):
            would += 1
            named += got
    return (base + f" Last {n} nights: would have read on {would} of {n} and named {named} of {total}. "
            "The monthly full scan is unchanged.")


def _day(value):
    raw = (value or "")[:10]
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def sunday_rollup(events, today, weekday=6, days=7, enabled=True, pending_unnamed=0):
    """Named unfollows over the last `days`, plus how many are still only a count.

    Saved data only. Returns None unless enabled and `today` falls on `weekday`
    (Monday is 0, Sunday is 6).
    """
    if not enabled:
        return None
    if isinstance(today, datetime):
        today = today.date()
    if today.weekday() != int(weekday):
        return None
    start = today - timedelta(days=int(days) - 1)
    named = []
    for e in events or []:
        if (e.get("event") or "") != "unfollowed_you":
            continue
        d = _day(e.get("date") or e.get("ts"))
        if d and start <= d <= today:
            named.append(e)
    pending = max(0, int(pending_unnamed or 0))
    lines = [f"Sunday rollup, last {int(days)} days. Saved data only."]
    if not named:
        lines.append("No named unfollows.")
    else:
        lines.append(f"Named unfollows: {len(named)}.")
        for e in named:
            who = e.get("username") or "unknown"
            followed = e.get("days")
            followed = "n/a" if followed in (None, "") else followed
            lines.append(f"@{who}: followed you for {followed} days")
    lines.append(f"Pending unnamed: {pending}.")
    return {"named": named, "pending_unnamed": pending, "text": "\n".join(lines)}
