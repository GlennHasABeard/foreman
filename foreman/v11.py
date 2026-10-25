#!/usr/bin/env python3
"""Foreman v1.1 shared helpers. Stdlib only, no X calls of its own.

Every template ships this file. It holds the v1.1 pieces that more than one bot uses:
install and hosting detection, chat commands that save to the bot's own files when there
is no hosting (KV), refused-read wording, estimate vs billed, the nightly billing check,
spend forecast and weekly digest, the shared profile cache, run-time spacing, the page
design, and the per-template list helpers.

  python3 v11.py chat "<owner message>"     handle a chat command for $CREW_BOT
  python3 v11.py mode                        install and hosting mode for $CREW_BOT
  python3 v11.py times 06:50 <n>             suggested run times, 20 minutes apart
  python3 v11.py billing-setup-note          the one-time setup line about the billed check

Nothing here holds an owner's settings. Every default is empty or off.
"""
import json
import os
import re
import statistics
import sys
import time
from datetime import datetime, timedelta, timezone

FOLDERS = {"Follow Audit": "follow-watch", "Follow Finder": "creator-scout", "Shoutout Picker": "shoutouts",
           "Reply Queue": "engagement", "Fan Finder": "engagement", "Rerun Picker": "reruns",
           "Analytics Log": "x-analytics", "Dispatch": "dispatch"}
STAGES = ("new", "engaged", "talked", "done")
REST_DAYS = 60
UTC = timezone.utc


def home():
    return os.environ.get("BOTS_HOME", "/workspace").rstrip("/")


def bot():
    b = os.environ.get("CREW_BOT")
    if not b:
        raise SystemExit("CREW_BOT is not set. Run with the bot's name in front.")
    return b


def data_dir(name=None):
    d = os.path.join(home(), FOLDERS.get(name or bot(), (name or bot()).lower().replace(" ", "-")), "data")
    os.makedirs(d, exist_ok=True)
    return d


def _load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _save(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1)
    os.replace(tmp, path)


def now():
    return datetime.now(UTC)


# ---------- install and hosting ----------

def installed():
    """Template bots installed in $BOTS_HOME (a bot counts once its folder has a config.json)."""
    out = []
    for n, f in FOLDERS.items():
        if n == "Dispatch":
            continue
        d = os.path.join(home(), f)
        slug = n.lower().replace(" ", "-")
        shared = list(FOLDERS.values()).count(f) > 1
        if os.path.exists(os.path.join(d, f".individual-{slug}")) or (
                not shared and os.path.isfile(os.path.join(d, "config.json"))):
            out.append(n)
    crew = _load(os.path.join(home(), "dispatch", "crew.json"), {})
    out += [b for b in crew.get("bots", []) if b in FOLDERS and b not in out and b != "Dispatch"]
    return sorted(out)


def is_crew():
    return os.path.isfile(os.path.join(home(), "dispatch", "crew.json"))


def hosted():
    """Hosting is on when the site settings file exists (written at hosting setup)."""
    return os.path.isfile(os.path.join(home(), "site", "site.env"))


def mode():
    """crew | home (2+ hosted templates) | own_page (one hosted bot) | chat (not hosted)."""
    if is_crew():
        return "crew"
    if not hosted():
        return "chat"
    return "home" if len(installed()) >= 2 else "own_page"


def surface():
    """Where Home items (follow-ups, top fans, status) show. Never a Home-only orphan."""
    return {"crew": "home", "home": "home", "own_page": "own page", "chat": "chat"}[mode()]


def home_panels():
    """Home panels: only installed bots. One hosted bot has no Home, its page is home."""
    m = mode()
    if m == "crew":
        return installed() + ["Bot health", "Cost digest"]
    if m == "home":
        p = list(installed())
        if {"Reply Queue", "Fan Finder"} & set(p):
            p.append("Top fans")
        return p
    return []


# ---------- chat commands (work with or without hosting) ----------

def store_path(name=None):
    slug = (name or bot()).lower().replace(" ", "-")
    return os.path.join(data_dir(name), f"chat_store-{slug}.json")


def load_store(name=None):
    s = _load(store_path(name), {})
    for k, v in (("never", {}), ("hide_until", {}), ("stages", {}), ("done", {}), ("notes", {}), ("events", [])):
        s.setdefault(k, v)
    return s


def save_store(s, name=None):
    _save(store_path(name), s)


def _h(x):
    return x.lstrip("@").lower()


CMDS = [
    (re.compile(r"^\s*never show @?(\w{1,15})\s*$", re.I), "never"),
    (re.compile(r"^\s*show @?(\w{1,15}) again\s*$", re.I), "show_again"),
    (re.compile(r"^\s*@?(\w{1,15}) is (new|engaged|talked|done)\s*$", re.I), "stage"),
    (re.compile(r"^\s*mark @?(\w{1,15}) done\s*$", re.I), "done"),
    (re.compile(r"^\s*mark @?(\w{1,15}) pending\s*$", re.I), "pending"),
    (re.compile(r"^\s*show me everything from @?(\w{1,15})\s*$", re.I), "timeline"),
    (re.compile(r"^\s*note @?(\w{1,15})\s+(.+)$", re.I | re.S), "note"),
    (re.compile(r"^\s*follow up @?(\w{1,15}) on (\d{4}-\d{2}-\d{2})\s*$", re.I), "follow_up"),
    (re.compile(r"^\s*(median|time to reply)\s*$", re.I), "median"),
]


def handle(text, name=None, post_times=None):
    """Run one chat command. Returns the reply line, or None if the text is not a command.
    Saves to the bot's own data/chat_store.json. Hosted pages save the same marks in KV;
    `merge_kv` folds those in so both ways agree."""
    s = load_store(name)
    t = now().isoformat(timespec="seconds")
    for rx, kind in CMDS:
        m = rx.match(text or "")
        if not m:
            continue
        h = _h(m.group(1)) if kind != "median" else None
        if kind == "never":
            s["never"][h] = t
            s["hide_until"].pop(h, None)
            msg = f"@{h} will never show again. Say \"show @{h} again\" to undo."
        elif kind == "show_again":
            was = s["never"].pop(h, None) or s["hide_until"].pop(h, None)
            msg = f"@{h} will show again." if was else f"@{h} was not hidden."
        elif kind == "stage":
            s["stages"][h] = {"stage": m.group(2).lower(), "ts": t}
            msg = f"@{h} is now {m.group(2).lower()}."
        elif kind == "done":
            s["done"][h] = t
            msg = f"Marked @{h} done."
        elif kind == "pending":
            s["done"].pop(h, None)
            msg = f"@{h} is pending again."
        elif kind == "note":
            s["notes"].setdefault(h, []).append({"ts": t, "text": m.group(2).strip()})
            msg = f"Saved a note on @{h}."
        elif kind == "follow_up":
            s["notes"].setdefault(h, []).append({"ts": t, "text": "follow up", "due": m.group(2)})
            msg = f"Follow-up on @{h} set for {m.group(2)}. It shows on your {surface()} when due."
        elif kind == "timeline":
            return "\n".join(timeline(h, name))
        elif kind == "median":
            return median_line(post_times or {}, name)
        if kind not in ("timeline", "median"):
            s["events"].append({"ts": t, "kind": kind, "who": h})
        save_store(s, name)
        return msg
    return None


def merge_kv(kv, name=None):
    """Fold hosted KV marks ({"never":{}, "done":{}, "stages":{}, "notes":{}}) into the file store."""
    s = load_store(name)
    for k in ("never", "done", "stages", "hide_until"):
        s[k].update((kv or {}).get(k) or {})
    for h, ns in ((kv or {}).get("notes") or {}).items():
        have = {n["ts"] for n in s["notes"].get(h, [])}
        s["notes"].setdefault(h, []).extend(n for n in ns if n["ts"] not in have)
    save_store(s, name)
    return s


def hide(h, days=REST_DAYS, name=None):
    s = load_store(name)
    s["hide_until"][_h(h)] = (now() + timedelta(days=days)).isoformat(timespec="seconds")
    save_store(s, name)


def visible(h, name=None, at=None):
    s = load_store(name)
    h = _h(h)
    if h in s["never"]:
        return False
    u = s["hide_until"].get(h)
    return not (u and datetime.fromisoformat(u) > (at or now()))


def hide_countdown(h, name=None, at=None):
    """'back in N days' for a resting account, or None."""
    u = load_store(name)["hide_until"].get(_h(h))
    if not u:
        return None
    d = (datetime.fromisoformat(u) - (at or now())).days + 1
    return f"back in {d} days" if d > 0 else None


def returning_soon(within=7, name=None, at=None):
    s = load_store(name)
    out = []
    for h, u in s["hide_until"].items():
        d = (datetime.fromisoformat(u) - (at or now())).days + 1
        if 0 < d <= within:
            out.append((d, h))
    return [f"@{h}: back in {d} days" for d, h in sorted(out)]


def done_pending(handles, name=None):
    done = load_store(name)["done"]
    hs = [_h(h) for h in handles]
    return {"done": [h for h in hs if h in done], "pending": [h for h in hs if h not in done]}


def median_reply(post_times, days, name=None, at=None):
    """Median minutes from post time to the done mark, for done marks in the last `days`.
    post_times: {handle: iso time of the item}. Works from chat marks or KV marks alike."""
    at = at or now()
    mins = []
    for h, dt in load_store(name)["done"].items():
        d = datetime.fromisoformat(dt)
        p = post_times.get(h)
        if p and at - d <= timedelta(days=days):
            mins.append((d - datetime.fromisoformat(p)).total_seconds() / 60)
    return statistics.median(mins) if mins else None


def median_line(post_times, name=None):
    parts = []
    for days in (7, 30):
        m = median_reply(post_times, days, name)
        parts.append(f"{days} days: " + (f"{m:.0f} min" if m is not None else "no done marks yet"))
    return "Median time to reply, from done marks. " + "; ".join(parts)


def timeline(h, name=None, extra_events=()):
    """Everything saved about one person: stage, done mark, notes, chat events, plus events the
    bot passes in (replies, quotes, mentions, follow events, shoutouts)."""
    h = _h(h)
    s = load_store(name)
    rows = [(e["ts"], e["kind"]) for e in s["events"] if e["who"] == h]
    rows += [(e["ts"], e["what"]) for e in extra_events if _h(e.get("who", "")) == h]
    rows += [(n["ts"], "note: " + n["text"] + (f" (due {n['due']})" if n.get("due") else "")) for n in s["notes"].get(h, [])]
    out = [f"Everything from @{h}"]
    if h in s["stages"]:
        out.append(f"stage: {s['stages'][h]['stage']}")
    out += [f"{ts[:16].replace('T', ' ')} UTC  {w}" for ts, w in sorted(rows)]
    if len(out) == 1:
        out.append("nothing saved yet")
    return out


def due_follow_ups(name=None, today=None):
    today = today or now().date().isoformat()
    return [f"@{h}: {n['text']} (due {n['due']})" for h, ns in load_store(name)["notes"].items()
            for n in ns if n.get("due") and n["due"] <= today]


# ---------- refused reads ----------

def read_result(what, status, count=None):
    """Never a quiet 0. A refused or failed read says so in words."""
    if status in (401, 403):
        return f"{what}: not read, X refused permission (HTTP {status})"
    if status and status >= 400:
        return f"{what}: not read, X answered HTTP {status}"
    if count is None:
        return f"{what}: not read"
    return f"{what}: {count}"


# ---------- spend: estimate vs billed ----------

def console_signed_in():
    """The billed check reads the X developer console in the bot's browser. The bot writes
    data/console-<slug>.json {"signed_in": true} after a successful read."""
    slug = bot().lower().replace(" ", "-")
    return bool(_load(os.path.join(data_dir(), f"console-{slug}.json"), {}).get("signed_in"))


def spend_line(estimate, billed=None):
    if billed is not None and console_signed_in():
        return f"Spend: estimate ${estimate:.2f}, X billed ${billed:.2f}"
    return f"Spend: ${estimate:.2f} (estimate, not billed yet)"


BILLING_NOTE = ("Spend shows as estimates. To see what X actually billed next to them, sign in to "
                "console.x.com in my browser once and say \"turn on the billed check\".")


def billing_setup_note():
    """Said once at setup, never again."""
    p = os.path.join(data_dir(), "billing_note_said-" + bot().lower().replace(" ", "-"))
    if os.path.exists(p) or console_signed_in():
        return None
    open(p, "w").close()
    return BILLING_NOTE


def switch_path():
    return os.environ.get("X_PRICE_SWITCH", os.path.join(home(), ".shared", "x_price_switch.json"))


def nightly_billing_check(billed_user_lookups, logged_user_lookups):
    """Flip attached profiles back to the old rate only if X billed more user lookups than the
    bots logged. Without the console signed in, nothing changes and estimates stay labeled."""
    if billed_user_lookups is None or not console_signed_in():
        return "Billing check skipped: console not signed in. Estimates stay labeled as estimates."
    if billed_user_lookups > logged_user_lookups:
        _save(switch_path(), {"attached_user_billed": True, "ts": now().isoformat(timespec="seconds")})
        return f"X billed {billed_user_lookups} user lookups, bots logged {logged_user_lookups}. Attached profiles back to $0.010."
    return f"Billing check OK: billed {billed_user_lookups} <= logged {logged_user_lookups}."


def month_forecast(daily_costs, day_of_month, days_in_month):
    if not daily_costs:
        return None
    spent = sum(daily_costs)
    avg = spent / max(len(daily_costs), 1)
    return round(spent + avg * (days_in_month - day_of_month), 2)


def weekly_digest(rows, last_week_total=None, saved_lookups=0):
    """rows: [{"kind": "post"|"user"|..., "cost": x}]. Each standalone bot sends its own; in a
    crew only Dispatch sends one cross-bot digest."""
    if is_crew() and bot() != "Dispatch":
        return None
    by = {}
    for r in rows:
        by[r["kind"]] = by.get(r["kind"], 0) + r["cost"]
    total = sum(by.values())
    lines = [f"{bot()} weekly cost: ${total:.2f} (estimate)"]
    lines += [f"  {k}: ${v:.2f}" for k, v in sorted(by.items())]
    if last_week_total is not None:
        lines.append(f"  last week: ${last_week_total:.2f}")
    if saved_lookups:
        lines.append(f"  profile cache saved {saved_lookups} paid lookups")
    return "\n".join(lines)


# ---------- shared profile cache ----------

def cache_on():
    return len(installed()) > 1 or is_crew()


def _cache_file():
    return os.path.join(home(), ".shared", "profile_cache.json")


def cache_put(users):
    if not cache_on():
        return
    d = _load(_cache_file(), {})
    t = time.time()
    for u in users or []:
        if u.get("id"):
            d[str(u["id"])] = {"t": t, "u": u}
    _save(_cache_file(), d)


def cache_get(ids, ttl=24 * 3600):
    if not cache_on():
        return {}
    d, t = _load(_cache_file(), {}), time.time()
    return {i: d[i]["u"] for i in map(str, ids) if i in d and t - d[i]["t"] < ttl}


# ---------- schedule ----------

def suggest_times(start, n, gap=20):
    h, m = map(int, start.split(":"))
    base = h * 60 + m
    return [f"{(base + i * gap) // 60 % 24:02d}:{(base + i * gap) % 60:02d}" for i in range(n)]


# ---------- page design ----------

def last_updated(ts, stale_hours=26, at=None):
    age = ((at or now()) - ts).total_seconds() / 3600
    cls = "stale" if age > stale_hours else "fresh"
    return f'<span class="updated {cls}">Last updated {ts.astimezone().strftime("%b %-d, %-I:%M %p %Z")}</span>'


PAGE_CSS = """:root{color-scheme:light dark;--bg:#fff;--fg:#1a1a1a;--line:#ddd;--coral:#e8604c}
@media(prefers-color-scheme:dark){:root{--bg:#121212;--fg:#eee;--line:#333}}
body{background:var(--bg);color:var(--fg);font:16px/1.45 system-ui,sans-serif;margin:0 auto;max-width:960px;padding:16px}
button,.btn{font:inherit;padding:6px 12px;border:1px solid var(--line);border-radius:8px;background:none;color:inherit;cursor:pointer}
.updated.stale{color:var(--coral)}table{border-collapse:collapse;width:100%}td,th{border-bottom:1px solid var(--line);padding:6px}"""


def page(title, body, updated, status_line=""):
    return (f"<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width'>"
            f"<title>{title}</title><style>{PAGE_CSS}</style><h1>{title}</h1>"
            f"<p>{last_updated(updated)}</p><p class=status>{status_line}</p>{body}")


def row_buttons(url, kinds=("Reply", "Like", "Open")):
    return " ".join(f'<a class=btn href="{url}" data-act="{k.lower()}">{k}</a>' for k in kinds)


def chat_report(counts, notable, cost_line, link=None, full_list=None):
    """Short chat report with link when hosted and published; full list otherwise."""
    lines = [", ".join(f"{v} {k}" for k, v in counts.items())] + list(notable) + [cost_line]
    if link:
        lines.append(link)
    elif full_list:
        lines += ["Publish is off or failed, so here is the list:"] + list(full_list)
    return "\n".join(lines)


# ---------- per-template helpers ----------

# Follow Audit
def unfollow_tiles(followers_lost, x_unfollows=None):
    """X's official unfollow count only when Analytics Log is installed, else 'followers lost'."""
    if x_unfollows is None or "Analytics Log" not in installed() and not is_crew():
        return {"followers lost": followers_lost}
    return {"unfollows (X)": x_unfollows, "removed by X": max(followers_lost - x_unfollows, 0)}


def split_missing(lookups):
    """lookups: {handle: profile dict or None (not found/suspended)}."""
    return {"Unfollowed you": sorted(h for h, u in lookups.items() if u),
            "Account gone": sorted(h for h, u in lookups.items() if not u)}


def newest_check_cost(size, rate=0.001):
    return f"Newest {size} followers check: about ${size * rate:.2f}"


def four_week_trend(events, at=None):
    """events: [{"ts":iso, "kind":"gain"|"loss"|"mutual"}] -> 4 weekly buckets, oldest first."""
    at = at or now()
    out = [{"gain": 0, "loss": 0, "mutual": 0} for _ in range(4)]
    for e in events:
        w = (at - datetime.fromisoformat(e["ts"])).days // 7
        if 0 <= w < 4:
            out[3 - w][e["kind"]] += 1
    return out


def top_risks(sections, n=5):
    return [f"{k}: {len(v)}" for k, v in sorted(sections.items(), key=lambda kv: -len(kv[1])) if v][:n]


def should_rebuild(full_data_mtime, last_build_mtime):
    return full_data_mtime > last_build_mtime


# Follow Finder
def prescreen(cands, settings):
    """Free pre-screen before any paid check. Quotas are the owner's own settings, off by default."""
    lo, hi = settings.get("min_followers", 0), settings.get("max_followers", 10 ** 12)
    keep, drops = [], {}
    for c in cands:
        why = None
        f = c.get("followers", 0)
        if not lo <= f <= hi:
            why = "outside follower range"
        elif c.get("following"):
            why = "already followed"
        elif not visible(c["username"]):
            why = "already shown or never show"
        elif settings.get("verified_only") is False and c.get("verified"):
            why = "verified"
        if why:
            drops[why] = drops.get(why, 0) + 1
        else:
            keep.append(c)
    q = settings.get("language_quota")  # e.g. {"lang": "xx", "max_share": 0.33}; None by default
    if q:
        cap = int(len(keep) * q["max_share"]) or 1
        same = [c for c in keep if c.get("lang") == q["lang"]]
        for c in same[cap:]:
            keep.remove(c)
            drops["language quota"] = drops.get("language quota", 0) + 1
    s = settings.get("size_quota")  # e.g. {"max_over": 50000, "max_share": 0.5}; None by default
    if s:
        cap = int(len(keep) * s["max_share"]) or 1
        big = [c for c in keep if c.get("followers", 0) > s["max_over"]]
        for c in big[cap:]:
            keep.remove(c)
            drops["size quota"] = drops.get("size quota", 0) + 1
    return keep, drops


def engagement_chips(c):
    chips = [f"{c.get('eng', 0) / max(c.get('followers', 1), 1):.1%} eng/follower"]
    if c.get("follows_you") and ("Follow Audit" in installed() or is_crew()):
        chips.append("follows you")
    return chips


def stats_strip(kept, drops, paid_skipped):
    return f"{kept} kept, {sum(drops.values())} dropped free, {paid_skipped} paid checks skipped"


# Shoutout Picker
def bench_warning(bench, slots):
    return None if bench >= slots else f"Bench can fill {bench} of {slots} slots."


def grouped_skips(skips):
    out = {}
    for h, why in skips:
        out.setdefault(why, []).append(h)
    return {k: (len(v), v) for k, v in sorted(out.items(), key=lambda kv: -len(kv[1]))}


def follow_audit_fresh(hours=24):
    p = os.path.join(home(), FOLDERS["Follow Audit"], "data", "followers.json")
    return os.path.isfile(p) and time.time() - os.path.getmtime(p) < hours * 3600


def top_fans_visible():
    return bool({"Reply Queue", "Fan Finder"} & set(installed())) or is_crew()


# Reply Queue
def regulars(items, at=None):
    """Distinct conversations per person this month. A long thread counts once. 10+ above 9."""
    at = at or now()
    conv = {}
    for i in items:
        if datetime.fromisoformat(i["ts"]).month == at.month:
            conv.setdefault(_h(i["who"]), set()).add(i["conversation_id"])
    return {h: (str(len(c)) if len(c) < 10 else "10+ this month") for h, c in conv.items() if len(c) >= 2}


def drowning(items, n=5):
    c = {}
    for i in items:
        if not i.get("answered"):
            c[i["post_id"]] = c.get(i["post_id"], 0) + 1
    return sorted(c.items(), key=lambda kv: -kv[1])[:n]


def queue_sort(items, key="time", only=None):
    """Mentions first, then the chosen sort. only: 'mentions'|'replies'|'regulars'|None."""
    if only:
        items = [i for i in items if i.get("type") == only or (only == "regulars" and i.get("regular"))]
    sk = {"time": lambda i: i["ts"], "likes": lambda i: -i.get("likes", 0)}[key]
    return sorted(items, key=lambda i: (i.get("type") != "mentions", sk(i)))


def draft_prefill(item):
    return f"@{_h(item['who'])} "


# Fan Finder
def reuse_pull(max_age_hours, name="Reply Queue"):
    """Reuse another bot's engagement pull when installed and fresh, else None (own pull)."""
    if name not in installed() and not is_crew():
        return None
    p = os.path.join(home(), FOLDERS[name], "data", "last_pull.json")
    if os.path.isfile(p):
        age = (time.time() - os.path.getmtime(p)) / 3600
        if age < max_age_hours:
            return {"path": p, "age_h": age, "line": f"Pull from {name}, {age:.0f}h ago, $0 extra"}
    return None


LIKES_BANNER = "new likes not read, stored likes still scored"


def score_breakdown(parts):
    return " + ".join(f"{k} {v}" for k, v in parts.items()) + f" = {sum(parts.values())}"


def why_left_out(reasons):
    return [f"@{_h(h)}: {r}" for h, r in reasons]


# Rerun Picker
def similar_to(text, picks, threshold=0.6):
    a = set(re.findall(r"\w+", text.lower()))
    for i, p in enumerate(picks, 1):
        b = set(re.findall(r"\w+", p.lower()))
        if a and b and len(a & b) / len(a | b) >= threshold:
            return f"similar to #{i}"
    return None


def sponsor_flag(text, sponsors):
    """sponsors is the owner's own list (empty by default), never a built-in list."""
    low = text.lower()
    hit = [s for s in (sponsors or []) if s.lower() in low]
    return f"possible sponsor: {', '.join(hit)}" if hit else None


# Analytics Log
def best_times(posts, top=3):
    by = {}
    for p in posts:
        hr = datetime.fromisoformat(p["ts"]).astimezone().hour
        by.setdefault(hr, []).append(p["impressions"])
    avg = sorted(((statistics.mean(v), h) for h, v in by.items()), reverse=True)
    return [f"{h:02d}:00 averages {a:,.0f} impressions" for a, h in avg[:top]]


def followers_per_post(posts):
    return sorted(((p.get("follows", 0), p["id"]) for p in posts), reverse=True)


def show_500k_chart(monetized):
    return bool(monetized)


def your_week(sections):
    """sections: {bot name: lines}. Only bots installed get a section."""
    inst = set(installed()) | ({"Dispatch"} if is_crew() else set())
    out = ["Your week on X"]
    for b, lines in sections.items():
        if b in inst:
            out.append(f"{b}:")
            out += [f"  {ln}" for ln in lines]
    return "\n".join(out)


def main(argv):
    if not argv:
        print(__doc__)
        return 0
    cmd = argv[0]
    if cmd == "chat":
        r = handle(" ".join(argv[1:]))
        print(r if r is not None else "not a command")
    elif cmd == "mode":
        print(f"{bot()}: {mode()}, Home items go to {surface()}, installed: {', '.join(installed()) or 'none'}")
    elif cmd == "times":
        print(" ".join(suggest_times(argv[1], int(argv[2]))))
    elif cmd == "billing-setup-note":
        print(billing_setup_note() or "already said")
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
