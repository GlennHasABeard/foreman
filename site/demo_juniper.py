#!/usr/bin/env python3
"""Fixed Juniper Vale demo for template screenshots. No X calls, no Cloudflare, no owner data.

Regenerate from the repo root:

  python3 site/demo_juniper.py

Writes demo/juniper/ (profile, page payloads, Home done marks, Game sample, HTML).
The Game sample is not a LIVE flag. Publish still hides the Game tab until
creator-scout/game/LIVE exists.

n55 live-vs-template diffs cannot tell which side is newer. This file is template-only.
"""
import json
import os
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "demo", "juniper")
FIXED = datetime(2026, 11, 5, 15, 0, tzinfo=timezone.utc)

OWNER = {
    "name": "Juniper Vale",
    "username": "junipervale_demo",
    "followers": 2400,
    "bio": "Watercolor studies of weather and river light. Demo data.",
}


def _demo(name):
    handle = name if name.endswith("_demo") else name + "_demo"
    if not handle.endswith("_demo"):
        raise ValueError(handle)
    return handle


def scout_pool():
    """Forty creators. Engagement is uneven so rarity_rel can name a real Legendary."""
    pool = []
    for i in range(40):
        handle = _demo(f"wash{i:02d}")
        # One high stand-in score, a few medium, the rest quiet. Points are the best-post score.
        if i == 0:
            points, likes, followers = 4000, 900, 800
        elif i < 8:
            points, likes, followers = 400, 80, 1500
        else:
            points, likes, followers = 20, 4, 2200
        pool.append({
            "username": handle,
            "name": f"Demo painter {i}",
            "followers": followers,
            "following": 400,
            "bio": "Watercolor sketchbook. Demo data.",
            "lang": "en",
            "top_posts": [{
                "id": str(1800000000000000000 + i),
                "text": "A river study in two washes. Demo data.",
                "points": points,
                "likes": likes,
                "created": "2026-11-01",
            }],
        })
    return pool


def rarity_labels(pool):
    """Labels from the Game tab's own cuts. Do not rewrite Legendary to Common."""
    sys.path.insert(0, os.path.join(ROOT, "follow-finder", "game"))
    import game_tab
    game_tab.NICHE[:] = []  # demo niche is empty so every pick counts, whatever config sits on the box
    cut = game_tab.cuts(pool, set())
    labels = {}
    for cand in pool:
        label, why = game_tab.rarity_rel(cand, set(), cut)
        labels[cand["username"]] = {"rarity": label, "why": why}
    return labels


def profile():
    return dict(OWNER, kind="demo", badge="Demo data", generated=FIXED.isoformat())


def pages(labels):
    pool = scout_pool()
    by_name = {c["username"]: c for c in pool}
    legendary = [h for h, lab in labels.items() if lab["rarity"] == "Legendary"]
    rare = [h for h, lab in labels.items() if lab["rarity"] == "Rare"]
    reply_rows = [
        {"key": "1001", "username": _demo("moss"), "chips": [{"t": "reply"}, {"t": "question"}],
         "text": "How do you keep the sky from going muddy? Demo data.",
         "links": [{"t": "Open and reply", "u": "https://x.com/moss_demo/status/1001"}],
         "question": True, "new": True, "g": "Everyone else"},
        {"key": "1002", "username": _demo("inkwash"), "chips": [{"t": "mention"}],
         "text": "Saved this river study. Demo data.",
         "links": [{"t": "Open and reply", "u": "https://x.com/inkwash_demo/status/1002"}],
         "question": False, "new": False, "g": "Everyone else"},
    ]
    leads = [{
        "key": "2001", "username": _demo("cedar"),
        "chips": [{"t": "1,200 followers"}, {"t": "verified"}, {"t": "3 replies"}],
        "text": "Paints weather. Demo data.",
        "links": [{"t": "Their reply", "u": "https://x.com/cedar_demo/status/2001"}],
    }]
    picks = []
    for handle in legendary[:1] + rare[:2] + [_demo("wash20")]:
        cand = by_name[handle]
        lab = labels[handle]
        picks.append({
            "username": handle, "name": cand["name"], "followers": cand["followers"],
            "bio": cand["bio"], "follows_you": False,
            "top_posts": cand["top_posts"], "rarity": lab["rarity"], "why": lab["why"],
        })
    shoutouts = [
        {"username": _demo("linen"), "followers": 1800, "label": "painters",
         "weeks_listed": 1, "week_label": "week 1 · new", "note": "Demo data."},
        {"username": _demo("ochre"), "followers": 900, "label": "painters",
         "weeks_listed": 3, "week_label": "week 3", "note": ""},
    ]
    reruns = [{
        "url": "https://x.com/junipervale_demo/status/3001", "date": "2026-09-12",
        "format": "photo", "views": 4200, "ratio": "3.2x", "last": "never",
        "text": "Three-layer river wash. Demo data.", "angle": "Show the second wash only.",
    }]
    audit = {
        "stats": [["followers", "2,400"], ["following", "310"]],
        "since": [
            {"e": "unfollowed_you", "u": _demo("pebble"), "d": "2026-11-04", "note": "12 days"},
            {"e": "gone", "u": _demo("faded"), "d": "2026-11-03", "note": "suspended"},
        ],
        "bad": [], "quiet": [],
    }
    analytics = {
        "verified": [{"date": "2026-08-07", "impressions": "1200"},
                     {"date": "2026-08-08", "impressions": "800"}],
        "tracker": [{"value": "40000", "pulled_at_et": "2026-11-05T15:00:00"}],
        "posts": [], "followers": [{"followers_total": "2400"}],
    }
    backlog = "18 people still engaging who don't follow you yet (+3 vs last week)"
    return {
        "reply-queue": reply_rows,
        "fan-finder": {"rows": leads, "backlog": backlog},
        "follow-finder": picks,
        "shoutout-picker": shoutouts,
        "rerun-picker": reruns,
        "follow-audit": audit,
        "analytics-log": analytics,
        "home": {"backlog": backlog},
    }


# Inbound at 14:18, Done at 15:00. qol7_medrt measures that gap as 42 minutes.
INBOUND_AT = "2026-11-05T14:18:00+00:00"
DONE_AT = "2026-11-05T15:00:00+00:00"


def median_inputs():
    """Posts, inbound events, and a Done mark qol7_medrt can time.

    The Done mark is {done: 1, at: ISO} plus the inbound time it answers.
    """
    who = _demo("inkwash")
    done = {who: {"done": 1, "on": True, "at": DONE_AT, "ts": DONE_AT, "inbound": INBOUND_AT}}
    events = {"in1": {"kind": "reply", "author": "u-ink", "username": who, "created": INBOUND_AT,
                      "text": "How do you keep the sky from going muddy? Demo data."}}
    posts = {"r1": {"kind": "reply", "created": DONE_AT, "replied_to": "in1",
                    "text": "A lighter first wash. Demo data."}}
    users = {"u-ink": {"username": who}}
    return {"posts": posts, "events": events, "users": users, "done": done}


def marks():
    """Home and Reply Queue read these done marks. inkwash_demo is Done, 42 minutes after the inbound post."""
    base = {"never": {}, "stages": {}, "notes": {}, "follow_ups": {}}
    base["done"] = median_inputs()["done"]
    return base


def game_sample(pool, labels):
    pack = []
    for cand in pool[:5]:
        lab = labels[cand["username"]]
        post = cand["top_posts"][0]
        pack.append({
            "h": cand["username"], "name": cand["name"], "followers": cand["followers"],
            "rarity": lab["rarity"], "why": lab["why"], "checked": True,
            "post": {"id": post["id"], "text": post["text"], "likes": post["likes"], "created": post["created"]},
        })
    return {
        "date": "2026-11-05", "built": FIXED.isoformat(), "x_calls": 0,
        "pack": pack, "spares": [], "deck": [], "rules": [], "chips": [],
        "score": {"streak": 1, "level": 1, "week": 2, "next_level": 10, "follows_today": 0, "follow_cap": 5},
        "note": "Sample only. The Game tab stays off until creator-scout/game/LIVE exists.",
    }


def _write(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
        f.write("\n")


def render_html(payload, home_marks):
    sys.path.insert(0, HERE)
    import pages_v11 as P
    import qol7_medrt
    med = payload["median"]
    med_line = qol7_medrt.publish_line(med["posts"], med["events"], med["done"], med["users"])
    nav = [("Home", "index.html"), ("Reply Queue", "reply-queue.html"), ("Fan Finder", "fan-finder.html"),
           ("Follow Finder", "follow-finder.html"), ("Shoutout Picker", "shoutout-picker.html"),
           ("Rerun Picker", "rerun-picker.html"), ("Follow Audit", "follow-audit.html"),
           ("Analytics Log", "analytics-log.html")]
    updated = "Updated Nov 5, 2026, 10:00 AM ET"
    html_dir = os.path.join(OUT, "html")
    os.makedirs(html_dir, exist_ok=True)
    pages = payload["pages"]
    bodies = {
        "Reply Queue": P.reply_queue(pages["reply-queue"], {"lines": [med_line]}, {}, None),
        "Fan Finder": P.fan_finder(pages["fan-finder"]["rows"], {"lines": [pages["fan-finder"]["backlog"]]}, {}),
        "Follow Finder": P.follow_finder(pages["follow-finder"], {"lines": ["40 kept in the free pre-screen"]}, False),
        "Shoutout Picker": P.shoutout_picker(pages["shoutout-picker"], {"lines": []}, False),
        "Rerun Picker": P.rerun_picker(pages["rerun-picker"], {"lines": []}, lambda t, prev: None, lambda t: None),
        "Follow Audit": P.follow_audit(pages["follow-audit"], {"lines": []}, None),
        "Analytics Log": P.analytics_log(pages["analytics-log"]["posts"], pages["analytics-log"]["followers"],
                                         pages["analytics-log"]["verified"], True, None, days=90,
                                         tracker=pages["analytics-log"]["tracker"]),
    }
    for title, href in nav[1:]:
        body = bodies[title]
        marks = home_marks if title == "Reply Queue" else {"never": {}, "done": {}, "stages": {}, "notes": {}, "follow_ups": {}}
        text = P.shell(title, P.SLUG(title), updated, "Demo data.", body, marks, nav, demo=True, hosted=False)
        with open(os.path.join(html_dir, href), "w", encoding="utf-8") as f:
            f.write(text)
    panels = [("p-reply-queue", "Reply Queue", "reply-queue.html",
               P.home_reply_queue(pages["reply-queue"], marks=home_marks))]
    home = P.home(panels, {}, None, [("followers", "2,400")], [])
    with open(os.path.join(html_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(P.shell("Home", "home", updated, "Demo data.", home, home_marks, nav, demo=True, hosted=False))


def readme(labels):
    legendary = sorted(h for h, lab in labels.items() if lab["rarity"] == "Legendary")
    return "\n".join([
        "# Juniper Vale demo",
        "",
        "Fake profile for screenshots. Juniper Vale, @junipervale_demo, about 2,400 followers, watercolor.",
        "Every other account ends in `_demo`. Pages show a Demo data badge.",
        "",
        "Regenerate from the repo root:",
        "",
        "    python3 site/demo_juniper.py",
        "",
        "No X calls and no Cloudflare. Do not put a real account in this folder.",
        "",
        "The Game sample is `game.json` here only. It does not create `creator-scout/game/LIVE`,",
        "so a normal publish still leaves the Game tab off.",
        "",
        "Legendary labels come from Follow Finder's rarity cut. This build: "
        + (", ".join("@" + h for h in legendary) or "none") + ".",
        "Those labels are stored as the cut returned them.",
        "",
        "Home done marks include @inkwash_demo so a Home card can show Done.",
        "That Done mark is {done: 1, at: 2026-11-05T15:00:00+00:00} for an inbound post at 14:18,",
        "so the Reply Queue median is 42 min. See median.json.",
        "",
        "Publish that page from this fixture, still with no Game LIVE flag:",
        "",
        "    BOTS_HOME=demo/juniper/bots SITE_DIR=demo/juniper/published LISTS_DEMO=1 python3 site/publish_lists.py --dry-run",
        "",
    ])


def write_bots(pages, med):
    """A tiny bots home so publish_lists can rebuild reply-queue.html from this fixture."""
    eng = os.path.join(OUT, "bots", "engagement")
    os.makedirs(os.path.join(eng, "reports"), exist_ok=True)
    os.makedirs(os.path.join(eng, "data"), exist_ok=True)
    _write(os.path.join(eng, "config.json"), {"timezone": "UTC"})
    open(os.path.join(eng, ".individual-reply-queue"), "w").close()
    _write(os.path.join(eng, "posts.json"), med["posts"])
    _write(os.path.join(eng, "events.json"), med["events"])
    _write(os.path.join(eng, "users.json"), med["users"])
    _write(os.path.join(eng, "data", "chat_store-reply-queue.json"), {
        "never": {}, "hide_until": {}, "stages": {}, "notes": {}, "events": [], "done": med["done"],
    })
    data = json.dumps(pages["reply-queue"], ensure_ascii=False).replace("</", "<\\/")
    with open(os.path.join(eng, "reports", "mention_radar.html"), "w", encoding="utf-8") as f:
        f.write("<!doctype html><script>const DATA=" + data + ";\nfunction noop(){}\n</script>\n")


def main():
    pool = scout_pool()
    labels = rarity_labels(pool)
    if not any(lab["rarity"] == "Legendary" for lab in labels.values()):
        raise SystemExit("Demo pool produced no Legendary card. Fix the scores instead of relabeling.")
    med = median_inputs()
    payload = {
        "profile": profile(),
        "pages": pages(labels),
        "marks": marks(),
        "median": med,
        "rarity": labels,
    }
    _write(os.path.join(OUT, "profile.json"), payload["profile"])
    _write(os.path.join(OUT, "pages.json"), payload["pages"])
    _write(os.path.join(OUT, "marks.json"), payload["marks"])
    _write(os.path.join(OUT, "median.json"), med)
    write_bots(payload["pages"], med)
    _write(os.path.join(OUT, "game.json"), game_sample(pool, labels))
    render_html(payload, payload["marks"])
    with open(os.path.join(OUT, "README.md"), "w", encoding="utf-8") as f:
        f.write(readme(labels))
    counts = {}
    for lab in labels.values():
        counts[lab["rarity"]] = counts.get(lab["rarity"], 0) + 1
    print(f"Wrote {OUT}. Rarity counts: {counts}. Game LIVE flag was not created.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
