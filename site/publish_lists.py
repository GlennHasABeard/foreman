#!/usr/bin/env python3
"""
publish_lists.py
Copies the latest page from each bot into one folder, writes an index page,
and deploys the folder to Cloudflare Pages so every list has a stable link.

  python3 publish_lists.py            copy, index, deploy
  python3 publish_lists.py --dry-run  copy and index only, no deploy (local output only)

Settings come from the environment (Foreman writes them to site/site.env):
  BOTS_HOME       folder that holds the bot folders
  PAGES_PROJECT   your Cloudflare Pages project name
  LISTS_URL       your lists address, either https://lists.yourdomain.com or
                  https://<project>.pages.dev (both behind Cloudflare Access)
  CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID   stored secrets, never in files
The KV namespace for checkmarks is bound to the Pages project as CHECKS in the
Cloudflare dashboard, so no KV id is kept here.

Follow Audit writes no page of its own, so this script builds
headcount.html from its saved scan data. That step makes no X API calls.

Needs CLOUDFLARE_API_TOKEN and CLOUDFLARE_ACCOUNT_ID in the environment, and
Node.js for `npx wrangler`. Keep the site behind Cloudflare Access.
"""

import argparse
import csv
import html
import json
import os
import subprocess
import sys
from datetime import date, datetime

BOTS_HOME = os.environ.get("BOTS_HOME", "/workspace").rstrip("/")
SITE_DIR = os.environ.get("SITE_DIR", BOTS_HOME + "/site/public")
PROJECT = os.environ.get("PAGES_PROJECT", "")
BASE_URL = os.environ.get("LISTS_URL", "").rstrip("/")
FW_DIR = os.environ.get("FW_DIR", BOTS_HOME + "/follow-watch")
HEADCOUNT_PAGE = os.path.join(FW_DIR, "reports", "headcount.html")

PAGES = [
    # (published name, source file, title, when it updates)
    ("radar.html", BOTS_HOME + "/engagement/reports/mention_radar.html", "Reply Queue", "Runs on its schedule"),
    ("leads.html", BOTS_HOME + "/engagement/reports/warm_leads.html", "Fan Finder", "Runs on its schedule"),
    ("scout.html", BOTS_HOME + "/creator-scout/reports/creator_scout.html", "Follow Finder", "Runs on its schedule"),
    ("shoutouts.html", BOTS_HOME + "/shoutouts/weeks/shoutout_list.html", "Shoutout Picker", "Weekly"),
    ("reruns.html", BOTS_HOME + "/reruns/picks/reruns.html", "Rerun Picker", "Weekly"),
    ("headcount.html", HEADCOUNT_PAGE, "Follow Audit", "After each full scan"),
]

WORKER = """export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if ("__BASE__" && !"__BASE__".includes(".pages.dev") && url.hostname.endsWith(".pages.dev")) {
      return Response.redirect("__BASE__" + url.pathname + url.search, 302);
    }
    if (url.pathname === "/api/checks") return checks(request, env, url);
    return env.ASSETS.fetch(request);
  },
};

// Checkmarks for each list page, kept in the CHECKS KV namespace so they
// follow you across browsers and devices. Same Access login as the pages.
async function checks(request, env, url) {
  const h = { "content-type": "application/json", "cache-control": "no-store" };
  const out = (body, status) => new Response(body, { status: status || 200, headers: h });
  if (!env.CHECKS) return out('{"error":"no CHECKS binding"}', 503);
  const page = url.searchParams.get("page") || "";
  if (!/^[A-Za-z0-9_.:-]{1,80}$/.test(page)) return out('{"error":"bad page"}', 400);
  const key = "checks:" + page;
  if (request.method === "GET") {
    const v = await env.CHECKS.get(key);
    return out(v === null ? "null" : v);
  }
  if (request.method === "PUT") {
    const body = await request.text();
    if (body.length > 200000) return out('{"error":"too big"}', 413);
    let obj;
    try { obj = JSON.parse(body); } catch (e) { return out('{"error":"bad json"}', 400); }
    if (!obj || typeof obj !== "object" || Array.isArray(obj)) return out('{"error":"bad json"}', 400);
    await env.CHECKS.put(key, JSON.stringify(obj), { expirationTtl: 60 * 60 * 24 * 180 });
    return out('{"ok":true}');
  }
  return out('{"error":"method"}', 405);
}
"""

INDEX = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Bot Lists</title>
<style>
*{box-sizing:border-box}body{margin:0;font-size:15px;line-height:1.45;overflow-x:hidden}
.wrap{position:relative;max-width:560px;margin:0 auto;padding:28px 16px 48px}
.top{display:flex;align-items:center;gap:14px;margin-bottom:6px}
.sub{font-size:13px;margin:0 0 18px}
.card{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:16px 18px;margin-bottom:10px;text-decoration:none}
.t{font-size:16px}.m{color:var(--mute);font-size:11px;margin-top:2px}.go{font-size:22px}
.off{opacity:.45}
.wrap>*{position:relative;z-index:1}
</style>__THEME__</head><body><div class="wrap">
<div class="top"><h1>Bot lists</h1></div>
<p class="sub">Updated __NOW__. Each page refreshes when its bot runs.</p>
__CARDS__
</div></body></html>"""

# ----------------------------------------------------------------------------
# Look: one plain black and white template. White background, black text, gray
# lines, system fonts. No colors, logos, images or theme options.
# Added to every page in <head>, after the page's own styles, so it wins.
# ----------------------------------------------------------------------------

THEME_CSS = """
:root,:root *{--bg:#ffffff!important;--card:#ffffff!important;--chip:#f2f2f2!important;--ink:#000000!important;
--body:#000000!important;--mute:#555555!important;--line:#cccccc!important;--acc:#000000!important;--acc-fill:#000000!important;
--on-acc:#ffffff!important;--good:#000000!important;--draft:#f7f7f7!important}
html,body{background:#ffffff!important;color:#000000!important;
font-family:system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif!important}
*{font-family:inherit!important;box-shadow:none!important;text-shadow:none!important}
h1{color:#000000!important;font-weight:700!important;background:none!important;animation:none!important}
a{color:#000000!important}
.card,.row,.st,a.card,.lmenu,.draft{background:#ffffff!important;border:1px solid #cccccc!important;border-radius:6px!important}
a.card:hover,.lmenu a:hover{background:#f2f2f2!important}
.sub,.note,.m,.nm,.age span,.why,.count{color:#555555!important}
.c{background:#f2f2f2!important;color:#000000!important;border:1px solid #cccccc!important}
.tog,.seg button,input[type=search],.nv,.lnav button,.row button,.tabs button{background:#ffffff!important;color:#000000!important;
border:1px solid #cccccc!important;border-radius:6px!important}
.seg button.on,.nv.arm{background:#000000!important;color:#ffffff!important;border-color:#000000!important}
.tabs button.on{border-bottom:2px solid #000000!important}
input[type=checkbox]{accent-color:#000000!important;filter:grayscale(1)}
img,svg{filter:grayscale(1)}
.lnav,header{background:#ffffff!important;border-bottom:1px solid #cccccc!important}
.nvtoast{background:#000000!important;color:#ffffff!important}
.nvtoast button{color:#ffffff!important;text-decoration:underline}
"""

THEME_JS = """<script data-lists-theme></script>"""


def theme_head():
    return '<meta name="color-scheme" content="light"><style data-lists-theme>' + THEME_CSS + "</style>"

# ----------------------------------------------------------------------------
# Follow Audit page, built from Follow Audit's saved data. No API calls.
# ----------------------------------------------------------------------------

def _read_csv(path):
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _int(x):
    try:
        return int(x)
    except (TypeError, ValueError):
        return None


def _is_verified(u):
    return bool(u.get("verified")) or (u.get("verified_type") or "none") in ("blue", "business", "government")


def _nice(d):
    try:
        return date.fromisoformat(d[:10]).strftime("%b %d, %Y")
    except (TypeError, ValueError):
        return ""


def build_headcount():
    """Rebuild headcount.html when Follow Audit has newer data than the page."""
    state_path = os.path.join(FW_DIR, "data", "state.json")
    if not os.path.exists(state_path):
        return False
    if os.path.exists(HEADCOUNT_PAGE) and os.path.getmtime(HEADCOUNT_PAGE) >= os.path.getmtime(state_path):
        return False
    with open(state_path, encoding="utf-8") as f:
        state = json.load(f)
    last = state.get("last_full") or {}
    if not last:
        return False
    reports = os.path.join(FW_DIR, "reports")
    accounts = state.get("accounts", {})
    s = last.get("summary", {})
    prev = (state.get("prev_full") or {})
    ps = prev.get("summary") or {}

    def delta(k):
        if k not in ps:
            return ""
        dv = s.get(k, 0) - ps[k]
        return f"{dv:+,}" if dv else "no change"

    stats = [["Followers", s.get("followers", 0), delta("followers")],
             ["Following", s.get("following", 0), delta("following")],
             ["Mutuals", s.get("mutuals", 0), delta("mutuals")],
             ["Verified followers", s.get("verified_followers", 0), delta("verified_followers")],
             ["Not following back", s.get("not_following_back", 0), delta("not_following_back")]]

    nfb = [{"u": r["username"], "n": r["name"], "w": _int(r["days_waiting"]), "wm": r["minimum"] == "yes",
            "v": r["verified"] == "yes", "f": _int(r["followers"]) or 0, "lp": r["last_post"],
            "t": r["flags"].replace("; ", ", ")}
           for r in _read_csv(os.path.join(reports, "not_following_back.csv"))]

    def flagged(fname):
        out = []
        for r in _read_csv(os.path.join(reports, fname)):
            idle = r["idle_days"]
            why = ", ".join(x for x in (r["reasons"], r["spam_matches"]) if x).replace("; ", ", ")
            out.append({"u": r["username"], "n": r["name"], "sc": _int(r["score"]) or 0,
                        "t": r["tags"].replace("; ", ", "), "why": why, "lp": r["last_post"],
                        "i": -1 if idle == "never posted" else _int(idle),
                        "f": _int(r["followers"]) or 0, "v": r["verified"] == "yes", "m": r["mutual"] == "yes"})
        return out

    quiet = flagged("flagged_following.csv")
    bad = flagged("flagged_followers.csv")

    since = []
    prev_ts = prev.get("ts")
    if prev_ts:
        labels = {"unfollowed_you": "Unfollowed you", "followed_back": "Followed you back",
                  "new_mutual": "New mutual", "new_follower": "New follower", "gone": "Gone"}
        for e in _read_csv(os.path.join(FW_DIR, "data", "events.csv")):
            if e["ts"] <= prev_ts or e["event"] not in labels:
                continue
            u = (accounts.get(e["id"]) or {}).get("user", {})
            pm = u.get("public_metrics") or {}
            days = _int(e["days"])
            note = ""
            if e["event"] in ("unfollowed_you", "followed_back") and days is not None:
                note = f"{days}{'+' if e['days_min'] else ''} days"
            elif e["event"] == "gone":
                note = e["detail"]
            since.append({"u": e["username"], "n": e["name"] or u.get("name", ""), "e": e["event"],
                          "k": labels[e["event"]], "note": note, "f": pm.get("followers_count", 0),
                          "v": _is_verified(u), "d": e["date"]})

    data = {"me": (state.get("me") or {}).get("username", ""), "scan": _nice(last.get("date", "")),
            "prev": _nice(prev_ts or ""), "stats": stats, "nfb": nfb, "quiet": quiet, "bad": bad, "since": since}
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    os.makedirs(os.path.dirname(HEADCOUNT_PAGE), exist_ok=True)
    with open(HEADCOUNT_PAGE, "w", encoding="utf-8") as f:
        f.write(HEADCOUNT.replace("__DATA__", blob))
    st = os.stat(state_path)
    os.utime(HEADCOUNT_PAGE, (st.st_atime, st.st_mtime))
    return True


HEADCOUNT = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Follow Audit</title>
<style>
:root{--bg:#ffffff;--card:#ffffff;--ink:#000000;--mute:#555555;--line:#cccccc;--acc:#000000;--chip:#f2f2f2;--good:#000000}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif}
.wrap{max-width:860px;margin:0 auto}
.top{padding:16px 16px 4px}
h1{margin:0 0 2px;font-size:20px}.sub{color:var(--mute);font-size:13px;margin:0 0 12px}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:8px}
.st{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 12px}
.st b{display:block;font-size:20px;font-variant-numeric:tabular-nums}.st span{color:var(--mute);font-size:12px}
.st i{font-style:normal;font-size:12px;color:var(--mute);margin-left:4px}
header{background:var(--bg);border-bottom:1px solid var(--line);padding:12px 16px}
.tabs{display:flex;gap:6px;overflow-x:auto;padding-bottom:8px;scrollbar-width:none}
.tabs button{flex:none;border:0;background:none;color:var(--mute);font:inherit;font-weight:600;padding:6px 2px;margin-right:10px;border-bottom:2px solid transparent;cursor:pointer}
.tabs button.on{color:var(--ink);border-color:var(--acc)}
.bar{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
input[type=search]{flex:1 1 180px;min-width:0;padding:8px 10px;border:1px solid var(--line);border-radius:8px;background:var(--card);color:var(--ink);font:inherit}
.seg{display:flex;gap:4px;flex-wrap:wrap}
.seg button,.tog{border:1px solid var(--line);background:var(--card);color:var(--ink);padding:6px 10px;border-radius:8px;font:inherit;font-size:13px;cursor:pointer}
.seg button.on{background:var(--ink);color:var(--bg);border-color:var(--ink)}
.tog{display:flex;gap:6px;align-items:center}
.count{color:var(--mute);font-size:13px;margin-top:8px}
.note{color:var(--mute);font-size:13px;margin:0 0 8px}
main{padding:12px 16px 40px}
.row{display:grid;grid-template-columns:auto 1fr auto;gap:12px;align-items:center;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 12px;margin-bottom:6px}
.row.done{opacity:.38}.row.out{opacity:0;transform:translateX(24px);transition:opacity .25s,transform .25s}.row input{width:18px;height:18px;accent-color:var(--acc)}
a.h{color:var(--ink);font-weight:600;text-decoration:none}a.h:hover{color:var(--acc);text-decoration:underline}
.nm{color:var(--mute);font-size:13px;margin-left:6px}
.meta{display:flex;gap:6px;flex-wrap:wrap;margin-top:3px}
.c{background:var(--chip);border-radius:999px;padding:1px 8px;font-size:12px;color:var(--mute)}
.c.a{color:var(--acc)}.c.g{color:var(--good)}
.why{color:var(--mute);font-size:12px;margin-top:3px}
.age{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.age b{display:block;font-size:16px}.age span{font-size:12px;color:var(--mute)}
.more{display:block;width:100%;padding:10px;border:1px dashed var(--line);background:none;color:var(--ink);border-radius:10px;font:inherit;cursor:pointer}
.empty{color:var(--mute);padding:24px 0;text-align:center}
@media (max-width:520px){.nm{display:block;margin:0}}
</style></head><body>
<div class="wrap top"><h1>Follow Audit</h1><p class="sub" id="sub"></p><div class="stats" id="stats"></div></div>
<header><div class="wrap">
<div class="tabs" id="tabs"></div>
<p class="note" id="note"></p>
<div class="bar"><input type="search" id="q" placeholder="Search handle or name">
<div class="seg" id="seg"></div>
<label class="tog"><input type="checkbox" id="hide" checked> Hide checked</label></div>
<div class="count" id="count"></div>
</div></header>
<main><div class="wrap" id="list"></div></main>
<script>
const D=__DATA__;
const esc=s=>String(s??"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const num=n=>(n??0).toLocaleString();
let done={};try{done=JSON.parse(localStorage.getItem("hc_done")||"{}")}catch(e){}
const save=()=>{try{localStorage.setItem("hc_done",JSON.stringify(done))}catch(e){}};
const idleTxt=r=>r.i===-1?["never","posted"]:r.i==null?["?","last post"]:[num(r.i),"days quiet"];
const TABS={
 nfb:{name:"Not following back",rows:D.nfb,
  note:"You follow them, they don't follow you. Longest wait first. A + means the wait started before tracking did.",
  sort:(a,b)=>(b.w??-1)-(a.w??-1),
  chips:[["All",r=>1],["90 d+",r=>r.w>90],["31 to 90 d",r=>r.w>30&&r.w<=90],["8 to 30 d",r=>r.w>7&&r.w<=30],["7 d or less",r=>r.w!=null&&r.w<=7],["Verified",r=>r.v]],
  meta:r=>[r.v?'<span class="c a">verified</span>':"",`<span class="c">${num(r.f)} followers</span>`,r.lp?`<span class="c">last post ${esc(r.lp)}</span>`:"",r.t?`<span class="c">${esc(r.t)}</span>`:""],
  right:r=>[r.w==null?"?":num(r.w)+(r.wm?"+":""),"days waiting"]},
 quiet:{name:"Went quiet",rows:D.quiet,
  note:"Accounts you follow that were flagged. Longest silent first.",
  sort:(a,b)=>(b.i===-1?1e9:b.i??-1)-(a.i===-1?1e9:a.i??-1),
  chips:[["All",r=>1],["Never posted",r=>r.i===-1],["1 yr+",r=>r.i>=365],["90 to 364 d",r=>r.i>=90&&r.i<365],["Fake or spam",r=>/likely fake|spam/.test(r.t)],["Mutuals",r=>r.m]],
  meta:r=>[r.m?'<span class="c g">mutual</span>':"",r.v?'<span class="c a">verified</span>':"",`<span class="c">${num(r.f)} followers</span>`,`<span class="c">${esc(r.t)}</span>`],
  why:1,right:idleTxt},
 bad:{name:"Flagged followers",rows:D.bad,
  note:"Followers with fake, spam or inactivity signals. Highest score first.",
  sort:(a,b)=>b.sc-a.sc,
  chips:[["All",r=>1],["Likely fake",r=>/likely fake/.test(r.t)],["Spam signals",r=>/spam/.test(r.t)],["Watch",r=>/watch/.test(r.t)],["Never posted",r=>r.i===-1],["Dormant",r=>/dormant/.test(r.t)]],
  meta:r=>[r.m?'<span class="c g">mutual</span>':"",r.v?'<span class="c a">verified</span>':"",`<span class="c">${num(r.f)} followers</span>`,`<span class="c">${esc(r.t)}</span>`],
  why:1,right:r=>[num(r.sc),"score"]},
 since:{name:"Since last scan",rows:D.since,
  note:D.prev?`Changes since the scan on ${D.prev}.`:"Changes show up after the second full scan.",
  sort:(a,b)=>(b.d||"").localeCompare(a.d||""),
  chips:[["All",r=>1],["Unfollowed you",r=>r.e==="unfollowed_you"],["Followed back",r=>r.e==="followed_back"||r.e==="new_mutual"],["New followers",r=>r.e==="new_follower"],["Gone",r=>r.e==="gone"]],
  meta:r=>[`<span class="c ${r.e==="unfollowed_you"||r.e==="gone"?"a":"g"}">${esc(r.k)}</span>`,r.v?'<span class="c a">verified</span>':"",`<span class="c">${num(r.f)} followers</span>`],
  right:r=>r.note?[esc(r.note),r.e==="gone"?"":r.e==="unfollowed_you"?"followed you":"to follow back"]:[esc(r.d||""),""]}
};
let tab="nfb",chip=0,shown=150;
document.getElementById("sub").textContent=`@${D.me}. Full scan of ${D.scan}. Read-only. Checked rows hide and stay checked on every device.`;
document.getElementById("stats").innerHTML=D.stats.map(([l,v,d])=>`<div class="st"><b>${num(v)}${d?`<i>${esc(d)}</i>`:""}</b><span>${esc(l)}</span></div>`).join("");
function tabs(){document.getElementById("tabs").innerHTML=Object.entries(TABS).map(([k,t])=>`<button data-k="${k}" class="${k===tab?"on":""}">${esc(t.name)} (${num(t.rows.length)})</button>`).join("")}
function render(){
 const T=TABS[tab],q=document.getElementById("q").value.trim().toLowerCase(),hide=document.getElementById("hide").checked;
 document.getElementById("note").textContent=T.note;
 document.getElementById("seg").innerHTML=T.chips.map(([l],i)=>`<button data-i="${i}" class="${i===chip?"on":""}">${esc(l)}</button>`).join("");
 const f=T.chips[chip][1];
 const rows=T.rows.filter(r=>f(r)&&(!q||r.u.toLowerCase().includes(q)||(r.n||"").toLowerCase().includes(q))&&!(hide&&done[tab+":"+r.u])).sort(T.sort);
 document.getElementById("count").textContent=`${num(rows.length)} of ${num(T.rows.length)}`;
 const L=document.getElementById("list");
 if(!rows.length){L.innerHTML='<div class="empty">Nothing here.</div>';return}
 L.innerHTML=rows.slice(0,shown).map(r=>{const key=tab+":"+r.u,[b,s]=T.right(r);
  return `<div class="row${done[key]?" done":""}"><input type="checkbox" data-key="${esc(key)}"${done[key]?" checked":""}>
<div><a class="h" href="https://x.com/${esc(r.u)}" target="_blank" rel="noopener">@${esc(r.u)}</a><span class="nm">${esc(r.n)}</span>
<div class="meta">${T.meta(r).join("")}</div>${T.why&&r.why?`<div class="why">${esc(r.why)}</div>`:""}</div>
<div class="age"><b>${b}</b><span>${s}</span></div></div>`}).join("")+(rows.length>shown?`<button class="more" id="more">Show ${num(Math.min(150,rows.length-shown))} more</button>`:"");
}
document.getElementById("tabs").onclick=e=>{const k=e.target.dataset.k;if(k){tab=k;chip=0;shown=150;tabs();render()}};
document.getElementById("seg").onclick=e=>{const i=e.target.dataset.i;if(i!=null){chip=+i;shown=150;render()}};
document.getElementById("q").oninput=()=>{shown=150;render()};
const H=document.getElementById("hide");try{if(localStorage.getItem("hc_hide")==="0")H.checked=false}catch(e){}
H.onchange=()=>{try{localStorage.setItem("hc_hide",H.checked?"1":"0")}catch(e){}render()};
document.getElementById("list").onclick=e=>{if(e.target.id==="more"){shown+=150;render();return}
 const k=e.target.dataset&&e.target.dataset.key;if(!k)return;if(e.target.checked)done[k]=1;else delete done[k];save();
 const row=e.target.closest(".row");row.classList.toggle("done",e.target.checked);
 if(e.target.checked&&H.checked){row.classList.add("out");setTimeout(render,260)}};
tabs();render();
</script></body></html>"""


# Added to every bot page on the way to the site. Checked items hide right away,
# "Hide checked" starts on, and the setting is remembered per page on that phone.
# Pages without the toggle (Shoutout Picker, Rerun Picker) get one.
HIDE_SCRIPT = """<script data-lists-hide>(function(){
var K="lists_hide:"+location.pathname,on=true;try{on=localStorage.getItem(K)!=="0"}catch(e){}
var st=document.createElement("style");st.textContent="body.hide-done .card.done,body.hide-done .row.done{display:none}";document.head.appendChild(st);
var cb=document.getElementById("hide");
if(!cb){var lab=document.createElement("label");lab.className="tog";
lab.style.cssText="display:inline-flex;gap:6px;align-items:center;font-size:13px;border:1px solid var(--line);background:var(--card);color:var(--ink);padding:6px 10px;border-radius:8px;margin-bottom:12px";
lab.innerHTML='<input type="checkbox" id="hide"> Hide checked';
var sub=document.querySelector(".sub");if(sub&&sub.parentNode)sub.parentNode.insertBefore(lab,sub.nextSibling);else document.body.insertBefore(lab,document.body.firstChild);
cb=lab.querySelector("input");}
cb.checked=on;
cb.addEventListener("change",function(){document.body.classList.toggle("hide-done",cb.checked);try{localStorage.setItem(K,cb.checked?"1":"0")}catch(e){}});
cb.dispatchEvent(new Event("change"));
})();</script>"""


# Added to every bot page. Saves checkmarks to the site (CHECKS KV) as well as
# the browser, so they carry across browsers, devices and web addresses. If the
# site store isn't set up or can't be reached, the page keeps working on the
# browser copy alone.
SYNC_SCRIPT = """<script data-lists-sync>(function(){
if(typeof done==="undefined"||typeof render!=="function")return;
var KN=(typeof KEY!=="undefined")?KEY:"hc_done",API="/api/checks?page="+encodeURIComponent(KN),SY=KN+":synced";
var ok=false,dirty=false,t=null,orig=Storage.prototype.setItem;
function push(){clearTimeout(t);t=setTimeout(function(){fetch(API,{method:"PUT",credentials:"same-origin",
 headers:{"content-type":"application/json"},body:JSON.stringify(done)}).catch(function(){})},300)}
Storage.prototype.setItem=function(k,v){try{return orig.apply(this,arguments)}finally{if(k===KN){if(ok)push();else dirty=true}}};
fetch(API,{credentials:"same-origin",cache:"no-store"}).then(function(r){if(!r.ok)throw 0;return r.json()}).then(function(s){
 var synced=false;try{synced=localStorage.getItem(SY)==="1"}catch(e){}
 var m={},k,merge=!s||!synced||dirty;
 if(s&&typeof s==="object")for(k in s)m[k]=s[k];
 if(merge)for(k in done)m[k]=done[k];
 done=m;ok=true;
 try{orig.call(localStorage,KN,JSON.stringify(done));orig.call(localStorage,SY,"1")}catch(e){}
 if(merge)push();
 render();
}).catch(function(){});
})();</script>"""

# Added to every bot page: a bar at the top with a menu of all the lists.
NAV_SCRIPT = """<script data-lists-nav>(function(){
var P=__NAV__,cur=location.pathname.split("/").pop()||"index.html";
var css=".lnav{position:sticky;top:0;z-index:50;display:flex;align-items:center;gap:10px;height:48px;padding:0 12px;"+
"background:var(--bg,#ffffff);border-bottom:1px solid var(--line,#cccccc);font:15px/1.4 system-ui,-apple-system,'Segoe UI',sans-serif}"+
".lnav button{display:flex;align-items:center;gap:8px;border:1px solid var(--line,#cccccc);background:var(--card,#ffffff);color:var(--ink,#000000);"+
"border-radius:8px;padding:6px 12px;font:inherit;font-weight:600;cursor:pointer}"+
".lnav svg{width:18px;height:18px}.lnav .here{color:var(--mute,#555555);font-size:14px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}"+
".lmenu{position:absolute;top:52px;left:12px;min-width:230px;background:var(--card,#ffffff);border:1px solid var(--line,#cccccc);"+
"border-radius:12px;box-shadow:0 8px 28px rgba(0,0,0,.18);padding:6px;display:none}.lmenu.open{display:block}"+
".lmenu a{display:block;padding:11px 12px;border-radius:8px;color:var(--ink,#000000);text-decoration:none}"+
".lmenu a:hover{background:var(--chip,#f2f2f2)}.lmenu a.on{color:var(--acc,#000000);font-weight:600}"+
".lmenu hr{border:0;border-top:1px solid var(--line,#cccccc);margin:4px 6px}";
var st=document.createElement("style");st.textContent=css;document.head.appendChild(st);
var title="Lists";P.forEach(function(p){if(p[0]===cur)title=p[1]});
var bar=document.createElement("div");bar.className="lnav";
var b=document.createElement("button");b.type="button";b.setAttribute("aria-expanded","false");
b.innerHTML='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 7h16M4 12h16M4 17h16"/></svg>Lists';
var here=document.createElement("span");here.className="here";here.textContent=title;
var m=document.createElement("div");m.className="lmenu";
var h='<a href="./">All lists</a><hr>';
P.forEach(function(p){h+='<a href="'+p[0]+'"'+(p[0]===cur?' class="on"':'')+'>'+p[1]+'</a>'});
m.innerHTML=h;bar.appendChild(b);bar.appendChild(here);bar.appendChild(m);
document.body.insertBefore(bar,document.body.firstChild);
function set(o){m.classList.toggle("open",o);b.setAttribute("aria-expanded",o?"true":"false")}
b.addEventListener("click",function(e){e.stopPropagation();set(!m.classList.contains("open"))});
document.addEventListener("click",function(e){if(!m.contains(e.target))set(false)});
document.addEventListener("keydown",function(e){if(e.key==="Escape")set(false)});
})();</script>"""


def nav_script():
    items = [[name, title] for name, _src, title, _when in PAGES]
    return NAV_SCRIPT.replace("__NAV__", json.dumps(items))

# Added to the Follow Finder page only. A "Never show" button on each card saves
# the handle to the site store (page key never-scout). Follow Finder reads that
# list before each run and keeps those accounts out for good.
NEVER_SCRIPT = """<script data-lists-never>(function(){
if(typeof render!=="function")return;
var API="/api/checks?page=never-scout",LK="never-scout",never={},last=null,tt=null;
try{never=JSON.parse(localStorage.getItem(LK)||"{}")}catch(e){}
var st=document.createElement("style");
st.textContent=".nv{margin-top:8px;border:1px solid var(--line);background:none;color:var(--mute);border-radius:8px;padding:6px 10px;font:inherit;font-size:12px;cursor:pointer}"+
".nv.arm{color:#ffffff;background:var(--acc);border-color:var(--acc)}"+
".nvtoast{position:fixed;left:50%;bottom:20px;transform:translateX(-50%);max-width:calc(100% - 32px);background:var(--ink);color:var(--bg);"+
"padding:10px 14px;border-radius:10px;font-size:14px;display:none;gap:14px;align-items:center;z-index:60;box-shadow:0 6px 20px rgba(0,0,0,.25)}"+
".nvtoast button{background:none;border:0;color:var(--acc);font:inherit;font-weight:600;cursor:pointer;padding:0}";
document.head.appendChild(st);
var toast=document.createElement("div");toast.className="nvtoast";document.body.appendChild(toast);
function keep(){try{localStorage.setItem(LK,JSON.stringify(never))}catch(e){}}
function store(){keep();fetch(API,{method:"PUT",credentials:"same-origin",headers:{"content-type":"application/json"},body:JSON.stringify(never)}).catch(function(){})}
function handleOf(c){var a=c.querySelector("a.h");return a?a.textContent.replace(/^@/,"").trim():""}
function decorate(){document.querySelectorAll("#list .card").forEach(function(c){var h=handleOf(c);if(!h)return;
 if(never[h.toLowerCase()]){c.style.display="none";return}
 if(!c.querySelector(".nv")){var b=document.createElement("button");b.type="button";b.className="nv";b.setAttribute("data-h",h);b.textContent="Never show";c.appendChild(b)}})}
var orig=render;render=function(){var r=orig.apply(this,arguments);decorate();return r};
document.getElementById("list").addEventListener("click",function(e){var b=e.target.closest?e.target.closest(".nv"):null;if(!b)return;
 if(!b.classList.contains("arm")){b.classList.add("arm");b.textContent="Tap again to hide for good";
  setTimeout(function(){if(b.isConnected){b.classList.remove("arm");b.textContent="Never show"}},4000);return}
 var h=b.getAttribute("data-h");never[h.toLowerCase()]=new Date().toISOString().slice(0,10);store();last=h;render();
 toast.textContent="@"+h+" won't be shown again ";var u=document.createElement("button");u.type="button";u.textContent="Undo";toast.appendChild(u);
 toast.style.display="flex";clearTimeout(tt);tt=setTimeout(function(){toast.style.display="none"},6000)});
toast.addEventListener("click",function(e){if(e.target.tagName!=="BUTTON"||!last)return;
 delete never[last.toLowerCase()];store();last=null;toast.style.display="none";render()});
fetch(API,{credentials:"same-origin",cache:"no-store"}).then(function(r){if(!r.ok)throw 0;return r.json()}).then(function(s){
 if(s&&typeof s==="object"){for(var k in s)never[k]=s[k];keep()}render()}).catch(function(){});
render();
})();</script>"""


def copy_page(src, dst):
    with open(src, encoding="utf-8") as f:
        page = f.read()
    add = ""
    if "hc_hide" not in page and "data-lists-hide" not in page:
        add += HIDE_SCRIPT
    if "data-lists-sync" not in page:
        add += SYNC_SCRIPT
    if "data-lists-nav" not in page:
        add += nav_script()
    if os.path.basename(dst) == "scout.html" and "data-lists-never" not in page:
        add += NEVER_SCRIPT
    if "data-lists-theme" not in page:
        add += THEME_JS
        if "</head>" in page:
            i = page.find("</head>")
            page = page[:i] + theme_head() + page[i:]
    # pages built before hosting was turned on still carry the local sentence
    page = page.replace("Checkmarks stay in this browser only.", "Checkmarks sync across your devices.")
    if add and "</body>" in page:
        i = page.rfind("</body>")
        page = page[:i] + add + page[i:]
    with open(dst, "w", encoding="utf-8") as f:
        f.write(page)


# ----------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    os.makedirs(SITE_DIR, exist_ok=True)
    try:
        if build_headcount():
            print("Built headcount.html from the latest Follow Audit scan.")
    except Exception as e:  # never let the Follow Audit page block the other lists
        print(f"Skipped headcount.html: {e}", file=sys.stderr)
    cards, copied = [], []
    for name, src, title, when in PAGES:
        dst = os.path.join(SITE_DIR, name)
        if os.path.exists(src):
            copy_page(src, dst)
            copied.append(name)
        if os.path.exists(dst):
            ts = datetime.fromtimestamp(os.path.getmtime(src if os.path.exists(src) else dst))
            cards.append(f'<a class="card" href="{name}"><div><div class="t">{html.escape(title)}</div>'
                         f'<div class="m">{html.escape(when)}. Last update {ts.strftime("%a %b %d, %I:%M %p")}</div></div>'
                         f'<span class="go">&rsaquo;</span></a>')
        else:
            cards.append(f'<div class="card off"><div><div class="t">{html.escape(title)}</div>'
                         f'<div class="m">No list yet</div></div></div>')
    now = datetime.now().strftime("%a %b %d, %I:%M %p")
    with open(os.path.join(SITE_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(INDEX.replace("__THEME__", theme_head()).replace("__NOW__", now)
                .replace("__CARDS__", "\n".join(cards)))
    # with a custom domain, send every pages.dev address to it, so the lists only
    # ever load behind Cloudflare Access. With pages.dev, protect *.pages.dev in Access.
    with open(os.path.join(SITE_DIR, "_worker.js"), "w", encoding="utf-8") as f:
        f.write(WORKER.replace("__BASE__", BASE_URL))
    # never cache, so the phone always shows the latest run
    with open(os.path.join(SITE_DIR, "_headers"), "w", encoding="utf-8") as f:
        f.write("/*\n  Cache-Control: no-store\n  X-Robots-Tag: noindex\n")
    print(f"Copied: {', '.join(copied) or 'nothing new'}")
    if a.dry_run:
        print(f"Dry run. Site folder ready at {SITE_DIR}")
        return
    for k in ("PAGES_PROJECT", "LISTS_URL", "CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ACCOUNT_ID"):
        if not os.environ.get(k):
            raise SystemExit(f"{k} is not set. Run Foreman hosting setup first (tokens go in stored secrets).")
    cmd = ["npx", "--yes", "wrangler@3", "pages", "deploy", SITE_DIR, "--project-name", PROJECT,
           "--branch", "main", "--commit-dirty=true"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.stderr.write(r.stdout[-2000:] + r.stderr[-2000:])
        raise SystemExit("Deploy failed. The pages are still in the site folder.")
    print(f"Published. Index: {BASE_URL}/")
    for name in copied:
        print(f"  {BASE_URL}/{name}")


if __name__ == "__main__":
    main()
