#!/usr/bin/env python3
"""Follow Finder Game tab (off unless game/LIVE exists).

Builds the daily pack, taste-test deck, binder, rules and score from files that
already exist on the box. It makes NO X calls at all:
  - picks:     $BOTS_HOME/creator-scout/reports/creator_scout.html (Follow Finder's DATA)
  - following: $BOTS_HOME/follow-watch/data/state.json (Follow Audit's nightly list)
  - replies:   $BOTS_HOME/engagement/posts.json (the owner's own replies Mention Radar / Reply Queue already saved)
  - marks:     lists-site KV "checks:game-*" via the Cloudflare API (same path and token as
               Follow Finder's never-show sync). Skipped cleanly when the token is not set.

Usage:
  game_tab.py build [--out DIR]           build game.json (run after Follow Finder)
  game_tab.py chat "not like @x because ..."
  game_tab.py chat "undo rule <id or words>"
  game_tab.py chat "already following @handle"
"""
import datetime as dt, json, os, re, sys, urllib.parse, urllib.request, urllib.error
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'nsfw'))
import nsfw  # hard NSFW filter, always on
def nsfw_block(c):
    return nsfw.check(c['username'], c.get('name') or '', c.get('bio') or '', text_of(c), (), c.get('sensitive', False))

HERE = os.path.dirname(os.path.abspath(__file__))
BOTS_HOME = os.environ.get("BOTS_HOME", "/workspace").rstrip("/")
SCOUT = os.environ.get("CS_DIR", BOTS_HOME + "/creator-scout")
SCOUT_HTML = f"{SCOUT}/reports/creator_scout.html"
SCOUT_CFG = f"{SCOUT}/config.json"
FW_STATE = BOTS_HOME + "/follow-watch/data/state.json"
POSTS = BOTS_HOME + "/engagement/posts.json"
STORE = os.environ.get("GAME_STORE", f"{HERE}/store.json")          # local copy: binder, packs, rules, score history
PACK_SIZE, FOLLOW_CAP = 5, 5
PTS = {"reply": 3, "follow": 1, "keeper": 5}  # follow-backs earn nothing
# Owner's niche words come from config.json "game_niche" (list). Empty = the "not my niche" chip says it can't judge.
NICHE = []  # filled from config.json below (after rj)

# Chip -> rule. "test" runs on a candidate; reliable False means we say so instead of guessing.
CHIPS = {
 "engagement bait": dict(what="Posts that ask for likes, reposts or tags in exchange for something",
   words=["like and repost", "like & repost", "rt to", "repost to", "tag a friend", "tag 3", "drop your",
          "comment below", "who's next", "follow for more"], reliable=True),
 "follow trains or giveaways": dict(what="Follow trains, follow-for-follow and giveaways",
   words=["follow train", "f4f", "follow for follow", "followback", "follow back", "giveaway", "gfa",
          "ifb", "#train", "drop your handle"], reliable=True),
 "reposts other people's work": dict(what="Accounts that repost or curate others' work",
   words=["credit:", "credits:", "via @", "not my art", "repost", "reposting", "curated", "dm for removal",
          "all rights belong"], reliable=False,
   note="Only catches bios and posts that say so. Saved data can't tell whose image it is."),
 "low effort or spammy ai": dict(what="Many near-identical posts, prompt dumps, or hashtag walls",
   words=["prompt in alt", "daily ai", "ai girl", "ai waifu"],
   hashtags=8, reliable=False,
   note="Uses a hashtag-wall and keyword check. Image quality itself can't be judged from saved data."),
 "not my niche": dict(what="Creators whose bio and best post miss your niche (game_niche in config.json)",
   niche=True, reliable=True),
 "too big already": dict(what="Creators over 10K followers", max_followers=10000, reliable=True),
 "politics or rage posts": dict(what="Political or outrage wording in bio or best post",
   words=["maga", "trump", "biden", "harris", "democrat", "republican", "woke", "leftist", "libs",
          "election", "ragebait", "outrage"], reliable=True),
 "nsfw": dict(what="Adult or suggestive content wording",
   words=["nsfw", "r18", "18+", "lewd", "onlyfans", "fansly", "spicy", "hentai", "waifu", "thicc", "boudoir"],
   reliable=False, note="Follow Finder already drops the obvious words. X's possibly_sensitive flag is checked too, but images can still slip through unless the optional image check is on."),
 "mostly self promo": dict(what="Bios and posts pushing shops, courses, links or commissions",
   words=["link in bio", "shop", "store", "course", "buy now", "commission", "patreon", "gumroad",
          "use my code", "check out my", "subscribe"], reliable=True),
}

def now(): return dt.datetime.now()
def today(): return now().date().isoformat()
def rj(p, d):
    try:
        with open(p, encoding="utf-8") as f: return json.load(f)
    except Exception: return d
def wj(p, o):
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f: json.dump(o, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)

def _load_niche():
    """Template: niche words are the owner's, never shipped. config.json "game_niche" (list of words),
    else words from the owner's search "queries" (operators and short words dropped)."""
    cfg = rj(SCOUT_CFG, {})
    w = cfg.get("game_niche") or []
    if not w:
        for q in cfg.get("queries") or []:
            for t in re.split(r'["()]| OR ', str(q)):
                t = t.strip().lower()
                if len(t) > 2 and not t.startswith(("-", "lang:", "is:", "has:", "min_")): w.append(t)
    return [x.lower() for x in w]
NICHE[:] = _load_niche()

# ---------------------------------------------------------------- KV (read, plus write for chat)
def _cf(path, method="GET", body=None):
    tok, acc = os.environ.get("CLOUDFLARE_API_TOKEN"), os.environ.get("CLOUDFLARE_ACCOUNT_ID")
    if not (tok and acc): raise RuntimeError("CLOUDFLARE_API_TOKEN or CLOUDFLARE_ACCOUNT_ID not set")
    h = {"Authorization": "Bearer " + tok}
    if body is not None: h["content-type"] = "application/json"
    req = urllib.request.Request("https://api.cloudflare.com/client/v4/accounts/" + acc + path,
                                 data=body, headers=h, method=method)
    with urllib.request.urlopen(req, timeout=30) as r: return r.read()

def _nid():
    title = rj(SCOUT_CFG, {}).get("never_show_namespace", os.environ.get("KV_NAMESPACE_TITLE", "bot-lists-checks"))
    ns = json.loads(_cf("/storage/kv/namespaces?per_page=100"))
    return next((n["id"] for n in ns.get("result", []) if n.get("title") == title), None)

GAME_PAGES = ["game-rules", "game-binder", "game-taste", "game-pending", "game-following"]
def kv_pull():
    """Server-side sync before each run. Returns {page: obj} or {} with a note."""
    try:
        nid = _nid()
        if not nid: return {}, "no KV namespace"
        out = {}
        for p in GAME_PAGES:
            try: out[p] = json.loads(_cf(f"/storage/kv/namespaces/{nid}/values/" + urllib.parse.quote("checks:" + p, safe="")) or b"{}") or {}
            except urllib.error.HTTPError as e:
                if e.code != 404: raise
        return out, "synced"
    except Exception as e:
        return {}, f"KV sync skipped: {e}"

def kv_push(page, obj):
    try:
        nid = _nid()
        if nid: _cf(f"/storage/kv/namespaces/{nid}/values/" + urllib.parse.quote("checks:" + page, safe=""),
                    "PUT", json.dumps(obj).encode())
        return True
    except Exception as e:
        print(f"KV write skipped: {e}. Saved locally, the page picks it up on next build.", file=sys.stderr)
        return False

# ---------------------------------------------------------------- inputs
def scout_picks():
    with open(SCOUT_HTML, encoding="utf-8") as f: html = f.read()
    i = html.find("const DATA=")
    return json.JSONDecoder().raw_decode(html, i + len("const DATA="))[0] if i >= 0 else []

def following():
    s = rj(FW_STATE, {})
    ids, names = set(), set()
    for i, a in (s.get("accounts") or {}).items():
        if a.get("following_now"):
            ids.add(i); u = (a.get("user") or {})
            n = (u.get("username") if isinstance(u, dict) else None) or ""
            if n: names.add(n.lower())
    FIDS.clear(); FIDS.update(ids)
    return names, (s.get("last_run") or {})

FIDS = set()  # Follow Audit following_now user IDs (match by ID)
_UID = {}
def uid_of(h):
    """handle -> X user ID from Follow Finder's saved data (cands rows carry id, db.json users). No calls."""
    import glob
    if not _UID:
        for f in sorted(glob.glob(f"{SCOUT}/scratch/prev_*/cands.json")) + [f"{SCOUT}/scratch/cands.json"]:
            for x in rj(f, []):
                if x.get("u") and x.get("id"): _UID[x["u"].lower()] = str(x["id"])
        for f in glob.glob(f"{SCOUT}/scratch/prev_*/db.json") + [f"{SCOUT}/scratch/db.json"]:
            for i, u in ((rj(f, {}) or {}).get("users") or {}).items():
                if isinstance(u, dict) and u.get("username"): _UID.setdefault(u["username"].lower(), str(u.get("id") or i))
    return _UID.get((h or "").lower())

def gate(c, ctx):
    """the one final filter. Runs on the finished pack AFTER the Rare floor and every swap,
    on every refill, on spares, and on a pack saved earlier today. Returns a reason or None."""
    h = c["username"].lower(); uid = uid_of(h)
    if uid and uid in ctx["fids"]: return "already followed (Follow Audit)"
    if uid and uid in ctx["af"]: return "already following (you marked it)"
    if not uid and h in ctx["fnames"]: return "already followed (handle fallback, no saved ID)"
    if h in ctx["af_h"]: return "already following (you marked it)"
    if h in ctx["never"]: return "never-scout"
    if nsfw_block(c): return "nsfw"
    hit = next((r for r in ctx["rules"] if (r.get("words") or r.get("niche") or r.get("max_followers") or r.get("hashtags")) and rule_hits(r, c)), None)
    if hit: return "rule:" + hit["id"]
    return None

def gated_fill(order, ctx, n, start=()):
    out = [c for c in start if not gate(c, ctx)]
    for c in order:
        if len(out) >= n: break
        if c not in out and not gate(c, ctx): out.append(c)
    return out

def post_authors():
    """{post_id: handle_lower} from Follow Finder's saved post and user data (no calls)."""
    import glob
    ids, out = {}, {}
    for f in glob.glob(f"{SCOUT}/scratch/db.json") + glob.glob(f"{SCOUT}/scratch/prev_*/db.json"):
        db = rj(f, {})
        users = db.get("users") or {}
        for uid, u in users.items():
            if isinstance(u, dict) and u.get("username"): ids[str(u.get("id") or uid)] = u["username"].lower()
        for pid, p in (db.get("posts") or {}).items():
            if isinstance(p, dict) and p.get("author_id") in ids: out[str(p.get("id") or pid)] = ids[p["author_id"]]
    for f in glob.glob(f"{SCOUT}/scratch/cands.json") + glob.glob(f"{SCOUT}/scratch/prev_*/cands.json"):
        for x in rj(f, []):
            if x.get("best"): out[str(x["best"])] = x["u"].lower()
    return out

REPLY_MATCH = {}
def my_replies():
    """{handle_lower: [dates]} from the owner's saved replies. posts.json has no in_reply_to_user_id,
    so the target is the author of the replied-to post id (replied_to) from Follow Finder's saved data.
    Falls back to the leading @mention only when that post isn't in saved data."""
    out, auth = {}, post_authors()
    idmap = {i: ((a.get("user") or {}).get("username") or "").lower() for i, a in (rj(FW_STATE, {}).get("accounts") or {}).items()}
    for i, u in ((rj(SCOUT + "/scratch/db.json", {}) or {}).get("users") or {}).items():
        if u.get("username"): idmap.setdefault(str(i), u["username"].lower())
    idmap = {k: v for k, v in idmap.items() if v}
    REPLY_MATCH.update(by_id=0, by_mention=0, none=0)
    for p in (rj(POSTS, {}) or {}).values():
        if not isinstance(p, dict) or p.get("kind") != "reply": continue
        uid_h = idmap.get(str(p.get("in_reply_to_user_id") or ""))
        h = uid_h or auth.get(str(p.get("replied_to") or ""))
        if h: REPLY_MATCH["by_id"] += 1
        else:
            m = re.match(r"\s*@(\w{1,15})", p.get("text") or "")
            h = m.group(1).lower() if m else None
            REPLY_MATCH["by_mention" if h else "none"] += 1
        if h: out.setdefault(h, []).append((p.get("created") or "")[:10])
    return out

def text_of(c):
    bp = best_post(c)
    return ((c.get("bio") or "") + " \n " + (bp.get("text") if bp else "")).lower()

def best_post(c):
    tp = c.get("top_posts") or []
    return max(tp, key=lambda p: p.get("points", 0)) if tp else None

def norm_cand(x):
    """Follow Finder's saved candidate row (scratch/prev_*/cands.json) -> DATA-like dict."""
    return dict(username=x["u"], name=x.get("name"), followers=x.get("f") or 0, following=x.get("g") or 0,
                bio=x.get("bio") or "", avatar=x.get("avatar"), lang=x.get("lang"),
                top_posts=[dict(id=x["best"], text=x.get("post") or "", points=x.get("pts") or 0,
                                likes=x.get("likes") or 0, created="")] if x.get("best") else [])

IDX = {}
RAR = {}  # handle -> rarity, set before draw_pack
def saved_days():
    """{date: [picks]} for every day Follow Finder saved, built only from files on disk."""
    import glob
    global IDX
    if not IDX:
        for f in sorted(glob.glob(f"{SCOUT}/scratch/prev_*/cands.json")) + [f"{SCOUT}/scratch/cands.json"]:
            for x in rj(f, []):
                if x.get("u"): IDX[x["u"].lower()] = x
        for c in scout_picks():  # today's published picks
            bp = best_post(c) or {}
            IDX.setdefault(c["username"].lower(), dict(u=c["username"], name=c.get("name"), f=c.get("followers"),
                g=c.get("following"), bio=c.get("bio"), avatar=c.get("avatar"), best=bp.get("id"),
                post=bp.get("text"), pts=bp.get("points"), likes=bp.get("likes")))
    out = {}
    for txt in sorted(glob.glob(f"{SCOUT}/picks/picks_????-??-??.txt")):
        d = os.path.basename(txt)[6:16]
        hs = [l.split()[0].rstrip("/").split("/")[-1].lower() for l in open(txt, encoding="utf-8") if l.strip()]
        day = [norm_cand(IDX[h]) for h in hs if h in IDX]
        if day: out[d] = day
    return out

def in_niche(c): return any(k in text_of(c) for k in NICHE) if NICHE else True  # no niche words set: every pick counts

def eng_rate(c):
    bp = best_post(c); f = max(c.get("followers") or 1, 1)
    return (bp.get("points", 0) / f) if bp else 0.0

# ---------------------------------------------------------------- rules
def rule_hits(rule, c):
    t = text_of(c)
    if rule.get("niche"): return bool(NICHE) and not in_niche(c)
    if rule.get("max_followers") and (c.get("followers") or 0) > rule["max_followers"]: return True
    if any(w in t for w in rule.get("words", [])): return True
    if rule.get("hashtags") and t.count("#") >= rule["hashtags"]: return True
    return False

def free_text_rule(txt):
    """Turn free text into a keyword rule only when it names concrete words. Otherwise say so."""
    q = re.findall(r'"([^"]{2,40})"|\'([^\']{2,40})\'', txt)
    words = [a or b for a, b in q]
    m = re.search(r"(?:posts? about|anything about|no|about|uses?|using)\s+([a-z0-9#@ ,/&'-]{2,60})", txt.lower())
    if not words and m:
        words = [w.strip() for w in re.split(r",|/| or | and ", m.group(1)) if 2 <= len(w.strip()) <= 30][:6]
    for k, r in CHIPS.items():
        if k in txt.lower(): return dict(chip=k, **r)
    if words:
        return dict(what="Bios or best posts that mention " + ", ".join(f'"{w}"' for w in words),
                    words=[w.lower() for w in words], reliable=True, free=txt)
    return dict(what=f'"{txt}"', words=[], reliable=False, free=txt,
                note="Couldn't turn this into a word check I trust. Saved as a note only, nothing is filtered.")

def new_rule(reason, handle=None, free=None):
    base = dict(chip=reason, **CHIPS[reason]) if reason in CHIPS else free_text_rule(free or reason)
    rid = "r" + now().strftime("%m%d%H%M%S") + (handle or "")[:4].lower()
    return dict(id=rid, from_handle=handle, created=now().isoformat(timespec="seconds"), active=True, **base)

# ---------------------------------------------------------------- build
def week_start():
    d = now().date(); return (d - dt.timedelta(days=d.weekday())).isoformat()

def blind_media(deck):
    """Template rule: blind cards use X's official embed widget only, under a solid cover over the name
    row and footer with taps blocked until reveal. No unofficial endpoints, no network here, $0."""
    for x in deck:
        x["bmedia"] = []
        x["bdate"] = (x.get("created") or "")[:10]

def blind_text(t):
    """Nothing identifying while blind: drop links and @handles."""
    t = re.sub(r"\bhttps?\S*|\bt\.co/\S*", "", t or "")
    t = re.sub(r"@\w{1,15}", "@someone", t)
    return re.sub(r"\s+", " ", t).strip()

def standin(c, follow_names):
    """Free Legendary stand-in. NOT a shared-follows check (that would need paid lookups)."""
    hs = (c["username"] or "").lower()
    tags = {t.lower() for t in re.findall(r"@(\w{1,15})", c.get("bio") or "")}
    ok = in_niche(c) and hs not in follow_names and not (tags & follow_names)
    return eng_rate(c) if ok else 0.0

def cuts(pool, follow_names):
    """Relative cut lines from every saved Follow Finder pick: top 3% stand-in = Legendary, next 15% = Rare."""
    n = len(pool)
    if not n: return (9e9, 9e9)
    sc = sorted(((standin(c, follow_names), eng_rate(c)) for c in pool), reverse=True)
    nl, nr = max(1, round(n * 0.03)), max(1, round(n * 0.18))
    leg = sc[nl - 1][0] if sc[nl - 1][0] > 0 else 9e9
    rare = sorted((max(a, b) for a, b in sc), reverse=True)[nr - 1]
    return (leg, rare)

HIDDEN_GEM = "Hidden gem: in your niche, you don't follow them, and nobody you follow is tagged in their bio"
def rarity_rel(c, follow_names, cut):
    if standin(c, follow_names) >= cut[0]: return "Legendary", HIDDEN_GEM
    if max(standin(c, follow_names), eng_rate(c)) >= cut[1]:
        bp = best_post(c)
        return "Rare", f"Top 18% of Follow Finder's picks for engagement. Best post got {bp.get('likes',0) if bp else 0} likes on {c.get('followers',0):,} followers"
    return "Common", "A solid fit near your size"

def draw_pack(pool, d, keeps, n=PACK_SIZE):
    """Keeps first, then a date-seeded shuffle so rarity in packs matches the pool, not a sort."""
    import random
    rng = random.Random(d)
    k = [c for c in pool if c["username"].lower() in keeps]
    rest = [c for c in pool if c["username"].lower() not in keeps]
    rng.shuffle(rest)
    pack = (k + rest)[:n]
    # Rare floor: one Rare (or better) whenever the day's pool has one
    if RAR and not any(RAR.get(c["username"].lower()) in ("Rare", "Legendary") for c in pack):
        r = [c for c in rest if RAR.get(c["username"].lower()) == "Rare" and c not in pack]
        if r and pack: pack[-1] = r[0]
    return pack

AF_SIM, SIM_BAD = set(), []
def simulate(days=7):
    fnames, _ = following()
    AF_SIM.update(k for k in (rj(STORE, {}).get("af") or {}) if not k.startswith("h:"))
    sd = saved_days()
    allp = [c for v in sd.values() for c in v]
    cut = cuts(allp, fnames)
    rows, seen = [], set()
    never = {h.lower() for h in rj(SCOUT_CFG, {}).get("never_show", [])}
    for d in sorted(sd)[-days:]:
        ctx = dict(fids=FIDS, af=AF_SIM, af_h=set(), fnames=fnames, never=never, rules=[])
        pool = [c for c in sd[d] if c["username"].lower() not in seen]
        RAR.clear(); RAR.update({c["username"].lower(): rarity_rel(c, fnames, cut)[0] for c in pool})
        order = draw_pack(pool, d, set(), n=len(pool))
        pack = gated_fill(order, ctx, PACK_SIZE, draw_pack(pool, d, set()))
        bad = [c["username"] for c in pack if (uid_of(c["username"]) in FIDS | AF_SIM) or c["username"].lower() in fnames]
        SIM_BAD.extend(bad)
        seen |= {c["username"].lower() for c in pack}
        r = [rarity_rel(c, fnames, cut)[0] for c in pack]
        rows.append((d, len(pool), r.count("Legendary"), r.count("Rare"), r.count("Common"), [c["username"] for c in pack]))
    return len(allp), cut, rows

def rarity(c, follow_names, kept, allow_legend=True):
    hs = (c["username"] or "").lower()
    bp = best_post(c)
    # "No overlap with anyone you follow": with saved data we can only check that they are
    # not followed by you and their bio tags nobody you follow. True mutual-follow overlap
    # would need a new paid lookup per creator, so it is NOT checked.
    tags = {t.lower() for t in re.findall(r"@(\w{1,15})", c.get("bio") or "")}
    if in_niche(c) and hs not in follow_names and not (tags & follow_names) and eng_rate(c) >= 0.08 and allow_legend:
        return "Legendary", "In your niche, you don't follow them, and their bio tags nobody you follow"
    if (c.get("followers") or 0) < 2000 and bp and eng_rate(c) >= 0.06:
        return "Rare", f"Under 2K followers and their best post got {bp.get('likes',0)} likes on {c.get('followers',0):,} followers"
    return "Common", "A solid fit near your size"

def why_line(c, rar_why):
    bp = best_post(c)
    if rar_why != "A solid fit near your size": return rar_why
    hit = next((k for k in NICHE if k in text_of(c)), None)
    return f"{('Posts ' + hit) if hit else 'In your search results'} and their best recent post got {bp.get('likes',0) if bp else 0} likes"

def style_tags(c):
    t = text_of(c); tags = []
    for k, ws in {"video": ["video", "film", "kling", "veo", "sora", "runway"], "anime": ["anime", "イラスト", "manga"],
                  "portrait": ["portrait", "selfie", "girl", "woman"], "horror": ["horror", "dark", "halloween"],
                  "robots": ["robot", "mecha", "cyber"], "landscape": ["landscape", "nature", "city"],
                  "fantasy": ["fantasy", "dragon", "dinosaur", "creature"]}.items():
        if any(w in t for w in ws): tags.append(k)
    return tags or ["general"]

def build(out_dir):
    st = rj(STORE, {"binder": {}, "packs": {}, "rules": [], "taste": {}, "blocked": {}, "score_days": {}})
    kv, kv_note = kv_pull()
    # merge site marks (phone/desktop) into the local store
    for rid, r in (kv.get("game-rules") or {}).items():
        if not isinstance(r, dict): continue
        loc = next((x for x in st["rules"] if x["id"] == rid), None)
        if r.get("undone"):
            if loc: loc["active"] = False
        elif not loc and r.get("reason"):
            st["rules"].append(new_rule(r["reason"], r.get("handle"), r.get("free")) | {"id": rid})
    # "Already following" marks from the cards, kept by user ID until Follow Audit's list has them
    for h, v in (kv.get("game-following") or {}).items():
        if isinstance(v, dict) and not v.get("undone"):
            st.setdefault("af", {})[str(v.get("id") or uid_of(h) or "h:" + h.lower())] = dict(h=h.lower(), at=v.get("at"))
    for h, v in (kv.get("game-taste") or {}).items():
        if isinstance(v, dict) and v.get("pick") in ("keep", "pass"): st["taste"][h.lower()] = v
    for h, v in (kv.get("game-binder") or {}).items():
        if h.lower() in st["binder"] and isinstance(v, dict) and v.get("opened"):
            st["binder"][h.lower()]["opened_at"] = v.get("at") or st["binder"][h.lower()].get("opened_at")

    picks = scout_picks()
    never = {h.lower() for h in rj(SCOUT_CFG, {}).get("never_show", [])}
    fnames, fw_run = following()
    reps = my_replies()
    d = today(); ws = week_start()

    # Pass signal: styles you passed on lose a little; keeps go to the top.
    pass_styles = {}
    for h, v in st["taste"].items():
        if v.get("pick") == "pass":
            for s in v.get("styles", []): pass_styles[s] = pass_styles.get(s, 0) + 1
    active = [r for r in st["rules"] if r.get("active")]
    af = st.setdefault("af", {})
    for k in [k for k in af if k in FIDS]: af.pop(k)  # Follow Audit caught up
    ctx = dict(fids=FIDS, af={k for k in af if not k.startswith("h:")}, af_h={v["h"] for v in af.values()},
               fnames=fnames, never=never, rules=active)
    pool, blocked_today = [], {}
    for c in picks:  # pre-filter only narrows the pool; gate() below is the one that decides
        h = c["username"].lower()
        why = gate(c, ctx)
        if why == "nsfw": st.setdefault("nsfw_blocked", {})[h] = nsfw_block(c)
        elif why and why.startswith("rule:"): blocked_today.setdefault(why[5:], []).append(h)
        if not why: pool.append(c)
    for rid, hs in blocked_today.items():
        wk = st["blocked"].setdefault(rid, {})
        for h in hs: wk[h] = d
    seen_in_binder = set(st["binder"])
    def score(c):
        h = c["username"].lower(); s = eng_rate(c) * 100
        if st["taste"].get(h, {}).get("pick") == "keep": s += 1000
        if h in seen_in_binder: s -= 500
        s -= 0.5 * sum(pass_styles.get(t, 0) for t in style_tags(c))
        return s
    pool.sort(key=score, reverse=True)
    # hard NSFW filter: a stored pack holding a now-blocked creator is redrawn
    nb = st.get("nsfw_blocked", {})
    if d in st["packs"] and any(str(x).lower() in nb for x in st["packs"][d]): del st["packs"][d]
    # a pack saved earlier today goes through the same final gate; any miss redraws it
    byh = {c["username"].lower(): c for c in picks}
    gate_log = {}
    if d in st["packs"]:
        for x in st["packs"][d]:
            c = byh.get(str(x).lower()); g = gate(c, ctx) if c else "not in today's picks"
            if g: gate_log[x] = g
        if gate_log:
            for x in gate_log: st["binder"].pop(str(x).lower(), None) if st["binder"].get(str(x).lower(), {}).get("first") == d else None
            del st["packs"][d]
    cut = cuts([c for v in saved_days().values() for c in v] or picks, fnames)
    def mk(c):
        r, rw = rarity_rel(c, fnames, cut); bp = best_post(c)
        return dict(checked=nsfw.checked(c["username"]), h=c["username"], uid=uid_of(c["username"]), name=c.get("name"), avatar=c.get("avatar"), followers=c.get("followers"),
                    rarity=r, why=rw if r != "Common" else why_line(c, rw), styles=style_tags(c),
                    post=dict(id=bp["id"], text=bp.get("text"), likes=bp.get("likes"), created=bp.get("created")) if bp else None,
                    caveats=[])
    if d not in st["packs"]:
        pack = []
        sd = saved_days(); allp = [c for v in sd.values() for c in v] or picks
        cut = cuts(allp, fnames)
        keeps = {h for h, v in st["taste"].items() if v.get("pick") == "keep"}
        RAR.clear(); RAR.update({c["username"].lower(): rarity_rel(c, fnames, cut)[0] for c in pool})
        srt = sorted(pool, key=score, reverse=True)
        chosen = draw_pack(srt, d, keeps)  # keeps, shuffle, Rare floor swap
        order = draw_pack(srt, d, keeps, n=len(srt))
        chosen = gated_fill(order, ctx, PACK_SIZE, chosen)  # final gate AFTER every swap, refills gated too
        for c in chosen:
            card = mk(c)
            pack.append(card)
            st["binder"].setdefault(c["username"].lower(), dict(card, first=d, opened_at=None))
        st["packs"][d] = [c["h"] for c in pack]
    for h in [h for h in st["binder"] if h in nb or nsfw.check(h)]: st["binder"].pop(h)
    for h, b in st["binder"].items(): b["checked"] = nsfw.checked(h)
    # caveats from unreliable active rules
    weak = [r for r in active if not r.get("reliable") and r.get("chip")]  # partial filters only
    # taste deck: today's pool not in pack and not already judged
    judged = set(st["taste"])
    deck = [dict(k=c["username"].lower(), text=(best_post(c) or {}).get("text", ""), blind=blind_text((best_post(c) or {}).get("text", "")), id=(best_post(c) or {}).get("id"),
                 likes=(best_post(c) or {}).get("likes", 0), styles=style_tags(c),
                 h=c["username"], name=c.get("name"), avatar=c.get("avatar"), followers=c.get("followers"), checked=nsfw.checked(c["username"]))
            for c in pool if c["username"].lower() not in judged and c["username"] not in st["packs"].get(d, []) and best_post(c) and nsfw.checked(c["username"])][:10]
    blind_media(deck)

    # scoring: followed (Follow Audit list), replies (saved replies), keeper at 30 days
    events, per_day_follows = [], {}
    for h, b in st["binder"].items():
        b["followed"] = (uid_of(h) in FIDS) if uid_of(h) else h in fnames
        if b["followed"] and not b.get("followed_seen"): b["followed_seen"] = d
        rd = sorted(x for x in reps.get(h, []) if x >= b["first"])
        b["replies"] = len(rd)
        if b.get("followed_seen"):
            per_day_follows.setdefault(b["followed_seen"], []).append(h)
        for x in rd: events.append((x, "reply", h))
        if rd and (dt.date.fromisoformat(rd[-1]) - dt.date.fromisoformat(b["first"])).days >= 30:
            b["keeper"] = True; events.append((rd[-1], "keeper", h))
    for day, hs in per_day_follows.items():
        for h in sorted(hs)[:FOLLOW_CAP]: events.append((day, "follow", h))
    week_pts = sum(PTS[k] for day, k, _ in events if day >= ws)
    total = sum(PTS[k] for _, k, _ in events)
    active_days = sorted({day for day, _, _ in events} | {v.get("at", "")[:10] for v in st["taste"].values() if v.get("at")})
    streak, cur = 0, now().date()
    s_days = set(active_days)
    if d not in s_days: cur -= dt.timedelta(days=1)
    while cur.isoformat() in s_days: streak += 1; cur -= dt.timedelta(days=1)
    level = 1 + week_pts // 10

    rules_out = []
    for r in st["rules"]:
        n = sum(1 for _, day in st["blocked"].get(r["id"], {}).items() if day >= ws)
        rules_out.append(dict(id=r["id"], what=r["what"], chip=r.get("chip"), free=r.get("free"),
                              reliable=r.get("reliable"), note=r.get("note"), active=r.get("active"),
                              from_handle=r.get("from_handle"), created=r["created"][:10], blocked_week=n))
    pack_cards = [dict(st["binder"][h.lower()], uid=uid_of(h), caveats=[r["note"] for r in weak if r.get("note")]) for h in st["packs"][d]]
    inpack = {h.lower() for h in st["packs"][d]}
    # spares for the "Already following" button: same final gate, best-scored first
    spares = [dict(mk(c), caveats=[r["note"] for r in weak if r.get("note")]) for c in gated_fill([c for c in pool if c["username"].lower() not in inpack], ctx, 10)]
    game = dict(date=d, built=now().isoformat(timespec="seconds"), kv=kv_note, follow_list=fw_run,
                pack=pack_cards, spares=spares, deck=deck, gate_redraw=gate_log,
                already_following=sorted(v["h"] for v in af.values()),
                binder=sorted(st["binder"].values(), key=lambda b: b["first"], reverse=True),
                rules=rules_out, chips=list(CHIPS),
                score=dict(week=week_pts, total=total, level=level, next_level=(level) * 10, streak=streak,
                           follows_today=len(per_day_follows.get(d, [])), follow_cap=FOLLOW_CAP, pts=PTS),
                x_calls=0, reply_match=dict(REPLY_MATCH))
    wj(STORE, st)
    os.makedirs(out_dir, exist_ok=True)
    wj(os.path.join(out_dir, "game.json"), game)
    print(f"Game: pack {len(pack_cards)} cards, deck {len(deck)}, binder {len(st['binder'])}, rules {len(rules_out)}, {kv_note}. X calls: 0.")
    return game

# ---------------------------------------------------------------- chat fallback
def _kv_rule(rid, val, merge=False):
    """mirror chat rules into the same KV page the UI uses (checks:game-rules)."""
    kv, note = kv_pull()
    if note != "synced": print(f"KV not updated ({note}); local store has it, next build keeps it.", file=sys.stderr); return
    cur = kv.get("game-rules") or {}
    cur[rid] = {**(cur.get(rid) or {}), **val} if merge else val
    kv_push("game-rules", cur)


def chat(msg):
    st = rj(STORE, {"binder": {}, "packs": {}, "rules": [], "taste": {}, "blocked": {}, "score_days": {}})
    m = re.match(r"\s*not like @?(\w{1,15})\s+because\s+(.+)", msg, re.I)
    if m:
        h, why = m.group(1), m.group(2).strip().rstrip(".")
        chip = next((k for k in CHIPS if k in why.lower()), None)
        r = new_rule(chip, h) if chip else new_rule(why, h, free=why)
        st["rules"].append(r); wj(STORE, st)
        _kv_rule(r["id"], dict(reason=chip or why, free=None if chip else why, handle=h, what=r["what"],
                               reliable=r.get("reliable"), note=r.get("note"), at=r["created"], via="chat"))
        msg = f"Rule added: {r['what']}."
        if not r.get("reliable"): msg += " Heads up: " + r.get("note", "")
        return msg + " Applies before the next pack."
    m = re.match(r"\s*undo rule\s+(.+)", msg, re.I)
    if m:
        q = m.group(1).strip().lower()
        hit = [r for r in st["rules"] if r.get("active") and (r["id"].lower() == q or q in r["what"].lower() or q == (r.get("chip") or ""))]
        if len(hit) != 1:
            return "No single active rule matches that." if not hit else "More than one rule matches: " + ", ".join(f"{r['id']} ({r['what']})" for r in hit)
        hit[0]["active"] = False; wj(STORE, st)
        _kv_rule(hit[0]["id"], {"undone": True, "at": now().isoformat(timespec="seconds"), "via": "chat"}, merge=True)
        return f"Undone: {hit[0]['what']}. It stops filtering from the next pack."
    m = re.match(r"\s*already following @?(\w{1,15})\s*$", msg, re.I)
    if m:
        h = m.group(1).lower(); uid = uid_of(h); at = now().isoformat(timespec="seconds")
        st.setdefault("af", {})[str(uid or "h:" + h)] = dict(h=h, at=at); wj(STORE, st)
        cur = (kv_pull()[0] or {}).get("game-following") or {}; cur[h] = dict(id=uid, at=at, via="chat"); kv_push("game-following", cur)
        return f"Marked @{h} as already following. They leave the pack from the next build and stay out until Follow Audit catches up."
    return 'Try "not like @handle because ...", "undo rule ..." or "already following @handle".'

if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "build":
        out = a[a.index("--out") + 1] if "--out" in a else HERE
        build(out)
    elif a and a[0] == "simulate":
        n, cut, rows = simulate()
        print(f"pool {n} saved picks, cuts {cut}")
        for r in rows: print(*r)
        print("followed accounts in packs:", SIM_BAD or "none")
    elif a and a[0] == "chat":
        print(chat(" ".join(a[1:])))
    else:
        print(__doc__)
