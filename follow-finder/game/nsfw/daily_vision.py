"""Follow Finder Game: optional image check. OFF by default.

Without it (the default) nothing here touches the network. Every pick that has no image verdict stays
blurred behind "Tap to show" in the Game. Follow Finder's hard NSFW text filter and X's possibly_sensitive
flag still run on every pick.

Turn it on by setting "game_image_check": true in Follow Finder's config.json (or say "turn on image check").
Sheets are built from the free embed data at cdn.syndication.twimg.com. That path is unofficial and
undocumented. It costs $0, but X can change or block it without notice. If a pick fails, it stays blurred.
Media expansions stay off. Nothing here calls a paid X or vision API. `prep` still waits for --yes.

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


SYND = "https://cdn.syndication.twimg.com/tweet-result?id={id}&lang=en&token=a"


def synd_tweet(tid):
    """Free unofficial embed. None if X blocks it. Never a paid media expansion."""
    try:
        req = urllib.request.Request(SYND.format(id=tid), headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


def cost_line(n):
    return n, 0.0, (f"Image check: {n} unrated picks via the free unofficial embed "
                    "(cdn.syndication.twimg.com), $0. If it fails, those picks stay blurred. Media expansions stay off.")


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
        print("Not read. Run again with --yes. This path is $0 and unofficial."); return
    S = g.rj(SJ, {}); ids = {g.best_post(x)["id"]: x["username"].lower() for x in pend}
    for tid, h in ids.items():
        body = synd_tweet(tid)
        if not body:
            continue
        photos = []
        for photo in body.get("photos") or []:
            url = photo.get("url") if isinstance(photo, dict) else None
            if url:
                photos.append(url)
        video = body.get("video") or {}
        poster = video.get("poster") or video.get("poster_url") if isinstance(video, dict) else None
        if poster:
            photos.append(poster)
        user = body.get("user") or {}
        avatar = user.get("profile_image_url_https") or user.get("profile_image_url") or ""
        S[h] = dict(post=tid, sensitive=bool(body.get("possibly_sensitive")), avatar=avatar, media=photos[:3])
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
