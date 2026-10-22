#!/usr/bin/env python3
"""
engagement.py
Read-only engagement tracker shared by two Grok Bots: Reply Queue and Fan Finder.

Commands
  auth        One-time sign-in that adds like.read to the Follow Audit token, so
              the script can see who liked your posts. Still read-only.
  pull        Read what's new since the last pull: your posts and replies, posts
              that mention you, quotes of your recent posts, and who liked your
              posts once they're a day old. Writes a cost report.
  pull --trial  Same, with tighter caps, for a first look at the cost.
  radar       No API calls. Lists replies, mentions and quotes from the last 72
              hours that you haven't replied to. Verified mutuals first.
  leads       No API calls. Lists verified accounts that liked, replied to or
              quoted your posts in the last 14 days and don't follow you.
  status      Counts and the last pull.

  radar and leads accept --pull-if-stale HOURS to pull first when the last pull
  is older than that.

What it never does
  No follow, like, repost, reply, post, DM, block or mute. GET requests only,
  plus the OAuth token exchange. Uses the Follow Audit sign-in.

Data lives in /workspace/engagement (override with --dir or EN_DIR).
Needs follow_watch.py in /workspace/follow-watch.
"""

import argparse
import csv
import html
import json
import os
import sys
from datetime import datetime, timedelta, timezone

# Where the bots live. Foreman sets BOTS_HOME for each bot. On Grok Bot that is /workspace.
BOTS_HOME = os.environ.get("BOTS_HOME", "/workspace").rstrip("/")

DEFAULT_CONFIG = {
    "follow_watch_dir": BOTS_HOME + "/follow-watch",
    "first_pull_days": 7,
    "keep_days": 30,
    "quote_check_hours": 72,
    "quote_recheck_hours": 10,
    "likers_after_hours": 24,
    "likers_before_days": 7,
    "max_liker_posts_per_run": 15,
    "max_likers_per_post": 100,
    "check_my_likes": True,
    "my_likes_max_per_pull": 400,
    "radar_hide_liked": True,
    "cap_basis": "low",
    "skip_handles": [],
    "max_cost_per_run": None,
    "trial_max_cost": None,
    "trial_max_liker_posts": 5,
    "radar_hours": 72,
    "radar_show": 40,
    "leads_days": 14,
    "leads_show": 20,
    "leads_verified_only": None,
    "leads_min_points": 2,
    "leads_min_followers": None,
    "leads_resurface_days": 21,
    "price_owned": 0.001,
    "price_post": 0.005,
    "price_like": 0.001,
    "price_user": 0.010,
    "liker_price_confirmed": None,
    "exclude_terms": None,
    "timezone": None,
}

TWEET_FIELDS = "created_at,public_metrics,conversation_id,referenced_tweets,in_reply_to_user_id,author_id,lang"

OPTIONAL_NONE = {"liker_price_confirmed"}

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


def write_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)
    os.replace(tmp, path)


def money(x):
    return f"${x:,.2f}"


class Store:
    def __init__(self, root):
        self.root = root
        self.reports = os.path.join(root, "reports")
        os.makedirs(self.reports, exist_ok=True)
        self.p = {k: os.path.join(root, f"{k}.json") for k in
                  ("config", "state", "posts", "events", "users", "runs", "shown_leads", "my_likes")}
        self.cfg = dict(DEFAULT_CONFIG)
        if os.path.exists(self.p["config"]):
            self.cfg.update(read_json(self.p["config"], {}))
        else:
            raise SystemExit(f"No config.json in {root}. Run Foreman setup first.")
        check_config(self.cfg, 'Reply Queue / Fan Finder config')

    def load(self, k, default):
        return read_json(self.p[k], default)

    def save(self, k, obj):
        write_json(self.p[k], obj)


def load_fw(cfg):
    d = cfg["follow_watch_dir"]
    if not os.path.exists(os.path.join(d, "follow_watch.py")):
        raise SystemExit(f"follow_watch.py not found in {d}.")
    sys.path.insert(0, d)
    import follow_watch as fw  # noqa: E402
    return fw


def local_now(cfg):
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo(cfg["timezone"]))
    except Exception:
        return datetime.now()


# ----------------------------------------------------------------------------
# Spend meter
# ----------------------------------------------------------------------------

class Spend:
    def __init__(self, cfg, cap):
        self.cfg, self.cap = cfg, cap
        self.owned = self.quotes = self.likers = self.users = self.requests = 0

    def low(self):
        c = self.cfg
        lp = c["liker_price_confirmed"] if c.get("liker_price_confirmed") is not None else c["price_like"]
        return self.owned * c["price_owned"] + self.quotes * c["price_post"] + self.likers * lp

    def liker_price(self):
        c = self.cfg
        return c["liker_price_confirmed"] if c.get("liker_price_confirmed") is not None else c["price_user"]

    def high(self):
        c = self.cfg
        return (self.owned * c["price_owned"] + self.quotes * c["price_post"]
                + self.likers * self.liker_price() + self.users * c["price_user"])

    def basis(self):
        """What the cap is checked against. X has billed at the low estimate so far
        (cost report, Oct 20), so the high estimate stopped pulls far too early."""
        return self.low() if self.cfg.get("cap_basis", "low") == "low" else self.high()

    def room(self, worst):
        return self.basis() + worst <= self.cap


# ----------------------------------------------------------------------------
# Pull
# ----------------------------------------------------------------------------

def user_fields(fw):
    return fw.USER_FIELDS + ",connection_status"


def slim_user(fw, u):
    s = fw.slim(u)
    if "connection_status" in u:
        s["connection_status"] = u["connection_status"]
    s["seen"] = iso(now_utc())
    return s


def paged(client, spend, path, params, kind, max_items=10 ** 9, worst_each=0.0, stop_ids=None):
    """Generic paged GET. kind decides which meter bucket counts the results.
    stop_ids: stop after a page that contains any of these ids (newest-first lists)."""
    out, users, token = [], {}, None
    while len(out) < max_items:
        if spend.basis() >= spend.cap:
            return out, users, True
        p = dict(params)
        if token:
            p["pagination_token"] = token
        body = client.get(path, p)
        spend.requests += 1
        data = body.get("data", []) or []
        inc = (body.get("includes") or {}).get("users", []) or []
        setattr(spend, kind, getattr(spend, kind) + len(data))
        spend.users += len(inc)
        out += data
        for u in inc:
            users[u["id"]] = u
        token = (body.get("meta") or {}).get("next_token")
        if not token or not data:
            break
        if stop_ids and any(d.get("id") in stop_ids for d in data):
            break
    return out, users, False


def ref(t, kind):
    for r in t.get("referenced_tweets") or []:
        if r.get("type") == kind:
            return r.get("id")
    return None


def cmd_pull(st, fw, client, trial=False):
    cfg = st.cfg
    started = now_utc()
    spend = Spend(cfg, cfg["trial_max_cost"] if trial else cfg["max_cost_per_run"])
    state = st.load("state", {})
    posts = st.load("posts", {})
    events = st.load("events", {})
    users = st.load("users", {})
    notes = []
    stopped = False

    me = client.me()
    spend.owned += 1
    my_id = me["id"]
    state["me"] = {"id": my_id, "username": me["username"]}
    first_start = iso(started - timedelta(days=cfg["first_pull_days"]))

    # 1. my own posts and replies
    params = {"max_results": 100, "tweet.fields": TWEET_FIELDS, "exclude": "retweets"}
    if state.get("own_since"):
        params["since_id"] = state["own_since"]
    else:
        params["start_time"] = first_start
    mine, _, hit = paged(client, spend, f"/users/{my_id}/tweets", params, "owned", worst_each=cfg["price_owned"])
    stopped |= hit
    for t in mine:
        replied = ref(t, "replied_to")
        quoted = ref(t, "quoted")
        kind = "reply" if replied else ("quote" if quoted else "original")
        posts[t["id"]] = {"created": t.get("created_at"), "kind": kind, "text": (t.get("text") or "")[:200],
                          "replied_to": replied, "quoted": quoted,
                          "metrics": t.get("public_metrics") or {},
                          "likers_fetched": posts.get(t["id"], {}).get("likers_fetched", False),
                          "quotes_checked": posts.get(t["id"], {}).get("quotes_checked")}
    if mine:
        state["own_since"] = max(mine, key=lambda t: int(t["id"]))["id"]

    # 2. what I've liked, so the radar can leave out anything I already liked.
    # Reads newest first and stops at the first like it already knows, so each
    # pull only pays for new likes. The saved list keeps growing (trimmed to 5,000).
    if cfg["check_my_likes"] and spend.room(100 * cfg["price_owned"]):
        try:
            known = st.load("my_likes", [])
            liked, _, _ = paged(client, spend, f"/users/{my_id}/liked_tweets",
                                {"max_results": 100, "tweet.fields": "created_at"}, "owned",
                                max_items=cfg["my_likes_max_per_pull"], worst_each=cfg["price_owned"],
                                stop_ids=set(known))
            new = [t["id"] for t in liked if t["id"] not in set(known)]
            st.save("my_likes", (new + known)[:5000])
            if new:
                notes.append(f"Read {len(new)} new likes of yours.")
        except SystemExit as e:
            if "403" not in str(e) and "401" not in str(e):
                raise
            notes.append("X refused reading my likes. Run `engagement.py auth` once to add like.read.")

    # 3. posts that mention me (replies to my posts land here too)
    params = {"max_results": 100, "tweet.fields": TWEET_FIELDS, "expansions": "author_id",
              "user.fields": user_fields(fw)}
    if state.get("mention_since"):
        params["since_id"] = state["mention_since"]
    else:
        params["start_time"] = first_start
    ments, inc, hit = paged(client, spend, f"/users/{my_id}/mentions", params, "owned",
                            worst_each=cfg["price_owned"] + cfg["price_user"])
    stopped |= hit
    if hit:
        notes.append("The cost cap stopped the mentions read early. Some older mentions in this window "
                     "may be missing. Raise max_cost_per_run if this repeats.")
    for u in inc.values():
        users[u["id"]] = slim_user(fw, u)
    for t in ments:
        if t.get("author_id") == my_id:
            continue
        replied = ref(t, "replied_to")
        kind = "reply" if replied and replied in posts else ("quote" if ref(t, "quoted") in posts else "mention")
        events[t["id"]] = {"kind": kind, "author": t.get("author_id"), "created": t.get("created_at"),
                           "text": (t.get("text") or "")[:280], "target": replied or ref(t, "quoted"),
                           "conversation": t.get("conversation_id")}
    if ments:
        state["mention_since"] = max(ments, key=lambda t: int(t["id"]))["id"]

    # 4. quotes of my recent originals
    qcut = started - timedelta(hours=cfg["quote_check_hours"])
    for pid, p in sorted(posts.items(), key=lambda x: x[1]["created"] or "", reverse=True):
        if p["kind"] == "reply" or not p.get("created") or ts(p["created"]) < qcut:
            continue
        last_q = p.get("quotes_checked")
        if last_q and (started - ts(last_q)).total_seconds() < cfg["quote_recheck_hours"] * 3600:
            continue
        if stopped or not spend.room(cfg["price_post"] + cfg["price_user"]):
            stopped = True
            break
        params = {"max_results": 100, "tweet.fields": TWEET_FIELDS, "expansions": "author_id",
                  "user.fields": user_fields(fw)}
        qs, inc, hit = paged(client, spend, f"/tweets/{pid}/quote_tweets", params, "quotes",
                             worst_each=cfg["price_post"] + cfg["price_user"])
        stopped |= hit
        for u in inc.values():
            users[u["id"]] = slim_user(fw, u)
        posts[pid]["quotes_checked"] = iso(started)
        for t in qs:
            if t.get("author_id") == my_id or (t.get("text") or "").startswith("RT @"):
                continue
            events[t["id"]] = {"kind": "quote", "author": t.get("author_id"), "created": t.get("created_at"),
                               "text": (t.get("text") or "")[:280], "target": pid,
                               "conversation": t.get("conversation_id")}

    # 5. who liked my originals once they're a day old
    lo = started - timedelta(days=cfg["likers_before_days"])
    hi = started - timedelta(hours=cfg["likers_after_hours"])
    todo = [pid for pid, p in posts.items()
            if p["kind"] != "reply" and not p.get("likers_fetched") and p.get("created")
            and lo <= ts(p["created"]) <= hi]
    todo.sort(key=lambda pid: posts[pid]["created"], reverse=True)
    limit = cfg["trial_max_liker_posts"] if trial else cfg["max_liker_posts_per_run"]
    likes_ok = True
    batch = todo[:limit]
    if batch and spend.room(len(batch) * cfg["price_owned"]):
        # refresh like counts, the ones saved when the post was new are stale
        body = client.get("/tweets", {"ids": ",".join(batch), "tweet.fields": "public_metrics"})
        spend.requests += 1
        spend.owned += len(body.get("data", []) or [])
        for t in body.get("data", []) or []:
            posts[t["id"]]["metrics"] = t.get("public_metrics") or posts[t["id"]]["metrics"]
    for pid in batch:
        n = min(cfg["max_likers_per_post"], posts[pid]["metrics"].get("like_count", 0) or 0)
        if n == 0:
            posts[pid]["likers_fetched"] = True
            continue
        if stopped or not spend.room(n * spend.liker_price()):
            stopped = True
            break
        try:
            likers, _, hit = paged(client, spend, f"/tweets/{pid}/liking_users",
                                   {"max_results": max(1, min(100, n)), "user.fields": user_fields(fw)}, "likers",
                                   max_items=n, worst_each=spend.liker_price())
        except SystemExit as e:
            if "403" in str(e) or "401" in str(e):
                likes_ok = False
                notes.append("X refused the likes lookup. Run `engagement.py auth` once to add like.read, "
                             "then likes will be included.")
                break
            raise
        stopped |= hit
        for u in likers:
            if u["id"] == my_id:
                continue
            users[u["id"]] = slim_user(fw, u)
            events[f"like:{pid}:{u['id']}"] = {"kind": "like", "author": u["id"], "created": posts[pid]["created"],
                                              "target": pid, "text": ""}
        posts[pid]["likers_fetched"] = True
    if limit and len(todo) > limit and likes_ok:
        notes.append(f"{len(todo) - limit} older posts are still waiting for a likes check. "
                     "They're picked up on the next pulls.")

    # prune
    keep_cut = started - timedelta(days=cfg["keep_days"])
    posts = {k: v for k, v in posts.items() if v.get("created") and ts(v["created"]) >= keep_cut}
    events = {k: v for k, v in events.items() if v.get("created") and ts(v["created"]) >= keep_cut}
    live = {e["author"] for e in events.values()}
    users = {k: v for k, v in users.items() if k in live}

    state["last_pull"] = iso(started)
    st.save("state", state)
    st.save("posts", posts)
    st.save("events", events)
    st.save("users", users)
    runs = st.load("runs", [])
    runs.append({"ts": iso(started), "trial": trial, "requests": spend.requests, "owned": spend.owned,
                 "quotes": spend.quotes, "likers": spend.likers, "users": spend.users,
                 "low": round(spend.low(), 4), "high": round(spend.high(), 4), "capped": stopped})
    st.save("runs", runs[-200:])
    path = write_pull_report(st, spend, stopped, notes, trial, posts, events, started)
    print(path)


def per_day(items, started, days):
    cut = started - timedelta(days=days)
    n = sum(1 for x in items if x and ts(x) >= cut)
    return n / days


def write_pull_report(st, spend, stopped, notes, trial, posts, events, started):
    cfg = st.cfg
    lt = local_now(cfg)
    L = [f"# Engagement pull{' (trial)' if trial else ''}, {lt.strftime('%a %b %d, %Y %I:%M %p')}", "",
         "Read-only run. Nothing was liked, replied to, posted or followed.", ""]
    for n in notes:
        L += [f"> {n}", ""]
    L += ["## Cost", "",
          f"- Requests: {spend.requests}",
          f"- Your own posts and mentions read: {spend.owned:,} at ${cfg['price_owned']:.3f}",
          f"- Quote posts read: {spend.quotes:,} at ${cfg['price_post']:.3f}",
          f"- Likers read: {spend.likers:,} at ${cfg['price_like']:.3f} to ${cfg['price_user']:.3f}",
          f"- Profiles attached to mentions and quotes: {spend.users:,}",
          f"- Estimated cost: {money(spend.low())} to {money(spend.high())}",
          f"- Cap: {money(spend.cap)}, checked before each page, so a run can pass it by one page"
          + (". Reached, some reads were left for the next pull." if stopped else ""),
          "", "The low number assumes likes and attached profiles bill at the like and owned rates. "
          "The high number bills every profile at the full user rate. The X developer console settles it.", ""]

    days = min(cfg["first_pull_days"], 7)
    own = [p["created"] for p in posts.values()]
    orig = [p for p in posts.values() if p["kind"] != "reply"]
    ments = [e["created"] for e in events.values() if e["kind"] in ("reply", "mention")]
    quotes = [e["created"] for e in events.values() if e["kind"] == "quote"]
    liked_posts = [p for p in orig if p.get("likers_fetched")]
    likes_seen = sum(1 for e in events.values() if e["kind"] == "like")
    likers_per_post = likes_seen / len(liked_posts) if liked_posts else \
        (sum(p["metrics"].get("like_count", 0) for p in orig) / len(orig) if orig else 0)
    od, md, qd = per_day(own, started, days), per_day(ments, started, days), per_day(quotes, started, days)
    origd = per_day([p["created"] for p in orig], started, days)
    likesd = origd * min(likers_per_post, cfg["max_likers_per_post"])
    c = cfg
    low = (od + md + 100 * c["check_my_likes"]) * c["price_owned"] + qd * c["price_post"] + likesd * c["price_like"]
    high = (od + md + 100 * c["check_my_likes"]) * c["price_owned"] + qd * (c["price_post"] + c["price_user"]) \
        + likesd * c["price_user"] + md * c["price_user"]
    L += ["## What a daily pull would cost", "",
          f"From the last {days} days: about {od:.0f} posts and replies of yours a day, {origd:.0f} of them "
          f"originals, {md:.0f} replies and mentions a day, {qd:.0f} quotes a day, and about "
          f"{likers_per_post:.0f} likes per original.", "",
          "| | Per day | Per 30 days |", "|---|---|---|",
          f"| With likes (Fan Finder uses them) | {money(low)} to {money(high)} | {money(low * 30)} to {money(high * 30)} |"]
    low_nl = low - likesd * c["price_like"]
    high_nl = high - likesd * c["price_user"]
    L += [f"| Without likes (Reply Queue only) | {money(low_nl)} to {money(high_nl)} | "
          f"{money(low_nl * 30)} to {money(high_nl * 30)} |", ""]
    L += ["## Data on hand", "",
          f"- Your posts: {len(posts):,} ({len(orig):,} originals, {len(liked_posts):,} checked for likes)",
          f"- Replies and mentions: {len(ments):,}",
          f"- Quotes: {len(quotes):,}",
          f"- Likes recorded: {likes_seen:,}", ""]
    path = os.path.join(st.reports, f"pull_{lt.strftime('%Y-%m-%d_%H%M')}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    return path


# ----------------------------------------------------------------------------
# Shared helpers for radar and leads
# ----------------------------------------------------------------------------

def follow_state(u, fw_accounts, uid):
    """Returns (they_follow_me, i_follow_them, source)."""
    cs = u.get("connection_status")
    if cs is not None:
        return "followed_by" in cs, "following" in cs, "live"
    a = fw_accounts.get(uid)
    if a:
        return bool(a.get("follower_now")), bool(a.get("following_now")), "scan"
    return False, False, "scan"


def bad_account(fw, fw_cfg, cfg, u, spam_res, today):
    a = fw.assess(u, today, fw_cfg, spam_res)
    if "likely fake" in a["tags"] or "spam signals" in a["tags"]:
        return "fake or spam signals"
    text = " ".join([u.get("name") or "", u.get("description") or ""]).lower()
    if any(t.lower() in text for t in cfg["exclude_terms"]):
        return "adult or NSFW"
    return None


PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title>
<style>
:root{--bg:#ffffff;--card:#ffffff;--ink:#000000;--mute:#555555;--line:#cccccc;--acc:#000000;--chip:#f2f2f2}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif}
.wrap{max-width:720px;margin:0 auto;padding:16px}h1{margin:0 0 2px;font-size:20px}.sub{color:var(--mute);font-size:13px;margin:0 0 12px}
.tog{display:inline-flex;gap:6px;align-items:center;font-size:13px;border:1px solid var(--line);background:var(--card);padding:6px 10px;border-radius:8px;margin-bottom:12px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px;margin-bottom:8px}.card.done{opacity:.4}
.top{display:flex;justify-content:space-between;gap:10px;align-items:flex-start}
a.h{color:var(--ink);font-weight:600;text-decoration:none}a.h:hover{color:var(--acc);text-decoration:underline}
.chips{display:flex;gap:6px;flex-wrap:wrap;margin-top:4px}.c{background:var(--chip);border-radius:999px;padding:1px 8px;font-size:12px;color:var(--mute)}.c.a{color:var(--acc)}
.txt{font-size:14px;margin:8px 0 4px;white-space:pre-wrap;word-break:break-word}
.links a{font-size:13px;color:var(--acc);text-decoration:none;margin-right:14px}
.chk{display:flex;gap:6px;align-items:center;font-size:13px;color:var(--mute);white-space:nowrap}.chk input{width:18px;height:18px;accent-color:var(--acc)}
.seg{display:flex;gap:6px;flex-wrap:wrap;margin:0 0 8px}.seg:empty{display:none}
.seg button{border:1px solid var(--line);background:var(--card);color:var(--ink);padding:6px 10px;border-radius:8px;font:inherit;font-size:13px;cursor:pointer}
.seg button.on{background:var(--ink);color:var(--bg);border-color:var(--ink)}
.count{color:var(--mute);font-size:13px;margin:0 0 10px}.count:empty{display:none}
</style></head><body><div class="wrap"><h1>__TITLE__</h1><p class="sub">__SUB__</p>
<label class="tog"><input type="checkbox" id="hide"> Hide checked</label>
<div class="seg" id="seg"></div><div class="count" id="count"></div><div id="list"></div></div>
<script>
const DATA=__DATA__;const KEY="__KEY__";let done={};
try{done=JSON.parse(localStorage.getItem(KEY)||"{}")}catch(e){}
const save=()=>{try{localStorage.setItem(KEY,JSON.stringify(done))}catch(e){}};
const esc=s=>String(s==null?"":s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const GROUPS=[];DATA.forEach(d=>{if(d.g&&!GROUPS.includes(d.g))GROUPS.push(d.g)});let grp="";
function chips(){const s=document.getElementById("seg");if(!GROUPS.length){s.innerHTML="";return}
s.innerHTML=[["","All",DATA.length]].concat(GROUPS.map(g=>[g,g,DATA.filter(d=>d.g===g).length]))
.map(([k,l,n])=>`<button data-g="${esc(k)}" class="${k===grp?"on":""}">${esc(l)} (${n})</button>`).join("")}
function render(){const hide=document.getElementById("hide").checked;
const rows=DATA.filter(d=>(!grp||d.g===grp)&&(!hide||!done[d.key]));
const open=DATA.filter(d=>(!grp||d.g===grp)&&!done[d.key]).length;
document.getElementById("count").textContent=GROUPS.length?`${open} not checked in this view`:"";
document.getElementById("list").innerHTML=rows.map(d=>`
<div class="card${done[d.key]?" done":""}"><div class="top"><div>
<a class="h" href="https://x.com/${encodeURIComponent(d.username)}" target="_blank" rel="noopener">@${esc(d.username)}</a>
<div class="chips">${d.chips.map(c=>'<span class="c'+(c.a?' a':'')+'">'+esc(c.t)+'</span>').join("")}</div></div>
<label class="chk"><input type="checkbox" data-k="${esc(d.key)}" ${done[d.key]?"checked":""}>done</label></div>
${d.text?'<div class="txt">'+esc(d.text)+'</div>':""}
<div class="links">${d.links.map(l=>'<a href="'+esc(l.u)+'" target="_blank" rel="noopener">'+esc(l.t)+'</a>').join("")}</div></div>`).join("")}
document.getElementById("list").addEventListener("change",e=>{const k=e.target.dataset.k;if(!k)return;if(e.target.checked)done[k]=1;else delete done[k];save();render()});
document.getElementById("seg").addEventListener("click",e=>{const g=e.target.dataset.g;if(g===undefined)return;grp=g;chips();render()});
document.getElementById("hide").addEventListener("change",render);chips();render();
</script></body></html>"""


def write_page(path, title, sub, key, data):
    page = (PAGE.replace("__TITLE__", html.escape(title)).replace("__SUB__", html.escape(sub))
            .replace("__KEY__", key).replace("__DATA__", json.dumps(data, ensure_ascii=False).replace("</", "<\\/")))
    with open(path, "w", encoding="utf-8") as f:
        f.write(page)


def ago(dt, now):
    h = (now - dt).total_seconds() / 3600
    return f"{h:.0f}h ago" if h < 48 else f"{h / 24:.0f}d ago"


# ----------------------------------------------------------------------------
# Radar
# ----------------------------------------------------------------------------

def cmd_radar(st, fw, fw_store):
    cfg = st.cfg
    state = st.load("state", {})
    if not state.get("last_pull"):
        raise SystemExit("No pull yet. Run `engagement.py pull` first.")
    posts, events, users = st.load("posts", {}), st.load("events", {}), st.load("users", {})
    my_likes = set(st.load("my_likes", []))
    me = state.get("me", {})
    fw_cfg = fw_store.load_config()
    fw_accounts = fw_store.load_state().get("accounts", {})
    spam_res = fw.compile_spam(fw_cfg)
    now = now_utc()
    today = local_now(cfg).date()
    cut = now - timedelta(hours=cfg["radar_hours"])
    answered = {p["replied_to"] for p in posts.values() if p.get("replied_to")} | \
               {p["quoted"] for p in posts.values() if p.get("quoted")}

    items, hidden = [], {}
    skip = {h.lower().lstrip("@") for h in cfg.get("skip_handles", ["grok"])}
    for eid, e in events.items():
        if e["kind"] == "like" or not e.get("created") or ts(e["created"]) < cut:
            continue
        if (e.get("text") or "").startswith("RT @"):
            continue
        if eid in answered:
            continue
        if cfg.get("radar_hide_liked", True) and eid in my_likes:
            hidden["you already liked"] = hidden.get("you already liked", 0) + 1
            continue
        u = users.get(e["author"]) or {}
        if (u.get("username") or "").lower() in skip:
            hidden["from skipped accounts"] = hidden.get("from skipped accounts", 0) + 1
            continue
        why = bad_account(fw, fw_cfg, cfg, u, spam_res, today) if u else None
        if why:
            hidden[why] = hidden.get(why, 0) + 1
            continue
        they, i, src = follow_state(u, fw_accounts, e["author"])
        verified = fw.is_verified(u)
        mutual = they and i
        tier = 0 if (verified and mutual) else 1 if verified else 2 if mutual else 3
        items.append({"id": eid, "e": e, "u": u, "tier": tier, "verified": verified, "mutual": mutual,
                      "liked": eid in my_likes})
    items.sort(key=lambda x: (x["liked"], x["tier"], -ts(x["e"]["created"]).timestamp()))
    shown = items[:cfg["radar_show"]]

    names = ["Verified mutuals", "Verified", "Mutuals", "Everyone else"]
    lt = local_now(cfg)
    L = [f"# Reply Queue, {lt.strftime('%a %b %d, %Y %I:%M %p')}", "",
         f"Replies, mentions and quotes from the last {cfg['radar_hours']} hours that you haven't replied to. "
         "Read-only. You reply yourself.", "",
         f"{len(items)} unanswered. " + ", ".join(f"{names[t]}: {sum(1 for x in items if x['tier'] == t)}"
                                              for t in range(4)) + ".", ""]
    if hidden:
        L += ["Hidden: " + ", ".join(f"{n} {why}" for why, n in hidden.items()) + ".", ""]
    data = []
    for t in range(4):
        group = [x for x in shown if x["tier"] == t and not x["liked"]]
        if not group:
            continue
        L += [f"## {names[t]} ({len(group)})", ""]
        for x in group:
            L.append(radar_line(x, posts, me, now))
        L.append("")
    liked = [x for x in shown if x["liked"]]
    if liked:
        L += [f"## You liked these but didn't reply ({len(liked)})", ""] + \
             [radar_line(x, posts, me, now) for x in liked] + [""]
    if len(items) > len(shown):
        L += [f"{len(items) - len(shown)} more are on the Reply Queue page, with filters for each group.", ""]
    for x in items:
        e, u = x["e"], x["u"]
        chips = [{"t": e["kind"]}, {"t": ago(ts(e["created"]), now)}]
        if x["verified"]:
            chips.append({"t": "verified", "a": True})
        if x["mutual"]:
            chips.append({"t": "mutual", "a": True})
        if x["liked"]:
            chips.append({"t": "you liked it"})
        links = [{"t": "Open and reply", "u": f"https://x.com/{u.get('username', 'i')}/status/{x['id']}"}]
        if e.get("target") and e["target"] in posts:
            links.append({"t": "Your post", "u": f"https://x.com/{me.get('username')}/status/{e['target']}"})
        data.append({"key": x["id"], "username": u.get("username", "unknown"), "chips": chips,
                     "text": e.get("text", ""), "links": links,
                     "g": "You liked these" if x["liked"] else names[x["tier"]]})
    path = os.path.join(st.reports, f"radar_{lt.strftime('%Y-%m-%d_%H%M')}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    write_page(os.path.join(st.reports, "mention_radar.html"), "Reply Queue",
               f"{len(items)} unanswered from the last {cfg['radar_hours']} hours, {lt.strftime('%b %d, %I:%M %p')}. "
               "Verified mutuals first, newest first within each group.", "radar-done", data)
    print(path)


def radar_line(x, posts, me, now):
    e, u = x["e"], x["u"]
    who = u.get("username", "unknown")
    snippet = (e.get("text") or "").replace("\n", " ")
    if len(snippet) > 120:
        snippet = snippet[:117] + "..."
    target = ""
    if e.get("target") and e["target"] in posts:
        target = f", on [your post](https://x.com/{me.get('username')}/status/{e['target']})"
    return (f"- [@{who}](https://x.com/{who}) {e['kind']}, {ago(ts(e['created']), now)}{target}: "
            f"[{snippet or 'open'}](https://x.com/{who}/status/{x['id']})")


# ----------------------------------------------------------------------------
# Leads
# ----------------------------------------------------------------------------

def cmd_leads(st, fw, fw_store):
    cfg = st.cfg
    state = st.load("state", {})
    if not state.get("last_pull"):
        raise SystemExit("No pull yet. Run `engagement.py pull` first.")
    posts, events, users = st.load("posts", {}), st.load("events", {}), st.load("users", {})
    shown = st.load("shown_leads", {})
    me = state.get("me", {})
    fw_cfg = fw_store.load_config()
    fw_accounts = fw_store.load_state().get("accounts", {})
    spam_res = fw.compile_spam(fw_cfg)
    now = now_utc()
    lt = local_now(cfg)
    today = lt.date()
    cut = now - timedelta(days=cfg["leads_days"])
    weights = {"like": 1, "reply": 3, "mention": 2, "quote": 4}

    agg = {}
    for eid, e in events.items():
        if not e.get("created") or ts(e["created"]) < cut or e["author"] == me.get("id"):
            continue
        a = agg.setdefault(e["author"], {"like": 0, "reply": 0, "mention": 0, "quote": 0, "points": 0, "links": []})
        a[e["kind"]] += 1
        a["points"] += weights.get(e["kind"], 1)
        if e["kind"] != "like" and len(a["links"]) < 3:
            a["links"].append(eid)

    leads, dropped = [], {}
    skip = {h.lower().lstrip("@") for h in cfg.get("skip_handles", ["grok"])}
    for uid, a in agg.items():
        u = users.get(uid)
        if not u:
            continue
        if (u.get("username") or "").lower() in skip:
            continue
        they, i, src = follow_state(u, fw_accounts, uid)
        if they:
            continue
        if i:
            dropped["you follow them already"] = dropped.get("you follow them already", 0) + 1
            continue
        if cfg["leads_verified_only"] and not fw.is_verified(u):
            dropped["not verified"] = dropped.get("not verified", 0) + 1
            continue
        fol = (u.get("public_metrics") or {}).get("followers_count", 0) or 0
        if fol < cfg["leads_min_followers"]:
            dropped["under the follower floor"] = dropped.get("under the follower floor", 0) + 1
            continue
        if a["points"] < cfg["leads_min_points"]:
            dropped["engaged only once"] = dropped.get("engaged only once", 0) + 1
            continue
        why = bad_account(fw, fw_cfg, cfg, u, spam_res, today)
        if why:
            dropped[why] = dropped.get(why, 0) + 1
            continue
        prev = shown.get(uid)
        if prev and (today - datetime.fromisoformat(prev["date"]).date()).days < cfg["leads_resurface_days"] \
                and a["points"] < prev["points"] + 3:
            dropped["shown recently"] = dropped.get("shown recently", 0) + 1
            continue
        leads.append({"id": uid, "u": u, "a": a, "fol": fol, "src": src})
    leads.sort(key=lambda x: (-x["a"]["points"], x["fol"]))
    top = leads[:cfg["leads_show"]]
    for x in top:
        shown[x["id"]] = {"username": x["u"].get("username"), "date": today.isoformat(), "points": x["a"]["points"]}
    st.save("shown_leads", shown)

    L = [f"# Fan Finder, {lt.strftime('%a %b %d, %Y')}", "",
         f"Verified accounts that engaged with your posts in the last {cfg['leads_days']} days and don't follow you. "
         "You don't follow them either. Read-only. You follow by hand.", ""]
    if cfg["max_liker_posts_per_run"] == 0:
        L += ["> Likes are turned off (max_liker_posts_per_run is 0), so this list counts replies, "
              "mentions and quotes.", ""]
    elif not any(e["kind"] == "like" for e in events.values()):
        L += ["> No likes in the data yet, so this list only counts replies, mentions and quotes.", ""]
    L += [f"## Leads ({len(top)})", "", "| Account | Followers | Likes | Replies | Quotes | Their posts |",
          "|---|---|---|---|---|---|"]
    data = []
    for x in top:
        u, a = x["u"], x["a"]
        who = u.get("username", "unknown")
        links = ", ".join(f"[{n + 1}](https://x.com/{who}/status/{eid})" for n, eid in enumerate(a["links"]))
        L.append(f"| [@{who}](https://x.com/{who}) | {x['fol']:,} | {a['like']} | {a['reply'] + a['mention']} | "
                 f"{a['quote']} | {links} |")
        chips = [{"t": f"{x['fol']:,} followers"}, {"t": "verified", "a": True}]
        for k, label in (("like", "likes"), ("reply", "replies"), ("quote", "quotes")):
            n = a[k] + (a["mention"] if k == "reply" else 0)
            if n:
                chips.append({"t": f"{n} {label}"})
        data.append({"key": x["id"], "username": who, "chips": chips,
                     "text": (u.get("description") or "")[:200],
                     "links": [{"t": f"Their {events[eid]['kind']}", "u": f"https://x.com/{who}/status/{eid}"}
                               for eid in a["links"]]})
    L.append("")
    if len(leads) > len(top):
        L += [f"{len(leads) - len(top)} more qualified. They show up on later runs.", ""]
    if dropped:
        L += ["Left out: " + ", ".join(f"{n} {why}" for why, n in sorted(dropped.items(), key=lambda x: -x[1])) + ".", ""]
    if top and all(x["src"] == "scan" for x in top):
        L += ["Follow status came from the Follow Audit scan, not live data. "
              "Someone who followed you since then could still show up.", ""]
    path = os.path.join(st.reports, f"leads_{today.isoformat()}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    write_page(os.path.join(st.reports, "warm_leads.html"), "Fan Finder",
               f"{len(top)} verified accounts that engage with your posts but don't follow you, "
               f"{lt.strftime('%b %d')}.", "leads-done-" + today.isoformat(), data)
    print(path)


def cmd_status(st):
    s = st.load("state", {})
    ev = st.load("events", {})
    kinds = {}
    for e in ev.values():
        kinds[e["kind"]] = kinds.get(e["kind"], 0) + 1
    print(f"Last pull: {s.get('last_pull', 'never')}")
    print(f"Posts: {len(st.load('posts', {}))}, events: " + ", ".join(f"{k} {n}" for k, n in kinds.items()))
    runs = st.load("runs", [])
    if runs:
        r = runs[-1]
        print(f"Last run cost: {money(r['low'])} to {money(r['high'])}{' (capped)' if r['capped'] else ''}")


def stale(st, hours):
    lp = st.load("state", {}).get("last_pull")
    return not lp or (now_utc() - ts(lp)).total_seconds() > hours * 3600


def main(argv=None):
    ap = argparse.ArgumentParser(description="Read-only engagement tracker for Reply Queue and Fan Finder.")
    ap.add_argument("command", choices=["auth", "pull", "radar", "leads", "status"])
    ap.add_argument("--trial", action="store_true")
    ap.add_argument("--paste", action="store_true", help="auth: paste the redirect URL instead of listening")
    ap.add_argument("--pull-if-stale", type=float, default=None, metavar="HOURS")
    ap.add_argument("--dir", default=os.environ.get("EN_DIR", BOTS_HOME + "/engagement"))
    a = ap.parse_args(argv)
    st = Store(a.dir)
    if a.command == "status":
        cmd_status(st)
        return
    fw = load_fw(st.cfg)
    fw_store = fw.Store(st.cfg["follow_watch_dir"])
    fw_cfg = fw_store.load_config()

    def client():
        return fw.XClient(fw_store, fw_cfg, fw.Meter({**fw_cfg, "max_resources_per_run": 10 ** 9}))

    if a.command == "auth":
        if "like.read" not in fw.SCOPES:
            fw.SCOPES = fw.SCOPES + " like.read"
        fw.cmd_auth(fw_store, fw_cfg, client(), a.paste)
        return
    if a.command == "pull" or (a.pull_if_stale is not None and stale(st, a.pull_if_stale)):
        cmd_pull(st, fw, client(), trial=a.trial)
        if a.command == "pull":
            return
    if a.command == "radar":
        cmd_radar(st, fw, fw_store)
    elif a.command == "leads":
        cmd_leads(st, fw, fw_store)


if __name__ == "__main__":
    main()
