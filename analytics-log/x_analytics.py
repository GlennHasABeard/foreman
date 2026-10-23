#!/usr/bin/env python3
"""
x_analytics.py
Bookkeeping for X analytics pulls. The Bot reads X's analytics pages in its
browser and saves the raw files. This script files them, parses them and keeps
the running records. It makes no X API calls and changes nothing on X.

  python3 x_analytics.py start morning|night     make a new pull folder and print the checklist
  python3 x_analytics.py start test              a full night checklist whose results stay inside its own
                                                 folder (test_data/) and never touch the running records
  python3 x_analytics.py finish [PULL_DIR]       parse a pull (default: the newest) and update the records
  python3 x_analytics.py status                  the last few pulls and their flags

Every pull folder is named by its local start time and kind, for example
pulls/2026-10-21_0732_morning. Folders and raw files are never overwritten.
Data lives in $BOTS_HOME/x-analytics (override with XA_DIR).
Python 3.9+ standard library only.
"""

import argparse
import csv
import json
import os
import re
import sys
from datetime import date, datetime, timedelta, timezone


# Where the bots live. Foreman sets BOTS_HOME for each bot. On Grok Bot that is /workspace.
BOTS_HOME = os.environ.get("BOTS_HOME", "/workspace").rstrip("/")

ROOT = os.environ.get("XA_DIR", BOTS_HOME + "/x-analytics")

# Local time comes from config.json (timezone). Columns ending in _et hold that local time.
def _local_tz():
    try:
        from zoneinfo import ZoneInfo
        with open(os.path.join(ROOT, "config.json"), encoding="utf-8") as f:
            name = json.load(f).get("timezone")
        return ZoneInfo(name) if name else None
    except Exception:
        return None


ET = _local_tz() or timezone.utc
TZ_LABEL = getattr(ET, "key", "UTC")
SCHEMA = "x-analytics-pull/1"
TWITTER_EPOCH_MS = 1288834974657

DEFAULT_CONFIG = {
    "engagement_posts": BOTS_HOME + "/engagement/posts.json",
    "rerun_posts": BOTS_HOME + "/reruns/posts.json",
    "follow_watch_dir": BOTS_HOME + "/follow-watch",
    "window_days": 90,
    "video_match_seconds": 600,
    "timezone": None,
    "has_premium": None,
    "has_monetization": None,
}
OPTIONAL_NONE = set()

# Panels and files X only shows with X Premium (verified) or with creator monetization.
# When the account doesn't have them, they are marked "not available on this account", never flagged.
NOT_AVAILABLE = "not available on this account"
PREMIUM_FILES = {"verified_90d.csv", "overview_verified_14d.csv"}
PREMIUM_PANELS = {"verified_followers", "verified_followers_pct", "verified_active_daily",
                  "yesterday_verified_impressions"}
MONETIZATION_FILES = {"tracker.png", "payouts_list.csv"}
MONETIZATION_PANELS = {"tracker", "payout_amount", "payout_date"}


def unavailable(cfg, name, panel=False):
    if panel:
        return ((name in PREMIUM_PANELS and not cfg.get("has_premium"))
                or (name in MONETIZATION_PANELS and not cfg.get("has_monetization")))
    return ((name in PREMIUM_FILES and not cfg.get("has_premium"))
            or (name in MONETIZATION_FILES and not cfg.get("has_monetization")))

# Panel values the Bot copies from the page, exactly as shown.
PANEL_KEYS_EVERY = [
    "tracker",
    "followers_total", "verified_followers", "verified_followers_pct",
    "new_follows_today", "unfollows_today", "new_follows_yesterday", "unfollows_yesterday",
    "active_1h", "active_3h", "active_6h", "active_24h",
    "verified_active_daily", "following_total",
]
# X has no 1h/3h/6h/24h verified-active readings. Old records had columns for them; they're removed.
DROPPED_FOLLOWER_COLS = ["verified_active_1h", "verified_active_3h", "verified_active_6h", "verified_active_24h"]
PANEL_KEYS_MORNING = ["yesterday_verified_impressions"]
PANEL_KEYS_NIGHT = ["payout_amount", "payout_date"]

# Night extras, written in panels.txt as "extra.<section>.<field>: <as shown>".
OVERVIEW_TOTALS = ["impressions", "engagement_rate", "engagements", "profile_visits", "replies", "likes",
                   "reposts", "bookmarks", "shares"]
EXTRA_SPEC = {
    "overview_1y_all": OVERVIEW_TOTALS,
    "overview_2w_all": OVERVIEW_TOTALS,
    "overview_2w_verified": OVERVIEW_TOTALS,
    "overview_90d_verified": OVERVIEW_TOTALS,
    "video_2w": ["views", "watch_time_hours", "completion_rate", "average_watch_time"],
    "video_1y": ["views", "watch_time_hours", "completion_rate", "average_watch_time"],
    "video_completion": ["start", "p25", "p50", "p75", "complete"],
    "audience_7d_age": ["13_17", "18_24", "25_34", "35_44", "45_54", "55_64", "65_plus"],
    "audience_7d_gender": ["male", "female", "not_specified"],
    "audience_7d_country": ["top"],
    "audience_7d_device": ["web", "ios", "android", "other"],
    "audience_7d_follow_status": ["followers", "non_followers"],
    "creator_studio": ["original_content_rewards", "subscriptions", "revenue_sharing", "open_requirements",
                       "subscriptions_open_requirements"],
}


def parse_extra(raw):
    """'186.1K (up 52%)' -> value 186100, change_pct 52. 'down 9.1%' -> -9.1. Text kept as text."""
    if raw is None or raw == "":
        return {"raw": None, "value": None, "change_pct": None, "status": "missing"}
    up = raw.upper()
    if up.startswith("NOT SHOWN") or up.startswith("FAILED"):
        return {"raw": raw, "value": None, "change_pct": None, "status": raw.split()[0].lower()}
    m = re.search(r"\((up|down)\s*([\d.]+)\s*%\)", raw, re.I)
    change = (float(m.group(2)) * (1 if m.group(1).lower() == "up" else -1)) if m else None
    main = re.sub(r"\((up|down)[^)]*\)", "", raw, flags=re.I).strip()
    hours = re.fullmatch(r"([\d.]+)\s*hours?", main, re.I)
    clock = re.fullmatch(r"(\d+):(\d{2})", main)
    if hours:
        value = float(hours.group(1))
    elif clock:
        value = int(clock.group(1)) * 60 + int(clock.group(2))
    else:
        value = parse_num(main)
    return {"raw": raw, "value": value, "change_pct": change, "status": "ok" if value is not None else "text"}


# Raw files. name: (kinds it's expected on, what it is)
RAW_FILES = {
    "tracker.png": (("morning", "night"), "Screenshot of the Creator / Monetization panel showing "
                    "'Verified Home Timeline impressions in the last 90 days'"),
    "followers.png": (("morning", "night"), "Screenshot of the followers block (verified and active followers), "
                      "plus the open Verified followers info panel showing the exact count"),
    "verified_90d.csv": (("morning", "night"), "Account overview export, Verified filter, 3M range "
                         "(or a custom 91-day range ending today)"),
    "overview_all_14d.csv": (("morning", "night"), "Account overview export, All filter, last 14 days. "
                             "The morning one gives yesterday's final all-impressions number"),
    "overview_verified_14d.csv": (("night",), "Account overview export, Verified filter, last 14 days"),
    "content_14d.csv": (("night",), "Content export, last 14 days"),
    "video_overview_14d.csv": (("night",), "Video overview export, last 14 days, daily"),
    "video_list.csv": (("night",), "Per-video list for videos uploaded in the last 14 days only: Video ID, "
                       "Upload date, Views, Duration, Post link (if shown). Copy it from the page if there's no export"),
    "payouts_list.csv": (("night",), "Every payout listed in Creator Studio (Revenue Sharing, Original Content "
                         "Rewards), columns: program,period,amount,paid_date. Copy the whole list as shown"),
    "active_heatmap.png": (("night",), "Screenshot of the active followers by hour heatmap, if X shows one"),
    "active_by_hour.csv": (("night",), "Active followers by hour of day, columns: hour,active "
                           "(hours as X shows them, note X's timezone in panels.txt as active_by_hour_tz). "
                           "Only if X shows it"),
}
OPTIONAL_FILES = {"active_by_hour.csv", "active_heatmap.png", "payouts_list.csv"}
OPTIONAL_PANELS = {"payout_amount", "payout_date", "yesterday_verified_impressions", "verified_followers_pct",
                   "following_total"}

# Column aliases for X's exports, matched after lowercasing and removing non-letters.
ALIASES = {
    "date": ["date", "day"],
    "impressions": ["impressions"],
    "likes": ["likes"],
    "engagements": ["engagements"],
    "bookmarks": ["bookmarks"],
    "shares": ["shares"],
    "new_follows": ["newfollows", "follows"],
    "unfollows": ["unfollows"],
    "replies": ["replies"],
    "reposts": ["reposts", "retweets"],
    "profile_visits": ["profilevisits", "userprofileclicks"],
    "create_post": ["createpost", "createposts", "posts"],
    "video_views": ["videoviews"],
    "media_views": ["mediaviews"],
    "post_id": ["postid", "tweetid", "id"],
    "text": ["posttext", "text", "tweettext", "post"],
    "link": ["postlink", "link", "tweetpermalink", "url"],
    "detail_expands": ["detailexpands"],
    "url_clicks": ["urlclicks"],
    "hashtag_clicks": ["hashtagclicks"],
    "permalink_clicks": ["permalinkclicks"],
    "views": ["views"],
    "watch_time_ms": ["watchtimems", "watchtime"],
    "completion_rate": ["completionrate"],
    "avg_watch_time_ms": ["averagewatchtimems", "avgwatchtimems", "averagewatchtime"],
    "video_id": ["videoid", "mediaid"],
    "upload_date": ["uploaddate", "uploaded"],
    "duration": ["duration", "videoduration", "length"],
    "post_link": ["postlink", "link", "url"],
}
OVERVIEW_FIELDS = ["date", "impressions", "likes", "engagements", "bookmarks", "shares", "new_follows",
                   "unfollows", "replies", "reposts", "profile_visits", "create_post", "video_views",
                   "media_views"]
CONTENT_FIELDS = ["post_id", "date", "text", "link", "impressions", "likes", "engagements", "bookmarks",
                  "shares", "new_follows", "replies", "reposts", "profile_visits", "detail_expands",
                  "url_clicks", "hashtag_clicks", "permalink_clicks"]
VIDEO_DAILY_FIELDS = ["date", "views", "watch_time_ms", "completion_rate", "avg_watch_time_ms"]
VIDEO_LIST_FIELDS = ["video_id", "upload_date", "views", "duration", "post_link"]
MISSING = "missing"


# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------

def now_et():
    return datetime.now(ET)


def read_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def append_csv(path, fields, rows):
    new = not os.path.exists(path) or os.path.getsize(path) == 0
    if not new:
        with open(path, newline="", encoding="utf-8") as f:
            old_header = next(csv.reader(f), [])
        if old_header != fields:
            old = read_csv(path)
            merged = old_header + [c for c in fields if c not in old_header]
            write_csv(path, merged, [{c: r.get(c, "not collected then") for c in merged} for r in old])
            fields = merged
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        if new:
            w.writeheader()
        for r in rows:
            w.writerow({k: (MISSING if r.get(k) is None else r.get(k)) for k in fields})


def drop_columns(path, cols):
    """Remove retired columns from a record file, keeping every row and every other column."""
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return
    with open(path, newline="", encoding="utf-8") as f:
        header = next(csv.reader(f), [])
    if not any(c in header for c in cols):
        return
    keep = [c for c in header if c not in cols]
    write_csv(path, keep, read_csv(path))


def write_csv(path, fields, rows):
    tmp = path + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: (MISSING if r.get(k) is None else r.get(k)) for k in fields})
    os.replace(tmp, path)


def read_csv(path):
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return []
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def norm(s):
    return re.sub(r"[^a-z]", "", (s or "").lower())


def parse_num(raw):
    """'349.3K' -> 349300, '6,412' -> 6412, '43.5%' -> 43.5, '1.2M' -> 1200000. None if not a number."""
    if raw is None:
        return None
    s = str(raw).strip().replace(",", "").replace("\u202f", "").replace(" ", "")
    s = re.sub(r"^[$€£]|USD$", "", s)
    if not s or s in ("-", "—", "–", "n/a", "N/A"):
        return None
    m = re.fullmatch(r"([+-]?\d+(?:\.\d+)?)([KkMmBb%]?)", s)
    if not m:
        return None
    v = float(m.group(1))
    mult = {"k": 1e3, "m": 1e6, "b": 1e9}.get(m.group(2).lower(), 1)
    v *= mult
    if m.group(2) == "%":
        return v
    return int(round(v)) if mult > 1 or v.is_integer() else v


DATE_FORMATS = ["%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%a, %b %d, %Y", "%b %d, %Y", "%a %b %d %Y",
                "%d %b %Y", "%B %d, %Y", "%a, %B %d, %Y", "%Y/%m/%d"]


def parse_date(raw):
    s = (raw or "").strip()
    if not s:
        return None
    s2 = re.split(r"[T ](?=\d{1,2}:\d{2})", s)[0].strip().rstrip(",")
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(s2, fmt).date()
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def loose_date(raw):
    """Dates written any way X writes them: 'Aug 29, 2026', 'Aug 29 2026', '2026-08-29'."""
    d = parse_date(raw)
    if d:
        return d
    s = re.sub(r"\s+", " ", (raw or "").replace(",", " ")).strip()
    for fmt in ("%b %d %Y", "%B %d %Y", "%a %b %d %Y", "%d %b %Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def payout_key(program, period):
    """Same payout however X words it: 'Aug 29, 2026 - Sep 12, 2026' == 'Aug 29 2026 to Sep 12 2026'."""
    prog = re.sub(r"[^a-z]", "", (program or "").lower())
    parts = [x for x in re.split(r"\s+(?:-|–|—|to|through)\s+|\s*[–—]\s*", (period or "").strip()) if x.strip()]
    dates = [loose_date(x) for x in parts]
    if dates and all(dates):
        per = "/".join(d.isoformat() for d in dates)
    else:
        per = re.sub(r"[^a-z0-9]", "", (period or "").lower())
    return prog, per


def dedupe_payouts(path):
    """Collapse rows that are the same payout written two ways. Keeps the first one seen."""
    rows = read_csv(path)
    if not rows:
        return rows
    keep, seen = [], set()
    for r in rows:
        k = payout_key(r.get("program"), r.get("period"))
        if k in seen:
            continue
        seen.add(k)
        keep.append(r)
    if len(keep) != len(rows):
        with open(path, newline="", encoding="utf-8") as f:
            header = next(csv.reader(f), [])
        write_csv(path, header, keep)
    return keep


def snowflake_time(post_id):
    try:
        ms = (int(post_id) >> 22) + TWITTER_EPOCH_MS
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)


def duration_seconds(raw):
    s = (raw or "").strip()
    if not s:
        return None
    if re.fullmatch(r"\d+:\d{2}(:\d{2})?", s):
        parts = [int(x) for x in s.split(":")]
        secs = 0
        for p in parts:
            secs = secs * 60 + p
        return secs
    m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(ms|s|sec|secs|seconds)?", s.lower())
    if m:
        v = float(m.group(1))
        if m.group(2) == "ms" or (m.group(2) is None and v > 3600):
            v /= 1000
        return round(v, 1)
    return None


def ends_with_question(text):
    t = re.sub(r"https?://\S+", "", text or "")
    t = re.sub(r"(\s*[#@]\w+)+\s*$", "", t)
    t = re.sub(r"[\s‍️\U0001F000-\U0001FAFF☀-➿]+$", "", t)
    return t.endswith("?") or t.endswith("？")


def map_columns(header, fields):
    """Returns {field: column name} for the columns found, and the list of unmapped columns."""
    out, used = {}, set()
    normed = {h: norm(h) for h in header}
    for field in fields:
        names = ALIASES.get(field, [field])
        for h, n in normed.items():
            if h in used:
                continue
            if n in names:
                out[field] = h
                used.add(h)
                break
    return out, [h for h in header if h not in used]


def snake(h):
    return re.sub(r"[^a-z0-9]+", "_", (h or "").lower()).strip("_") or "column"


def all_fields(rows, base):
    """base fields first, then every other column the rows carry, in a stable order."""
    seen = [k for r in rows for k in r if k not in base and not k.endswith("_raw") and k != "extra"]
    extra = []
    for k in seen:
        if k not in extra:
            extra.append(k)
    return base + extra


def later_sections(path):
    """Sections X puts under the main table, e.g. 'Your videos' under the video overview.
    Returns [(title, header, rows)]. A section is a title line, a header line, then rows."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        grid = [r for r in csv.reader(f)]
    cells = lambda r: [c for c in r if c.strip()]
    out, i, n = [], 0, len(grid)
    blocks = []
    while i < n:
        while i < n and not cells(grid[i]):
            i += 1
        start = i
        while i < n and cells(grid[i]):
            i += 1
        if start < i:
            blocks.append(grid[start:i])
    for b in blocks[1:]:
        title = ""
        if len(cells(b[0])) <= 1 and len(b) > 1:
            title, b = cells(b[0])[0] if cells(b[0]) else "", b[1:]
        if len(b) < 2:
            continue
        header = [h.strip() for h in b[0]]
        rows = [dict(zip(header, r)) for r in b[1:]]
        out.append((title or "section", header, rows))
    return out


def parse_export(path, fields, key_field):
    """Parse an X CSV export into rows keyed by our field names. Returns (rows, problems)."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        grid = [r for r in csv.reader(f)]
    if not any(any(c.strip() for c in r) for r in grid):
        return [], ["file is empty"]
    # X sometimes puts a title line (e.g. "Video overview") above the real header row
    hdr_i = None
    for i, r in enumerate(grid[:10]):
        if key_field in map_columns([c for c in r if c.strip()], fields)[0]:
            hdr_i = i
            break
    if hdr_i is None:
        return [], [f"no {key_field} column (first lines: " + " / ".join(",".join(r) for r in grid[:3])[:200] + ")"]
    header = grid[hdr_i]
    rows = [dict(zip(header, r)) for r in grid[hdr_i + 1:] if any(c.strip() for c in r)]
    if not rows:
        return [], ["no data rows under the header"]
    cols, extra = map_columns(list(rows[0].keys()), fields)
    extra = [h for h in extra if h]
    problems = []
    missing = [f for f in fields if f not in cols]
    if key_field in missing:
        return [], [f"no {key_field} column (columns: {', '.join(rows[0].keys())})"]
    if missing:
        problems.append("columns not in this export: " + ", ".join(missing))
    out = []
    for r in rows:
        o = {}
        for f in fields:
            raw = r.get(cols[f]) if f in cols else None
            if f in ("date", "upload_date"):
                d = parse_date(raw)
                o[f] = d.isoformat() if d else None
                o[f + "_raw"] = raw
            elif f in ("text", "link", "post_link", "post_id", "video_id"):
                o[f] = (raw or "").strip() if raw is not None else None
            elif f == "duration":
                o[f] = (raw or "").strip() if raw is not None else None
                o["duration_s"] = duration_seconds(raw)
            else:
                o[f] = parse_num(raw)
        for h in extra:  # every column X exported, even ones not on the list, under its own name
            k = snake(h)
            if k in o or k in fields:
                k = "x_" + k
            raw = (r.get(h) or "").strip()
            num = parse_num(raw)
            o[k] = num if num is not None else (raw or None)
        if key_field == "date" and o["date"] is None and out:
            break  # a second section starts below the daily rows (e.g. "Your videos")
        out.append(o)
    if key_field == "date" and any(o["date"] is None for o in out):
        problems.append("some dates could not be read: " + ", ".join(
            sorted({str(o.get('date_raw')) for o in out if o['date'] is None})[:5]))
    return out, problems


def read_panels(path):
    """panels.txt lines 'key: value'. Value kept raw. 'FAILED ...' or 'NOT SHOWN' allowed."""
    vals = {}
    if not os.path.exists(path):
        return vals
    with open(path, encoding="utf-8") as f:
        for line in f:
            if ":" not in line or line.strip().startswith("#"):
                continue
            k, v = line.split(":", 1)
            vals[k.strip().lower()] = v.strip()
    return vals


def panel_item(vals, key):
    raw = vals.get(key)
    if raw is None or raw == "":
        return {"raw": None, "value": None, "status": "missing"}
    up = raw.upper()
    if up.startswith("FAILED"):
        return {"raw": raw, "value": None, "status": "failed", "note": raw[6:].strip(" :-")}
    if up.startswith("NOT SHOWN"):
        return {"raw": raw, "value": None, "status": "not shown", "note": raw[9:].strip(" :-")}
    if up.startswith("NOT AVAILABLE"):
        return {"raw": raw, "value": None, "status": NOT_AVAILABLE}
    main, _, of = raw.partition("/")
    v = parse_num(main)
    item = {"raw": raw, "value": v, "status": "ok" if v is not None else "unreadable",
            "rounded": bool(re.search(r"\d[KkMm]\s*$", main.strip()))}
    if of.strip():
        item["out_of"] = parse_num(of)
    return item


# ----------------------------------------------------------------------------
# paths
# ----------------------------------------------------------------------------

class P:
    def __init__(self, root=ROOT):
        self.root = root
        self.pulls = os.path.join(root, "pulls")
        self.data = os.path.join(root, "data")
        for d in (self.pulls, self.data):
            os.makedirs(d, exist_ok=True)
        self.config = os.path.join(root, "config.json")

    def cfg(self):
        c = dict(DEFAULT_CONFIG)
        if os.path.exists(self.config):
            c.update(read_json(self.config, {}))
        else:
            raise SystemExit(f"No config.json in {self.root}. Run Foreman setup first.")
        missing = sorted(k for k, v in c.items() if v is None and k not in OPTIONAL_NONE)
        if missing:
            raise SystemExit(f"Analytics Log config is missing settings: {', '.join(missing)}. Run Foreman setup.")
        return c

    def d(self, name):
        return os.path.join(self.data, name)


# ----------------------------------------------------------------------------
# start
# ----------------------------------------------------------------------------

def cmd_start(p, kind):
    t = now_et()
    base = f"{t.strftime('%Y-%m-%d_%H%M')}_{kind}"
    pid, n = base, 2
    while os.path.exists(os.path.join(p.pulls, pid)):
        pid, n = f"{base}-{n}", n + 1
    folder = os.path.join(p.pulls, pid)
    raw = os.path.join(folder, "raw")
    os.makedirs(raw)
    mode = "night" if kind == "test" else kind
    keys = PANEL_KEYS_EVERY + (PANEL_KEYS_MORNING if mode == "morning" else PANEL_KEYS_NIGHT)
    extra_keys = []
    if mode == "night":
        keys.append("active_by_hour_tz")
        extra_keys = [f"extra.{sec}.{fld}" for sec, flds in EXTRA_SPEC.items() for fld in flds]
    with open(os.path.join(raw, "panels.txt"), "w", encoding="utf-8") as f:
        f.write(f"# {pid}\n# Copy each value exactly as X shows it, e.g. 349.3K or 337K or 6,412.\n"
                "# If X doesn't show one, write NOT SHOWN. If the page fails, write FAILED and the reason.\n"
                "# Panels shown as '4.9K / 6.4K': copy the whole thing. The part after / is kept too.\n"
                "# active_*: Verified filter OFF. Read each window (1h 3h 6h 24h).\n"
                "# verified_active_daily: Verified filter ON, the one daily figure X shows.\n"
                "# verified_followers: open the Verified followers info panel and copy the exact count\n"
                "# (e.g. 2,912), not the rounded 2.9K card. Same for followers_total if the card is rounded.\n")
        for k in keys:
            f.write(f"{k}: \n")
        if extra_keys:
            f.write("# Night extras. Copy each exactly as shown, change included, e.g. 186.1K (up 52%).\n"
                    "# overview_1y_all = Overview, 1Y, All. overview_2w_* = 2W range. overview_90d_verified =\n"
                    "# the same custom 91-day range as verified_90d.csv, Verified filter. audience_7d_* = Audience tab,\n"
                    "# 7 days. audience_7d_country.top = the countries as shown, e.g. US 51.5%, Japan 7.9%.\n"
                    "# creator_studio = the status badge for each program, open_requirements = what's still unmet.\n")
            for k in extra_keys:
                f.write(f"{k}: \n")
    manifest = {"schema": SCHEMA, "pull_id": pid, "kind": kind, "started_at_et": t.isoformat(timespec="seconds"),
                "finished": False}
    write_json(os.path.join(folder, "manifest.json"), manifest)
    lines = [f"Pull folder: {folder}", f"Started {t.strftime('%a %b %d, %Y %I:%M %p')} {TZ_LABEL} ({kind}).", "",
             "Save these into raw/ with exactly these names:"]
    for name, (kinds, what) in RAW_FILES.items():
        if mode in kinds:
            opt = " (optional)" if name in OPTIONAL_FILES else ""
            lines.append(f"- {name}{opt}: {what}")
    lines += ["", "Fill in raw/panels.txt, one value per line, exactly as shown:"] + [f"- {k}" for k in keys]
    if extra_keys:
        lines += ["", "Night extras, also in panels.txt (sections: " + ", ".join(EXTRA_SPEC) + ")"]
    lines += ["", f"Then run: python3 {os.path.abspath(__file__)} finish {folder}"]
    print("\n".join(lines))


# ----------------------------------------------------------------------------
# finish
# ----------------------------------------------------------------------------

def load_post_meta(cfg):
    """Type and media for my posts from the other bots' saved data. No API calls."""
    meta = {}
    eng = read_json(cfg["engagement_posts"], {})
    for i, x in eng.items():
        meta.setdefault(i, {})["type"] = x.get("kind") if x.get("kind") in ("original", "reply", "quote") else None
        meta[i]["type_source"] = "engagement"
    rr = read_json(cfg["rerun_posts"], {})
    for i, x in rr.items():
        m = meta.setdefault(i, {})
        if x.get("kind"):
            m["type"], m["type_source"] = x["kind"], "reruns"
        media = x.get("media")
        if isinstance(media, list):
            if "video" in media:
                m["media"] = "video"
            elif "animated_gif" in media:
                m["media"] = "gif"
            elif media:
                m["media"] = "image"
            else:
                m["media"] = "text only"
            m["media_source"] = "reruns"
    return meta


def window_stats(rows_by_date, today, tracker, days):
    """rows_by_date {iso date: impressions}. Returns window sums and what drops next."""
    def total(end, n):
        ds = [(end - timedelta(days=k)).isoformat() for k in range(n)]
        have = [d for d in ds if rows_by_date.get(d) is not None]
        return sum(rows_by_date[d] for d in have), len(have)

    incl, n_incl = total(today, days)
    excl, n_excl = total(today - timedelta(days=1), days)
    # The tracker covers the days ending yesterday (today-days .. today-1), the same window as
    # sum_ending_yesterday. Its oldest day is the first to leave, on tomorrow's reading.
    oldest = today - timedelta(days=days)
    upcoming = []
    for k in range(7):
        d = (oldest + timedelta(days=k)).isoformat()
        upcoming.append({"date": d, "leaves_on_reading_of": (today + timedelta(days=k + 1)).isoformat(),
                         "verified_impressions": rows_by_date.get(d)})
    ratio = round(tracker / excl, 4) if tracker and excl else None
    return {"window_days": days,
            "sum_incl_today": incl, "days_present_incl_today": n_incl,
            "sum_ending_yesterday": excl, "days_present_ending_yesterday": n_excl,
            "settled_through": (today - timedelta(days=2)).isoformat(),
            "drops_next_date": upcoming[0]["date"], "drops_next_value": upcoming[0]["verified_impressions"],
            "next_7_to_drop": upcoming,
            "tracker_value": tracker, "tracker_over_sum_ending_yesterday": ratio}


def mark_complete(rows, started):
    """X dates its daily exports in UTC. A day is complete once that UTC day has ended at pull time,
    so a night pull's newest row (tomorrow in UTC) is partial."""
    utc_today = started.astimezone(timezone.utc).date().isoformat()
    for r in rows:
        if r.get("date"):
            r["day_complete"] = "yes" if r["date"] < utc_today else "no, partial"
    return rows


def merge_daily(path_latest, path_history, pid, pulled, rows, fields):
    """Daily tables: history keeps every reading, latest keeps the newest value per date."""
    fields = all_fields(rows, list(fields))
    hist_fields = ["pull_id", "pulled_at_et"] + fields
    append_csv(path_history, hist_fields, [dict(r, pull_id=pid, pulled_at_et=pulled) for r in rows])
    latest = {r["date"]: r for r in read_csv(path_latest) if r.get("date")}
    changed = 0
    for r in rows:
        if not r.get("date"):
            continue
        old = latest.get(r["date"])
        new = {f: r.get(f) for f in fields}
        new["last_pull"] = pid
        new["first_seen_pull"] = old.get("first_seen_pull", pid) if old else pid
        if old and str(old.get("impressions", old.get("views"))) != str(new.get("impressions", new.get("views"))):
            changed += 1
        latest[r["date"]] = new
    rows_out = [latest[d] for d in sorted(latest)]
    write_csv(path_latest, all_fields(rows_out, fields + ["first_seen_pull", "last_pull"]), rows_out)
    return changed


def impressions_at_24h(history, posted):
    """history: [(pulled_at datetime, impressions)]. Interpolates to exactly 24h after posting."""
    if not posted or not history:
        return None, "no readings"
    target = posted + timedelta(hours=24)
    pts = sorted((t, v) for t, v in history if v is not None)
    before = [x for x in pts if x[0] <= target]
    after = [x for x in pts if x[0] >= target]
    hrs = lambda t: round((t - posted).total_seconds() / 3600, 1)
    if before and after:
        (t0, v0), (t1, v1) = before[-1], after[0]
        if t1 == t0:
            return v0, f"read at {hrs(t0)}h"
        if (t1 - t0) > timedelta(hours=30):
            return None, f"readings too far apart ({hrs(t0)}h and {hrs(t1)}h)"
        v = v0 + (v1 - v0) * (target - t0).total_seconds() / (t1 - t0).total_seconds()
        return int(round(v)), f"interpolated between {hrs(t0)}h and {hrs(t1)}h"
    if after and hrs(after[0][0]) <= 28:
        return after[0][1], f"nearest reading at {hrs(after[0][0])}h"
    if before and hrs(before[-1][0]) >= 20 and (now_et() - posted) < timedelta(hours=30):
        return None, "not 24h old at the last reading"
    if not after:
        return None, "not 24h old yet"
    return None, f"first reading came at {hrs(after[0][0])}h"


def cmd_finish(p, folder):
    cfg = p.cfg()
    if not folder:
        open_pulls = []
        for d in os.listdir(p.pulls):
            m = read_json(os.path.join(p.pulls, d, "manifest.json"), None)
            if m and not m.get("finished"):
                open_pulls.append((m["started_at_et"], d))
        if not open_pulls:
            raise SystemExit("No unfinished pull. Run start first, or name the pull folder.")
        folder = os.path.join(p.pulls, max(open_pulls)[1])
    folder = os.path.abspath(folder)
    man_path = os.path.join(folder, "manifest.json")
    man = read_json(man_path, None)
    if not man:
        raise SystemExit(f"No manifest.json in {folder}. Was it made with start?")
    if os.path.exists(os.path.join(folder, "pull.json")):
        raise SystemExit(f"{folder} is already finished. Start a new pull instead of overwriting this one.")
    pid, kind = man["pull_id"], man["kind"]
    mode = "night" if kind == "test" else kind
    if kind == "test":
        # a test pull reads like a night pull but never touches the real records
        test_data = os.path.join(folder, "test_data")
        os.makedirs(test_data, exist_ok=True)
        for name in os.listdir(p.data):
            if name.endswith(".csv"):
                with open(os.path.join(p.data, name), "rb") as src, open(os.path.join(test_data, name), "wb") as dst:
                    dst.write(src.read())
        p.data = test_data
    started = datetime.fromisoformat(man["started_at_et"])
    pulled = man["started_at_et"]
    today = started.date()
    raw = os.path.join(folder, "raw")
    flags, items = [], {}

    def have(name):
        f = os.path.join(raw, name)
        return f if os.path.exists(f) and os.path.getsize(f) > 0 else None

    def expect_file(name):
        kinds, _ = RAW_FILES[name]
        if mode not in kinds:
            items[name] = "not expected on a " + kind + " pull"
            return None
        if unavailable(cfg, name):
            items[name] = NOT_AVAILABLE
            return None
        f = have(name)
        if not f:
            items[name] = "missing"
            if name not in OPTIONAL_FILES:
                flags.append(f"{name} missing")
        else:
            items[name] = "ok"
        return f

    panels = read_panels(os.path.join(raw, "panels.txt"))
    panel_keys = PANEL_KEYS_EVERY + (PANEL_KEYS_MORNING if mode == "morning" else PANEL_KEYS_NIGHT)
    pv = {k: panel_item(panels, k) for k in panel_keys}
    for k in pv:
        if unavailable(cfg, k, panel=True):
            pv[k] = {"raw": NOT_AVAILABLE, "value": None, "status": NOT_AVAILABLE}
    for k, v in pv.items():
        items["panel:" + k] = v["status"]
        if v["status"] != "ok" and v["status"] != NOT_AVAILABLE and k not in OPTIONAL_PANELS:
            flags.append(f"panel {k}: {v['status']}" + (f" ({v.get('note')})" if v.get("note") else ""))

    out = {"schema": SCHEMA, "pull_id": pid, "kind": kind, "pulled_at_et": pulled,
           "timezones": {
               "pulled_at_et": TZ_LABEL,
               "posted_at_et": "exact, from each post ID, converted to " + TZ_LABEL,
               "x_export_dates": "as X writes them, not converted. See content_export_date_check below.",
           }}

    # 1. tracker
    tr = pv["tracker"]
    shot = expect_file("tracker.png")
    out["tracker"] = {"value": tr["value"], "raw": tr["raw"], "status": tr["status"],
                      "screenshot": f"raw/tracker.png" if shot else None}
    prev = read_csv(p.d("tracker.csv"))
    prev_ok = [r for r in prev if r.get("status") == "ok"]
    out["tracker"]["change_since_last_pull"] = (
        tr["value"] - int(prev_ok[-1]["value"]) if tr["value"] is not None and prev_ok else None)
    append_csv(p.d("tracker.csv"), ["pull_id", "pulled_at_et", "kind", "value", "raw", "status", "screenshot"],
               [dict(out["tracker"], pull_id=pid, pulled_at_et=pulled, kind=kind)])

    # 2. followers
    expect_file("followers.png")
    fol = {k: pv[k]["value"] for k in PANEL_KEYS_EVERY if k != "tracker"}
    for k in ("verified_followers", "followers_total"):
        if pv[k].get("rounded"):
            flags.append(f"{k} was copied rounded ({pv[k]['raw']}). Read the exact count from the "
                         f"{'Verified followers' if k == 'verified_followers' else 'Followers'} info panel")
    rounded = pv["verified_followers"].get("rounded") or pv["followers_total"].get("rounded")
    if fol.get("verified_followers") and fol.get("followers_total") and (
            not rounded or fol.get("verified_followers_pct") is None):
        # exact counts beat X's whole-number percent
        fol["verified_followers_pct"] = round(100 * fol["verified_followers"] / fol["followers_total"], 2)
        fol["verified_followers_pct_source"] = ("computed from rounded values, approximate" if rounded
                                                else "computed from exact counts")
    elif fol.get("verified_followers_pct") is not None:
        fol["verified_followers_pct_source"] = "shown by X"
    fol["raw"] = {k: pv[k]["raw"] for k in PANEL_KEYS_EVERY if k != "tracker"}
    fol["status"] = {k: pv[k]["status"] for k in PANEL_KEYS_EVERY if k != "tracker"}
    fol["rounded"] = sorted(k for k in PANEL_KEYS_EVERY if k != "tracker" and pv[k].get("rounded"))
    fol["out_of"] = {k: pv[k]["out_of"] for k in PANEL_KEYS_EVERY if k != "tracker" and "out_of" in pv[k]}
    out["followers"] = fol
    fcols = [k for k in PANEL_KEYS_EVERY if k != "tracker"]
    drop_columns(p.d("followers.csv"), DROPPED_FOLLOWER_COLS)
    append_csv(p.d("followers.csv"), ["pull_id", "pulled_at_et", "kind"] + fcols + ["verified_followers_pct_source"],
               [dict({k: fol.get(k) for k in fcols}, pull_id=pid, pulled_at_et=pulled, kind=kind,
                     verified_followers_pct_source=fol.get("verified_followers_pct_source"))])

    # 4. verified daily, full window (every pull)
    v90 = expect_file("verified_90d.csv")
    by_date = {}
    if v90:
        rows, probs = parse_export(v90, OVERVIEW_FIELDS, "date")
        mark_complete(rows, started)
        for pr in probs:
            flags.append(f"verified_90d.csv: {pr}")
        by_date = {r["date"]: r.get("impressions") for r in rows if r.get("date")}
        changed = merge_daily(p.d("verified_daily_latest.csv"), p.d("verified_daily_history.csv"), pid, pulled,
                              rows, OVERVIEW_FIELDS)
        ws = window_stats(by_date, today, tr["value"], cfg["window_days"])
        ws["export_first_date"] = min(by_date) if by_date else None
        ws["export_last_date"] = max(by_date) if by_date else None
        ws["days_in_export"] = len(by_date)
        ws["dates_revised_since_last_reading"] = changed
        if ws["days_present_ending_yesterday"] < cfg["window_days"]:
            flags.append(f"verified_90d.csv covers {ws['days_present_ending_yesterday']} of the "
                         f"{cfg['window_days']} days ending yesterday. Export a 3M or custom 91-day range.")
        out["verified_window"] = ws
        append_csv(p.d("verified_window.csv"),
                   ["pull_id", "pulled_at_et", "kind", "tracker_value", "sum_ending_yesterday",
                    "days_present_ending_yesterday", "sum_incl_today", "tracker_over_sum_ending_yesterday",
                    "drops_next_date", "drops_next_value", "settled_through", "dates_revised_since_last_reading"],
                   [dict(ws, pull_id=pid, pulled_at_et=pulled, kind=kind)])
    else:
        out["verified_window"] = {"status": NOT_AVAILABLE if unavailable(cfg, "verified_90d.csv") else "missing"}

    # 3. account overview, 14 days: All on every pull, Verified at night
    for name, label in (("overview_all_14d.csv", "all"), ("overview_verified_14d.csv", "verified")):
        if mode not in RAW_FILES[name][0]:
            continue
        f = expect_file(name)
        if not f:
            out[f"overview_{label}"] = {"status": "missing"}
            continue
        rows, probs = parse_export(f, OVERVIEW_FIELDS, "date")
        mark_complete(rows, started)
        for pr in probs:
            flags.append(f"{name}: {pr}")
        merge_daily(p.d(f"overview_{label}_latest.csv"), p.d(f"overview_{label}_history.csv"),
                    pid, pulled, rows, OVERVIEW_FIELDS)
        out[f"overview_{label}"] = {"status": "ok", "days": len(rows), "rows": rows}

    # 3b. morning: yesterday's final numbers, verified and all
    if mode == "morning":
        yd = (today - timedelta(days=1)).isoformat()
        val = by_date.get(yd)
        src = "verified_90d.csv"
        if val is None and pv.get("yesterday_verified_impressions", {}).get("value") is not None:
            val, src = pv["yesterday_verified_impressions"]["value"], "panel"
        all_rows = {r.get("date"): r for r in out.get("overview_all", {}).get("rows", [])}
        all_imp = (all_rows.get(yd) or {}).get("impressions")
        share = round(100 * val / all_imp, 2) if val is not None and all_imp else None
        out["yesterday_verified"] = {"date": yd, "value": val, "source": src if val is not None else None,
                                     "status": "ok" if val is not None else "missing",
                                     "all_impressions": all_imp,
                                     "all_source": "overview_all_14d.csv" if all_imp is not None else None,
                                     "verified_share_pct": share}
        if val is None:
            if cfg.get("has_premium"):
                flags.append(f"yesterday's verified impressions ({yd}) missing")
        if all_imp is None:
            flags.append(f"yesterday's all impressions ({yd}) missing from overview_all_14d.csv")
        append_csv(p.d("yesterday_verified.csv"),
                   ["pull_id", "pulled_at_et", "date", "value", "source", "all_impressions", "all_source",
                    "verified_share_pct"],
                   [dict(out["yesterday_verified"], pull_id=pid, pulled_at_et=pulled)])

    if mode == "night":
        # 5. posts
        cf = expect_file("content_14d.csv")
        vl = expect_file("video_list.csv")
        vids = {}
        if vl:
            vrows, probs = parse_export(vl, VIDEO_LIST_FIELDS, "video_id")
            for pr in probs:
                if "post_link" not in pr:
                    flags.append(f"video_list.csv: {pr}")
            links = link_videos(vrows, read_json(cfg["rerun_posts"], {}), cfg.get("video_match_seconds", 600))
            for r in vrows:
                hit = links.get(r.get("video_id"))
                if hit:
                    r["linked_post"], r["link_method"] = hit
                    vids[hit[0]] = r
            linked = len(links)
            out_methods = {}
            for _, how in links.values():
                key = how.split(" (")[0]
                out_methods[key] = out_methods.get(key, 0) + 1
            if vrows and linked < len(vrows):
                flags.append(f"video_list.csv: {linked} of {len(vrows)} videos linked to a post. The rest had no "
                             "post link and no saved video post close enough in time")
            merged = merge_by_key(read_csv(p.d("video_list_latest.csv")), vrows, "video_id", pid)
            write_csv(p.d("video_list_latest.csv"), all_fields(merged, VIDEO_LIST_FIELDS + [
                "duration_s", "linked_post", "link_method", "last_pull"]), merged)
            out["video_list"] = {"status": "ok", "videos": len(vrows), "linked": linked,
                                 "link_methods": out_methods, "rows": vrows}
        else:
            out["video_list"] = {"status": "missing"}
        if cf:
            out["posts"] = process_posts(p, cfg, cf, pid, started, vids, flags)
        else:
            out["posts"] = {"status": "missing"}

        # 6. video daily
        vo = expect_file("video_overview_14d.csv")
        if vo:
            rows, probs = parse_export(vo, VIDEO_DAILY_FIELDS, "date")
            mark_complete(rows, started)
            for pr in probs:
                flags.append(f"video_overview_14d.csv: {pr}")
            merge_daily(p.d("video_daily_latest.csv"), p.d("video_daily_history.csv"), pid, pulled,
                        rows, VIDEO_DAILY_FIELDS)
            out["video_daily"] = {"status": "ok", "days": len(rows), "rows": rows}
            save_sections(p, vo, "video_overview", pid, pulled, out["video_daily"])
        else:
            out["video_daily"] = {"status": "missing"}

        # 7. active followers by hour
        ah = expect_file("active_by_hour.csv")
        if ah:
            hrs = []
            for r in read_csv(ah):
                h = r.get("hour") or r.get("Hour")
                v = parse_num(r.get("active") or r.get("Active"))
                hrs.append({"hour": h, "active": v})
            tz = panels.get("active_by_hour_tz") or "not noted"
            append_csv(p.d("active_by_hour.csv"), ["pull_id", "pulled_at_et", "x_timezone", "hour", "active"],
                       [dict(h, pull_id=pid, pulled_at_et=pulled, x_timezone=tz) for h in hrs])
            out["active_by_hour"] = {"status": "ok", "x_timezone": tz, "hours": hrs}
        else:
            out["active_by_hour"] = {"status": "not shown or not saved"}

        # 7. extras from the analytics pages
        extras, absent = {}, []
        for sec, flds in EXTRA_SPEC.items():
            extras[sec] = {fld: parse_extra(panels.get(f"extra.{sec}.{fld}")) for fld in flds}
            if all(v["status"] == "missing" for v in extras[sec].values()):
                absent.append(sec)
        if absent:
            flags.append("extras not recorded: " + ", ".join(absent))
        out["extras"] = extras
        append_csv(p.d("extras_history.csv"),
                   ["pull_id", "pulled_at_et", "section", "field", "raw", "value", "change_pct", "status"],
                   [{"pull_id": pid, "pulled_at_et": pulled, "section": sec, "field": fld, **v}
                    for sec, d in extras.items() for fld, v in d.items() if v["status"] != "missing"])

        # 7. payout history as listed in Creator Studio, kept once per program and period
        pl = expect_file("payouts_list.csv")
        if pl:
            before = len(read_csv(p.d("payouts_list.csv")))
            have_rows = dedupe_payouts(p.d("payouts_list.csv"))
            removed = before - len(have_rows)
            if removed:
                flags.append(f"payouts_list.csv: removed {removed} duplicate rows left by an older pull")
            seen = {payout_key(r.get("program"), r.get("period")) for r in have_rows}
            new_rows = []
            for r in read_csv(pl):
                r = {k.strip().lower(): (v or "").strip() for k, v in r.items() if k}
                key = payout_key(r.get("program"), r.get("period"))
                if key in seen or not r.get("amount"):
                    continue
                seen.add(key)
                new_rows.append({"program": r.get("program"), "period": r.get("period"),
                                 "amount_raw": r.get("amount"), "amount": parse_num(r.get("amount")),
                                 "paid_date": r.get("paid_date") or None, "first_seen_pull": pid})
            append_csv(p.d("payouts_list.csv"), ["program", "period", "amount_raw", "amount", "paid_date",
                                                 "first_seen_pull"], new_rows)
            total = sum(parse_num(r.get("amount")) or 0 for r in read_csv(p.d("payouts_list.csv")))
            out["payouts_list"] = {"status": "ok", "new_payouts": len(new_rows), "duplicates_removed": removed,
                                   "rows": before - removed + len(new_rows), "listed_total": round(total, 2)}
        else:
            out["payouts_list"] = {"status": NOT_AVAILABLE if unavailable(cfg, "payouts_list.csv")
                                   else "not saved this pull"}

        # 7. payouts
        amt, pdt = pv.get("payout_amount", {}), pv.get("payout_date", {})
        if amt.get("value") is not None:
            pays = read_csv(p.d("payouts.csv"))
            key = (amt["raw"], pdt.get("raw") or "")
            new = not any((r.get("amount_raw"), r.get("payout_date")) == key for r in pays)
            if new:
                append_csv(p.d("payouts.csv"), ["pull_id", "pulled_at_et", "amount_raw", "amount", "payout_date"],
                           [{"pull_id": pid, "pulled_at_et": pulled, "amount_raw": amt["raw"],
                             "amount": amt.get("value"), "payout_date": pdt.get("raw")}])
            out["payout"] = {"amount_raw": amt["raw"], "payout_date": pdt.get("raw"), "new": new}
        else:
            out["payout"] = {"status": amt.get("raw") or "none shown"}

    # 7. follows and unfollows by name: Follow Audit
    fw = cfg["follow_watch_dir"]
    fw_state = read_json(os.path.join(fw, "data", "state.json"), {})
    out["follow_watch"] = {
        "events_csv": os.path.join(fw, "data", "events.csv"),
        "last_full_scan": (fw_state.get("last_full") or {}).get("date"),
        "note": "Names of who followed and unfollowed come from Follow Audit scans, with verified status. "
                "They're only as fresh as its last scan.",
    }

    # same keys on every pull, in the same order
    sections = ["tracker", "followers", "yesterday_verified", "verified_window", "overview_all",
                "overview_verified", "posts", "video_daily", "video_list", "active_by_hour", "payout",
                "payouts_list", "extras", "follow_watch"]
    for k in sections:
        out.setdefault(k, {"status": f"not expected on a {kind} pull"})
    head = {k: out[k] for k in ("schema", "pull_id", "kind", "pulled_at_et", "timezones")}
    out = dict(head, **{k: out[k] for k in sections})
    out["items"] = items
    out["flags"] = flags
    out["finished_at_et"] = now_et().isoformat(timespec="seconds")
    write_json(os.path.join(folder, "pull.json"), out)
    man["finished"] = True
    write_json(man_path, man)
    append_csv(p.d("pulls.csv"), ["pull_id", "pulled_at_et", "kind", "flag_count", "flags"],
               [{"pull_id": pid, "pulled_at_et": pulled, "kind": kind, "flag_count": len(flags),
                 "flags": " | ".join(flags) or "none"}])
    print(summary(out))


def snow_time(x):
    try:
        return datetime.fromtimestamp(((int(re.sub(r"\D", "", str(x).split("_")[-1])) >> 22) + TWITTER_EPOCH_MS)
                                      / 1000, tz=timezone.utc)
    except (TypeError, ValueError):
        return None


def link_videos(vrows, rr_posts, max_seconds):
    """Video ID -> (post id, how). X's analytics Video ID isn't the API media id, but both are made
    at upload time, so a video matches the saved video whose media id was made closest in time.
    Each post is used once, closest pairs first. Exact id or post-link matches win outright."""
    by_media, posts_by_id = {}, set(rr_posts)
    cands = []  # (media time, post id)
    for pid_, x in rr_posts.items():
        if not ({"video", "animated_gif"} & set(x.get("media") or [])):
            continue
        for k in x.get("media_keys") or []:
            by_media[k.split("_")[-1]] = pid_
            if k.split("_")[0] in ("7", "13", "16"):
                t = snow_time(k)
                if t:
                    cands.append((t, pid_))
    out, used = {}, set()
    pairs = []
    for r in vrows:
        vid = r.get("video_id") or ""
        m = re.search(r"/status/(\d+)", r.get("post_link") or "")
        num = re.sub(r"\D", "", vid.split("_")[-1])
        if m:
            out[vid] = (m.group(1), "post link")
            used.add(m.group(1))
        elif num in by_media:
            out[vid] = (by_media[num], "same media id")
            used.add(by_media[num])
        elif num in posts_by_id:
            out[vid] = (num, "video id is the post id")
            used.add(num)
        else:
            t = snow_time(vid)
            if t:
                for ct, pid_ in cands:
                    d = abs((ct - t).total_seconds())
                    if d <= max_seconds:
                        pairs.append((d, vid, pid_))
    for d, vid, pid_ in sorted(pairs):
        if vid in out or pid_ in used:
            continue
        out[vid] = (pid_, f"upload time match ({d:.0f}s apart)")
        used.add(pid_)
    return out


def save_sections(p, path, prefix, pid, pulled, into):
    """Every table X adds under an export's main one is kept: a history row per pull and a
    latest file keyed by its first column."""
    saved = []
    for title, header, rows in later_sections(path):
        name = f"{prefix}_{snake(title)}"
        clean = [{snake(h) or f"col{i}": (parse_num(r.get(h)) if parse_num(r.get(h)) is not None
                                         else ((r.get(h) or "").strip() or None))
                  for i, h in enumerate(header) if h} for r in rows]
        fields = [snake(h) for h in header if h]
        append_csv(p.d(f"{name}_history.csv"), ["pull_id", "pulled_at_et"] + fields,
                   [dict(r, pull_id=pid, pulled_at_et=pulled) for r in clean])
        key = fields[0] if fields else None
        if key:
            cur = {str(r.get(key)): r for r in read_csv(p.d(f"{name}_latest.csv")) if r.get(key)}
            for r in clean:
                if r.get(key) is not None:
                    cur[str(r[key])] = dict(r, last_pull=pid)
            write_csv(p.d(f"{name}_latest.csv"), fields + ["last_pull"], list(cur.values()))
        saved.append({"section": title, "rows": len(clean), "file": f"{name}_latest.csv"})
    if saved:
        into["sections"] = saved


def merge_by_key(old_rows, new_rows, key, pid):
    cur = {r[key]: r for r in old_rows if r.get(key)}
    for r in new_rows:
        if r.get(key):
            cur[r[key]] = dict({k: v for k, v in r.items() if not k.endswith("_raw")}, last_pull=pid)
    return list(cur.values())


def process_posts(p, cfg, path, pid, started, vids, flags):
    rows, probs = parse_export(path, CONTENT_FIELDS, "post_id")
    for pr in probs:
        flags.append(f"content_14d.csv: {pr}")
    meta = load_post_meta(cfg)
    metric_fields = ["impressions", "likes", "engagements", "bookmarks", "shares", "new_follows", "replies",
                     "reposts", "profile_visits", "detail_expands", "url_clicks", "hashtag_clicks",
                     "permalink_clicks"]
    metric_fields = all_fields(rows, metric_fields + [f for f in CONTENT_FIELDS if f not in metric_fields])
    metric_fields = [f for f in metric_fields if f not in ("post_id", "date", "text", "link")]
    pulled_utc = started.astimezone(timezone.utc)
    hist_rows, tz_utc, tz_et, compared = [], 0, 0, 0
    for r in rows:
        posted = snowflake_time(r["post_id"])
        r["posted_at_et"] = posted.astimezone(ET).isoformat(timespec="seconds") if posted else None
        r["age_hours"] = round((pulled_utc - posted).total_seconds() / 3600, 1) if posted else None
        if posted and r.get("date"):
            compared += 1
            tz_utc += r["date"] == posted.date().isoformat()
            tz_et += r["date"] == posted.astimezone(ET).date().isoformat()
        hist_rows.append(dict({f: r.get(f) for f in metric_fields}, pull_id=pid,
                              pulled_at_et=started.isoformat(timespec="seconds"), post_id=r["post_id"],
                              posted_at_et=r["posted_at_et"], age_hours=r["age_hours"]))
    append_csv(p.d("posts_history.csv"),
               ["pull_id", "pulled_at_et", "post_id", "posted_at_et", "age_hours"] + metric_fields, hist_rows)

    # union every post ID ever seen, freshest figures win per post
    latest = {r["post_id"]: r for r in read_csv(p.d("posts_latest.csv")) if r.get("post_id")}
    for r in rows:
        if not r.get("post_id"):
            continue
        m = meta.get(r["post_id"], {})
        typ, tsrc = m.get("type"), m.get("type_source")
        if not typ:
            t = (r.get("text") or "").strip()
            typ, tsrc = ("repost", "text") if t.startswith("RT @") else (("reply", "text guess") if t.startswith("@")
                                                                           else ("unknown", "not in saved data"))
        media, msrc = m.get("media"), m.get("media_source")
        v = vids.get(r["post_id"])
        if v:
            media, msrc = "video", "video_list"
        if not media:
            media, msrc = "unknown", "not in saved data yet"
        posted_et_date = r["posted_at_et"][:10] if r.get("posted_at_et") else None
        latest[r["post_id"]] = dict(
            {f: r.get(f) for f in CONTENT_FIELDS + metric_fields},
            posted_at_et=r.get("posted_at_et"), export_date=r.get("date"),
            export_date_differs_from_et=(r.get("date") != posted_et_date) if posted_et_date and r.get("date") else None,
            type=typ, type_source=tsrc, media=media, media_source=msrc,
            video_length_s=(v or {}).get("duration_s") if media == "video" else "n/a",
            ends_with_question=ends_with_question(r.get("text")),
            last_pull=pid, first_seen_pull=(latest.get(r["post_id"]) or {}).get("first_seen_pull", pid))

    # impressions at exactly 24h old, from every reading of each post
    hist = {}
    for h in read_csv(p.d("posts_history.csv")):
        try:
            t = datetime.fromisoformat(h["pulled_at_et"])
        except (TypeError, ValueError):
            continue
        hist.setdefault(h["post_id"], []).append((t, parse_num(h.get("impressions"))))
    for pid_, r in latest.items():
        posted = snowflake_time(pid_)
        v, how = impressions_at_24h(hist.get(pid_, []), posted)
        r["impressions_24h"], r["impressions_24h_method"] = v, how

    fields = (["post_id", "posted_at_et", "export_date", "export_date_differs_from_et", "type", "type_source",
               "media", "media_source", "video_length_s", "ends_with_question", "text", "link"]
              + metric_fields + ["impressions_24h", "impressions_24h_method", "first_seen_pull", "last_pull"])
    ordered = sorted(latest.values(), key=lambda r: r.get("posted_at_et") or "", reverse=True)
    write_csv(p.d("posts_latest.csv"), [f for f in all_fields(ordered, fields) if f != "date"], ordered)

    check = {"posts_compared": compared, "export_date_equals_utc_date": tz_utc, "export_date_equals_et_date": tz_et}
    if compared:
        if tz_utc == compared and tz_et < compared:
            check["conclusion"] = "X's content export dates posts in UTC, so evening ET posts show the next day"
        elif tz_et == compared:
            check["conclusion"] = "X's content export dates match Eastern time"
        else:
            check["conclusion"] = "mixed, check by hand"
    unknown_type = sum(1 for r in rows if (latest.get(r.get("post_id")) or {}).get("type") == "unknown")
    unknown_media = sum(1 for r in rows if (latest.get(r.get("post_id")) or {}).get("media") == "unknown")
    if unknown_type:
        flags.append(f"{unknown_type} posts have no type in saved data yet")
    if unknown_media:
        flags.append(f"{unknown_media} posts have no media type in saved data yet")
    return {"status": "ok", "posts_in_export": len(rows), "posts_tracked_total": len(latest),
            "content_export_date_check": check}


# ----------------------------------------------------------------------------
# output
# ----------------------------------------------------------------------------

def fmt(n):
    if n is None:
        return "missing"
    return f"{n:,}" if isinstance(n, int) else str(n)


def summary(o):
    t = datetime.fromisoformat(o["pulled_at_et"])
    L = [f"X analytics, {o['kind']} pull, {t.strftime('%a %b %d, %Y %I:%M %p')} {TZ_LABEL} ({o['pull_id']})"]
    tr = o["tracker"]
    ch = tr.get("change_since_last_pull")
    L.append(f"500K verified impressions tracker: {tr['raw'] or 'missing'}" + (f" ({ch:+,} since last pull)" if ch is not None else ""))
    f = o["followers"]
    L.append(f"Followers: {fmt(f.get('followers_total'))}, verified {fmt(f.get('verified_followers'))}"
             f" ({fmt(f.get('verified_followers_pct'))}%). Following: {fmt(f.get('following_total'))}")
    L.append(f"Today: +{fmt(f.get('new_follows_today'))} / -{fmt(f.get('unfollows_today'))}. "
             f"Yesterday: +{fmt(f.get('new_follows_yesterday'))} / -{fmt(f.get('unfollows_yesterday'))}")
    L.append(f"Active, all: 1h {fmt(f.get('active_1h'))}, 3h {fmt(f.get('active_3h'))}, 6h {fmt(f.get('active_6h'))}, "
             f"24h {fmt(f.get('active_24h'))}")
    L.append(f"Verified active today (daily panel): {fmt(f.get('verified_active_daily'))}")
    if f.get("rounded"):
        L.append("Shown rounded by X: " + ", ".join(f["rounded"]))
    if o.get("yesterday_verified", {}).get("date"):
        y = o["yesterday_verified"]
        line = f"Yesterday ({y['date']}), final: verified {fmt(y['value'])}, all {fmt(y.get('all_impressions'))}"
        if y.get("verified_share_pct") is not None:
            line += f", verified share {y['verified_share_pct']}%"
        L.append(line)
    w = o.get("verified_window", {})
    if w.get("sum_ending_yesterday") is not None:
        L.append(f"Verified export, {w['window_days']} days ending yesterday: {fmt(w['sum_ending_yesterday'])} "
                 f"over {w['days_present_ending_yesterday']} days. Tracker / sum: "
                 f"{fmt(w['tracker_over_sum_ending_yesterday'])}")
        L.append(f"Leaves the window next: {w['drops_next_date']} ({fmt(w['drops_next_value'])}), "
                 f"on the {w['next_7_to_drop'][0]['leaves_on_reading_of']} reading. "
                 "Next 7: " + ", ".join(f"{x['date'][5:]} {fmt(x['verified_impressions'])}"
                                         for x in w["next_7_to_drop"]))
    if o["kind"] in ("night", "test"):
        po = o.get("posts", {})
        if po.get("status") == "ok":
            L.append(f"Posts: {po['posts_in_export']} in the export, {po['posts_tracked_total']} tracked in total. "
                     + po["content_export_date_check"].get("conclusion", ""))
        pls = o.get("payouts_list", {})
        if pls.get("status") == "ok":
            L.append(f"Payouts in Creator Studio: {pls['rows']} listed, {pls['new_payouts']} new this pull. "
                     f"Total of all listed: ${pls['listed_total']:,.2f}")
        if o.get("payout", {}).get("new"):
            L.append(f"New payout: {o['payout']['amount_raw']} on {o['payout']['payout_date']}")
    L.append("Flags: " + ("; ".join(o["flags"]) if o["flags"] else "none"))
    return "\n".join(L)


def cmd_checkvideos(p):
    """Why videos don't link to posts: compares video IDs with the media ids Rerun Picker saved."""
    cfg = p.cfg()
    rr = read_json(cfg["rerun_posts"], {})
    cut = datetime.now(timezone.utc) - timedelta(days=14)
    recent = {i: x for i, x in rr.items() if x.get("created") and
              datetime.fromisoformat(x["created"].replace("Z", "+00:00")) >= cut}
    with_keys = {i: x for i, x in recent.items() if x.get("media_keys")}
    videos = {i: x for i, x in recent.items() if "video" in (x.get("media") or [])}
    keys = {k.split("_")[-1]: (i, k) for i, x in rr.items() for k in (x.get("media_keys") or [])}
    pulls = sorted(d for d in os.listdir(p.pulls) if os.path.exists(os.path.join(p.pulls, d, "raw", "video_list.csv")))
    vl = read_csv(os.path.join(p.pulls, pulls[-1], "raw", "video_list.csv")) if pulls else []
    ids = []
    for r in vl:
        cols, _ = map_columns(list(r.keys()), ["video_id"])
        if "video_id" in cols:
            ids.append(r[cols["video_id"]].strip())
    hits = [v for v in ids if re.sub(r"\D", "", v.split("_")[-1]) in {k for k in keys}]
    print(f"Rerun Picker posts from the last 14 days: {len(recent)}. With media ids saved: {len(with_keys)}. "
          f"With video: {len(videos)}.")
    print("Sample saved media keys: " + ", ".join(k for x in list(with_keys.values())[:5] for k in x["media_keys"][:1]))
    print(f"Video IDs in the newest video_list.csv ({pulls[-1] if pulls else 'none'}): {len(ids)}. "
          "Sample: " + ", ".join(ids[:5]))
    print(f"Same id: {len(hits)} of {len(ids)}")
    vids_t = [(snow_time(k), i) for i, x in rr.items() if {"video", "animated_gif"} & set(x.get("media") or [])
              for k in (x.get("media_keys") or []) if snow_time(k)]
    gaps = []
    for v in ids:
        t = snow_time(v)
        if t and vids_t:
            gaps.append(min(abs((ct - t).total_seconds()) for ct, _ in vids_t))
    if gaps:
        gaps.sort()
        q = lambda f: gaps[min(len(gaps) - 1, int(f * len(gaps)))]
        print(f"Gap to the nearest saved video, in seconds: smallest {gaps[0]:.0f}, median {q(0.5):.0f}, "
              f"90% under {q(0.9):.0f}, largest {gaps[-1]:.0f}")
    links = link_videos([{"video_id": v} for v in ids], rr, cfg.get("video_match_seconds", 600))
    print(f"Linked with the current rules (window {cfg.get('video_match_seconds', 600)}s): {len(links)} of {len(ids)}")


def cmd_status(p):
    rows = read_csv(p.d("pulls.csv"))[-10:]
    if not rows:
        print("No finished pulls yet.")
        return
    for r in rows:
        print(f"{r['pull_id']}: {r['flag_count']} flags. {r['flags']}")
    open_pulls = [d for d in sorted(os.listdir(p.pulls))
                  if not read_json(os.path.join(p.pulls, d, "manifest.json"), {}).get("finished", True)]
    if open_pulls:
        print("Started but not finished: " + ", ".join(open_pulls))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Files and parses X analytics pulls. No X API calls.")
    ap.add_argument("command", choices=["start", "finish", "status", "checkvideos"])
    ap.add_argument("arg", nargs="?", help="start: morning or night. finish: pull folder (default newest)")
    a = ap.parse_args(argv)
    p = P()
    if a.command == "start":
        if a.arg not in ("morning", "night", "test"):
            raise SystemExit("start needs morning, night or test")
        cmd_start(p, a.arg)
    elif a.command == "finish":
        cmd_finish(p, a.arg)
    elif a.command == "checkvideos":
        cmd_checkvideos(p)
    else:
        cmd_status(p)


if __name__ == "__main__":
    main()
