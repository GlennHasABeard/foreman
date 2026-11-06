#!/usr/bin/env python3
"""Median time to reply at publish (v1.2). No X API calls.

New Done ticks are {done: 1, at: ISO}. Unticking deletes the mark. Anything that
only checks Done as true or false still works (bare 1, True, or {on: true}).

q4rt is filled at publish from two clocks: your replies in posts.json matched to
the inbound engagement they answer, and Done marks that carry a time. A bare 1
has no time, so it does not enter the median.
"""
from datetime import datetime, timezone
import statistics


def is_done(mark):
    if mark in (1, True, "1"):
        return True
    if isinstance(mark, dict):
        if "done" in mark:
            return bool(mark.get("done"))
        return bool(mark.get("on", True))
    if isinstance(mark, str) and mark:
        return True
    return False


def done_at(mark):
    """ISO time for a Done mark, or None when the mark has no clock (a bare 1)."""
    if isinstance(mark, dict):
        return mark.get("at") or mark.get("ts") or None
    if isinstance(mark, str) and mark not in ("1", "true", "True"):
        return mark
    return None


def new_done_mark(at):
    return {"done": 1, "at": at}


def _parse(ts):
    if not ts or not isinstance(ts, str):
        return None
    try:
        d = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d


def _minutes(start, end):
    a, b = _parse(start), _parse(end)
    if not a or not b:
        return None
    mins = (b - a).total_seconds() / 60
    if mins < 0:
        return None
    return mins


def _author_name(event, users):
    if not isinstance(event, dict):
        return ""
    if event.get("username"):
        return str(event["username"]).lstrip("@").lower()
    author = event.get("author")
    user = (users or {}).get(author) if author else None
    if isinstance(user, dict):
        return str(user.get("username") or "").lstrip("@").lower()
    return ""


def q4rt(posts, events, done_marks, users=None):
    """Median minutes.

    posts: {id: {kind, created, replied_to}}.
    events: {id: {created, author or username}}.
    done_marks: {handle: iso string | {done, at} | 1}. A bare 1 has no clock and is skipped.
    A Done mark with `at` is paired with that handle's latest inbound post from before `at`.
    """
    samples = []
    events = events or {}
    for post in (posts or {}).values():
        if not isinstance(post, dict):
            continue
        if post.get("kind") not in (None, "reply", "quote"):
            continue
        inbound = post.get("replied_to") or post.get("quoted")
        src = events.get(inbound) if inbound else None
        if not isinstance(src, dict):
            continue
        mins = _minutes(src.get("created"), post.get("created"))
        if mins is not None:
            samples.append(mins)
    by_user = {}
    for event in events.values():
        name = _author_name(event, users)
        if name and isinstance(event, dict) and event.get("created"):
            by_user.setdefault(name, []).append(event["created"])
    for handle, mark in (done_marks or {}).items():
        if not is_done(mark):
            continue
        at = done_at(mark)
        if not at:
            continue
        inbound = mark.get("inbound") if isinstance(mark, dict) else None
        if not inbound:
            candidates = [c for c in by_user.get(str(handle).lstrip("@").lower(), [])
                          if _parse(c) and _parse(at) and _parse(c) <= _parse(at)]
            inbound = max(candidates) if candidates else None
        mins = _minutes(inbound, at)
        if mins is not None:
            samples.append(mins)
    n = len(samples)
    median = statistics.median(samples) if samples else None
    if median is None:
        line = "Median time to reply: no done marks yet"
    else:
        line = f"Median time to reply: {median:.0f} min (n={n})"
    return {"n": n, "median_min": median, "samples": samples, "line": line}


def publish_line(posts, events, done_marks, users=None):
    """The line publish writes onto the Reply Queue page."""
    return q4rt(posts, events, done_marks, users)["line"]
