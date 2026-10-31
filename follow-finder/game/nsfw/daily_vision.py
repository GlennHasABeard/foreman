"""Follow Finder Game: optional image check. OFF by default.

Without it (the default) nothing here touches the network. Every pick that has no image verdict stays
blurred behind "Tap to show" in the Game, and the Blind Taste Test uses X's official embed widget under a
solid cover. Follow Finder's hard NSFW text filter and X's possibly_sensitive flag still run on every pick.

Turn it on by setting "game_image_check": true in Follow Finder's config.json (or say "turn on image check").
It then reads each unrated pick's best post once with X media expansions
(GET /2/tweets?ids=...&expansions=attachments.media_keys,author_id), which is an official X API read,
priced from the crew's price table: one post read per pick plus one attached profile. The cost is printed
before anything is read, and `prep` stops unless you pass --yes. It never uses an unofficial endpoint.

Usage:
  python3 daily_vision.py cost          -> how many picks are unrated and what the check would cost
  python3 daily_vision.py prep --yes    -> read media for unrated picks, build sheets/daily_*.jpg, print pending
  python3 daily_vision.py rate HANDLE safe|suggestive|explicit|unchecked "note"   (the bot views the sheets itself)
  python3 daily_vision.py apply         -> re-filter today's page/csv/picks (refilter_today.py); NSFW -> never_show
"""
import json, os, sys, subprocess, urllib.request
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(H))
import game_tab as g
VJ, SJ, CFG = os.path.join(H, "vision.json"), os.path.join(H, "media.json"), os.path.join(H, "..", "..", "config.json")


def cfg():
    try:
        return json.load(open(CFG))
    except Exception:
        return {}


def pending():
    V = g.rj(VJ, {})
    return [c for c in g.scout_picks() if c["username"].lower() not in V and g.best_post(c)]


def rates():
    sys.path.insert(0, cfg().get("follow_watch_dir") or os.path.join(os.environ.get("BOTS_HOME", "/workspace"), "follow-watch"))
    import x_prices
    return x_prices.RATES


def cost_line(n):
    R = rates(); each = R["post"] + R["attached_user"]
    return n, each, f"Image check: {n} unrated picks x ${each:.3f} (one post read with media expansions plus its attached profile) = ${n * each:.2f}"


def get(url, path):
    if not url: return None
    if os.path.exists(path): return path
    try:
        req = urllib.request.Request(url + ("?name=small" if "pbs.twimg.com/media" in url else ""), headers={"User-Agent": "Mozilla/5.0"})
        open(path, "wb").write(urllib.request.urlopen(req, timeout=20).read()); return path
    except Exception: return None


def prep(yes):
    c = cfg()
    if not c.get("game_image_check"):
        print("Image check is off (the default). Unrated picks stay blurred behind Tap to show. No X calls made.")
        return
    pend = pending(); n, each, line = cost_line(len(pend)); print(line)
    if not pend: return
    if not yes:
        print("Not read. Run again with --yes to spend this."); return
    sys.path.insert(0, c.get("follow_watch_dir") or os.path.join(os.environ.get("BOTS_HOME", "/workspace"), "follow-watch"))
    import follow_watch as fw
    st = fw.Store(c.get("follow_watch_dir") or os.path.join(os.environ.get("BOTS_HOME", "/workspace"), "follow-watch"))
    fc = st.load_config(); client = fw.XClient(st, fc, fw.Meter({**fc, "max_resources_per_run": 10 ** 9}))
    S = g.rj(SJ, {}); ids = {g.best_post(x)["id"]: x["username"].lower() for x in pend}
    L = list(ids)
    for i in range(0, len(L), 100):
        body = client.get("/tweets", {"ids": ",".join(L[i:i + 100]), "tweet.fields": "possibly_sensitive,attachments",
                                      "expansions": "attachments.media_keys,author_id",
                                      "media.fields": "type,url,preview_image_url", "user.fields": "profile_image_url"})
        inc = body.get("includes") or {}
        media = {m["media_key"]: m.get("url") or m.get("preview_image_url") for m in inc.get("media", []) or []}
        users = {u["id"]: (u.get("profile_image_url") or "").replace("_normal", "_200x200") for u in inc.get("users", []) or []}
        for t in body.get("data", []) or []:
            h = ids.get(t["id"])
            if not h: continue
            keys = (t.get("attachments") or {}).get("media_keys") or []
            S[h] = dict(post=t["id"], sensitive=bool(t.get("possibly_sensitive")), avatar=users.get(t.get("author_id")),
                        media=[media.get(k) for k in keys if media.get(k)][:3])
    json.dump(S, open(SJ, "w"), ensure_ascii=False, indent=0)
    from PIL import Image, ImageDraw
    os.makedirs(os.path.join(H, "img"), exist_ok=True); os.makedirs(os.path.join(H, "sheets"), exist_ok=True)
    T = 280; hs = [x["username"].lower() for x in pend if x["username"].lower() in S]; out = []
    for n0 in range(0, len(hs), 8):
        grp = hs[n0:n0 + 8]; sh = Image.new("RGB", (T * 4, (T + 22) * len(grp)), "white"); d = ImageDraw.Draw(sh)
        for r, h in enumerate(grp):
            v = S[h]; y = r * (T + 22); d.text((4, y + 4), f"@{h}" + ("  [X possibly_sensitive]" if v.get("sensitive") else ""), fill="black")
            for col, u in enumerate([v.get("avatar")] + (v.get("media") or [])[:3]):
                p = get(u, os.path.join(H, "img", f"{h}_d{col}.jpg"))
                if p:
                    try: im = Image.open(p).convert("RGB"); im.thumbnail((T, T)); sh.paste(im, (col * T, y + 20))
                    except Exception: pass
        f = os.path.join(H, "sheets", f"daily_{g.dt.date.today()}_{n0 // 8:02d}.jpg"); sh.save(f, quality=80); out.append(f)
    print(json.dumps({"pending": hs, "sheets": out}))


def rate(h, verdict, note=""):
    V = g.rj(VJ, {}); V[h.lstrip("@").lower()] = [verdict, note or "image check"]
    json.dump(V, open(VJ, "w"), ensure_ascii=False, indent=0)
    if verdict in ("suggestive", "explicit"):  # NSFW -> never-scout
        c = cfg(); ns = c.setdefault("never_show", [])
        if h.lstrip("@").lower() not in {x.lstrip("@").lower() for x in ns}: ns.append(h.lstrip("@")); json.dump(c, open(CFG, "w"), indent=2)
    print("ok", h, verdict)


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["cost"]: print(cost_line(len(pending()))[2] + ("" if cfg().get("game_image_check") else " (image check is off)"))
    elif a[:1] == ["prep"]: prep("--yes" in a)
    elif a[:1] == ["rate"]: rate(a[1], a[2], " ".join(a[3:]))
    elif a[:1] == ["apply"]: subprocess.run([sys.executable, os.path.join(H, "refilter_today.py")], check=True)
    else: print(__doc__)
