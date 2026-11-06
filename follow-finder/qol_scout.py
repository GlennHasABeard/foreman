#!/usr/bin/env python3
"""Follow Finder pre-screen helpers (v1.2). Free, no X API calls.

Language shares are floors, not caps. Size bands are floors filled after the
language floor, and they never push a language under its floor.
`lang_balance_slack` is accepted so older configs still load. It is unused.
"""
import math
import re
from datetime import date, datetime, timedelta

# Word-boundary off-topic filters. None of these are niche words.
OFFTOPIC = (
    (re.compile(r"\b(?:casino|betting)\b", re.I), "casino or betting"),
    (re.compile(r"\bai\s+(?:tool|product)\b", re.I), "AI tool or product"),
    (re.compile(r"\b(?:promo|giveaway)\b", re.I), "promo or giveaway"),
    (re.compile(r"\bglamour\b", re.I), "glamour"),
)


def offtopic_reason(text, extra_terms=()):
    """Return a reason when text hits an off-topic filter, else None."""
    blob = text or ""
    for rx, why in OFFTOPIC:
        if rx.search(blob):
            return why
    for term in extra_terms or []:
        term = str(term).strip()
        if not term:
            continue
        if re.search(r"\b" + re.escape(term) + r"\b", blob, re.I):
            return term
    return None


def _need(limit, share):
    if not limit or not share:
        return 0
    return min(int(limit), max(0, math.ceil(float(share) * int(limit) - 1e-9)))


def select_shortlist(ranked, limit, lang_balance=None, size_bands=None, slack=None):
    """Cut a ranked list to `limit`.

    Each lang_balance share is a floor: that language is kept up to at least its
    share when enough candidates exist, and there is no upper limit. Other
    languages are not forced. slack is ignored (old configs still load).
    size_bands are floors applied after the language floor. A language-floor
    pick is never removed to make room for a size band.
    """
    del slack  # kept on the signature so callers can pass lang_balance_slack
    pool = list(ranked or [])
    if not limit or int(limit) <= 0:
        return pool
    limit = int(limit)
    if len(pool) <= limit and not lang_balance and not size_bands:
        return pool
    chosen, seen = [], set()

    def take(cand):
        key = id(cand)
        if key in seen or len(chosen) >= limit:
            return False
        chosen.append(cand)
        seen.add(key)
        return True

    locked = []
    for lang, share in (lang_balance or {}).items():
        need, have = _need(limit, share), 0
        for cand in pool:
            if have >= need:
                break
            if (cand.get("lang") or "") == lang and take(cand):
                locked.append(cand)
                have += 1
    for band in size_bands or []:
        need = _need(limit, band.get("share") or 0)
        lo, hi = band.get("min", 0), band.get("max", 10 ** 12)
        have = sum(1 for cand in chosen if lo <= (cand.get("followers") or 0) <= hi)
        for cand in pool:
            if have >= need or len(chosen) >= limit:
                break
            followers = cand.get("followers") or 0
            if lo <= followers <= hi and take(cand):
                have += 1
    for cand in pool:
        if len(chosen) >= limit:
            break
        take(cand)
    # Language floors stay even if a later step wanted the slot. take() never evicts.
    del locked
    return chosen


def sensitive_rest_cfg(cfg):
    block = (cfg or {}).get("sensitive_rest") or {}
    return int(block.get("fails") or 3), int(block.get("days") or 30)


def _as_date(today):
    if isinstance(today, datetime):
        return today.date()
    if isinstance(today, date):
        return today
    return date.fromisoformat(str(today)[:10])


def resting(state, handle, today):
    rec = (state or {}).get((handle or "").lstrip("@").lower()) or {}
    until = rec.get("rest_until")
    if not until:
        return False
    try:
        return _as_date(today) <= date.fromisoformat(str(until)[:10])
    except ValueError:
        return False


def note_sensitive(state, handle, today, fails_needed=3, rest_days=30):
    """Count a sensitive-media fail. After `fails_needed`, rest for `rest_days`."""
    state = state if isinstance(state, dict) else {}
    handle = (handle or "").lstrip("@").lower()
    today = _as_date(today)
    if resting(state, handle, today):
        return state[handle]
    rec = state.setdefault(handle, {"fails": 0})
    rec["fails"] = int(rec.get("fails") or 0) + 1
    rec["last"] = today.isoformat()
    if rec["fails"] >= int(fails_needed):
        rec["rest_until"] = (today + timedelta(days=int(rest_days))).isoformat()
    return rec


def shown_under_like_floor(shown_likes, floor, has_post):
    """The like floor applies to the shown best post. No post means no floor."""
    if not has_post:
        return False
    return int(shown_likes or 0) < int(floor or 0)
