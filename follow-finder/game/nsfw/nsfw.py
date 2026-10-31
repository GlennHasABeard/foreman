"""Hard NSFW filter (always on). check(user, post_text, link_urls, sensitive) -> reason|None
vision verdicts: vision.json {handle: [verdict, note]}; suggestive/explicit block."""
import json, os, re
HERE = os.path.dirname(os.path.abspath(__file__))
TERMS = ["nsfw","18+","🔞","r18","r-18","onlyfans","only fans","fansly","fanvue","fanfix","loyalfans","manyvids",
 "ai girlfriend","ai gf","ai model","ai influencer","waifu","lewd","hentai","ecchi","sexy","spicy","uncensored",
 "lingerie","bikini","boudoir","thirst","adult content","explicit","xxx","porn","nude","pin-up","pinup",
 "グラビア","エロ","水着","セクシー","r18","下着"]
ADULT_DOMAINS = ["onlyfans.com","fansly.com","fanvue.com","fanfix.io","loyalfans.com","manyvids.com","patreon.com/r18","pixiv.net/fanbox"]
LINKHUBS = ["linktr.ee","allmylinks.com","beacons.ai","lnk.bio","solo.to","bio.link","getallmylinks.com"]
HUB_HINT = ["spicy","exclusive","18","🔞","🌶","uncensored","private","vip","link in bio","dm for"]
def _vision():
    p = os.path.join(HERE, "vision.json")
    return json.load(open(p)) if os.path.exists(p) else {}
VISION = _vision()
def text_reason(blob, urls=()):
    b = (blob or "").lower()
    for t in TERMS:
        if re.search(r"(?<![a-z0-9])"+re.escape(t)+r"(?![a-z0-9])", b): return f"text: '{t}'"
    u = " ".join(urls).lower() + " " + b
    for d in ADULT_DOMAINS:
        if d in u: return f"link: {d}"
    if any(h in u for h in LINKHUBS) and any(x in b for x in HUB_HINT): return "link-in-bio page + adult hint"
    return None
PROFILE_ONLY = {"ai model","ai influencer","spicy","explicit","exclusive","sexy","thirst"}
def check(handle, name="", bio="", post_text="", urls=(), sensitive=False):
    if sensitive: return "X marked post possibly_sensitive"
    r = text_reason(" ".join([name or "", bio or ""]), urls)
    if not r:
        r = text_reason(post_text or "")
        if r and r.split("'")[1] in PROFILE_ONLY: r = None
        if r: r = r.replace("text:", "post text:")
    if r: return r
    v = VISION.get((handle or "").lower())
    if v and v[0] in ("suggestive","explicit"): return f"vision {v[0]}: {v[1]}"
    return None
def checked(handle):  # vision passed
    v = VISION.get((handle or "").lower()); return bool(v and v[0]=="safe")
