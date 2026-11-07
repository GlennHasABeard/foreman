#!/usr/bin/env python3
"""Shoutout Picker helpers (v1.2). Saved data only, except the optional rollover lookup.

rollover_lookup ships off. One batched users/by is about $0.01 per rollover.
"""
import csv
import os
import re
from datetime import date, datetime

LEAVE_OUT = {"likely fake", "spam signals", "never posted"}
RANK_LAST = {"watch", "inactive", "dormant"}
GONE = {"deleted", "suspended", "deactivated"}
ROLLOVER_COST = 0.01
ROLLOVERS_PER_MONTH = 4


def rollover_monthly_cost():
    """About four weekly rollovers. Shown at setup. The check stays off until the owner says yes."""
    return ROLLOVER_COST * ROLLOVERS_PER_MONTH


def rollover_lookup_on(cfg):
    return bool((cfg or {}).get("rollover_lookup", False))


def rollover_setup_line():
    """Say this during setup, before the owner answers. Default remains off."""
    month = rollover_monthly_cost()
    return (f"The deleted or suspended account check is off. If you turn it on, one batched lookup "
            f"runs each weekly rollover, about ${ROLLOVER_COST:.2f}, about ${month:.2f} a month. "
            "Leave it off unless you want that spend.")


def rollover_cost_line(on):
    month = rollover_monthly_cost()
    if on:
        return ("Rollover lookup is on. One batched users/by drops deleted or suspended accounts "
                f"before review. About ${ROLLOVER_COST:.2f} per rollover, about ${month:.2f} a month.")
    return rollover_setup_line()


def classify_users_by(body, requested):
    """Map usernames to active, deleted or suspended from one users/by body."""
    body = body or {}
    found = {}
    for user in body.get("data") or []:
        name = (user.get("username") or "").lower()
        if name:
            found[name] = "active"
    out = {}
    for err in body.get("errors") or []:
        name = str(err.get("value") or err.get("resource_id") or "").lstrip("@").lower()
        title = (str(err.get("title") or "") + " " + str(err.get("detail") or "")).lower()
        if not name:
            continue
        out[name] = "suspended" if "suspend" in title else "deleted"
    for name in requested or []:
        key = str(name).lstrip("@").lower()
        if key in found:
            out[key] = "active"
        elif key not in out:
            out[key] = "deleted"
    return out


def is_gone(status):
    return (status or "").lower() in GONE


def week_label(weeks_listed, promoted=False):
    """week N. Week 1 adds · new or · runner-up promoted."""
    n = int(weeks_listed or 1)
    if n <= 1:
        return "week 1 · runner-up promoted" if promoted else "week 1 · new"
    return f"week {n}"


def fresh_post(last_post, today, days=14):
    raw = str(last_post or "")[:10]
    if not raw:
        return False
    if isinstance(today, datetime):
        today = today.date()
    try:
        return (today - date.fromisoformat(raw)).days <= int(days)
    except ValueError:
        return False


def flag_decision(tags):
    """out, last, or ok. flagged_filter uses Follow Audit's flag files."""
    names = set()
    for tag in tags or []:
        names.add(str(tag).strip().lower())
    if names & LEAVE_OUT:
        return "out"
    if names & RANK_LAST:
        return "last"
    return "ok"


def load_flag_csv(path):
    """{handle: set of tags} from a flagged_followers or flagged_following csv."""
    out = {}
    if not path or not os.path.exists(path):
        return out
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        handle = (row.get("handle") or row.get("username") or row.get("user") or "").lstrip("@").lower()
        if not handle:
            continue
        raw = row.get("tags") or row.get("tag") or row.get("flags") or row.get("reason") or ""
        tags = [t.strip() for t in re.split(r"[|,]", raw) if t.strip()]
        out.setdefault(handle, set()).update(tags)
    return out


def load_flags(follow_watch_dir):
    data = os.path.join(follow_watch_dir or "", "data")
    flags = {}
    for name in ("flagged_followers.csv", "flagged_following.csv"):
        for handle, tags in load_flag_csv(os.path.join(data, name)).items():
            flags.setdefault(handle, set()).update(tags)
    return flags


def split_flagged(items, flags, handle_of):
    """Return (kept_in_order, left_out). left_out is [(handle, tags)]. Rank-last stays, at the end."""
    clean, last, left = [], [], []
    for item in items or []:
        handle = (handle_of(item) or "").lstrip("@").lower()
        decision = flag_decision((flags or {}).get(handle))
        if decision == "out":
            left.append((handle, sorted((flags or {}).get(handle) or [])))
        elif decision == "last":
            last.append(item)
        else:
            clean.append(item)
    return clean + last, left


def shoutout_handles(text):
    if "shoutout" not in (text or "").lower():
        return []
    return re.findall(r"@([A-Za-z0-9_]{1,15})", text)


def catch_up_plan(log_rows, posts, today):
    """New log rows from saved posts. No X calls. posts: [{id, text, created, url}]."""
    if isinstance(today, datetime):
        today = today.date()
    have = {(str(r.get("handle") or "").lstrip("@").lower(), r.get("post_url") or "") for r in log_rows or []}
    added = []
    for post in posts or []:
        handles = shoutout_handles(post.get("text") or "")
        url = post.get("url") or ""
        if not url and post.get("id"):
            url = f"https://x.com/i/status/{post['id']}"
        posted = str(post.get("created") or today.isoformat())[:10]
        for handle in handles:
            key = (handle.lower(), url)
            if key in have:
                continue
            have.add(key)
            added.append({"date": posted, "handle": handle, "id": "", "post_url": url, "added": today.isoformat()})
    return added


def needs_extra_band(keeps, list_size, already_added):
    """One extra band only, and only when keeps are still short."""
    return int(keeps) < int(list_size) and not already_added
