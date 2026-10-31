#!/usr/bin/env python3
"""v1.1 wiring shared by every template bot and the site builder. No X API calls.

Each bot calls after_run(name, page=..., estimate=...) at the end of a run. That:
  * builds the bot's v1.1 panel from its own saved files (helpers in v11.py),
  * applies chat-store marks (never show, done, stage, notes) so they work without hosting,
  * injects the panel into the bot's HTML page (between <!--v11--> markers),
  * saves reports/v11-<slug>.json (read by the site's Home, own page and Your week),
  * returns the chat lines (status, labeled spend, follow-ups when they have nowhere else to show).

  python3 v11_wire.py after "Reply Queue"   rebuild one bot's panel now
  python3 v11_wire.py week                  print Your week (installed bots only)
  python3 v11_wire.py health                Dispatch bot health
  python3 v11_wire.py digest                Dispatch weekly cost digest
"""
import csv
import html
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import v11  # noqa: E402

SLUG = lambda n: n.lower().replace(" ", "-")  # noqa: E731
PAGES = {"Follow Audit": "follow-audit.html", "Follow Finder": "follow-finder.html", "Shoutout Picker": "shoutout-picker.html",
         "Reply Queue": "reply-queue.html", "Fan Finder": "fan-finder.html", "Rerun Picker": "rerun-picker.html",
         "Analytics Log": "analytics-log.html"}


def root(name):
    return os.path.join(v11.home(), v11.FOLDERS[name])


def _j(path, default):
    return v11._load(path, default)


def _csv(path):
    try:
        with open(path, newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))
    except OSError:
        return []


def _cfg(name):
    return _j(os.path.join(root(name), "config.json"), {})


def _ts(s):
    try:
        d = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=v11.UTC)
    except ValueError:
        return None


def _num(x):
    try:
        return float(str(x).replace(",", ""))
    except (TypeError, ValueError):
        return 0.0


# ---------- per-bot panels: (lines, html, extra) from saved files ----------

def panel_follow_audit(name):
    d = os.path.join(root(name), "data")
    ev = _csv(os.path.join(d, "events.csv"))
    kind = {"new_follower": "gain", "followed_back": "mutual", "new_mutual": "mutual",
            "unfollowed_you": "loss", "gone": "loss"}
    trend = v11.four_week_trend([{"ts": e["ts"], "kind": kind[e["event"]]} for e in ev
                                 if e.get("event") in kind and _ts(e.get("ts"))])
    recent = [e for e in ev if e.get("event") in ("unfollowed_you", "gone")
              and _ts(e.get("ts")) and v11.now() - _ts(e["ts"]) < timedelta(days=7)]
    split = v11.split_missing({e["username"] or e["id"]: (e["event"] == "unfollowed_you") or None for e in recent})
    lost = len(recent)
    x_unf = None
    if "Analytics Log" in v11.installed() or v11.is_crew():
        rows = _csv(os.path.join(root("Analytics Log"), "data", "followers.csv"))
        vals = [_num(r.get("unfollows")) for r in rows[-7:] if r.get("unfollows") not in (None, "")]
        x_unf = int(sum(vals)) if vals else None
    tiles = v11.unfollow_tiles(lost, x_unf)
    risks = v11.top_risks({lbl: _csv(os.path.join(d, f)) for lbl, f in
                           (("Flagged followers", "flagged_followers.csv"), ("Flagged following", "flagged_following.csv"),
                            ("Not following back", "not_following_back.csv"))})
    cfg = _cfg(name)
    lines = [", ".join(f"{v} {k}" for k, v in tiles.items()),
             f"Unfollowed you: {len(split['Unfollowed you'])}, account gone: {len(split['Account gone'])}",
             "4-week trend (gain/loss/mutual): " + " | ".join(f"{w['gain']}/{w['loss']}/{w['mutual']}" for w in trend),
             v11.newest_check_cost(int(cfg.get("newest_check_size", 350)))]
    lines += ["Top risks: " + ", ".join(risks)] if risks else []
    return lines, {"split": split, "trend": trend, "tiles": tiles}


def panel_follow_finder(name):
    runs = _j(os.path.join(root(name), "runs.json"), [])
    last = runs[-1] if isinstance(runs, list) and runs else {}
    lines = []
    if isinstance(last, dict) and "kept" in last:
        drops = last.get("drops") or {}
        lines.append(v11.stats_strip(last.get("kept", 0), drops if isinstance(drops, dict) else {},
                                     last.get("paid_skipped", 0)))
    back = v11.returning_soon(name=name)
    if back:
        lines.append("Returning soon: " + ", ".join(back))
    never = sorted(v11.load_store(name)["never"])
    if never:
        lines.append(f"Never shown again: {len(never)}")
    return lines, {"never": never}


def panel_shoutout_picker(name):
    r = root(name)
    q = _j(os.path.join(r, "queue.json"), [])
    handles = [x.get("handle", "") if isinstance(x, dict) else str(x) for x in q]
    dp = v11.done_pending(handles, name=name)
    done, pending = dp["done"], dp["pending"]
    cfg = _cfg(name)
    lines = [f"This week: {len(done)} done, {len(pending)} still to post"]
    w = v11.bench_warning(len(_j(os.path.join(r, "bench.json"), [])), int(cfg.get("list_size", 10)))
    lines += [w] if w else []
    sk = _j(os.path.join(r, "skips.json"), {})
    pairs = [(h, (v.get("reason") if isinstance(v, dict) else None) or "skipped, resting") for h, v in sk.items()]
    g = v11.grouped_skips(pairs)
    if g:
        lines.append("Left out: " + ", ".join(f"{k} {n}" for k, (n, _) in g.items()))
    if not v11.follow_audit_fresh():
        lines.append("Follow Audit data is older than a day or missing, mutual check used the last saved list.")
    return lines, {"done": done, "pending": pending}


def _engagement_items():
    r = root("Reply Queue")
    ev = _j(os.path.join(r, "events.json"), {})
    users = _j(os.path.join(r, "users.json"), {})
    posts = _j(os.path.join(r, "posts.json"), {})
    done = v11.load_store("Reply Queue")["done"]
    items = []
    for k, e in ev.items():
        if e.get("kind") == "like" or not e.get("created"):
            continue
        who = (users.get(e.get("author")) or {}).get("username") or e.get("author") or "?"
        items.append({"ts": e["created"].replace("Z", "+00:00"), "who": who, "conversation_id": e.get("conversation") or k,
                      "post_id": e.get("conversation") or k, "type": "mentions" if e.get("kind") == "mention" else "replies",
                      "answered": k in done or v11._h(who) in done})
    times = {}
    for i in items:
        times.setdefault(v11._h(i["who"]), i["ts"])
    return items, times


def panel_reply_queue(name):
    items, times = _engagement_items()
    window = int(_cfg(name).get("window_hours", 72))
    cut = v11.now() - timedelta(hours=window)
    open_ = [i for i in items if not i["answered"] and _ts(i["ts"]) and _ts(i["ts"]) >= cut]
    reg = v11.regulars(items)
    lines = [f"{len(open_)} open in the last {window}h ({sum(i['type'] == 'mentions' for i in open_)} mentions first)",
             v11.median_line(times, name=name)]
    dr = v11.drowning(open_)
    if dr and dr[0][1] > 1:
        lines.append("Most unanswered: " + ", ".join(f"thread {p} ({n})" for p, n in dr[:3]))
    if reg:
        lines.append("Regulars: " + ", ".join(f"@{h} {n}" for h, n in sorted(reg.items())[:8]))
    v11._save(os.path.join(root(name), "data", "last_pull.json"), {"at": v11.now().isoformat(), "items": len(items)})
    order = [f"@{i['who']} ({i['type']})" for i in v11.queue_sort(open_)][:20]
    return lines, {"queue": order, "regulars": reg}


def panel_fan_finder(name):
    r = root(name)
    shown = _j(os.path.join(r, "shown_leads.json"), {})
    st = v11.load_store(name)
    lines = []
    reuse = v11.reuse_pull(int(_cfg(name).get("reuse_pull_hours", 12)))
    lines.append(reuse["line"] if reuse else "Own engagement pull this run")
    hidden = [(x.get("username"), v11.hide_countdown(x.get("username") or "", name=name)) for x in shown.values()]
    hidden = [(h, n) for h, n in hidden if h and n]
    if hidden:
        lines.append(f"Resting: {len(hidden)}, e.g. @{hidden[0][0]} {hidden[0][1]}")
    if st["stages"]:
        lines.append("Stages: " + ", ".join(f"@{h} {s.get('stage') if isinstance(s, dict) else s}" for h, s in sorted(st["stages"].items())[:10]))
    if not _j(os.path.join(r, "my_likes.json"), {}):
        lines.append(v11.LIKES_BANNER)
    return lines, {"stage": st["stages"]}


def panel_rerun_picker(name):
    r = root(name)
    posts = _j(os.path.join(r, "posts.json"), {})
    shown = _j(os.path.join(r, "shown.json"), {})
    sponsors = _cfg(name).get("sponsor_terms") or []
    picks, flags = [], []
    vals = posts.values() if isinstance(posts, dict) else posts
    for p in vals:
        if not isinstance(p, dict):
            continue
        pid = str(p.get("id", ""))
        if shown and pid not in shown:
            continue
        t = p.get("text", "")
        f = [x for x in (v11.similar_to(t, picks), v11.sponsor_flag(t, sponsors)) if x]
        if f:
            flags.append(f"{pid}: {', '.join(f)}")
        picks.append(t)
    return ([f"Flags: {len(flags)}"] + flags[:5]) if picks else ["No picks saved yet"], {"flags": flags}


def panel_analytics_log(name):
    d = os.path.join(root(name), "data")
    rows = _csv(os.path.join(d, "posts_latest.csv"))
    posts = []
    for r in rows:
        ts = _ts(r.get("posted_at_et") or r.get("date") or "")
        if ts:
            posts.append({"ts": ts.isoformat(), "impressions": _num(r.get("impressions")),
                          "follows": _num(r.get("new_follows") or r.get("follows")), "id": r.get("post_id", "")})
    lines = []
    if posts:
        lines += ["Best hours: " + ", ".join(v11.best_times(posts))]
        fp = [x for x in v11.followers_per_post(posts) if x[0] > 0][:3]
        if fp:
            lines.append("Most follows from a post: " + ", ".join(f"{p} ({int(n)})" for n, p in fp))
    cfg = _cfg(name)
    if v11.show_500k_chart(cfg.get("has_monetization", cfg.get("monetized"))):
        lines.append("500K verified impressions chart: on")
    return lines or ["No posts pulled yet"], {}


PANELS = {"Follow Audit": panel_follow_audit, "Follow Finder": panel_follow_finder,
          "Shoutout Picker": panel_shoutout_picker, "Reply Queue": panel_reply_queue,
          "Fan Finder": panel_fan_finder, "Rerun Picker": panel_rerun_picker, "Analytics Log": panel_analytics_log}


# ---------- spend ----------

def todays_estimate(name):
    """Bot's own ledger (bot_spend) total for today, labeled as an estimate by spend_line."""
    led = _j(os.path.join(root(name), "data", "spend_ledger.json"), {})
    if v11.is_crew():
        led = _j(os.path.join(v11.home(), "dispatch", "spend_ledger.json"), {})
    day = led.get(datetime.now().date().isoformat(), {}) if isinstance(led, dict) else {}
    if isinstance(day, dict):
        return float(day.get("spent", day.get("total", 0)) or 0)
    return float(day or 0)


# ---------- the hook every bot calls ----------

def _html_block(name, lines, extra, status):
    li = "".join(f"<li>{html.escape(x)}</li>" for x in lines)
    fu = ""
    if v11.mode() == "own_page":
        due = v11.due_follow_ups(name)
        if due:
            fu = "<h3>Follow-ups due</h3><ul>" + "".join(f"<li>{html.escape(x)}</li>" for x in due) + "</ul>"
    never = sorted(v11.load_store(name)["never"])
    hide_js = ("<script>(function(){var n=" + json.dumps(never) + ";document.querySelectorAll('[data-user],[data-h]')"
               ".forEach(function(e){var h=(e.getAttribute('data-user')||e.getAttribute('data-h')||'').toLowerCase();"
               "if(n.indexOf(h.replace('@',''))>=0)e.style.display='none'})})();</script>") if never else ""
    return (f'<!--v11--><section class="v11"><style>.v11 .updated.stale{{color:#e8604c}}</style>'
            f'<p>{v11.last_updated(v11.now())}</p><p class="status">{html.escape(status)}</p>'
            f"<ul>{li}</ul>{fu}</section>{hide_js}<!--/v11-->")


def inject(page, block):
    if not page or not os.path.isfile(page):
        return False
    with open(page, encoding="utf-8") as f:
        s = f.read()
    a, b = s.find("<!--v11-->"), s.find("<!--/v11-->")
    if a >= 0 and b > a:
        s = s[:a] + s[b + len("<!--/v11-->"):]
    i = s.rfind("</body>")
    s = s[:i] + block + s[i:] if i >= 0 else s + block
    with open(page, "w", encoding="utf-8") as f:
        f.write(s)
    return True


# ---------- v1.1: page marks from KV before each run ----------

def _site_env():
    env = {}
    path = os.path.join(v11.home(), "site", "site.env")
    try:
        for line in open(path, encoding="utf-8"):
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.strip().split("=", 1)
                env[k.strip().removeprefix("export ").strip()] = v.strip().strip('"').strip("'")
    except OSError:
        pass
    return env


def _kv_get(keys, fetch=None):
    """Read checks:<key> values from the CHECKS namespace (same API calls as the live Scout sync).
    Returns {key: parsed json}; missing keys are left out. `fetch(path)` is swappable for tests."""
    import urllib.error
    import urllib.parse
    import urllib.request
    env = {**_site_env(), **os.environ}
    tok, acc = env.get("CLOUDFLARE_API_TOKEN"), env.get("CLOUDFLARE_ACCOUNT_ID")
    if fetch is None:
        if not tok or not acc:
            raise RuntimeError("no Cloudflare token in site.env")
        base = env.get("CF_API_BASE", "https://api.cloudflare.com/client/v4")

        def fetch(path):
            req = urllib.request.Request(base + "/accounts/" + acc + path, headers={"Authorization": "Bearer " + tok})
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8")
    title = env.get("KV_NAMESPACE_TITLE", "bot-lists-checks")
    nss = json.loads(fetch("/storage/kv/namespaces?per_page=100")).get("result", [])
    nid = next((n["id"] for n in nss if n.get("title") == title), None)
    if not nid:
        raise RuntimeError(f"KV namespace {title} not found")
    out = {}
    for k in keys:
        try:
            out[k] = json.loads(fetch(f"/storage/kv/namespaces/{nid}/values/" + urllib.parse.quote("checks:" + k, safe="")))
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                raise RuntimeError("the API token needs Workers KV Storage Read") from e
            # 404: nothing saved from the page yet
        except ValueError:
            pass
    return out


def before_run(name, fetch=None):
    """Call at the start of a run. Hosted only: pull this bot's page marks (never show, show again,
    stages, done, notes, follow-ups) from KV and merge them into its store, newest mark winning.
    Never raises and never blocks a run. Returns a one-line status or ''."""
    if fetch is None and not v11.hosted():
        return ""
    os.environ["CREW_BOT"] = name
    slug = name.lower().replace(" ", "-")
    keys = ["marks-" + slug] + (["never-scout", "never-scout-undo"] if name == "Follow Finder" else [])
    try:
        got = _kv_get(keys, fetch)
    except Exception as e:
        return f"Page marks not synced ({e}). The run goes on with marks saved here."
    kv = dict(got.get("marks-" + slug) or {})
    # the live Scout lists: never-scout {h: ts}, never-scout-undo {h: ts}
    legacy = got.get("never-scout") or {}
    undo = got.get("never-scout-undo") or {}
    if isinstance(legacy, list):
        legacy = {h: "" for h in legacy}
    nv = kv.setdefault("never", {})
    for h, ts in legacy.items():
        e = {"on": True, "ts": ts if isinstance(ts, str) else ""}
        if v11._when(e["ts"]) >= v11._when((nv.get(h) or {}).get("ts")):
            nv[h] = e
    for h, ts in (undo.items() if isinstance(undo, dict) else []):
        e = {"on": False, "ts": ts if isinstance(ts, str) else ""}
        if v11._when(e["ts"]) > v11._when((nv.get(h) or {}).get("ts")):
            nv[h] = e
    if not any(kv.get(k) for k in ("never", "done", "stages", "notes", "follow_ups", "hide_until")):
        return ""
    v11.merge_kv(kv, name)
    n = sum(len(kv.get(k) or {}) for k in ("never", "done", "stages", "notes", "follow_ups"))
    return f"Synced {n} page mark{'s' if n != 1 else ''} from your page."


def after_run(name, page=None, estimate=None, billed=None, status="Ran OK", reads=()):
    """Call at the end of a run. Never raises: v1.1 extras must not break a run."""
    os.environ["CREW_BOT"] = name
    try:
        lines, extra = PANELS[name](name)
    except Exception as e:  # keep the run's own report
        lines, extra = [f"v1.1 panel skipped: {e}"], {}
    lines = list(reads) + lines
    est = todays_estimate(name) if estimate is None else estimate
    spend = v11.spend_line(est, billed)
    out = {"bot": name, "at": v11.now().isoformat(), "status": status, "lines": lines, "spend": spend,
           "mode": v11.mode(), "extra": extra}
    try:
        v11._save(os.path.join(root(name), "reports", f"v11-{SLUG(name)}.json"), out)
        inject(page, _html_block(name, lines + [spend], extra, status))
    except Exception as e:
        lines.append(f"v1.1 page update skipped: {e}")
    chat = [f"{name}: {status}"] + lines + [spend]
    if v11.mode() == "chat":
        due = v11.due_follow_ups(name)
        chat += ["Follow-ups due:"] + due if due else []
    note = v11.billing_setup_note()
    if note:
        chat.append(note)
    return chat


def saved(name):
    return _j(os.path.join(root(name), "reports", f"v11-{SLUG(name)}.json"), None)


# ---------- site: Home, own page, Your week, Dispatch ----------

def week_text():
    secs = {}
    for n in v11.installed():
        s = saved(n)
        if s:
            secs[n] = s["lines"][:3] + [s["spend"]]
    if v11.is_crew():
        secs["Dispatch"] = health()
    return v11.your_week(secs)


def health(stale_hours=30):
    """Dispatch bot health: last run time and status per bot, from each bot's saved v1.1 report."""
    out = []
    for n in v11.installed():
        s = saved(n)
        if not s:
            out.append(f"{n}: no run saved yet")
            continue
        age = (v11.now() - _ts(s["at"])).total_seconds() / 3600
        flag = " (late)" if age > stale_hours else ""
        out.append(f"{n}: {s['status']}, {age:.0f}h ago{flag}")
    return out


def digest():
    if not v11.is_crew():
        return None
    led = _j(os.path.join(v11.home(), "dispatch", "spend_ledger.json"), {})
    today = datetime.now().date()
    rows, last = [], 0.0
    for k, v in (led.items() if isinstance(led, dict) else []):
        try:
            dd = (today - datetime.fromisoformat(k).date()).days
        except ValueError:
            continue
        amt = float(v.get("spent", 0) if isinstance(v, dict) else v or 0)
        if dd < 7:
            rows.append({"bot": "crew", "cost": amt, "kind": "X API"})
        elif dd < 14:
            last += amt
    os.environ.setdefault("CREW_BOT", "Dispatch")
    return v11.weekly_digest(rows, last)


def home_html(updated_cards):
    """Home panels from saved v1.1 reports (only installed bots). Empty when there is no Home."""
    parts = []
    for n in v11.home_panels():
        if n == "Bot health":
            body = health()
        elif n == "Cost digest":
            dg = digest()
            body = [dg] if isinstance(dg, str) else (dg or [])
        elif n == "Top fans":
            s = saved("Reply Queue") or {}
            body = [f"@{h} {c}" for h, c in list((s.get("extra") or {}).get("regulars", {}).items())[:5]] or ["none yet"]
        else:
            s = saved(n)
            body = (s["lines"][:4] + [s["spend"]]) if s else ["No run yet"]
        li = "".join(f"<li>{html.escape(str(x))}</li>" for x in body)
        href = PAGES.get(n)
        t = f'<a href="{href}">{html.escape(n)}</a>' if href else html.escape(n)
        parts.append(f'<div class="card v11h"><div class="t">{t}</div><ul class="m">{li}</ul></div>')
    due = []
    for n in v11.installed():
        due += v11.due_follow_ups(n)
    if due and parts:
        parts.append('<div class="card v11h"><div class="t">Follow-ups due</div><ul class="m">'
                     + "".join(f"<li>{html.escape(x)}</li>" for x in due) + "</ul></div>")
    return "\n".join(parts)


def main(argv):
    if argv[:1] == ["after"] and len(argv) > 1:
        print("\n".join(after_run(argv[1])))
    elif argv[:1] == ["week"]:
        print(week_text())
    elif argv[:1] == ["health"]:
        print("\n".join(health()))
    elif argv[:1] == ["digest"]:
        print(digest() or "Digest is a Dispatch (crew) feature.")
    else:
        print(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])


# ---------- 7-day totals for Your week and Home ----------

def _when(ts):
    if isinstance(ts, (int, float)):
        return datetime.fromtimestamp(ts, v11.UTC)
    return _ts(ts)


def done_since(name, days=7):
    """Marks done (chat or page) in the last `days` days."""
    if name not in v11.installed():
        return None
    cut = datetime.now(v11.UTC) - timedelta(days=days)
    return sum(1 for t in (v11.load_store(name).get("done") or {}).values() if (_when(t) or cut) > cut)


def spend_days(days=7):
    """(spent over the last `days` days, daily cap or None). Crew ledger when crewed, else each bot's own ledger."""
    today = datetime.now().date()
    keep = {(today - timedelta(d)).isoformat() for d in range(days)}
    if v11.is_crew():
        leds = [_j(os.path.join(v11.home(), "dispatch", "spend_ledger.json"), {})]
        cap = _j(os.path.join(v11.home(), "dispatch", "crew.json"), {}).get("daily_spend_cap")
    else:
        roots = sorted({root(n) for n in v11.installed()})
        leds = [_j(os.path.join(r, "data", "spend_ledger.json"), {}) for r in roots]
        caps = [_j(os.path.join(r, "config.json"), {}).get("daily_spend_cap") for r in roots]
        caps = [float(c) for c in caps if isinstance(c, (int, float))]
        cap = sum(caps) if caps else None
    tot = 0.0
    for led in leds:
        for k, v in (led.items() if isinstance(led, dict) else []):
            if k in keep:
                tot += float((v.get("spent", v.get("total", 0)) if isinstance(v, dict) else v) or 0)
    return tot, (float(cap) if cap is not None else None)


def follow_events(days=7):
    """Follow Audit events.csv over the last `days` days -> {new, unfollowed, gone}."""
    if "Follow Audit" not in v11.installed():
        return None
    cut = datetime.now(v11.UTC) - timedelta(days=days)
    out = {"new": 0, "unfollowed": 0, "gone": 0}
    for r in _csv(os.path.join(root("Follow Audit"), "data", "events.csv")):
        t = _ts(r.get("ts") or "")
        if not t or t < cut:
            continue
        e = (r.get("event") or "").lower()
        if e in ("new_follower", "followed_you", "follow"):
            out["new"] += 1
        elif e in ("unfollowed_you", "unfollow"):
            out["unfollowed"] += 1
        elif e in ("gone", "account_gone", "suspended", "deactivated"):
            out["gone"] += 1
    return out


def _own_posts():
    """The owner's own saved posts, merged by id from Reply Queue and Rerun Picker posts.json ($0)."""
    out = {}
    for n in ("Rerun Picker", "Reply Queue"):
        if n in v11.installed():
            d = _j(os.path.join(root(n), "posts.json"), {})
            for k, v in (d.items() if isinstance(d, dict) else []):
                if isinstance(v, dict):
                    out.setdefault(k, {}).update({a: b for a, b in v.items() if b is not None or a not in out.get(k, {})})
    return out


def _recent(posts, days):
    cut = datetime.now(v11.UTC) - timedelta(days=days)
    return {k: v for k, v in posts.items() if (_ts(v.get("created") or "") or cut) > cut}


def replies_handled(days=7):
    """Reply Queue items from the last `days` days handled by a reply (your saved posts), a like (my_likes.json)
    or a Done mark. Each item counts once, in that order. None when Reply Queue isn't installed."""
    if "Reply Queue" not in v11.installed():
        return None
    r = root("Reply Queue")
    ev = _j(os.path.join(r, "events.json"), {})
    cut = datetime.now(v11.UTC) - timedelta(days=days)
    items = [k for k, e in ev.items() if isinstance(e, dict) and e.get("kind") != "like"
             and (_ts((e.get("created") or "").replace("Z", "+00:00")) or cut) > cut]
    rto = {v.get("replied_to") for v in _own_posts().values() if v.get("kind") == "reply" and v.get("replied_to")}
    likes = _j(os.path.join(r, "my_likes.json"), [])
    likes = set(likes if isinstance(likes, list) else likes.keys() if isinstance(likes, dict) else [])
    done = v11.load_store("Reply Queue").get("done") or {}
    users = _j(os.path.join(r, "users.json"), {})
    rep = [i for i in items if i in rto]
    lk = [i for i in items if i not in rto and i in likes]
    def marked(i):
        who = (users.get(ev[i].get("author")) or {}).get("username") or ""
        return i in done or (who and v11._h(who) in done)
    mk = [i for i in items if i not in rto and i not in likes and marked(i)]
    return {"items": len(items), "replied": len(rep), "liked": len(lk), "marked": len(mk), "done": len(rep) + len(lk) + len(mk)}


def shoutouts_week(days=7):
    """Shoutouts counted from your own posts: a post (not the auto @prefix of a reply) that says "shoutout" and tags an
    @handle. Goal is the owner's `weekly_goal` in Shoutout Picker's config (None = not set). Unused = this week's
    picks not tagged in any of those posts. None when Shoutout Picker isn't installed."""
    if "Shoutout Picker" not in v11.installed():
        return None
    posts, tagged = [], set()
    for k, v in sorted(_recent(_own_posts(), days).items()):
        t = v.get("text") or ""
        if v.get("kind") == "reply":
            t = re.sub(r"^(@\w+\s+)+", "", t)
        tags = re.findall(r"(?<!\w)@(\w{1,15})", t)
        if "shoutout" in t.lower() and tags:
            posts.append(k); tagged |= {x.lower() for x in tags}
    picks = _j(os.path.join(root("Shoutout Picker"), "queue.json"), [])
    picks = [p.get("username") for p in picks if isinstance(p, dict) and p.get("username")] if isinstance(picks, list) else []
    goal = _cfg("Shoutout Picker").get("weekly_goal")
    return {"posts": len(posts), "goal": goal if isinstance(goal, int) and goal > 0 else None,
            "unused": [h for h in picks if h.lower() not in tagged]}


def reruns_used(days=7):
    """Picks from the newest Rerun Picker picks file (picks_YYYY-MM-DD.csv, no .bak/.orig copies) that you quoted,
    reposted, reused the media of, or marked Done. Returns (used, picked) or None when Rerun Picker isn't installed."""
    if "Rerun Picker" not in v11.installed():
        return None
    r = root("Rerun Picker")
    files = sorted(f for f in os.listdir(os.path.join(r, "picks")) if re.fullmatch(r"picks_\d{4}-\d{2}-\d{2}\.csv", f)) \
        if os.path.isdir(os.path.join(r, "picks")) else []
    if not files:
        return (0, 0)
    rows = _csv(os.path.join(r, "picks", files[-1]))
    posts = _own_posts()
    recent = _recent(posts, days)
    done = v11.load_store("Rerun Picker").get("done") or {}
    used = 0
    for row in rows:
        url = row.get("post_url") or ""
        pid = url.rstrip("/").rsplit("/", 1)[-1]
        mk = set((posts.get(pid) or {}).get("media_keys") or [])
        hit = any(v.get("quoted") == pid or v.get("reposted") == pid or (mk and mk & set(v.get("media_keys") or []))
                  for k, v in recent.items() if k != pid)
        if hit or url in done or pid in done:
            used += 1
    return (used, len(rows))

