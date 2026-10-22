#!/usr/bin/env python3
"""
creator_scout.py
Read-only finder for creators in your niche on X.

Commands
  trial     Small, capped run. Reads a few posts per search, builds a shortlist,
            and writes a cost section that projects what a daily run would cost.
  run       Normal run with the limits in config.json.
  verify    Cheap route. Takes a text file of X links found some other way (for
            example Grok Bot's built-in X search), looks up each profile and
            linked post, and applies the same filters. About $0.01 per profile
            and $0.005 per post.
  estimate  No API calls. Reprints the cost projection from the last run.

How it finds people
  1. Runs a few X recent searches (last 7 days) set in config.json (queries). The authors come back attached to the posts, so no extra
     profile lookups are needed.
  2. Keeps authors in a follower range, with a sane following-to-follower ratio,
     an account older than a few months, and no fake or spam flags.
  3. Drops anyone you already follow (from Follow Audit data, no API cost) and
     anyone it showed you recently.
  4. Ranks by how well their posts land relative to their size and writes a
     report, a CSV and a phone-friendly HTML page with profile and post links.

What it never does
  No follow, like, repost, reply, post, DM, block or mute. GET requests only.
  It reuses Follow Audit's read-only token, so X would refuse a write anyway.

Spending
  Every post and profile X returns is counted. A run stops paging before the
  next page would push it past max_cost_per_run. The report shows the count,
  the estimate both ways X may bill attached profiles, and a daily projection.

Needs follow_watch.py in the Follow Audit folder (default /workspace/follow-watch).
Data lives in /workspace/creator-scout (override with --dir or CS_DIR).
"""

import argparse
import csv
import html
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone

# Where the bots live. Foreman sets BOTS_HOME for each bot. On Grok Bot that is /workspace.
BOTS_HOME = os.environ.get("BOTS_HOME", "/workspace").rstrip("/")

DEFAULT_CONFIG = {
    "follow_watch_dir": BOTS_HOME + "/follow-watch",
    "min_followers": None,
    "max_followers": None,
    "verified_only": None,
    "max_following_ratio": 2.0,
    "min_following_ratio": 0.1,
    "min_account_age_days": 90,
    "resurface_after_days": 60,
    "min_best_post_likes": 10,
    "exclude_terms": None,
    "adult_filter": True,
    "never_show": [],
    "shortlist_size": None,
    "sort_order": "relevancy",
    "queries": None,
    "posts_per_query": 100,
    "max_cost_per_run": None,
    "trial_posts_per_query": 40,
    "trial_max_cost": None,
    "price_per_post": 0.005,
    "price_per_user": 0.010,
    "projection_targets": [5, 10, 15, 25],
}

TWEET_FIELDS = "created_at,public_metrics,author_id,lang,possibly_sensitive"

# General adult content filter. On by default (adult_filter in config.json), applied on top of
# your own exclude_terms. Matched as plain text against name, bio and the posts read.
ADULT_FILTER_TERMS = [
    "nsfw", "r18", "r-18", "18+", "18禁", "成人向け", "🔞", "xxx", "porn", "nude", "nudes", "explicit",
    "adult content", "onlyfans", "fansly", "fanvue", "fanfix", "lewd", "hentai", "uncensored",
    "sexy", "sensual", "seductive", "spicy", "lingerie", "boudoir",
]

OPTIONAL_NONE = set()

def check_config(cfg, where):
    """Every setting left as None must come from the user's own config.json, written by Foreman."""
    missing = sorted(k for k, v in cfg.items() if v is None and k not in OPTIONAL_NONE)
    if missing:
        raise SystemExit(f"{where} is missing settings: {', '.join(missing)}. Run Foreman setup or add them to config.json.")
    return cfg


def write_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1, ensure_ascii=False)
    os.replace(tmp, path)


def read_json(path, default):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return default


class Paths:
    def __init__(self, root):
        self.root = root
        self.reports = os.path.join(root, "reports")
        os.makedirs(self.reports, exist_ok=True)
        self.config = os.path.join(root, "config.json")
        self.seen = os.path.join(root, "seen.json")
        self.runs = os.path.join(root, "runs.json")


def load_config(p):
    cfg = dict(DEFAULT_CONFIG)
    if os.path.exists(p.config):
        cfg.update(read_json(p.config, {}))
    else:
        raise SystemExit(f"No config.json in {p.root}. Run Foreman setup first.")
    return check_config(cfg, 'Follow Finder config')


def sync_never_show(p, cfg):
    """Adds handles hidden with the Never show button on the lists site to never_show.
    Reads the site's KV store through the Cloudflare API. Needs CLOUDFLARE_API_TOKEN with
    Workers KV Storage Read, and CLOUDFLARE_ACCOUNT_ID. Any problem is reported and skipped."""
    import urllib.error
    import urllib.parse
    import urllib.request
    tok, acc = os.environ.get("CLOUDFLARE_API_TOKEN"), os.environ.get("CLOUDFLARE_ACCOUNT_ID")
    if not (tok and acc):
        print("Never-show sync skipped: CLOUDFLARE_API_TOKEN or CLOUDFLARE_ACCOUNT_ID not set.", file=sys.stderr)
        return

    def cf(path):
        req = urllib.request.Request(os.environ.get("CF_API_BASE", "https://api.cloudflare.com/client/v4") + "/accounts/" + acc + path,
                                     headers={"Authorization": "Bearer " + tok})
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read()

    try:
        title = cfg.get("never_show_namespace", os.environ.get("KV_NAMESPACE_TITLE", "bot-lists-checks"))
        ns = json.loads(cf("/storage/kv/namespaces?per_page=100"))
        nid = next((n["id"] for n in ns.get("result", []) if n.get("title") == title), None)
        if not nid:
            print(f"Never-show sync skipped: no KV namespace named {title}.", file=sys.stderr)
            return
        try:
            raw = cf(f"/storage/kv/namespaces/{nid}/values/" + urllib.parse.quote("checks:never-scout", safe=""))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return
            raise
        site = json.loads(raw or b"{}") or {}
    except urllib.error.HTTPError as e:
        hint = " The API token needs Workers KV Storage Read." if e.code in (401, 403) else ""
        print(f"Never-show sync skipped: Cloudflare returned {e.code}.{hint}", file=sys.stderr)
        return
    except Exception as e:  # never block a run over this
        print(f"Never-show sync skipped: {e}", file=sys.stderr)
        return
    cur = [h.lstrip("@") for h in cfg.get("never_show", [])]
    have = {h.lower() for h in cur}
    add = [h.lstrip("@") for h in site if isinstance(site, dict) and h.lstrip("@").lower() not in have]
    if add:
        cfg["never_show"] = cur + add
        saved = read_json(p.config, {})
        saved["never_show"] = cfg["never_show"]
        write_json(p.config, saved)
        print(f"Never-show: added {len(add)} from the lists site ({', '.join('@' + h for h in add)}).",
              file=sys.stderr)


def load_fw(cfg):
    fw_dir = cfg["follow_watch_dir"]
    if not os.path.exists(os.path.join(fw_dir, "follow_watch.py")):
        raise SystemExit(f"follow_watch.py not found in {fw_dir}. Set follow_watch_dir in config.json.")
    sys.path.insert(0, fw_dir)
    import follow_watch as fw  # noqa: E402
    return fw


# ----------------------------------------------------------------------------
# Spend meter
# ----------------------------------------------------------------------------

class Spend:
    def __init__(self, cfg, cap):
        self.cfg = cfg
        self.cap = cap
        self.posts = 0
        self.users = 0
        self.requests = 0

    def low(self, posts=None, users=None):
        return (self.posts if posts is None else posts) * self.cfg["price_per_post"]

    def high(self, posts=None, users=None):
        p = self.posts if posts is None else posts
        u = self.users if users is None else users
        return p * self.cfg["price_per_post"] + u * self.cfg["price_per_user"]

    def room_for(self, page_posts):
        # worst case: every post on the next page has a new author
        nxt = self.high(self.posts + page_posts, self.users + page_posts)
        return nxt <= self.cap


# ----------------------------------------------------------------------------
# Search
# ----------------------------------------------------------------------------

def build_query(q, cfg, verified):
    q = q.strip()
    if verified and "is:verified" not in q:
        q += " is:verified"
    return q


def search(client, spend, query, want, sort_order):
    """Returns (posts, users_by_id, stopped_for_budget)."""
    posts, users, token = [], {}, None
    while len(posts) < want:
        page = max(10, min(100, want - len(posts)))
        if not spend.room_for(page):
            return posts, users, True
        params = {"query": query, "max_results": page, "tweet.fields": TWEET_FIELDS,
                  "expansions": "author_id", "user.fields": client_user_fields(),
                  "sort_order": sort_order}
        if token:
            params["next_token"] = token
        body = client.get("/tweets/search/recent", params)
        spend.requests += 1
        data = body.get("data", []) or []
        inc = (body.get("includes") or {}).get("users", []) or []
        spend.posts += len(data)
        spend.users += len(inc)
        posts.extend(data)
        for u in inc:
            users[u["id"]] = u
        token = (body.get("meta") or {}).get("next_token")
        if not token or not data:
            break
    return posts, users, False


_USER_FIELDS = None


def client_user_fields():
    return _USER_FIELDS


# ----------------------------------------------------------------------------
# Filtering and ranking
# ----------------------------------------------------------------------------

def account_age_days(u, today):
    c = u.get("created_at")
    if not c:
        return None
    try:
        return (today - datetime.fromisoformat(c.replace("Z", "+00:00")).date()).days
    except ValueError:
        return None


def post_points(p):
    m = p.get("public_metrics") or {}
    return ((m.get("like_count", 0) or 0) + 2 * (m.get("retweet_count", 0) or 0)
            + 2 * (m.get("quote_count", 0) or 0) + (m.get("reply_count", 0) or 0))


def post_age_hours(p, now_utc):
    c = p.get("created_at")
    if not c:
        return 10 ** 6
    try:
        return (now_utc - datetime.fromisoformat(c.replace("Z", "+00:00"))).total_seconds() / 3600
    except ValueError:
        return 10 ** 6


def evaluate(users, posts, cfg, fw, fw_cfg, today, following, followers, seen, my_id):
    spam_res = fw.compile_spam(fw_cfg)
    now_utc = datetime.now(timezone.utc)
    by_author = {}
    for p in posts:
        by_author.setdefault(p.get("author_id"), []).append(p)
    kept, dropped = [], {}
    terms = {t.lower() for t in (ADULT_FILTER_TERMS if cfg.get("adult_filter", True) else []) + list(cfg.get("exclude_terms", []))}
    never = {h.lower().lstrip("@") for h in cfg.get("never_show", [])}

    def drop(why):
        dropped.setdefault(why, []).append(u.get("username", uid))

    for uid, u in users.items():
        if uid == my_id:
            continue
        pm = u.get("public_metrics") or {}
        fol = pm.get("followers_count", 0) or 0
        fing = pm.get("following_count", 0) or 0
        if cfg["verified_only"] and not fw.is_verified(u):
            drop("not verified"); continue
        if uid in following:
            drop("you already follow"); continue
        s = seen.get(uid)
        if s and (today - date.fromisoformat(s["shown"])).days < cfg["resurface_after_days"]:
            drop("shown recently"); continue
        if not (cfg["min_followers"] <= fol <= cfg["max_followers"]):
            drop("outside follower range"); continue
        if fing > cfg["max_following_ratio"] * max(fol, 1):
            drop("follows far more than follow them"); continue
        if fing < cfg.get("min_following_ratio", 0) * fol:
            drop("follows almost no one, unlikely to follow back"); continue
        age = account_age_days(u, today)
        if age is not None and age < cfg["min_account_age_days"]:
            drop("account too new"); continue
        a = fw.assess(u, today, fw_cfg, spam_res)
        if "likely fake" in a["tags"] or "spam signals" in a["tags"]:
            drop("fake or spam signals"); continue
        if (u.get("username") or "").lower() in never:
            drop("on your never-show list"); continue
        their = sorted(by_author.get(uid, []), key=post_points, reverse=True)
        text = " ".join([u.get("name") or "", u.get("description") or "", u.get("url") or ""]
                        + [q.get("text") or "" for q in their]).lower()
        if any(t in text for t in terms):
            drop("adult or suggestive content"); continue
        if any(q.get("possibly_sensitive") for q in their):
            drop("post marked sensitive by X"); continue
        best = post_points(their[0]) if their else 0
        best_likes = ((their[0].get("public_metrics") or {}).get("like_count", 0) or 0) if their else 0
        settled = [q for q in their if post_age_hours(q, now_utc) >= 24]
        if settled:
            settled_likes = max((q.get("public_metrics") or {}).get("like_count", 0) or 0 for q in settled)
            if settled_likes < cfg.get("min_best_post_likes", 0):
                drop("best post under the like floor"); continue
        rate = best / max(fol, 1)
        kept.append({
            "id": uid, "username": u.get("username", ""), "name": u.get("name", ""),
            "followers": fol, "following": fing, "posts_total": pm.get("tweet_count", 0) or 0,
            "bio": (u.get("description") or "").replace("\n", " "),
            "avatar": u.get("profile_image_url", ""),
            "follows_you": uid in followers,
            "best_points": best, "rate": rate,
            "top_posts": [{"id": p["id"], "text": (p.get("text") or "").replace("\n", " ")[:140],
                           "points": post_points(p),
                           "likes": (p.get("public_metrics") or {}).get("like_count", 0),
                           "created": (p.get("created_at") or "")[:10]} for p in their[:3]],
            "lang": (their[0].get("lang") if their else "") or "",
        })
    kept.sort(key=lambda c: (not c["follows_you"], -c["rate"], -c["best_points"]))
    return kept, dropped


# ----------------------------------------------------------------------------
# Output
# ----------------------------------------------------------------------------

def money(x):
    return f"${x:,.2f}"


def projection_rows(cfg, posts, users, new_candidates):
    if not posts or not new_candidates:
        return None
    per_post = new_candidates / posts
    users_per_post = users / posts
    rows = []
    for target in cfg["projection_targets"]:
        need = target / per_post
        low = need * cfg["price_per_post"]
        high = low + need * users_per_post * cfg["price_per_user"]
        rows.append((target, int(round(need)), low, high))
    return per_post, users_per_post, rows


def write_report(p, cfg, now, mode, spend, stopped, kept, dropped, shortlist, past, queries_used, notes):
    today = now.date()
    L = [f"# Follow Finder: {mode}, {now.strftime('%a %b %d, %Y %I:%M %p')}", "",
         "Read-only run. Nothing was followed, liked, reposted or replied to.", ""]
    for n in notes:
        L += [f"> {n}", ""]

    if mode == "verify":
        L += ["## Cost", "",
              f"- Profiles looked up: {spend.users:,} at ${cfg['price_per_user']:.3f} each",
              f"- Posts looked up: {spend.posts:,} at ${cfg['price_per_post']:.3f} each",
              f"- Estimated cost: {money(spend.high())}",
              "", "Check the X developer console for the billed amount.", ""]
    else:
        L += ["## Cost", "",
          f"- Search requests: {spend.requests}",
          f"- Posts read: {spend.posts:,}",
          f"- Author profiles attached: {spend.users:,}",
          f"- Estimated cost: {money(spend.low())} if X bills posts only, "
          f"{money(spend.high())} if it also bills each attached profile",
          f"- Cap for this run: {money(spend.cap)}" + (" (reached, paging stopped early)" if stopped else ""),
          "", "Check the X developer console for the billed amount. It settles which of the two numbers is right.", ""]

    proj = None if mode == "verify" else projection_rows(cfg, spend.posts, spend.users, len(kept))
    if mode == "verify":
        L += ["## What this route would cost daily", "",
              f"Checking {spend.users} profiles and {spend.posts} posts came to about {money(spend.high())}. "
              f"Doing this every day is about {money(spend.high() * 30)} per 30 days in X credits, "
              "plus whatever share of your Grok Bot weekly usage the search took.", ""]
    elif proj:
        per_post, upp, rows = proj
        L += ["## What a daily run would cost", "",
              f"This run found {len(kept)} new candidates from {spend.posts:,} posts, "
              f"about 1 for every {1 / per_post:.0f} posts read.", "",
              "| New creators a day | Posts to read | Per day | Per 30 days |",
              "|---|---|---|---|"]
        for target, need, low, high in rows:
            L.append(f"| {target} | {need:,} | {money(low)} to {money(high)} | {money(low * 30)} to {money(high * 30)} |")
        L += ["", "The rate drops over time as the people you already follow and the ones already shown "
              "fall out of the pool. Expect later runs to cost somewhat more per new name.", ""]
    else:
        L += ["## What a daily run would cost", "", "No candidates found, so there is nothing to project from. "
              "Widen the follower range or change the queries in config.json.", ""]

    L += [f"## Shortlist ({len(shortlist)})", ""]
    if shortlist:
        L += ["| Account | Followers | Following | Best post | Lang | Note |", "|---|---|---|---|---|---|"]
        for c in shortlist:
            best = c["top_posts"][0] if c["top_posts"] else None
            bl = (f"[{best['likes']:,} likes](https://x.com/{c['username']}/status/{best['id']})" if best else "")
            L.append(f"| [@{c['username']}](https://x.com/{c['username']}) | {c['followers']:,} | "
                     f"{c['following']:,} | {bl} | {c['lang']} | {'follows you' if c['follows_you'] else ''} |")
        L += ["", "Open creator_scout.html for the same list with post previews and checkboxes.", ""]
    if len(kept) > len(shortlist):
        L += [f"{len(kept) - len(shortlist)} more qualified and are saved in candidates.csv. "
              "They were not marked as shown, so they can appear in a later run.", ""]

    L += ["## Why authors were left out", ""]
    if dropped:
        for why, names in sorted(dropped.items(), key=lambda x: -len(x[1])):
            if len(names) <= 20:
                L.append(f"- {why} ({len(names)}): " + ", ".join("@" + n for n in names))
            else:
                L.append(f"- {why}: {len(names):,}")
    else:
        L.append("- none")
    L += ["", "## Searches used", ""] + [f"- `{q}`" for q in queries_used] + [""]

    if past:
        L += ["## Earlier picks", "",
              f"Of {past['shown']} creators shown before, you now follow {past['you_follow']} and "
              f"{past['mutual']} follow you back. This updates when Follow Audit runs a full scan.", ""]

    path = os.path.join(p.reports, f"{today.isoformat()}_{mode}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    return path


def write_csv(p, kept):
    path = os.path.join(p.reports, "candidates.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["username", "name", "followers", "following", "follows_you", "best_post_points",
                    "engagement_per_follower", "lang", "profile", "best_post", "bio"])
        for c in kept:
            bp = c["top_posts"][0]["id"] if c["top_posts"] else ""
            w.writerow([c["username"], c["name"], c["followers"], c["following"],
                        "yes" if c["follows_you"] else "", c["best_points"], f"{c['rate']:.4f}", c["lang"],
                        f"https://x.com/{c['username']}",
                        f"https://x.com/{c['username']}/status/{bp}" if bp else "", c["bio"]])
    return path


HTML_PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Follow Finder</title>
<style>
:root{--bg:#ffffff;--card:#ffffff;--ink:#000000;--mute:#555555;--line:#cccccc;--acc:#000000;--chip:#f2f2f2}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif}
.wrap{max-width:760px;margin:0 auto;padding:16px}
h1{margin:0 0 2px;font-size:20px}.sub{color:var(--mute);font-size:13px;margin:0 0 14px}
.tog{display:inline-flex;gap:6px;align-items:center;font-size:13px;border:1px solid var(--line);background:var(--card);padding:6px 10px;border-radius:8px;margin-bottom:12px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px;margin-bottom:10px}
.card.done{opacity:.4}
.top{display:grid;grid-template-columns:44px 1fr auto;gap:10px;align-items:center}
.top.noav{grid-template-columns:1fr auto}
.top img{width:44px;height:44px;border-radius:50%;background:var(--chip);object-fit:cover}
a.h{color:var(--ink);font-weight:600;text-decoration:none}a.h:hover{color:var(--acc);text-decoration:underline}
.nm{color:var(--mute);font-size:13px}
.chips{display:flex;gap:6px;flex-wrap:wrap;margin-top:4px}.c{background:var(--chip);border-radius:999px;padding:1px 8px;font-size:12px;color:var(--mute)}.c.a{color:var(--acc)}
.bio{color:var(--mute);font-size:13px;margin:8px 0 6px}
.posts a{display:block;color:var(--ink);text-decoration:none;font-size:13px;border-top:1px solid var(--line);padding:6px 0}
.posts a:hover{color:var(--acc)}.posts b{color:var(--acc);font-weight:600;margin-right:6px}
.chk{display:flex;gap:6px;align-items:center;font-size:13px;color:var(--mute)}.chk input{width:18px;height:18px;accent-color:var(--acc)}
</style></head><body><div class="wrap">
<h1>Follow Finder</h1>
<p class="sub">__SUB__</p>
<label class="tog"><input type="checkbox" id="hide"> Hide checked</label>
<div id="list"></div></div>
<script>
const DATA=__DATA__;const KEY="creator-scout-done";let done={};
try{done=JSON.parse(localStorage.getItem(KEY)||"{}")}catch(e){}
const save=()=>{try{localStorage.setItem(KEY,JSON.stringify(done))}catch(e){}};
const esc=s=>String(s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
function render(){const hide=document.getElementById("hide").checked;
document.getElementById("list").innerHTML=DATA.filter(c=>!hide||!done[c.username]).map(c=>`
<div class="card${done[c.username]?" done":""}"><div class="top${c.avatar?"":" noav"}">
${c.avatar?`<img src="${esc(c.avatar)}" alt="" loading="lazy" onerror="this.parentNode.classList.add('noav');this.remove()">`:""}
<div><a class="h" href="https://x.com/${encodeURIComponent(c.username)}" target="_blank" rel="noopener">@${esc(c.username)}</a> <span class="nm">${esc(c.name)}</span>
<div class="chips"><span class="c">${c.followers.toLocaleString()} followers</span><span class="c">follows ${c.following.toLocaleString()}</span>${c.lang?'<span class="c">'+esc(c.lang)+'</span>':""}${c.follows_you?'<span class="c a">follows you</span>':""}</div></div>
<label class="chk"><input type="checkbox" data-u="${esc(c.username)}" ${done[c.username]?"checked":""}>done</label></div>
${c.bio?'<div class="bio">'+esc(c.bio)+'</div>':""}
<div class="posts">${c.top_posts.map(p=>`<a href="https://x.com/${encodeURIComponent(c.username)}/status/${p.id}" target="_blank" rel="noopener"><b>${p.likes.toLocaleString()} likes</b>${esc(p.text)}</a>`).join("")}</div></div>`).join("")}
document.getElementById("list").addEventListener("change",e=>{const u=e.target.dataset.u;if(!u)return;if(e.target.checked)done[u]=1;else delete done[u];save();render()});
document.getElementById("hide").addEventListener("change",render);render();
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


def write_html(p, shortlist, now, cfg=None):
    cfg = cfg or {}
    data = [{k: c[k] for k in ("username", "name", "followers", "following", "lang", "follows_you",
                               "bio", "avatar", "top_posts")} for c in shortlist]
    kind = "verified creators" if cfg.get("verified_only") else "creators"
    sub = (f"{len(shortlist)} {kind} in your follower range, {now.strftime('%b %d, %Y')}. "
           "Handles open the profile, posts open the post. " + check_note())
    page = (HTML_PAGE.replace("__SUB__", html.escape(sub))
            .replace("__DATA__", json.dumps(data, ensure_ascii=False).replace("</", "<\\/")))
    path = os.path.join(p.reports, "creator_scout.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(page)
    return path


# ----------------------------------------------------------------------------

def run(mode, p, cfg, client, fw, fw_store, now):
    global _USER_FIELDS
    _USER_FIELDS = fw.USER_FIELDS
    today = now.date()
    fw_cfg = fw_store.load_config()
    fw_state = fw_store.load_state()
    accounts = fw_state.get("accounts", {})
    following = {i for i, a in accounts.items() if a.get("following_now")}
    followers = {i for i, a in accounts.items() if a.get("follower_now")}
    my_id = (fw_state.get("me") or {}).get("id")
    notes = []
    if not fw_state.get("baseline_date"):
        notes.append("No Follow Audit scan found, so people you already follow could not be filtered out.")

    trial = mode == "trial"
    per_q = cfg["trial_posts_per_query"] if trial else cfg["posts_per_query"]
    cap = cfg["trial_max_cost"] if trial else cfg["max_cost_per_run"]
    spend = Spend(cfg, cap)
    seen = read_json(p.seen, {})

    # split the cap evenly so every search runs, assuming the worst case of
    # one new author per post
    worst_per_post = cfg["price_per_post"] + cfg["price_per_user"]
    fair = int(cap / (len(cfg["queries"]) * worst_per_post))
    if fair < per_q:
        per_q = max(10, fair)
        notes.append(f"Cap of {money(cap)} split across {len(cfg['queries'])} searches allows "
                     f"{per_q} posts each.")

    all_posts, all_users, stopped, used = [], {}, False, []
    verified = cfg["verified_only"]
    for q in cfg["queries"]:
        query = build_query(q, cfg, verified)
        try:
            posts, users, hit = search(client, spend, query, per_q, cfg["sort_order"])
        except SystemExit as e:
            msg = str(e)
            if verified and "is:verified" in msg:
                verified = False
                notes.append("X rejected the is:verified search operator on this account, so searches ran "
                             "without it and unverified authors were filtered out afterward. That reads more "
                             "posts per useful name.")
                query = build_query(q, cfg, False)
                posts, users, hit = search(client, spend, query, per_q, cfg["sort_order"])
            else:
                raise
        used.append(query)
        all_posts += posts
        all_users.update(users)
        if hit:
            stopped = True

    kept, dropped = evaluate(all_users, all_posts, cfg, fw, fw_cfg, today, following, followers, seen, my_id)
    shortlist = kept[:cfg["shortlist_size"]]
    for c in shortlist:
        seen[c["id"]] = {"username": c["username"], "shown": today.isoformat()}
    write_json(p.seen, seen)

    past = None
    earlier = [i for i, s in seen.items() if s["shown"] != today.isoformat()]
    if earlier and fw_state.get("baseline_date"):
        past = {"shown": len(earlier),
                "you_follow": sum(1 for i in earlier if i in following),
                "mutual": sum(1 for i in earlier if i in following and i in followers)}

    runs = read_json(p.runs, [])
    runs.append({"ts": now.isoformat(timespec="seconds"), "mode": mode, "requests": spend.requests,
                 "posts": spend.posts, "users": spend.users, "candidates": len(kept),
                 "shortlist": len(shortlist), "cost_low": round(spend.low(), 4),
                 "cost_high": round(spend.high(), 4), "stopped_for_cap": stopped})
    write_json(p.runs, runs[-200:])

    report = write_report(p, cfg, now, mode, spend, stopped, kept, dropped, shortlist, past, used, notes)
    write_csv(p, kept)
    write_html(p, shortlist, now, cfg)
    print(report)



LINK_RE = None


def parse_links(text):
    import re
    users, posts = [], []
    for m in re.finditer(r"(?:x|twitter)\.com/([A-Za-z0-9_]{1,15})(?:/status/(\d+))?", text):
        name, pid = m.group(1), m.group(2)
        if name.lower() in ("i", "home", "search", "intent", "share"):
            continue
        if name.lower() not in [u.lower() for u in users]:
            users.append(name)
        if pid and pid not in posts:
            posts.append(pid)
    for m in re.finditer(r"(?<![\w/])@([A-Za-z0-9_]{1,15})", text):
        if m.group(1).lower() not in [u.lower() for u in users]:
            users.append(m.group(1))
    return users, posts


def verify(p, cfg, client, fw, fw_store, now, src):
    global _USER_FIELDS
    _USER_FIELDS = fw.USER_FIELDS
    today = now.date()
    with open(src, encoding="utf-8") as f:
        names, post_ids = parse_links(f.read())
    if not names:
        raise SystemExit(f"No X profile links or @handles found in {src}.")
    fw_cfg = fw_store.load_config()
    fw_state = fw_store.load_state()
    accounts = fw_state.get("accounts", {})
    following = {i for i, a in accounts.items() if a.get("following_now")}
    followers = {i for i, a in accounts.items() if a.get("follower_now")}
    my_id = (fw_state.get("me") or {}).get("id")
    notes = [f"Verify run on {len(names)} handles and {len(post_ids)} post links from {os.path.basename(src)}."]
    if not fw_state.get("baseline_date"):
        notes.append("No Follow Audit scan found, so people you already follow could not be filtered out.")

    spend = Spend(cfg, cfg["max_cost_per_run"])
    if len(names) * cfg["price_per_user"] + len(post_ids) * cfg["price_per_post"] > spend.cap:
        raise SystemExit("This list would cost more than max_cost_per_run. Shorten it or raise the cap.")
    users, missing = {}, []
    for i in range(0, len(names), 100):
        chunk = names[i:i + 100]
        body = client.get("/users/by", {"usernames": ",".join(chunk), "user.fields": fw.USER_FIELDS})
        spend.requests += 1
        for u in body.get("data", []) or []:
            users[u["id"]] = u
        spend.users += len(chunk)
        found = {u["username"].lower() for u in body.get("data", []) or []}
        missing += [n for n in chunk if n.lower() not in found]
    posts = []
    for i in range(0, len(post_ids), 100):
        chunk = post_ids[i:i + 100]
        body = client.get("/tweets", {"ids": ",".join(chunk), "tweet.fields": TWEET_FIELDS})
        spend.requests += 1
        posts += body.get("data", []) or []
        spend.posts += len(chunk)
    if missing:
        notes.append("Not found (renamed, suspended or deleted): " + ", ".join("@" + m for m in missing))

    seen = read_json(p.seen, {})
    kept, dropped = evaluate(users, posts, cfg, fw, fw_cfg, today, following, followers, seen, my_id)
    shortlist = kept[:cfg["shortlist_size"]]
    for c in shortlist:
        seen[c["id"]] = {"username": c["username"], "shown": today.isoformat()}
    write_json(p.seen, seen)
    runs = read_json(p.runs, [])
    runs.append({"ts": now.isoformat(timespec="seconds"), "mode": "verify", "requests": spend.requests,
                 "posts": spend.posts, "users": spend.users, "candidates": len(kept),
                 "shortlist": len(shortlist), "cost_low": round(spend.high(), 4),
                 "cost_high": round(spend.high(), 4), "stopped_for_cap": False})
    write_json(p.runs, runs[-200:])
    report = write_report(p, cfg, now, "verify", spend, False, kept, dropped, shortlist, None,
                          [f"links from {os.path.basename(src)}"], notes)
    write_csv(p, kept)
    write_html(p, shortlist, now, cfg)
    print(report)


def estimate(p, cfg):
    runs = read_json(p.runs, [])
    if not runs:
        raise SystemExit("No runs yet. Run `trial` first.")
    r = runs[-1]
    proj = projection_rows(cfg, r["posts"], r["users"], r["candidates"])
    print(f"Last run {r['ts']} ({r['mode']}): {r['posts']} posts, {r['users']} profiles, "
          f"{r['candidates']} candidates, cost {money(r['cost_low'])} to {money(r['cost_high'])}")
    if not proj:
        print("No candidates in the last run, nothing to project.")
        return
    for target, need, low, high in proj[2]:
        print(f"{target:>3} new a day: ~{need:,} posts, {money(low)} to {money(high)} a day, "
              f"{money(low * 30)} to {money(high * 30)} per 30 days")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Read-only finder for creators in your niche on X.")
    ap.add_argument("command", choices=["trial", "run", "verify", "estimate"])
    ap.add_argument("file", nargs="?", help="verify: text file with X profile and post links")
    ap.add_argument("--dir", default=os.environ.get("CS_DIR", BOTS_HOME + "/creator-scout"))
    args = ap.parse_args(argv)
    p = Paths(args.dir)
    cfg = load_config(p)
    if args.command == "estimate":
        estimate(p, cfg)
        return
    sync_never_show(p, cfg)
    fw = load_fw(cfg)
    fw_store = fw.Store(cfg["follow_watch_dir"])
    fw_cfg = fw_store.load_config()
    now = fw.local_now(fw_cfg)
    client = fw.XClient(fw_store, fw_cfg, fw.Meter({**fw_cfg, "max_resources_per_run": 10 ** 9}))
    if args.command == "verify":
        if not args.file:
            raise SystemExit("verify needs a text file of X links, for example: verify picks.txt")
        verify(p, cfg, client, fw, fw_store, now, args.file)
    else:
        run(args.command, p, cfg, client, fw, fw_store, now)


if __name__ == "__main__":
    main()
