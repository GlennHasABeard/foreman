#!/usr/bin/env python3
"""Reply Queue / Mention Radar collapsing (v1.2). No X API calls.

One row per account, questions first. Emoji-only, gm/gn-only and link-only replies
fold into one row. Multi-person threads roll up by root. Rows newer than the previous
radar run (when that run is at least 30 minutes old) are marked new.
"""
import re
from datetime import datetime, timezone

QUESTION_OPENERS = ("how", "what", "why", "where", "which", "whose")
_EMOJI = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002700-\U000027BF"
    "\U00002600-\U000026FF"
    "\U0001F1E6-\U0001F1FF"
    "\U0000FE00-\U0000FE0F"
    "\U0000200D"
    "]+",
    flags=re.UNICODE,
)
_URL = re.compile(r"https?://\S+|t\.co/\S+")
_GM = re.compile(r"^(gm|gn|good morning|good night)[\s!.]*$", re.I)


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


def is_question(text):
    """A question is a '?' or a how/what/why/where/which/whose opener."""
    raw = (text or "").strip()
    if "?" in raw:
        return True
    m = re.match(r"([A-Za-z]+)\b", raw)
    return bool(m and m.group(1).lower() in QUESTION_OPENERS)


def is_low_value(text):
    """Emoji-only, gm/gn-only, or link-only."""
    raw = (text or "").strip()
    if not raw:
        return False
    if _GM.match(raw):
        return True
    no_link = _URL.sub(" ", raw).strip()
    if raw and not no_link:
        return True
    no_emoji = _EMOJI.sub("", no_link)
    no_emoji = re.sub(r"[\s.,!?:;~*'\"()\-]+", "", no_emoji)
    return not no_emoji and bool(_EMOJI.search(raw))


def _norm(item):
    e = item.get("e") if isinstance(item.get("e"), dict) else {}
    u = item.get("u") if isinstance(item.get("u"), dict) else {}
    text = e.get("text") if e else item.get("text")
    return {
        "id": str(item.get("id") or e.get("id") or ""),
        "username": (item.get("username") or u.get("username") or "unknown").lstrip("@"),
        "text": text or "",
        "created": item.get("created") or e.get("created") or "",
        "kind": item.get("kind") or e.get("kind") or "reply",
        "author": str(item.get("author") or e.get("author") or ""),
        "conversation": str(item.get("conversation") or e.get("conversation") or ""),
        "target": str(item.get("target") or e.get("target") or ""),
        "tier": item.get("tier", 3),
        "liked": bool(item.get("liked")),
        "maybe_liked": bool(item.get("maybe_liked")),
        "verified": bool(item.get("verified")),
        "mutual": bool(item.get("mutual")),
        "raw": item,
    }


def _lead(group):
    questions = [i for i in group if is_question(i["text"])]
    pool = questions or list(group)
    return max(pool, key=lambda i: i["created"] or "")


def _is_new(created, prev_run, now, min_minutes=30):
    prev, cur, made = _parse(prev_run), _parse(now), _parse(created)
    if not prev or not cur or not made:
        return False
    if (cur - prev).total_seconds() < int(min_minutes) * 60:
        return False
    return made > prev


def _root(item):
    return item["conversation"] or item["target"] or ""


def prepare_radar(items, prev_run=None, now=None, min_people=2, thread_rollup=True, min_minutes=30):
    """Collapse radar items into the rows the page and the markdown report show.

    Returns {rows, new_count, low_count, accounts, items}.
    A row's `more` is the extra posts from that account. `fold` holds them.
    `low` is the single emoji / gm / link-only summary. `thread` is set on a
    rolled-up conversation. `new` is true when any post in the row is new.
    """
    now = now or datetime.now(timezone.utc).isoformat()
    norm = [_norm(i) for i in items or []]
    low = [i for i in norm if is_low_value(i["text"])]
    low_ids = {id(i) for i in low}
    rest = [i for i in norm if id(i) not in low_ids]
    threads, singles = [], list(rest)
    if thread_rollup:
        groups = {}
        for i in rest:
            root = _root(i)
            if root:
                groups.setdefault(root, []).append(i)
        used = set()
        for root, group in groups.items():
            people = {g["username"].lower() for g in group}
            if len(people) >= int(min_people) and len(group) >= int(min_people):
                threads.append((root, group))
                used.update(id(g) for g in group)
        singles = [i for i in rest if id(i) not in used]

    by_user = {}
    for i in singles:
        by_user.setdefault(i["username"].lower(), []).append(i)

    rows = []

    def row_from(group, **extra):
        lead = _lead(group)
        others = [g for g in group if g is not lead]
        new = any(_is_new(g["created"], prev_run, now, min_minutes) for g in group)
        text = (lead["text"] or "").replace("\n", " ")
        rec = {
            "id": lead["id"], "username": lead["username"], "text": text, "kind": lead["kind"],
            "created": lead["created"], "question": any(is_question(g["text"]) for g in group),
            "new": new, "more": len(others), "from_account": len(group),
            "fold": [{"id": g["id"], "text": (g["text"] or "").replace("\n", " "), "kind": g["kind"]} for g in others],
            "tier": lead["tier"], "liked": any(g["liked"] for g in group),
            "maybe_liked": any(g["maybe_liked"] for g in group),
            "verified": lead["verified"], "mutual": lead["mutual"],
            "low": False, "thread": None,
        }
        rec.update(extra)
        return rec

    for _root_id, group in threads:
        latest = max(group, key=lambda i: i["created"] or "")
        people = len({g["username"].lower() for g in group})
        rec = row_from(group, thread={"people": people, "pings": len(group), "root": _root_id})
        rec["text"] = f"{people} people · {len(group)} pings. {(latest['text'] or '').replace(chr(10), ' ')}"
        rec["question"] = any(is_question(g["text"]) for g in group)
        rows.append(rec)
    for group in by_user.values():
        rows.append(row_from(group))
    if low:
        rows.append({
            "id": "low-value", "username": "", "text": f"{len(low)} emoji, gm or link-only replies",
            "kind": "reply", "created": "", "question": False,
            "new": any(_is_new(g["created"], prev_run, now, min_minutes) for g in low),
            "more": 0, "from_account": len(low), "fold": [], "tier": 9, "liked": False,
            "maybe_liked": False, "verified": False, "mutual": False, "low": True, "thread": None,
        })
    plain = [r for r in rows if not r["low"]]
    qs = sorted([r for r in plain if r["question"]], key=lambda r: r["created"] or "", reverse=True)
    rest_rows = sorted([r for r in plain if not r["question"]], key=lambda r: r["created"] or "", reverse=True)
    rows = qs + rest_rows + [r for r in rows if r["low"]]
    new_items = [i for i in norm if _is_new(i["created"], prev_run, now, min_minutes)]
    return {
        "rows": rows,
        "new_count": len(new_items),
        "low_count": len(low),
        "accounts": len({i["username"].lower() for i in norm if i["username"]}),
        "items": len(norm),
    }


def md_lines(prepared):
    """One line per account, with +N more. The new count leads."""
    lines = []
    n = prepared.get("new_count") or 0
    if n:
        lines.append(f"{n} new since last run.")
    for row in prepared.get("rows") or []:
        if row.get("low"):
            lines.append(f"- {row['text']}")
            continue
        who = row.get("username") or "someone"
        extra = f" +{row['more']} more" if row.get("more") else ""
        snip = (row.get("text") or "").replace("\n", " ")
        if len(snip) > 140:
            snip = snip[:137] + "..."
        lines.append(f"- @{who} {row.get('kind') or 'reply'}{extra}: {snip or 'open'}")
    return lines
