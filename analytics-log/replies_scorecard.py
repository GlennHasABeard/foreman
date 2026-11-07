#!/usr/bin/env python3
"""Weekly replies scorecard (v1.2.1). On by default. $0.

Reads the content export already pulled. No X API calls.
Config replies_scorecard: {enabled: true, days: 7, top: 10, reply_types: ["reply"]}.
Set enabled to false to turn it off.
"""
from datetime import date, datetime, timedelta


DEFAULTS = {"enabled": True, "days": 7, "top": 10, "reply_types": ["reply"]}


def settings(cfg):
    block = {}
    if isinstance(cfg, dict):
        raw = cfg.get("replies_scorecard")
        if isinstance(raw, dict):
            block = raw
        elif isinstance(raw, bool):
            block = {"enabled": raw}
    out = dict(DEFAULTS)
    out.update({k: v for k, v in block.items() if v is not None})
    out["enabled"] = bool(out.get("enabled", True))
    return out


def enabled(cfg):
    return settings(cfg)["enabled"]


def _day(value):
    raw = str(value or "")[:10]
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def _num(row, *keys):
    for key in keys:
        if key in row and row[key] not in (None, ""):
            try:
                return float(str(row[key]).replace(",", ""))
            except (TypeError, ValueError):
                return 0.0
    metrics = row.get("metrics") if isinstance(row.get("metrics"), dict) else {}
    for key in keys:
        if key in metrics and metrics[key] not in (None, ""):
            try:
                return float(metrics[key])
            except (TypeError, ValueError):
                return 0.0
    return 0.0


def scorecard(posts, cfg=None, today=None):
    """Return None when the scorecard is off. Otherwise {rows, line, enabled: True}."""
    opt = settings(cfg)
    if not opt["enabled"]:
        return None
    if today is None:
        today = date.today()
    if isinstance(today, datetime):
        today = today.date()
    start = today - timedelta(days=int(opt["days"]) - 1)
    kinds = {str(k).lower() for k in (opt.get("reply_types") or ["reply"])}
    rows = []
    for post in posts or []:
        if not isinstance(post, dict):
            continue
        kind = str(post.get("kind") or post.get("type") or "reply").lower()
        if kind not in kinds:
            continue
        posted = _day(post.get("created") or post.get("date") or post.get("posted_at"))
        if posted and not (start <= posted <= today):
            continue
        views = _num(post, "impression_count", "impressions", "views")
        follows = _num(post, "follows", "new_follows", "user_profile_clicks")
        rows.append({
            "id": post.get("id") or post.get("post_id") or "",
            "date": posted.isoformat() if posted else "",
            "text": (post.get("text") or "")[:140],
            "views": views,
            "follows": follows,
        })
    rows.sort(key=lambda r: (-r["views"], -r["follows"]))
    top = rows[:int(opt["top"])]
    line = (f"Replies scorecard, last {int(opt['days'])} days: {len(rows)} replies, "
            f"showing {len(top)}. From the content export already pulled, $0.")
    return {"rows": top, "count": len(rows), "line": line, "enabled": True}


def off_line():
    return ("Replies scorecard is off in this config. It is on by default, reads the content export "
            "already pulled, and costs $0. Set replies_scorecard.enabled to true to turn it back on.")
