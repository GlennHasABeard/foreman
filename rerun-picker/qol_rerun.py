#!/usr/bin/env python3
"""Rerun Picker helpers (v1.2). The tally-night skip and the nudge make no X calls.
"""
import re
from datetime import datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None

# Soft cap matches these series in the post text. Word boundaries, so "wan" is not "want".
TOOL_SERIES = (
    ("Minimax/Hailuo", ("minimax", "hailuo")),
    ("Wan", ("wan",)),
    ("Seedance", ("seedance",)),
    ("Kling", ("kling",)),
    ("Runway", ("runway",)),
    ("Luma", ("luma",)),
    ("Pika", ("pika",)),
    ("Veo", ("veo",)),
    ("Sora", ("sora",)),
)


def _parse(ts):
    if not ts:
        return None
    try:
        d = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except ValueError:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d


def _local(ts, tzname):
    d = _parse(ts)
    if not d:
        return None
    if ZoneInfo and tzname:
        try:
            return d.astimezone(ZoneInfo(tzname))
        except Exception:
            return d
    return d


def later_local_day(post_created, rerun_created, tzname=None):
    """A quote or repost counts only on a later local day than the post itself."""
    post = _local(post_created, tzname)
    rerun = _local(rerun_created, tzname)
    if not post or not rerun:
        return False
    return rerun.date() > post.date()


def tally_night_skip(now_local, last_pull_iso, min_days=6):
    """Skip ($0) unless it is Sunday or the last pull is `min_days` or older.

    Returns (skip, reason). No last pull means the pull should run.
    """
    if isinstance(now_local, datetime) and now_local.weekday() == 6:
        return False, "Sunday, pull runs"
    if not last_pull_iso:
        return False, "no pull yet"
    last = _parse(last_pull_iso)
    if not last:
        return False, "no pull yet"
    if isinstance(now_local, datetime):
        age = (now_local.date() - last.astimezone(now_local.tzinfo or timezone.utc).date()).days
    else:
        age = (now_local - last.date()).days
    if age >= int(min_days):
        return False, f"last pull is {age} days old"
    return True, (f"Tally night pull skipped, $0. Not Sunday and the last pull is {age} days old "
                  f"(under {int(min_days)}).")


def tool_of(text):
    blob = text or ""
    for name, keys in TOOL_SERIES:
        for key in keys:
            if re.search(r"\b" + re.escape(key) + r"\b", blob, re.I):
                return name
    return None


def cap_per_tool(ranked, limit, max_per=2):
    """Soft cap. Over-cap posts are used only when nothing else is left. 0 turns the cap off."""
    ranked = list(ranked or [])
    if not limit:
        return ranked
    limit = int(limit)
    if not max_per:
        return ranked[:limit]
    max_per = int(max_per)
    picked, overflow, counts = [], [], {}
    for cand in ranked:
        if len(picked) >= limit:
            break
        tool = tool_of(cand.get("text") or "")
        if tool and counts.get(tool, 0) >= max_per:
            overflow.append(cand)
            continue
        picked.append(cand)
        if tool:
            counts[tool] = counts.get(tool, 0) + 1
    for cand in overflow:
        if len(picked) >= limit:
            break
        picked.append(cand)
    return picked


def media_list(picks, rejects):
    """Video picks left after rejects. Nothing is downloaded here."""
    rejected = {str(r) for r in (rejects or [])}
    out = []
    for pick in picks or []:
        url = str(pick.get("url") or pick.get("post_url") or "")
        pid = str(pick.get("id") or "")
        if url in rejected or pid in rejected:
            continue
        fmt = (pick.get("format") or pick.get("media") or "")
        if isinstance(fmt, (list, tuple)):
            fmt = "/".join(fmt)
        if "video" not in str(fmt).lower():
            continue
        out.append(pick)
    return out


def nudge_line(review_age_days, has_rejects, stale_days=3):
    """One nudge when a review is stale and no rejects are synced. None means stay quiet.

    The caller must not build picks when this returns a line.
    """
    if has_rejects:
        return None
    if review_age_days is None or int(review_age_days) < int(stale_days):
        return None
    return (f"Review is {int(review_age_days)} days old and no rejects are synced. "
            "One nudge, no build.")
