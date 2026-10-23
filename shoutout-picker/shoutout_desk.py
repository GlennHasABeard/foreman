#!/usr/bin/env python3
"""
shoutout_desk.py
Keeps your shoutout history and builds a weekly list of mutuals to choose from.

Commands
  log-add FILE      Add shoutouts to the log. FILE is a CSV with columns
                    date,handle,post_url, one row per person shouted out. A post
                    that features two people gets two rows with the same link.
                    A row with the same handle and link as one already logged is
                    skipped.
  seed-skips FILE   Start the 28-day rest for every row marked skip in a filled-in
                    review CSV, without building a list.
  candidates        Write review/to_review.csv: last week's unpicked list first,
                    then mutuals in your follower range who have never had a
                    shoutout. Uses Follow Audit data, no API calls.
  week FILE         Read the review CSV the Bot filled in and build this week's
                    list (list_size names). Order: last week's unpicked names, then last
                    week's runners-up, then new names. Extra qualifiers are saved
                    as runners-up. Skips aren't reviewed again for 28 days.
  remove HANDLE...  Take people off the list for good. They never come back.
  restore HANDLE... Undo a remove.
  status            Counts and the current list.

Review CSV columns (the Bot fills these in from each account's recent posts)
  handle, verdict (keep or skip), label, sample_post_url, followers_now, last_post_date, note
  label is one of the labels in config.json (for example "photographers"). With no labels
  configured, leave it empty and the list is one plain list.

Read-only toward X. This script makes no network calls at all.
Data lives in /workspace/shoutouts (override with --dir or SD_DIR).
"""

import argparse
import csv
import html
import json
import os
import re
import sys
from datetime import date, datetime

# Where the bots live. Foreman sets BOTS_HOME for each bot. On Grok Bot that is /workspace.
BOTS_HOME = os.environ.get("BOTS_HOME", "/workspace").rstrip("/")

DEFAULT_CONFIG = {
    "follow_watch_dir": BOTS_HOME + "/follow-watch",
    "max_followers": None,
    "min_followers": None,
    "list_size": None,
    "review_pool": 40,
    "skip_cooldown_days": 28,
    "runners_up": 10,
    "timezone": None,
    # what kinds of accounts to shout out, in your words. The Bot reviews against this.
    "account_kinds": "",
    # optional labels to sort the list into, in this order. Empty means one plain list.
    "labels": [],
}

LOG_FIELDS = ["date", "handle", "id", "post_url", "added"]

OPTIONAL_NONE = set()

def check_config(cfg, where):
    """Every setting left as None must come from the user's own config.json, written by Foreman."""
    missing = sorted(k for k, v in cfg.items() if v is None and k not in OPTIONAL_NONE)
    if missing:
        raise SystemExit(f"{where} is missing settings: {', '.join(missing)}. Run Foreman setup or add them to config.json.")
    return cfg


def read_json(path, default):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return default


def write_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1, ensure_ascii=False)
    os.replace(tmp, path)


def norm(h):
    return (h or "").strip().lstrip("@").lower()


def today_local(cfg):
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo(cfg["timezone"])).date()
    except Exception:
        return date.today()


class Desk:
    def __init__(self, root):
        self.root = root
        self.review_dir = os.path.join(root, "review")
        self.weeks_dir = os.path.join(root, "weeks")
        for d in (root, self.review_dir, self.weeks_dir):
            os.makedirs(d, exist_ok=True)
        self.config_path = os.path.join(root, "config.json")
        self.log_path = os.path.join(root, "shoutout_log.csv")
        self.queue_path = os.path.join(root, "queue.json")
        self.removed_path = os.path.join(root, "removed.json")
        self.bench_path = os.path.join(root, "bench.json")
        self.skips_path = os.path.join(root, "skips.json")
        self.cfg = dict(DEFAULT_CONFIG)
        if os.path.exists(self.config_path):
            self.cfg.update(read_json(self.config_path, {}))
        else:
            raise SystemExit(f"No config.json in {root}. Run Foreman setup first.")
        check_config(self.cfg, 'Shoutout Picker config')

    # --- data ---------------------------------------------------------------

    def log(self):
        if not os.path.exists(self.log_path):
            return []
        with open(self.log_path, newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    def save_log(self, rows):
        rows.sort(key=lambda r: (r["date"], r["handle"].lower()))
        with open(self.log_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=LOG_FIELDS)
            w.writeheader()
            for r in rows:
                w.writerow({k: r.get(k, "") for k in LOG_FIELDS})

    def queue(self):
        return read_json(self.queue_path, [])

    def removed(self):
        return read_json(self.removed_path, {})

    def bench(self):
        return read_json(self.bench_path, [])

    def skips(self):
        return read_json(self.skips_path, {})

    def fw_accounts(self):
        path = os.path.join(self.cfg["follow_watch_dir"], "data", "state.json")
        state = read_json(path, {})
        if not state.get("accounts"):
            raise SystemExit(f"No Follow Audit data at {path}. Run a Follow Audit full scan first.")
        return state, state["accounts"]

    def shouted(self):
        ids, handles = set(), set()
        for r in self.log():
            if r.get("id"):
                ids.add(r["id"])
            handles.add(norm(r["handle"]))
        return ids, handles


def handle_index(accounts):
    idx = {}
    for i, a in accounts.items():
        u = a.get("user") or {}
        if u.get("username"):
            idx[norm(u["username"])] = i
    return idx


# ----------------------------------------------------------------------------

def cmd_log_add(desk, path):
    _, accounts = desk.fw_accounts()
    idx = handle_index(accounts)
    rows = desk.log()
    have = {(norm(r["handle"]), r.get("post_url", "")) for r in rows}
    added, skipped = 0, 0
    today = today_local(desk.cfg).isoformat()
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            h = norm(r.get("handle"))
            url = (r.get("post_url") or "").strip()
            if not h:
                continue
            if (h, url) in have:
                skipped += 1
                continue
            rows.append({"date": (r.get("date") or "").strip()[:10], "handle": h,
                         "id": idx.get(h, ""), "post_url": url, "added": today})
            have.add((h, url))
            added += 1
    desk.save_log(rows)
    people = len({norm(r["handle"]) for r in rows})
    print(f"Added {added} shoutouts, skipped {skipped} already logged. "
          f"Log holds {len(rows)} shoutouts to {people} accounts.")



SIZE_BANDS = [(0, 249), (250, 499), (500, 749), (750, 10 ** 9)]


def spread_by_size(items, seed):
    """Shuffle within follower bands, then take one from each band in turn,
    so small and larger accounts both get reviewed every week."""
    import random
    rng = random.Random(seed)
    bands = [[] for _ in SIZE_BANDS]
    for it in items:
        fol = it[1]
        for n, (lo, hi) in enumerate(SIZE_BANDS):
            if lo <= fol <= hi:
                bands[n].append(it)
                break
    for b in bands:
        rng.shuffle(b)
    out = []
    while any(bands):
        for b in bands:
            if b:
                out.append(b.pop())
    return out


def cmd_candidates(desk):
    cfg = desk.cfg
    state, accounts = desk.fw_accounts()
    shout_ids, shout_handles = desk.shouted()
    removed_handles = {norm(h) for h in desk.removed()}
    queue = desk.queue()
    bench = desk.bench()
    today = today_local(cfg)
    cooldown = cfg.get("skip_cooldown_days", 28)
    recent_skips = {h for h, d in desk.skips().items()
                    if (today - date.fromisoformat(d)).days < cooldown}
    taken = {q["id"] for q in queue} | {b["id"] for b in bench}

    dropped_mutual = []

    def still_ok(entry):
        a = accounts.get(entry["id"]) or {}
        u = a.get("user") or {"username": entry["username"]}
        h = norm(u.get("username"))
        if entry["id"] in shout_ids or h in shout_handles or h in removed_handles:
            return None
        if a and not (a.get("follower_now") and a.get("following_now")):
            dropped_mutual.append(u.get("username", entry["username"]))
            return None
        return a, u

    rows = []
    for source, entries in (("rollover", queue), ("runner-up", bench)):
        for e in entries:
            got = still_ok(e)
            if not got:
                continue
            a, u = got
            rows.append({"handle": u.get("username", e["username"]), "source": source,
                         "followers": (u.get("public_metrics") or {}).get("followers_count", e.get("followers", "")),
                         "weeks_listed": e.get("weeks_listed", 0)})

    baseline = state.get("baseline_date", "")
    fresh, old = [], []
    for i, a in accounts.items():
        if not (a.get("follower_now") and a.get("following_now")):
            continue
        if i in taken or i in shout_ids:
            continue
        u = a.get("user") or {}
        h = norm(u.get("username"))
        if not h or h in shout_handles or h in removed_handles or h in recent_skips:
            continue
        fol = (u.get("public_metrics") or {}).get("followers_count", 0) or 0
        if not (cfg["min_followers"] <= fol <= cfg["max_followers"]):
            continue
        newest = max(a.get("follower_since") or "", a.get("following_since") or "")
        item = (newest, fol, u.get("username"), i)
        (fresh if newest and newest > baseline else old).append(item)
    fresh.sort(key=lambda x: x[0], reverse=True)
    iso = today.isocalendar()
    ordered = fresh + spread_by_size(old, f"{iso[0]}-{iso[1]}")
    room = max(0, cfg["review_pool"] - len(rows))
    for newest, fol, name, i in ordered[:room]:
        rows.append({"handle": name, "source": "new mutual" if newest > baseline else "new",
                     "followers": fol, "weeks_listed": 0})

    path = os.path.join(desk.review_dir, "to_review.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["handle", "source", "followers_at_last_scan", "weeks_listed",
                    "verdict", "label", "sample_post_url", "followers_now", "last_post_date", "note"])
        for r in rows:
            w.writerow([r["handle"], r["source"], r["followers"], r["weeks_listed"], "", "", "", "", "", ""])
    scan = state.get("last_full", {}).get("date", "unknown")
    pool = len(fresh) + len(old)
    count = {}
    for r in rows:
        count[r["source"]] = count.get(r["source"], 0) + 1
    print(path)
    print(", ".join(f"{n} {k}" for k, n in count.items()) +
          f" to review. Eligible new pool: {pool} ({len(fresh)} became mutual since the {baseline or 'unset'} baseline). "
          f"Skipped in the last {cooldown} days and left out: {len(recent_skips)}. Mutual list from the scan of {scan}.")
    lf = state.get("last_full") or {}
    if lf.get("partial"):
        print(f"PARTIAL: Follow Audit's last scan read only the first {(lf.get('read') or {}).get('followers')} "
              f"followers (--limit {lf.get('limit')}), so this list covers only those mutuals, not all of them.")
    if dropped_mutual:
        print("No longer mutual, taken off the list: " + ", ".join("@" + h for h in dropped_mutual))


def cmd_week(desk, review_path):
    cfg = desk.cfg
    state, accounts = desk.fw_accounts()
    idx = handle_index(accounts)
    shout_ids, shout_handles = desk.shouted()
    removed_handles = {norm(h) for h in desk.removed()}
    old_queue = desk.queue()
    old_by_id = {q["id"]: q for q in old_queue}
    bench_by_id = {b["id"]: b for b in desk.bench()}
    skips = desk.skips()
    today = today_local(cfg)

    with open(review_path, newline="", encoding="utf-8") as f:
        reviews = list(csv.DictReader(f))

    picked_last_week = [q for q in old_queue
                        if q["id"] in shout_ids or norm(q["username"]) in shout_handles]
    dropped = []
    roll, runners, new = [], [], []
    for r in reviews:
        h = norm(r.get("handle"))
        if not h:
            continue
        i = idx.get(h)
        verdict = (r.get("verdict") or "").strip().lower()
        note = (r.get("note") or "").strip()
        try:
            fol_now = int(str(r.get("followers_now") or "").replace(",", ""))
        except ValueError:
            fol_now = None
        a = accounts.get(i) or {}
        if fol_now is None:
            fol_now = ((a.get("user") or {}).get("public_metrics") or {}).get("followers_count")
        reason = None
        if h in shout_handles or (i and i in shout_ids):
            reason = "already had a shoutout"
        elif h in removed_handles:
            reason = "removed"
        elif verdict != "keep":
            reason = note or "skipped in review"
            if "not reviewed" not in reason.lower():
                skips[h] = today.isoformat()
        elif fol_now is not None and not (cfg["min_followers"] <= fol_now <= cfg["max_followers"]):
            reason = f"now has {fol_now:,} followers"
            skips[h] = today.isoformat()
        source = (r.get("source") or "").strip()
        if reason:
            dropped.append((r.get("handle"), reason, source))
            continue
        skips.pop(h, None)
        item = {"id": i or "h:" + h, "username": r.get("handle").lstrip("@"),
                "followers": fol_now, "label": clean_label(r.get("label") or r.get("art_type") or "", cfg),
                "sample_post": (r.get("sample_post_url") or "").strip(),
                "last_post": (r.get("last_post_date") or "").strip(), "note": note}
        prev = old_by_id.get(item["id"])
        if prev:
            item["added"] = prev["added"]
            item["weeks_listed"] = prev.get("weeks_listed", 1) + 1
            roll.append(item)
        elif item["id"] in bench_by_id:
            item["added"] = today.isoformat()
            item["benched"] = bench_by_id[item["id"]].get("benched", today.isoformat())
            item["weeks_listed"] = 1
            runners.append(item)
        else:
            item["added"] = today.isoformat()
            item["weeks_listed"] = 1
            new.append(item)

    roll.sort(key=lambda x: x["added"])
    runners.sort(key=lambda x: x.get("benched", ""))
    ordered = roll + runners + new
    week = ordered[:cfg["list_size"]]
    labels = [l.lower() for l in cfg.get("labels") or []]
    if labels:  # sort into the owner's labels, in their order, unlabeled last
        week.sort(key=lambda x: labels.index((x.get("label") or "").lower()) if (x.get("label") or "").lower() in labels else len(labels))
    waiting = ordered[cfg["list_size"]:cfg["list_size"] + cfg.get("runners_up", 10)]
    extra = len(ordered) - len(week) - len(waiting)
    for w_ in waiting:
        w_.setdefault("benched", today.isoformat())
        w_["weeks_listed"] = 0
    write_json(desk.queue_path, week)
    write_json(desk.bench_path, [{"id": w_["id"], "username": w_["username"], "followers": w_["followers"],
                                  "benched": w_["benched"], "weeks_listed": 0} for w_ in waiting])
    write_json(desk.skips_path, skips)

    L = [f"# Shoutout list, week of {today.strftime('%b %d, %Y')}", "",
         "Read-only. Nothing was posted. Pick from these and post the shoutouts yourself.", ""]
    if picked_last_week:
        L += ["Picked from last week's list: " + ", ".join("@" + q["username"] for q in picked_last_week), ""]
    L += [f"## This week ({len(week)})", "",
          ("| # | Account | Followers | Label | Sample | Note |" if labels else "| # | Account | Followers | Sample | Note |"),
          "|---|---|---|---|---|---|" if labels else "|---|---|---|---|---|"]
    for n, it in enumerate(week, 1):
        if it["weeks_listed"] > 1:
            tag = f"week {it['weeks_listed']} on the list"
        elif it.get("benched"):
            tag = "runner-up from last week"
        else:
            tag = "new"
        if it["note"]:
            tag += f". {it['note']}"
        sample = f"[post]({it['sample_post']})" if it["sample_post"] else ""
        fol = f"{it['followers']:,}" if isinstance(it["followers"], int) else ""
        L.append(f"| {n} | [@{it['username']}](https://x.com/{it['username']}) | {fol} | "
                 + (f"{it['label'] or 'no label'} | " if labels else "") + f"{sample} | {tag} |")
    L.append("")
    if len(week) < cfg["list_size"]:
        L += [f"Only {len(week)} qualified this week. Raise review_pool in config.json or wait for new mutuals.", ""]
    if waiting:
        L += [f"## Runners-up ({len(waiting)})", "",
              "They qualified but didn't fit. They come back first next week, right after anyone you didn't pick.", ""]
        L += [f"- [@{w_['username']}](https://x.com/{w_['username']}), "
              f"{w_['followers']:,} followers" + (", " + w_['label'] if w_.get('label') else "") if isinstance(w_["followers"], int)
              else f"- [@{w_['username']}](https://x.com/{w_['username']})" for w_ in waiting] + [""]
        if extra > 0:
            L += [f"{extra} more qualified beyond that and will be reviewed again in a later week.", ""]
    left = [d for d in dropped if d[2] in ("rollover", "runner-up")]
    if left:
        L += ["## Left the list", ""] + [f"- @{h} ({src}): {why}" for h, why, src in left] + [""]
    other = [d for d in dropped if d[2] not in ("rollover", "runner-up")]
    if other:
        L += [f"## Skipped in review ({len(other)})", "",
              f"Skipped accounts aren't reviewed again for {cfg.get('skip_cooldown_days', 28)} days.", ""]
        L += [f"- @{h}: {why}" for h, why, _ in other] + [""]
    log = desk.log()
    L += [f"Shoutout log: {len(log)} shoutouts to {len({norm(r['handle']) for r in log})} accounts. "
          f"Removed for good: {len(removed_handles)}.", "",
          "Anyone you don't shout out this week rolls over. To drop someone, say remove @handle.", ""]
    md = os.path.join(desk.weeks_dir, f"{today.isoformat()}.md")
    with open(md, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    write_html(desk, week, today)
    print(md)


HTML_PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Shoutout List</title>
<style>
:root{--bg:#ffffff;--card:#ffffff;--ink:#000000;--mute:#555555;--line:#cccccc;--acc:#000000;--chip:#f2f2f2}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif}
.wrap{max-width:680px;margin:0 auto;padding:16px}
h1{margin:0 0 2px;font-size:20px}.sub{color:var(--mute);font-size:13px;margin:0 0 14px}
.card{display:grid;grid-template-columns:28px 1fr auto;gap:10px;align-items:center;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px;margin-bottom:8px}
.card.done{opacity:.4}.n{color:var(--mute);font-variant-numeric:tabular-nums;text-align:center}
a.h{color:var(--ink);font-weight:600;text-decoration:none}a.h:hover{color:var(--acc);text-decoration:underline}
.chips{display:flex;gap:6px;flex-wrap:wrap;margin-top:4px}.c{background:var(--chip);border-radius:999px;padding:1px 8px;font-size:12px;color:var(--mute)}.c.a{color:var(--acc)}
a.s{font-size:13px;color:var(--acc);text-decoration:none;display:inline-block;margin-top:4px}
.note{font-size:12px;color:var(--mute);margin-top:2px}
.chk{display:flex;gap:6px;align-items:center;font-size:13px;color:var(--mute)}.chk input{width:18px;height:18px;accent-color:var(--acc)}
</style></head><body><div class="wrap">
<h1>Shoutout list</h1><p class="sub">__SUB__</p><div id="list"></div></div>
<script>
const DATA=__DATA__;const KEY="shoutout-done-__WEEK__";let done={};
try{done=JSON.parse(localStorage.getItem(KEY)||"{}")}catch(e){}
const save=()=>{try{localStorage.setItem(KEY,JSON.stringify(done))}catch(e){}};
const esc=s=>String(s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
function render(){document.getElementById("list").innerHTML=DATA.map((c,i)=>`
<div class="card${done[c.username]?" done":""}"><div class="n">${i+1}</div><div>
<a class="h" href="https://x.com/${encodeURIComponent(c.username)}" target="_blank" rel="noopener">@${esc(c.username)}</a>
<div class="chips">${c.followers!=null?'<span class="c">'+Number(c.followers).toLocaleString()+' followers</span>':""}${c.label?'<span class="c">'+esc(c.label)+'</span>':""}${c.weeks_listed>1?'<span class="c a">week '+c.weeks_listed+'</span>':'<span class="c">new</span>'}</div>
${c.sample_post?'<a class="s" href="'+esc(c.sample_post)+'" target="_blank" rel="noopener">Sample post</a>':""}${c.note?'<div class="note">'+esc(c.note)+'</div>':""}</div>
<label class="chk"><input type="checkbox" data-u="${esc(c.username)}" ${done[c.username]?"checked":""}>done</label></div>`).join("")}
document.getElementById("list").addEventListener("change",e=>{const u=e.target.dataset.u;if(!u)return;if(e.target.checked)done[u]=1;else delete done[u];save();render()});render();
</script></body></html>"""



def check_note():
    """The checkmark sentence for list pages. Hosted lists sync checks through the site,
    otherwise they live in this browser only."""
    try:
        with open(os.path.join(BOTS_HOME, "dispatch", "crew.json"), encoding="utf-8") as f:
            hosted = bool(json.load(f).get("hosting"))
    except Exception:  # noqa
        hosted = False
    return "Checkmarks sync across your devices." if hosted else "Checkmarks stay in this browser only."


def clean_label(raw, cfg):
    """Keep a label only if it is one of the owner's labels. With no labels configured, no label."""
    raw = raw.strip()
    labels = cfg.get("labels") or []
    for l in labels:
        if raw.lower() == l.lower():
            return l
    return ""


def write_html(desk, week, today):
    sub = (f"Week of {today.strftime('%b %d, %Y')}. Mutuals in your follower range who haven't had a shoutout. "
           "Unpicked names roll over to next week. " + check_note())
    data = [{k: it.get(k) for k in ("username", "followers", "label", "sample_post", "weeks_listed", "note")}
            for it in week]
    page = (HTML_PAGE.replace("__SUB__", html.escape(sub)).replace("__WEEK__", today.isoformat())
            .replace("__DATA__", json.dumps(data, ensure_ascii=False).replace("</", "<\\/")))
    with open(os.path.join(desk.weeks_dir, "shoutout_list.html"), "w", encoding="utf-8") as f:
        f.write(page)


def cmd_seed_skips(desk, review_path):
    skips = desk.skips()
    today = today_local(desk.cfg).isoformat()
    n = 0
    with open(review_path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            h = norm(r.get("handle"))
            if h and (r.get("verdict") or "").strip().lower() == "skip" \
                    and "not reviewed" not in (r.get("note") or "").lower():
                skips[h] = today
                n += 1
    write_json(desk.skips_path, skips)
    print(f"Started the {desk.cfg.get('skip_cooldown_days', 28)}-day rest for {n} skipped accounts. "
          f"{len(skips)} accounts are resting.")


def cmd_remove(desk, handles, restore=False):
    removed = desk.removed()
    queue = desk.queue()
    today = today_local(desk.cfg).isoformat()
    for h in handles:
        h = norm(h)
        if restore:
            removed.pop(h, None)
        else:
            removed[h] = today
    if not restore:
        gone = {norm(h) for h in handles}
        queue = [q for q in queue if norm(q["username"]) not in gone]
        write_json(desk.queue_path, queue)
        write_json(desk.bench_path, [b for b in desk.bench() if norm(b["username"]) not in gone])
    write_json(desk.removed_path, removed)
    verb = "Restored" if restore else "Removed for good"
    print(f"{verb}: " + ", ".join("@" + norm(h) for h in handles) + f". List now has {len(queue)} names.")


def cmd_status(desk):
    log = desk.log()
    q = desk.queue()
    print(f"Shoutout log: {len(log)} shoutouts to {len({norm(r['handle']) for r in log})} accounts.")
    if log:
        print(f"Most recent: @{log[-1]['handle']} on {log[-1]['date']}")
    print(f"Removed for good: {len(desk.removed())}")
    print(f"Current list ({len(q)}): " + ", ".join("@" + x["username"] for x in q))
    b = desk.bench()
    print(f"Runners-up ({len(b)}): " + ", ".join("@" + x["username"] for x in b))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Shoutout log and weekly candidate list.")
    ap.add_argument("command", choices=["log-add", "seed-skips", "candidates", "week", "remove", "restore", "status"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--dir", default=os.environ.get("SD_DIR", BOTS_HOME + "/shoutouts"))
    a = ap.parse_args(argv)
    desk = Desk(a.dir)
    if a.command == "log-add":
        if not a.args:
            raise SystemExit("log-add needs a CSV file with date,handle,post_url")
        cmd_log_add(desk, a.args[0])
    elif a.command == "seed-skips":
        if not a.args:
            raise SystemExit("seed-skips needs a filled-in review CSV")
        cmd_seed_skips(desk, a.args[0])
    elif a.command == "candidates":
        cmd_candidates(desk)
    elif a.command == "week":
        cmd_week(desk, a.args[0] if a.args else os.path.join(desk.review_dir, "to_review.csv"))
    elif a.command in ("remove", "restore"):
        if not a.args:
            raise SystemExit(f"{a.command} needs at least one handle")
        cmd_remove(desk, a.args, restore=a.command == "restore")
    else:
        cmd_status(desk)


if __name__ == "__main__":
    main()
