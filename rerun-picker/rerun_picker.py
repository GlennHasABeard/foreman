#!/usr/bin/env python3
"""
rerun_picker.py
Finds your best older media posts that are due for a quote-post rerun.

Commands
  pull            Read your timeline. The first run backfills as far as X allows
                  (up to your last 3,200 posts). Later runs read only what's new.
  pick            No API calls. Scores your media posts against your typical
                  posts from the same month, skips anything you've quoted or
                  reposted recently, and writes picks/picks_<date>.csv plus a report.
  render FILE     No API calls. Builds reruns.html from a picks CSV after the Bot
                  has filled in the angle and draft columns.
  status          Counts and the last pull.

How a post is judged
  ratio  = its impressions divided by the median impressions of your original
           posts in the 30 days around it. 3.0x means three times your normal.
  It must be an original post with an image or video, at least 21 days old, not
  quoted or reposted by you in the last 60 days, not shown as a pick in the last
  56 days, and free of sponsor or affiliate markers.

Read-only. GET requests only. Uses the crew's one shared sign-in
($BOTS_HOME/dispatch/x_signin.json, owned by Dispatch). Run with CREW_BOT="Rerun Picker".
A pull a cap stops says what it didn't read, and the next pull fills the gap.
Data lives in /workspace/reruns (override with --dir or RR_DIR).
"""

import argparse
import csv
import html
import json
import os
import statistics
import sys
from datetime import datetime, timedelta, timezone

class CapReached(Exception):
    """Replaced by follow_watch.CapReached once the shared client is loaded."""


# Where the bots live. Foreman sets BOTS_HOME for each bot. On Grok Bot that is /workspace.
BOTS_HOME = os.environ.get("BOTS_HOME", "/workspace").rstrip("/")

_PRICES = None


def P():
    """The crew's shared price table (x_prices.py, next to follow_watch.py)."""
    global _PRICES
    if _PRICES is None:
        here = os.path.dirname(os.path.abspath(__file__))
        for d in (os.environ.get("FW_DIR"), os.path.join(BOTS_HOME, "follow-watch"),
                  os.path.join(here, "..", "follow-audit"), os.path.join(here, "..", "follow-watch")):
            if d and os.path.exists(os.path.join(d, "x_prices.py")):
                if d not in sys.path:
                    sys.path.insert(0, d)
                import x_prices
                _PRICES = x_prices
                break
        else:
            raise SystemExit("x_prices.py not found. It ships next to follow_watch.py in the Follow Audit folder.")
    return _PRICES


DEFAULT_CONFIG = {
    "follow_watch_dir": BOTS_HOME + "/follow-watch",
    "picks": None,
    "min_age_days": None,
    "rerun_cooldown_days": 60,
    "repick_after_days": 56,
    "min_ratio": None,
    "median_window_days": 30,
    "media_only": None,
    "skip_media_types": None,
    "skip_terms": None,
    "max_cost_per_pull": None,
    "timezone": None,
}

TWEET_FIELDS = "created_at,public_metrics,referenced_tweets,attachments,conversation_id"

OPTIONAL_NONE = set()

def check_config(cfg, where):
    """Every setting left as None must come from the user's own config.json, written by Foreman."""
    missing = sorted(k for k, v in cfg.items() if v is None and k not in OPTIONAL_NONE)
    if missing:
        raise SystemExit(f"{where} is missing settings: {', '.join(missing)}. Run Foreman setup or add them to config.json.")
    return cfg


def now_utc():
    return datetime.now(timezone.utc)


def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def read_json(path, default):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return default


def write_json(path, obj, pretty=False):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1 if pretty else None)
    os.replace(tmp, path)


def local_now(cfg):
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo(cfg["timezone"]))
    except Exception:
        return datetime.now()


class Store:
    def __init__(self, root):
        self.root = root
        self.picks_dir = os.path.join(root, "picks")
        os.makedirs(self.picks_dir, exist_ok=True)
        self.cfg_path = os.path.join(root, "config.json")
        self.cfg = dict(DEFAULT_CONFIG)
        if os.path.exists(self.cfg_path):
            self.cfg.update(read_json(self.cfg_path, {}))
        else:
            raise SystemExit(f"No config.json in {root}. Run Foreman setup first.")
        check_config(self.cfg, 'Rerun Picker config')
        self.posts_path = os.path.join(root, "posts.json")
        self.state_path = os.path.join(root, "state.json")
        self.shown_path = os.path.join(root, "shown.json")

    def posts(self):
        return read_json(self.posts_path, {})

    def state(self):
        return read_json(self.state_path, {})

    def shown(self):
        return read_json(self.shown_path, {})


def load_fw(cfg):
    d = cfg["follow_watch_dir"]
    if not os.path.exists(os.path.join(d, "follow_watch.py")):
        raise SystemExit(f"follow_watch.py not found in {d}.")
    sys.path.insert(0, d)
    import follow_watch as fw  # noqa: E402
    return fw


def ref(t, kind):
    for r in t.get("referenced_tweets") or []:
        if r.get("type") == kind:
            return r.get("id")
    return None


# ----------------------------------------------------------------------------

def cmd_pull(st, client, days=None):
    """Reads new posts first, then any gap an earlier capped pull left (with until_id), so
    'the rest come next pull' is true. A cap stop always says what wasn't read."""
    cfg = st.cfg
    state = st.state()
    posts = st.posts()
    me = client.me()
    my_id = me["id"]
    state["me"] = {"id": my_id, "username": me["username"]}
    read = 1
    requests = 1
    capped = False
    crew_cap = None
    not_read = []
    base = {"max_results": 100, "tweet.fields": TWEET_FIELDS,
            "expansions": "attachments.media_keys", "media.fields": "type"}

    def read_timeline(extra):
        """Newest first. Returns (newest id, oldest id, finished)."""
        nonlocal read, requests, capped, crew_cap
        token, hi, lo = None, None, None
        while True:
            if read * P().RATES["owned"] >= cfg["max_cost_per_pull"]:
                capped = True
                return hi, lo, False
            p = {**base, **extra}
            if token:
                p["pagination_token"] = token
            try:
                body = client.get(f"/users/{my_id}/tweets", p)
            except CapReached as e:
                capped, crew_cap = True, e
                return hi, lo, False
            requests += 1
            data = body.get("data", []) or []
            read += len(data)
            media = {m["media_key"]: m.get("type") for m in (body.get("includes") or {}).get("media", []) or []}
            for t in data:
                keys = (t.get("attachments") or {}).get("media_keys") or []
                types = sorted({media.get(k, "media") for k in keys})
                if ref(t, "retweeted"):
                    kind = "repost"
                elif ref(t, "replied_to"):
                    kind = "reply"
                elif ref(t, "quoted"):
                    kind = "quote"
                else:
                    kind = "original"
                posts[t["id"]] = {"created": t.get("created_at"), "kind": kind, "text": (t.get("text") or "")[:280],
                                  "media": types, "media_keys": keys, "metrics": t.get("public_metrics") or {},
                                  "quoted": ref(t, "quoted"), "reposted": ref(t, "retweeted"),
                                  "metrics_at": iso(now_utc()),
                                  "settled": bool(t.get("created_at")) and (now_utc() - ts(t["created_at"])).days >= 7}
                if hi is None or int(t["id"]) > int(hi):
                    hi = t["id"]
                if lo is None or int(t["id"]) < int(lo):
                    lo = t["id"]
            token = (body.get("meta") or {}).get("next_token")
            if not token or not data:
                return hi, lo, True

    # 1. what's new
    if days:
        # re-read the last N days in full, e.g. to fill in media ids on posts read before they were saved
        extra = {"start_time": iso(now_utc() - timedelta(days=days))}
    else:
        extra = {"since_id": state["since_id"]} if state.get("since_id") else {}
    hi, lo, done = read_timeline(extra)
    old_since = state.get("since_id")
    if hi and (old_since is None or int(hi) > int(old_since)):
        state["since_id"] = hi
    gaps = state.pop("gaps", None) or ([state.pop("gap")] if state.get("gap") else [])
    if not done and not days:
        if lo:
            # posts older than lo and newer than the old since_id are still unread: remember the gap
            gaps.append({"since_id": old_since, "until_id": lo})
            not_read.append("older posts in this window")
        else:
            not_read.append("new posts")  # since_id didn't move, so the next pull starts from the same place
    # 2. fill gaps earlier capped pulls left, newest gap first
    left = []
    for gap in sorted(gaps, key=lambda g: -int(g.get("until_id") or 0)):
        if capped:
            left.append(gap)
            continue
        _, glo, gdone = read_timeline({k: v for k, v in gap.items() if v})
        if not gdone:
            if glo:
                gap["until_id"] = glo
            left.append(gap)
    if left:
        state["gaps"] = left
        if "older posts in this window" not in not_read:
            not_read.append("older posts left from an earlier capped pull")
    # 3. refresh counts once a post is a week old, so early reads don't undercount it
    stale = [i for i, x in posts.items()
             if x["kind"] == "original" and x.get("created") and not x.get("settled")
             and (now_utc() - ts(x["created"])).days >= 7]
    refreshed = 0
    for k in range(0, len(stale), 100):
        if capped or (read + len(stale[k:k + 100])) * P().RATES["owned"] > cfg["max_cost_per_pull"]:
            capped = True
            not_read.append("view-count refresh")
            break
        chunk = stale[k:k + 100]
        try:
            body = client.get("/tweets", {"ids": ",".join(chunk), "tweet.fields": "public_metrics"}, owned=True)
        except CapReached as e:
            capped, crew_cap = True, e
            not_read.append("view-count refresh")
            break
        requests += 1
        got = body.get("data", []) or []
        read += len(got)
        for t in got:
            posts[t["id"]]["metrics"] = t.get("public_metrics") or posts[t["id"]]["metrics"]
            posts[t["id"]]["metrics_at"] = iso(now_utc())
            posts[t["id"]]["settled"] = True
            refreshed += 1
        for i in chunk:
            posts[i]["settled"] = True  # deleted posts come back missing, don't retry them
    state["last_pull"] = iso(now_utc())
    state["last_pull_not_read"] = not_read
    state.setdefault("first_pull", state["last_pull"])
    write_json(st.state_path, state, pretty=True)
    write_json(st.posts_path, posts)
    oldest = min((p["created"] for p in posts.values() if p.get("created")), default=None)
    cost = read * P().RATES["owned"]
    # read and requests start at 1 for the account check, which is not a post
    print(f"Read {read - 1:,} posts in {requests - 1} timeline requests, plus the account check, about ${cost:.2f}.")
    if not_read:
        which = "the crew's daily cap" if crew_cap else "this pull's cost cap"
        print(f"{client.who} stopped before {not_read[0]}, cap reached ({which}). Not read this pull: "
              f"{', '.join(not_read)}. They come next pull." + (f" {crew_cap}" if crew_cap else ""))
    print(f"History on hand: {len(posts):,} posts" + (f", back to {oldest[:10]}." if oldest else ".")
          + (f" Refreshed view counts on {refreshed} posts that just turned a week old."
             if "view-count refresh" not in not_read else
             f" Refreshed view counts on {refreshed} of {len(stale)} posts due; the rest wait for the cap."))


def median_for(created, originals, window_days):
    lo, hi = created - timedelta(days=window_days / 2), created + timedelta(days=window_days / 2)
    vals = [p["metrics"].get("impression_count", 0) for p in originals if lo <= ts(p["created"]) <= hi]
    vals = [v for v in vals if v]
    return statistics.median(vals) if len(vals) >= 5 else None


def cmd_pick(st):
    cfg = st.cfg
    state = st.state()
    if not state.get("last_pull"):
        raise SystemExit("No pull yet. Run `rerun_picker.py pull` first.")
    posts = st.posts()
    shown = st.shown()
    me = state["me"]["username"]
    if state.get("last_pull_not_read") or state.get("gaps"):
        print(f"Note: the last pull stopped before {(state.get('last_pull_not_read') or ['older posts'])[0]}, "
              "cap reached, so some posts aren't in the history yet. Picks come from what is on hand.")
    now = now_utc()
    lt = local_now(cfg)
    today = lt.date()

    last_rerun = {}
    for p in posts.values():
        target = p.get("quoted") or p.get("reposted")
        if target and target in posts:
            if target not in last_rerun or p["created"] > last_rerun[target]:
                last_rerun[target] = p["created"]

    originals = [dict(p, id=i) for i, p in posts.items() if p["kind"] == "original" and p.get("created")]
    if not any(p["metrics"].get("impression_count") for p in originals):
        raise SystemExit("No view counts in the data. X didn't return impression_count, so posts can't be scored.")

    cands, dropped = [], {}

    def drop(why):
        dropped[why] = dropped.get(why, 0) + 1

    for p in originals:
        created = ts(p["created"])
        if (now - created).days < cfg["min_age_days"]:
            continue
        if set(p["media"] or ["text"]) & set(cfg["skip_media_types"]):
            continue
        if cfg["media_only"] and not p["media"]:
            continue
        text = (p.get("text") or "").lower()
        if any(t.lower() in text for t in cfg["skip_terms"]):
            drop("sponsor or affiliate post")
            continue
        lr = last_rerun.get(p["id"])
        if lr and (now - ts(lr)).days < cfg["rerun_cooldown_days"]:
            drop(f"you quoted or reposted it in the last {cfg['rerun_cooldown_days']} days")
            continue
        sh = shown.get(p["id"])
        if sh and (today - datetime.fromisoformat(sh).date()).days < cfg["repick_after_days"]:
            drop("picked recently")
            continue
        med = median_for(created, originals, cfg["median_window_days"])
        imp = p["metrics"].get("impression_count", 0) or 0
        if not med or not imp:
            drop("not enough posts around it to compare")
            continue
        ratio = imp / med
        if ratio < cfg["min_ratio"]:
            continue
        m = p["metrics"]
        eng = (m.get("like_count", 0) + 2 * m.get("retweet_count", 0) + 3 * m.get("quote_count", 0)
               + 2 * m.get("bookmark_count", 0) + m.get("reply_count", 0))
        cands.append({**p, "ratio": ratio, "median": med, "imp": imp, "eng_rate": eng / imp if imp else 0,
                      "last_rerun": lr})
    cands.sort(key=lambda c: (-c["ratio"], -c["eng_rate"]))
    picks = cands[:cfg["picks"]]
    for c in picks:
        shown[c["id"]] = today.isoformat()
    write_json(st.shown_path, shown, pretty=True)

    path = os.path.join(st.picks_dir, f"picks_{today.isoformat()}.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["post_url", "date", "format", "impressions", "vs_typical", "likes", "reposts", "quotes",
                    "bookmarks", "last_rerun", "text", "angle", "draft"])
        for c in picks:
            m = c["metrics"]
            w.writerow([f"https://x.com/{me}/status/{c['id']}", c["created"][:10], "/".join(c["media"]),
                        c["imp"], f"{c['ratio']:.1f}x", m.get("like_count", 0), m.get("retweet_count", 0),
                        m.get("quote_count", 0), m.get("bookmark_count", 0),
                        (c["last_rerun"] or "never")[:10], c["text"].replace("\n", " "), "", ""])

    span = sorted(p["created"] for p in originals)
    L = [f"# Rerun picks, week of {today.strftime('%b %d, %Y')}", "",
         "Your strongest media posts that are due for a quote-post rerun. Read-only. You post the reruns.", "",
         f"Scored {len(originals):,} original posts from {span[0][:10]} to {span[-1][:10]}. "
         f"{len(cands)} cleared {cfg['min_ratio']}x your typical views for their month.", "",
         "| # | Post | Date | Format | Views | vs typical | Last rerun |", "|---|---|---|---|---|---|---|"]
    for n, c in enumerate(picks, 1):
        L.append(f"| {n} | [{c['text'][:50].replace('|', '/').replace(chr(10), ' ') or 'post'}]"
                 f"(https://x.com/{me}/status/{c['id']}) | {c['created'][:10]} | {'/'.join(c['media'])} | "
                 f"{c['imp']:,} | {c['ratio']:.1f}x | {(c['last_rerun'] or 'never')[:10]} |")
    L.append("")
    if dropped:
        L += ["Left out: " + ", ".join(f"{n} {why}" for why, n in sorted(dropped.items(), key=lambda x: -x[1])) + ".", ""]
    L += [f"Picks file for angles and drafts: {path}", ""]
    md = os.path.join(st.picks_dir, f"picks_{today.isoformat()}.md")
    with open(md, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    print(md)
    print(path)


PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Rerun Picks</title>
<style>
:root{--bg:#ffffff;--card:#ffffff;--ink:#000000;--mute:#555555;--line:#cccccc;--acc:#000000;--chip:#f2f2f2;--draft:#ffffff}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif}
.wrap{max-width:720px;margin:0 auto;padding:16px}h1{margin:0 0 2px;font-size:20px}.sub{color:var(--mute);font-size:13px;margin:0 0 14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px;margin-bottom:10px}.card.done{opacity:.4}
.top{display:flex;justify-content:space-between;gap:10px;align-items:flex-start}
.n{font-weight:600}.chips{display:flex;gap:6px;flex-wrap:wrap;margin-top:6px}.c{background:var(--chip);border-radius:999px;padding:1px 8px;font-size:12px;color:var(--mute)}.c.a{color:var(--acc)}
.orig{font-size:14px;color:var(--mute);margin:10px 0 0}
.angle{font-size:14px;margin:10px 0 0}.angle b{color:var(--acc);font-weight:600}
.draft{background:var(--draft);border:1px solid var(--line);border-radius:8px;padding:10px;margin-top:8px;font-size:14px;white-space:pre-wrap}
.row{display:flex;gap:14px;align-items:center;margin-top:8px}
.row a,.row button{font-size:13px;color:var(--acc);text-decoration:none;background:none;border:0;padding:0;cursor:pointer;font:inherit;font-size:13px}
.chk{display:flex;gap:6px;align-items:center;font-size:13px;color:var(--mute);white-space:nowrap}.chk input{width:18px;height:18px;accent-color:var(--acc)}
</style></head><body><div class="wrap"><h1>Rerun picks</h1><p class="sub">__SUB__</p><div id="list"></div></div>
<script>
const DATA=__DATA__;const KEY="__KEY__";let done={};
try{done=JSON.parse(localStorage.getItem(KEY)||"{}")}catch(e){}
const save=()=>{try{localStorage.setItem(KEY,JSON.stringify(done))}catch(e){}};
const esc=s=>String(s==null?"":s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
function render(){document.getElementById("list").innerHTML=DATA.map((d,i)=>`
<div class="card${done[d.url]?" done":""}"><div class="top"><div><span class="n">${i+1}. ${esc(d.date)}</span>
<div class="chips"><span class="c a">${esc(d.ratio)} typical views</span><span class="c">${Number(d.views).toLocaleString()} views</span><span class="c">${esc(d.format)}</span><span class="c">last rerun: ${esc(d.last)}</span></div></div>
<label class="chk"><input type="checkbox" data-k="${esc(d.url)}" ${done[d.url]?"checked":""}>posted</label></div>
<div class="orig">${esc(d.text)}</div>
${d.angle?'<div class="angle"><b>Angle:</b> '+esc(d.angle)+'</div>':""}
${d.draft?'<div class="draft">'+esc(d.draft)+'</div>':""}
<div class="row"><a href="${esc(d.url)}" target="_blank" rel="noopener">Open post to quote</a>${d.draft?'<button data-copy="'+i+'">Copy draft</button>':""}</div></div>`).join("")}
document.getElementById("list").addEventListener("change",e=>{const k=e.target.dataset.k;if(!k)return;if(e.target.checked)done[k]=1;else delete done[k];save();render()});
document.getElementById("list").addEventListener("click",e=>{const i=e.target.dataset.copy;if(i==null)return;
const t=DATA[+i].draft;const ok=()=>{e.target.textContent="Copied";setTimeout(()=>e.target.textContent="Copy draft",1500)};
if(navigator.clipboard)navigator.clipboard.writeText(t).then(ok,()=>{});});
render();
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


def cmd_render(st, path):
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    data = [{"url": r["post_url"], "date": r["date"], "format": r["format"], "views": int(r["impressions"] or 0),
             "ratio": r["vs_typical"], "last": r["last_rerun"], "text": r["text"],
             "angle": (r.get("angle") or "").strip(), "draft": (r.get("draft") or "").strip()} for r in rows]
    lt = local_now(st.cfg)
    sub = (f"{len(data)} picks, {lt.strftime('%b %d, %Y')}. Open the post, quote it with the draft or your own "
           "take, then tick it. " + check_note())
    page = (PAGE.replace("__SUB__", html.escape(sub)).replace("__KEY__", "reruns-" + os.path.basename(path))
            .replace("__DATA__", json.dumps(data, ensure_ascii=False).replace("</", "<\\/")))
    out = os.path.join(st.picks_dir, "reruns.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(page)
    missing = sum(1 for d in data if not d["draft"])
    print(out)
    if missing:
        print(f"{missing} picks have no draft yet.")


def cmd_status(st):
    s, p = st.state(), st.posts()
    kinds = {}
    for x in p.values():
        kinds[x["kind"]] = kinds.get(x["kind"], 0) + 1
    print(f"Last pull: {s.get('last_pull', 'never')}. Posts: {len(p):,} (" +
          ", ".join(f"{k} {n}" for k, n in sorted(kinds.items())) + ")")
    print(f"Shown as picks so far: {len(st.shown())}")
    if s.get("last_pull_not_read"):
        print(f"Last pull stopped before {s['last_pull_not_read'][0]}, cap reached. "
              f"Not read: {', '.join(s['last_pull_not_read'])}.")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Find your best older media posts for quote-post reruns.")
    ap.add_argument("command", choices=["pull", "pick", "render", "status"])
    ap.add_argument("file", nargs="?")
    ap.add_argument("--days", type=int, help="pull: re-read the last N days in full instead of only new posts")
    ap.add_argument("--dir", default=os.environ.get("RR_DIR", BOTS_HOME + "/reruns"))
    a = ap.parse_args(argv)
    st = Store(a.dir)
    if a.command == "pull":
        fw = load_fw(st.cfg)
        fws = fw.Store(st.cfg["follow_watch_dir"])
        fwc = fws.load_config()
        client = fw.XClient(fws, fwc, fw.Meter({**fwc, "max_resources_per_run": 10 ** 9}))
        global CapReached
        CapReached = fw.CapReached
        try:
            cmd_pull(st, client, a.days)
        except fw.CapReached as e:  # stopped at the account check: nothing was read or saved
            print(f"{client.who} stopped before {e.label}, cap reached. Nothing was read or saved this pull. {e}")
            sys.exit(3)
    elif a.command == "pick":
        cmd_pick(st)
    elif a.command == "render":
        if not a.file:
            raise SystemExit("render needs a picks CSV")
        cmd_render(st, a.file)
    else:
        cmd_status(st)


if __name__ == "__main__":
    main()
