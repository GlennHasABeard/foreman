#!/usr/bin/env python3
"""v1.1 template pages. Plain light and dark theme, real buttons, Last updated and a
status line on every page. Stdlib only, no X API calls.

Each page is built from the DATA the bot already embeds in its own report page
(`const DATA=...` / `const D=...`) plus the bot's saved v1.1 report and its mark store.
Page marks (never show, show again, stages, done, follow-ups, notes) save to the
CHECKS KV through /api/checks?page=marks-<bot> when hosted, and the bot pulls them
back into its own files before every run (v11_wire.before_run). Without hosting the
page says which chat command does the same thing.

Nothing here holds an owner's settings, names or styling.
"""
import html
import json
import os
import re
from datetime import datetime
from urllib.parse import quote

def E(x, quote=True):
    """Escape page text. Page copy never shows a semicolon, so '; ' becomes ', '."""
    return html.escape(re.sub(r"\s*;\s*", ", ", str(x)), quote=quote)


RAW = html.escape  # posts, drafts and links exactly as written
SLUG = lambda n: n.lower().replace(" ", "-")  # noqa: E731
FILES = {"Reply Queue": "reply-queue.html", "Fan Finder": "fan-finder.html", "Follow Finder": "follow-finder.html",
         "Shoutout Picker": "shoutout-picker.html", "Rerun Picker": "rerun-picker.html", "Follow Audit": "follow-audit.html",
         "Analytics Log": "analytics-log.html"}
# Page names before v1.1. The site keeps a small redirect page under each old name.
OLD_FILES = {"Reply Queue": "radar.html", "Fan Finder": "leads.html", "Follow Finder": "scout.html",
             "Shoutout Picker": "shoutouts.html", "Rerun Picker": "reruns.html", "Follow Audit": "headcount.html",
             "Analytics Log": "analytics.html"}

CSS = """
:root{color-scheme:light;--bg:#ffffff;--card:#ffffff;--soft:#f3f4f6;--ink:#111111;--mute:#5b5f66;--line:#d9dbe0;
--acc:#111111;--on-acc:#ffffff;--coral:#d9534f;--warn:#8a5a00;--warnbg:#fff6e0}
:root[data-theme=dark]{color-scheme:dark;--bg:#121212;--card:#1b1b1b;--soft:#262626;--ink:#f1f1f1;--mute:#a3a7ad;
--line:#353535;--acc:#f1f1f1;--on-acc:#121212;--coral:#ff7a6b;--warn:#ffcf70;--warnbg:#2b2410}
@media(prefers-color-scheme:dark){:root:not([data-theme=light]){color-scheme:dark;--bg:#121212;--card:#1b1b1b;--soft:#262626;
--ink:#f1f1f1;--mute:#a3a7ad;--line:#353535;--acc:#f1f1f1;--on-acc:#121212;--coral:#ff7a6b;--warn:#ffcf70;--warnbg:#2b2410}}
*{box-sizing:border-box}html,body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.45 system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
a{color:inherit}.wrap{max-width:1400px;margin:0 auto;padding:0 14px 60px}
header.top{position:sticky;top:0;z-index:5;background:var(--bg);border-bottom:1px solid var(--line)}
nav.bar{display:flex;gap:4px;overflow-x:auto;max-width:1400px;margin:0 auto;padding:8px 14px;scrollbar-width:none}
nav.bar a{white-space:nowrap;text-decoration:none;padding:6px 10px;border-radius:8px;font-size:13px;color:var(--mute)}
nav.bar a.on{background:var(--soft);color:var(--ink);font-weight:600}
h1{font-size:24px;margin:14px 0 2px}h2{font-size:17px;margin:22px 0 8px}
.meta{display:flex;flex-wrap:wrap;gap:6px 14px;font-size:13px;color:var(--mute);margin-bottom:6px}
.updated.stale{color:var(--coral);font-weight:600}.status{font-size:13px;margin:0 0 10px;padding:8px 10px;
background:var(--soft);border-radius:8px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px;margin-bottom:10px}
.row{display:flex;gap:10px;align-items:flex-start}.grow{flex:1;min-width:0}
.who{font-weight:600;text-decoration:none;cursor:pointer}.nm{color:var(--mute);font-size:13px}
.txt{margin:6px 0;white-space:pre-wrap;overflow-wrap:anywhere}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin:6px 0}
.chip{font-size:12px;padding:2px 8px;border-radius:999px;background:var(--soft);border:1px solid var(--line)}
.chip.strong{background:var(--acc);color:var(--on-acc);border-color:var(--acc)}
.chip.flag{background:var(--warnbg);color:var(--warn);border-color:var(--warn)}
.btns{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}
button,.btn{font:inherit;font-size:13px;padding:7px 12px;min-height:34px;border:1px solid var(--line);border-radius:8px;
background:var(--card);color:var(--ink);cursor:pointer;text-decoration:none;display:inline-flex;align-items:center;gap:6px}
.btn.pri,button.pri{background:var(--acc);color:var(--on-acc);border-color:var(--acc)}
button.on{background:var(--acc);color:var(--on-acc);border-color:var(--acc)}
textarea{width:100%;font:inherit;font-size:14px;padding:8px;border:1px solid var(--line);border-radius:8px;
background:var(--bg);color:var(--ink);min-height:62px;margin-top:6px}
select,input[type=search],input[type=text],input[type=date]{font:inherit;font-size:13px;padding:6px 8px;border:1px solid var(--line);
border-radius:8px;background:var(--card);color:var(--ink)}
.tools{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin:8px 0 12px}
.seg{display:inline-flex;border:1px solid var(--line);border-radius:8px;overflow:hidden}
.seg button{border:0;border-radius:0;min-height:32px}.seg button+button{border-left:1px solid var(--line)}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:8px;margin:8px 0}
.tile{border:1px solid var(--line);border-radius:10px;padding:10px 12px;background:var(--card)}
.tile b{display:block;font-size:22px}.tile span{font-size:12px;color:var(--mute)}
.warnbox{background:var(--warnbg);color:var(--warn);border:1px solid var(--warn);border-radius:10px;padding:10px 12px;margin:8px 0}
.note{font-size:13px;color:var(--mute)}ul.plain{margin:4px 0;padding-left:18px}
.done .txt,.done .who{opacity:.55;text-decoration:line-through}
.hide{display:none!important}
.toast{position:fixed;left:50%;bottom:18px;transform:translateX(-50%);background:var(--ink);color:var(--bg);padding:10px 14px;
border-radius:10px;display:none;gap:12px;align-items:center;z-index:20;max-width:calc(100% - 28px)}
.toast button{background:none;border:0;color:var(--bg);text-decoration:underline;padding:0;min-height:0}
.drawer{position:fixed;top:0;right:0;bottom:0;width:min(420px,100%);background:var(--card);border-left:1px solid var(--line);
z-index:30;transform:translateX(105%);transition:transform .2s;overflow:auto;padding:16px}
.drawer.open{transform:none}.drawer h3{margin:0 0 8px}
.panel .ctl{display:none;gap:6px}.customizing .panel .ctl{display:flex}.customizing .panel.off{opacity:.45;display:block!important}
.panel.off{display:none}
.bar7{display:flex;gap:4px;align-items:flex-end;height:60px}.bar7 i{flex:1;background:var(--acc);border-radius:3px 3px 0 0;min-height:2px}
.demo{position:fixed;right:10px;bottom:10px;font-size:11px;padding:3px 8px;border-radius:6px;background:var(--soft);
border:1px solid var(--line);color:var(--mute);z-index:4}
.strip{grid-template-columns:repeat(auto-fit,minmax(150px,1fr))}
.item{padding:8px 0;border-top:1px solid var(--line)}.item:first-of-type{border-top:0}.item .txt{margin:4px 0}.item .btns{margin-top:4px}
.tile .nm{margin-top:4px;font-size:12px}
.tbl{width:100%;border-collapse:collapse;font-size:14px}.tbl th,.tbl td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);
vertical-align:top;overflow-wrap:anywhere}.tbl th{font-size:12px;color:var(--mute);font-weight:600}.tbl td.n,.tbl th.n{text-align:right;white-space:nowrap}
.prog{height:12px;border-radius:999px;background:var(--soft);border:1px solid var(--line);overflow:hidden;margin:6px 0}
.prog i{display:block;height:100%;background:var(--acc)}
.chart{display:flex;gap:2px;align-items:flex-end;height:120px;border-bottom:1px solid var(--line);margin-top:6px}
.chart i{flex:1;background:var(--acc);border-radius:2px 2px 0 0;min-height:1px;opacity:.85}
.cols{display:grid;gap:12px;grid-template-columns:1fr}.cols>*{min-width:0}
.wk .card h2{margin:0 0 6px}.wk ul.plain li{overflow-wrap:anywhere}
@media(min-width:760px){div[id$="-list"],.cols,.wk,#panels{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;align-items:start}
div[id$="-list"]>.card,.wk>.card,#panels>.card{margin:0}#panels .panel.off{display:none}.customizing #panels .panel.off{display:block!important}}
@media(min-width:1200px){#panels,.wk{grid-template-columns:repeat(3,minmax(0,1fr))}}
@media(min-width:760px){#panels{display:block;columns:2;column-gap:12px}#panels>.card{break-inside:avoid;display:inline-block;width:100%;margin:0 0 12px}
#panels .panel.off{display:none}.customizing #panels .panel.off{display:inline-block!important}}
@media(min-width:1200px){#panels{columns:3}}
@media(max-width:560px){h1{font-size:21px}.btns .btn,.btns button{flex:1;justify-content:center}}
"""

# Shared page script: theme switch, marks (KV when hosted, this browser otherwise), toast.
JS = r"""
(function(){
var q=new URLSearchParams(location.search),r=document.documentElement;
var th=q.get("theme")||localStorage.getItem("v11-theme");if(th==="light"||th==="dark")r.setAttribute("data-theme",th);
window.V11={};var V=window.V11;V.page=document.body.getAttribute("data-marks");V.hosted=document.body.getAttribute("data-hosted")==="1"&&!q.has("local");V.preview=location.protocol==="file:";
V.m={never:{},done:{},stages:{},notes:{},follow_ups:{}};
function newer(a,b){return !b||(a&&a.ts>b.ts)}
V.merge=function(dst,src){if(!src)return dst;["never","done","stages","follow_ups"].forEach(function(k){var s=src[k]||{};dst[k]=dst[k]||{};
 for(var h in s){if(newer(s[h],dst[k][h]))dst[k][h]=s[h]}});dst.notes=dst.notes||{};var n=src.notes||{};
 for(var h in n){var have={};(dst.notes[h]=dst.notes[h]||[]).forEach(function(x){have[x.ts]=1});
  n[h].forEach(function(x){if(!have[x.ts])dst.notes[h].push(x)})}return dst};
try{V.merge(V.m,JSON.parse(document.getElementById("v11-marks").textContent))}catch(e){}
var LK="v11-marks-"+V.page;try{V.merge(V.m,JSON.parse(localStorage.getItem(LK)||"null"))}catch(e){}
V.api="/api/checks?page=marks-"+encodeURIComponent(V.page);
V.save=function(){try{localStorage.setItem(LK,JSON.stringify(V.m))}catch(e){}
 if(!V.hosted||V.preview)return;fetch(V.api,{method:"PUT",credentials:"same-origin",headers:{"content-type":"application/json"},body:JSON.stringify(V.m)})
 .then(function(r){if(!r.ok)throw 0;return r.json()}).then(function(s){if(s&&typeof s==="object"&&s.never){V.merge(V.m,s);try{localStorage.setItem(LK,JSON.stringify(V.m))}catch(e){}V.render()}}).catch(function(){V.offline()})};
V.set=function(kind,h,val){h=h.replace(/^@/,"").toLowerCase();var e={ts:new Date().toISOString()};for(var k in val)e[k]=val[k];
 V.m[kind][h]=e;V.save();V.render()};
V.on=function(kind,h){var e=V.m[kind][h.replace(/^@/,"").toLowerCase()];return !!(e&&e.on)};
V.stage=function(h){var e=V.m.stages[h.toLowerCase()];return e?e.stage:"new"};
V.offline=function(){var n=document.getElementById("v11-offline");if(n)n.classList.remove("hide")};
V.render=function(){(V.renderers||[]).forEach(function(f){f()})};V.renderers=[];
var t=document.createElement("div");t.className="toast";var tt;
document.addEventListener("DOMContentLoaded",function(){document.body.appendChild(t)});
V.toast=function(msg,undo){t.textContent=msg+" ";if(undo){var b=document.createElement("button");b.type="button";b.textContent="Undo";
 b.onclick=function(){undo();t.style.display="none"};t.appendChild(b)}t.style.display="flex";clearTimeout(tt);
 tt=setTimeout(function(){t.style.display="none"},6000)};
document.addEventListener("DOMContentLoaded",function(){var tb=document.getElementById("v11-theme");if(tb)tb.onclick=function(){var d=r.getAttribute("data-theme")==="dark"||
 (!r.getAttribute("data-theme")&&matchMedia("(prefers-color-scheme: dark)").matches);var n=d?"light":"dark";
 r.setAttribute("data-theme",n);try{localStorage.setItem("v11-theme",n)}catch(e){}}});
if(V.hosted&&!V.preview)fetch(V.api,{credentials:"same-origin",cache:"no-store"}).then(function(r){if(!r.ok)throw 0;return r.json()})
 .then(function(s){if(s&&typeof s==="object"){V.merge(V.m,s);try{localStorage.setItem(LK,JSON.stringify(V.m))}catch(e){}V.render()}})
 .catch(function(){V.offline()});else if(!V.hosted)document.addEventListener("DOMContentLoaded",V.offline);
document.addEventListener("DOMContentLoaded",function(){V.render()});
})();
"""


def store_to_marks(store):
    """Bot's file store (chat marks, merged KV) -> page marks, so chat marks show on the page."""
    m = {"never": {}, "done": {}, "stages": {}, "notes": {}, "follow_ups": {}}
    for h, ts in (store.get("never") or {}).items():
        m["never"][h] = {"on": True, "ts": _iso(ts)}
    for h, ts in (store.get("hide_until") or {}).items():
        m["never"].setdefault(h, {"on": False, "ts": "", "until": ts})
    for h, ts in (store.get("done") or {}).items():
        m["done"][h] = {"on": True, "ts": _iso(ts)}
    for h, st in (store.get("stages") or {}).items():
        m["stages"][h] = st if isinstance(st, dict) else {"stage": st, "ts": ""}
    for h, ns in (store.get("notes") or {}).items():
        m["notes"][h] = [n for n in ns if not n.get("due")]
        for n in ns:
            if n.get("due"):
                m["follow_ups"][h] = {"on": True, "due": n["due"], "ts": n["ts"], "text": n.get("text", "follow up")}
    for k, v in (store.get("tombstones") or {}).items():
        kind, _, h = k.partition(":")
        if kind in m and (h not in m[kind] or (m[kind][h].get("ts") or "") < v):
            m[kind][h] = {"on": False, "ts": v}
    return m


def _iso(ts):
    return ts if isinstance(ts, str) else ""


def extract(path, var="DATA"):
    """The JSON a bot page embeds as `const DATA=` (or `const D=`)."""
    try:
        with open(path, encoding="utf-8") as f:
            s = f.read()
    except OSError:
        return None
    m = re.search(r"const " + var + r"=(.*?);(?:const |let |var |\n|function )", s, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(1).replace("<\\/", "</"))
    except ValueError:
        return None


def nav(items, here):
    links = "".join(f'<a href="{E(href)}" class="{"on" if t == here else ""}">{E(t)}</a>' for t, href in items)
    return f'<header class="top"><nav class="bar">{links}</nav></header>'


def shell(title, slug, updated_html, status, body, marks, navitems, demo=False, offline_hint="", hosted=True):
    off = (f'<p id="v11-offline" class="note hide">Not hosted, or the sync is unreachable: marks stay in this browser. '
           f'{E(offline_hint)}</p>') if offline_hint else '<p id="v11-offline" class="hide"></p>'
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1"><title>{E(title)}</title>'
            f'<style>{CSS}</style></head><body data-marks="{E(slug)}" data-hosted="{1 if hosted else 0}">'
            f'<script type="application/json" id="v11-marks">{_j(marks)}</script><script>{JS}</script>'
            f'{nav(navitems, title)}<div class="wrap">'
            f'<h1>{E(title)}</h1><div class="meta">{updated_html}<button type="button" id="v11-theme" '
            f'aria-label="Light or dark">Light / dark</button></div><p class="status">{E(status)}</p>{off}{body}</div>'
            + ('<div class="demo">Demo data</div>' if demo else "") + "</body></html>")


def _j(x):
    return json.dumps(x, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def data_script(name, obj):
    return f'<script type="application/json" id="{name}">{_j(obj)}</script>'


def intent_reply(tweet_id, text=""):
    return f"https://x.com/intent/post?in_reply_to={quote(str(tweet_id))}" + (f"&text={quote(text)}" if text else "")


def intent_like(tweet_id):
    return f"https://x.com/intent/like?tweet_id={quote(str(tweet_id))}"


def intent_post(text, url=""):
    return "https://x.com/intent/post?text=" + quote(text) + (f"&url={quote(url)}" if url else "")


# ---------------------------------------------------------------- Reply Queue

def _medv(line):
    m = re.search(r"(\d+(?:\.\d+)?\s*(?:min|h|hours?|minutes?))", line or "")
    return m.group(1) if m else "–"


def snippet(text, words=6):
    w = re.sub(r"https?://\S+", "", str(text or "")).split()
    return " ".join(w[:words]) + ("…" if len(w) > words else "") if w else ""


def reply_queue(items, saved, post_text=None):
    """items: Reply Queue DATA rows {key, username, chips, text, links, g}.
    post_text: {post id: text} from the bot's posts.json, for the Drowning posts list."""
    post_text = post_text or {}
    ex = (saved or {}).get("extra") or {}
    regs = {k.lower(): v for k, v in (ex.get("regulars") or {}).items()}
    rows, posts = [], {}
    for i, x in enumerate(items or []):
        kind = ((x.get("chips") or [{}])[0].get("t") or "reply").lower()
        your = next((l["u"] for l in x.get("links") or [] if l.get("t") == "Your post"), "")
        if your:
            posts.setdefault(your, []).append(x["username"])
        rows.append({"k": str(x.get("key", i)), "u": x.get("username", ""), "kind": kind, "i": i,
                     "chips": [c.get("t", "") for c in x.get("chips") or []][1:], "text": x.get("text", ""),
                     "open": (x.get("links") or [{}])[0].get("u", ""), "your": your, "reg": regs.get(x.get("username", "").lower(), 0),
                     "g": x.get("g", "")})
    drown = sorted(((len(v), p, v) for p, v in posts.items()), reverse=True)[:5]
    med = next((l for l in (saved or {}).get("lines", []) if l.startswith("Median time to reply")), "Median time to reply: no done marks yet")
    def ptitle(url):
        pid = url.rstrip("/").split("/")[-1].split("?")[0]
        return snippet(post_text.get(pid, "")) or f"Post ending {pid[-4:]}"
    dr = "".join(f'<li><a href="{E(p)}" target="_blank" rel="noopener">{E(ptitle(p))}</a>: {n} waiting '
                 f'({E(", ".join("@" + u for u in sorted(set(v))[:4]))})</li>' for n, p, v in drown if n > 1)
    body = (f'<div class="tiles"><div class="tile"><b id="rq-open">{len(rows)}</b><span>waiting on a reply</span></div>'
            f'<div class="tile"><b id="rq-med">{E(_medv(med))}</b>'
            f'<span>median time to reply (7 days)</span></div><div class="tile"><b>{len([r for r in rows if r["reg"]])}</b>'
            f'<span>from regulars</span></div></div>'
            + (f'<h2>Drowning posts</h2><ul class="plain">{dr}</ul>' if dr else "")
            + '<h2>Queue</h2><div class="tools"><div class="seg" id="rq-f">'
            + "".join(f'<button type="button" data-f="{f}" class="{"on" if f == "all" else ""}">{t}</button>'
                      for f, t in (("all", "All"), ("mention", "Mentions"), ("reply", "Replies"), ("quote", "Quotes"), ("regular", "Regulars")))
            + '</div><select id="rq-s" aria-label="Sort"><option value="m">Mentions first</option><option value="new">Newest</option>'
              '<option value="old">Oldest</option><option value="reg">Regulars first</option></select>'
              '<label class="note"><input type="checkbox" id="rq-done"> show done</label></div><div id="rq-list"></div>'
            + data_script("rq-data", rows) + "<script>" + r"""
(function(){var D=JSON.parse(document.getElementById("rq-data").textContent),V=window.V11,f="all",s="m";
function esc(t){var d=document.createElement("div");d.textContent=t;return d.innerHTML}
function ri(id,t){return "https://x.com/intent/post?in_reply_to="+encodeURIComponent(id)+(t?"&text="+encodeURIComponent(t):"")}
function card(x){var done=V.on("done",x.u),dr=localStorage.getItem("v11-draft-"+x.k)||"";
 return '<div class="card'+(done?' done':'')+'" data-h="'+esc(x.u)+'"><div class="row"><div class="grow">'+
 '<a class="who" href="https://x.com/'+esc(x.u)+'" target="_blank" rel="noopener">@'+esc(x.u)+'</a> <span class="nm">'+esc(x.kind)+'</span>'+
 '<div class="chips">'+(x.reg?'<span class="chip strong">Regular · '+x.reg+' conversations</span>':'')+
 x.chips.map(function(c){return '<span class="chip">'+esc(c)+'</span>'}).join("")+'</div>'+
 '<div class="txt">'+esc(x.text)+'</div><label class="note">Your reply draft</label><textarea data-k="'+esc(x.k)+'">'+esc(dr)+'</textarea>'+
 '<div class="btns"><a class="btn pri" data-act="reply" target="_blank" rel="noopener" href="'+ri(x.k,dr)+'">Reply</a>'+
 '<a class="btn" data-act="like" target="_blank" rel="noopener" href="https://x.com/intent/like?tweet_id='+encodeURIComponent(x.k)+'">Like</a>'+
 '<a class="btn" data-act="open" target="_blank" rel="noopener" href="'+esc(x.open)+'">Open</a>'+
 '<button type="button" data-done="'+esc(x.u)+'">'+(done?'Done ✓':'Mark done')+'</button></div></div></div></div>'}
function render(){var L=D.filter(function(x){return (f==="all"||(f==="regular"?x.reg>0:x.kind===f))&&
 (document.getElementById("rq-done").checked||!V.on("done",x.u))});
 L.sort(function(a,b){if(s==="m")return (b.kind==="mention")-(a.kind==="mention")||a.i-b.i;if(s==="old")return b.i-a.i;
  if(s==="reg")return b.reg-a.reg||a.i-b.i;return a.i-b.i});
 document.getElementById("rq-list").innerHTML=L.map(card).join("")||'<p class="note">Nothing waiting. Nice.</p>';
 document.getElementById("rq-open").textContent=D.filter(function(x){return !V.on("done",x.u)}).length}
V.renderers.push(render);
document.getElementById("rq-f").onclick=function(e){var b=e.target.closest("button");if(!b)return;f=b.getAttribute("data-f");
 this.querySelectorAll("button").forEach(function(x){x.classList.toggle("on",x===b)});render()};
document.getElementById("rq-s").onchange=function(){s=this.value;render()};document.getElementById("rq-done").onchange=render;
document.getElementById("rq-list").addEventListener("input",function(e){if(e.target.tagName!=="TEXTAREA")return;var k=e.target.getAttribute("data-k");
 localStorage.setItem("v11-draft-"+k,e.target.value);var a=e.target.parentNode.querySelector('[data-act=reply]');a.href=ri(k,e.target.value)});
document.getElementById("rq-list").addEventListener("click",function(e){var b=e.target.closest("[data-done]");if(!b)return;var h=b.getAttribute("data-done");
 var was=V.on("done",h);V.set("done",h,{on:!was});if(!was)V.toast("Marked @"+h+" done.",function(){V.set("done",h,{on:false})})});
})();</script>""")
    return body


# ---------------------------------------------------------------- Fan Finder

def fan_finder(items, saved, store):
    lines = (saved or {}).get("lines", [])
    rows = [{"u": x.get("username", ""), "chips": [c.get("t", "") for c in x.get("chips") or []], "text": x.get("text", ""),
             "links": x.get("links") or [], "i": i} for i, x in enumerate(items or [])]
    left = []
    for h, u in (store.get("hide_until") or {}).items():
        left.append({"u": h, "why": "resting after being shown", "until": u})
    for h in (store.get("never") or {}):
        left.append({"u": h, "why": "you hid them", "until": ""})
    extra_left = ((saved or {}).get("extra") or {}).get("left_out") or []
    body = ("".join(f'<p class="note">{E(l)}</p>' for l in lines if "pull" in l.lower() or "likes" in l.lower())
            + '<div class="tools"><div class="seg" id="ff-st">'
            + "".join(f'<button type="button" data-s="{s}" class="{"on" if s == "all" else ""}">{s.title()}</button>'
                      for s in ("all", "new", "engaged", "talked", "done"))
            + '</div></div><div id="ff-list"></div><h2>Why left out</h2><div id="ff-left"></div>'
            + data_script("ff-data", rows) + data_script("ff-left-data", left + extra_left) + "<script>" + r"""
(function(){var D=JSON.parse(document.getElementById("ff-data").textContent),L=JSON.parse(document.getElementById("ff-left-data").textContent),
V=window.V11,f="all",ST=["new","engaged","talked","done"];
function esc(t){var d=document.createElement("div");d.textContent=t;return d.innerHTML}
function days(u){if(!u)return "";var d=Math.ceil((new Date(u)-new Date())/864e5);return d>0?"back in "+d+" days":""}
function render(){var rows=D.filter(function(x){return !V.on("never",x.u)&&(f==="all"||V.stage(x.u)===f)});
 document.getElementById("ff-list").innerHTML=rows.map(function(x){var st=V.stage(x.u);return '<div class="card" data-h="'+esc(x.u)+'">'+
 '<a class="who" href="https://x.com/'+esc(x.u)+'" target="_blank" rel="noopener">@'+esc(x.u)+'</a>'+
 '<div class="chips"><span class="chip strong">Why: '+esc(x.chips.slice(2).join(" + ")||"engaged with you")+'</span>'+
 x.chips.slice(0,2).map(function(c){return '<span class="chip">'+esc(c)+'</span>'}).join("")+'</div><div class="txt">'+esc(x.text)+'</div>'+
 '<div class="btns"><label class="note">Stage <select data-stage="'+esc(x.u)+'">'+ST.map(function(s){return '<option'+(s===st?' selected':'')+'>'+s+'</option>'}).join("")+'</select></label>'+
 x.links.map(function(l){return '<a class="btn" target="_blank" rel="noopener" href="'+esc(l.u)+'">'+esc(l.t)+'</a>'}).join("")+
 '<button type="button" data-hide="'+esc(x.u)+'">Hide</button></div></div>'}).join("")||'<p class="note">No one in this stage.</p>';
 var left=L.filter(function(x){return x.why!=="you hid them"||V.on("never",x.u)});
 D.forEach(function(x){if(V.on("never",x.u)&&!left.some(function(y){return y.u===x.u.toLowerCase()}))left.push({u:x.u,why:"you hid them"})});
 document.getElementById("ff-left").innerHTML=left.map(function(x){return '<div class="card row"><div class="grow"><b>@'+esc(x.u)+'</b> <span class="nm">'+
 esc(x.why)+(x.until?", "+days(x.until):"")+(x.pos?", queue position "+x.pos:"")+'</span></div><button type="button" data-again="'+esc(x.u)+'">Show again</button></div>'}).join("")||
 '<p class="note">Nobody left out right now.</p>'}
V.renderers.push(render);
document.getElementById("ff-st").onclick=function(e){var b=e.target.closest("button");if(!b)return;f=b.getAttribute("data-s");
 this.querySelectorAll("button").forEach(function(x){x.classList.toggle("on",x===b)});render()};
document.addEventListener("change",function(e){var h=e.target.getAttribute&&e.target.getAttribute("data-stage");if(h)V.set("stages",h,{stage:e.target.value})});
document.addEventListener("click",function(e){var b=e.target.closest("[data-hide],[data-again]");if(!b)return;
 if(b.hasAttribute("data-hide")){var h=b.getAttribute("data-hide");V.set("never",h,{on:true});V.toast("@"+h+" hidden.",function(){V.set("never",h,{on:false})})}
 else{var h=b.getAttribute("data-again");V.set("never",h,{on:false});L=L.filter(function(x){return x.u!==h});render();V.toast("@"+h+" will show again.")}});
})();</script>""")
    return body


# ---------------------------------------------------------------- Follow Finder

def follow_finder(items, saved, follows_chip):
    rows = []
    for i, c in enumerate(items or []):
        fol = c.get("followers") or 0
        likes = [p.get("likes", 0) for p in c.get("top_posts") or []]
        eng = (sum(likes) / len(likes) / fol * 100) if likes and fol else 0
        rows.append({"u": c.get("username", ""), "n": c.get("name", ""), "f": fol, "fg": c.get("following", 0),
                     "bio": c.get("bio", ""), "you": bool(c.get("follows_you")) and follows_chip, "eng": round(eng, 2),
                     "post": ((c.get("top_posts") or [{}])[0]).get("text", ""), "pid": ((c.get("top_posts") or [{}])[0]).get("id", ""), "i": i})
    strip = no_paid(next((l for l in (saved or {}).get("lines", []) if "kept" in l.lower() or "pre-screen" in l.lower()), ""))
    body = (tiles_html([("picks this run", len(rows)), ("followed you already", sum(1 for r in rows if r["you"]))])
            + (f'<p class="note">{E(strip)}</p>' if strip else "")
            + '<div class="tools"><div class="seg" id="sc-t"><button type="button" class="on" data-t="list">Shortlist</button>'
              '<button type="button" data-t="never">Never show <span id="sc-nc"></span></button></div>'
              '<select id="sc-s"><option value="eng">Engagement per follower</option><option value="f">Followers</option>'
              '<option value="i">As found</option></select></div><div id="sc-list"></div>'
            + data_script("sc-data", rows) + "<script>" + r"""
(function(){var D=JSON.parse(document.getElementById("sc-data").textContent),V=window.V11,tab="list",s="eng";
function esc(t){var d=document.createElement("div");d.textContent=t;return d.innerHTML}
function n(x){return x>=1e3?(x/1e3).toFixed(x>=1e4?0:1)+"K":String(x)}
function render(){var nv=Object.keys(V.m.never).filter(function(h){return V.m.never[h].on});document.getElementById("sc-nc").textContent="("+nv.length+")";
 if(tab==="never"){document.getElementById("sc-list").innerHTML=nv.map(function(h){return '<div class="card row"><div class="grow"><b>@'+esc(h)+
  '</b> <span class="nm">hidden '+esc((V.m.never[h].ts||"").slice(0,10))+'</span></div><button type="button" data-undo="'+esc(h)+'">Undo</button></div>'}).join("")||
  '<p class="note">Nobody hidden.</p>';return}
 var L=D.filter(function(x){return !V.on("never",x.u)}).sort(function(a,b){return s==="i"?a.i-b.i:(b[s]-a[s])});
 document.getElementById("sc-list").innerHTML=L.map(function(x){return '<div class="card" data-h="'+esc(x.u)+'"><a class="who" target="_blank" rel="noopener" href="https://x.com/'+
 esc(x.u)+'">@'+esc(x.u)+'</a> <span class="nm">'+esc(x.n)+'</span><div class="chips"><span class="chip strong">'+x.eng+'% engagement</span>'+
 '<span class="chip">'+n(x.f)+' followers</span>'+(x.you?'<span class="chip">follows you</span>':'')+'</div><div class="txt">'+esc(x.bio)+'</div>'+
 (x.post?'<div class="note">Top post: '+esc(x.post)+'</div>':'')+'<div class="btns"><a class="btn pri" target="_blank" rel="noopener" href="https://x.com/'+esc(x.u)+'">Open profile</a>'+
 '<button type="button" data-never="'+esc(x.u)+'">Never show</button></div></div>'}).join("")}
V.renderers.push(render);
document.getElementById("sc-t").onclick=function(e){var b=e.target.closest("button");if(!b)return;tab=b.getAttribute("data-t");
 this.querySelectorAll("button").forEach(function(x){x.classList.toggle("on",x===b)});render()};
document.getElementById("sc-s").onchange=function(){s=this.value;render()};
document.addEventListener("click",function(e){var b=e.target.closest("[data-never],[data-undo]");if(!b)return;
 if(b.hasAttribute("data-never")){var h=b.getAttribute("data-never");V.set("never",h,{on:true});V.toast("@"+h+" won't be shown again.",function(){V.set("never",h,{on:false})})}
 else{V.set("never",b.getAttribute("data-undo"),{on:false})}});
})();</script>""")
    return body


def no_paid(line):
    """Drop the 'N paid lookups/checks skipped' part of a Follow Finder line. Picks this run replaces it."""
    return re.sub(r",?\s*\d+ paid (?:lookups|checks) skipped", "", line or "").strip(" ,")


# ---------------------------------------------------------------- Shoutout Picker

def shoutout_picker(items, saved, write_ok):
    rows = [{"u": x.get("username", ""), "f": x.get("followers") or 0, "l": x.get("label") or "", "p": x.get("sample_post") or "",
             "w": x.get("weeks_listed") or 0, "note": x.get("note") or ""} for x in items or []]
    lines = (saved or {}).get("lines", [])
    bench = [l for l in lines if "bench" in l.lower()]
    skips = [l for l in lines if l.startswith("Left out")]
    wr = ('<button type="button" class="pri" id="so-write">Write shoutout</button>' if write_ok else
          '<span class="note">Write shoutout turns on when Reply Queue or Fan Finder is installed.</span>')
    body = ("".join(f'<div class="warnbox">{E(b)}</div>' for b in bench)
            + '<div class="tiles"><div class="tile"><b id="so-d">0</b><span>done</span></div>'
              '<div class="tile"><b id="so-p">0</b><span>pending</span></div></div>'
            + f'<div class="tools">{wr}<div class="seg" id="so-f"><button type="button" class="on" data-f="all">All</button>'
              '<button type="button" data-f="p">Pending</button><button type="button" data-f="d">Done</button></div></div>'
              '<div id="so-out" class="card hide"><label class="note">Your shoutout post</label><textarea id="so-txt"></textarea>'
              '<div class="btns"><a class="btn pri" id="so-post" target="_blank" rel="noopener" href="#">Post on X</a></div></div>'
              '<div id="so-list"></div>'
            + "".join(f'<p class="note">{E(s)}</p>' for s in skips)
            + data_script("so-data", rows) + "<script>" + r"""
(function(){var D=JSON.parse(document.getElementById("so-data").textContent),V=window.V11,f="all";
function esc(t){var d=document.createElement("div");d.textContent=t;return d.innerHTML}
function render(){var d=D.filter(function(x){return V.on("done",x.u)}).length;document.getElementById("so-d").textContent=d;
 document.getElementById("so-p").textContent=D.length-d;
 document.getElementById("so-list").innerHTML=D.filter(function(x){var o=V.on("done",x.u);return f==="all"||(f==="d")===o}).map(function(x){var o=V.on("done",x.u);
 return '<div class="card'+(o?' done':'')+'" data-h="'+esc(x.u)+'"><div class="row"><div class="grow"><a class="who" target="_blank" rel="noopener" href="https://x.com/'+esc(x.u)+'">@'+esc(x.u)+
 '</a><div class="chips">'+(x.l?'<span class="chip strong">'+esc(x.l)+'</span>':'')+'<span class="chip">'+x.f.toLocaleString()+' followers</span>'+
 (x.w?'<span class="chip">listed '+x.w+' weeks</span>':'')+(x.note?'<span class="chip">'+esc(x.note)+'</span>':'')+'</div>'+
 (x.p?'<a class="note" target="_blank" rel="noopener" href="'+esc(x.p)+'">Sample post</a>':'')+'</div>'+
 '<div class="seg"><button type="button" data-st="'+esc(x.u)+'" data-v="0" class="'+(o?'':'on')+'">Pending</button><button type="button" data-st="'+esc(x.u)+'" data-v="1" class="'+(o?'on':'')+'">Done</button></div></div></div>'}).join("")}
V.renderers.push(render);
document.getElementById("so-f").onclick=function(e){var b=e.target.closest("button");if(!b)return;f=b.getAttribute("data-f");
 this.querySelectorAll("button").forEach(function(x){x.classList.toggle("on",x===b)});render()};
document.addEventListener("click",function(e){var b=e.target.closest("[data-st]");if(!b)return;V.set("done",b.getAttribute("data-st"),{on:b.getAttribute("data-v")==="1"})});
var w=document.getElementById("so-write");if(w)w.onclick=function(){var p=D.filter(function(x){return !V.on("done",x.u)});
 var t="This week's shoutouts: go follow these creators\n"+p.map(function(x){return "@"+x.u}).join(" ");var a=document.getElementById("so-txt");
 a.value=t;document.getElementById("so-out").classList.remove("hide");upd()};
function upd(){document.getElementById("so-post").href="https://x.com/intent/post?text="+encodeURIComponent(document.getElementById("so-txt").value)}
document.getElementById("so-txt").oninput=upd;
})();</script>""")
    return body


# ---------------------------------------------------------------- Rerun Picker

def rerun_picker(items, saved, similar, sponsor):
    out = []
    for i, r in enumerate(items or []):
        chips = []
        if similar(r.get("text", ""), [x.get("text", "") for x in (items or [])[:i]]):
            chips.append(("flag", f"similar to an earlier pick"))
        sp = sponsor(r.get("text", ""))
        if sp:
            chips.append(("flag", sp))
        ch = "".join(f'<span class="chip {c}">{E(t)}</span>' for c, t in chips)
        draft = r.get("draft") or ""
        out.append(f'<div class="card"><div class="chips"><span class="chip strong">{E(str(r.get("ratio", "")))} vs typical</span>'
                   f'<span class="chip">{int(r.get("views") or 0):,} views</span><span class="chip">{E(r.get("format", ""))}</span>'
                   f'<span class="chip">posted {E(r.get("date", ""))}</span>'
                   f'<span class="chip">last rerun: {E(r.get("last") or "never")}</span>{ch}</div>'
                   f'<div class="txt">{RAW(r.get("text", ""))}</div>'
                   + (f'<p><b>New angle:</b> {E(r["angle"])}</p>' if r.get("angle") else "")
                   + f'<label class="note">Quote-post text</label><textarea data-u="{RAW(r.get("url", ""))}">{RAW(draft)}</textarea>'
                   f'<div class="btns"><a class="btn pri" data-q target="_blank" rel="noopener" href="{RAW(intent_post(draft, r.get("url", "")))}">Quote it</a>'
                   f'<a class="btn" target="_blank" rel="noopener" href="{E(r.get("url", ""))}">Open original</a></div></div>')
    js = ("<script>document.addEventListener('input',function(e){var t=e.target;if(!t.dataset||!t.dataset.u)return;"
          "t.parentNode.querySelector('[data-q]').href='https://x.com/intent/post?text='+encodeURIComponent(t.value)+'&url='+encodeURIComponent(t.dataset.u)})</script>")
    return ("".join(out) or '<p class="note">No picks this week.</p>') + js


# ---------------------------------------------------------------- Follow Audit

def follow_audit(D, saved, x_counts):
    D = D or {}
    since = D.get("since") or []
    unf = [e for e in since if e.get("e") == "unfollowed_you"]
    gone = [e for e in since if e.get("e") == "gone"]
    new = [e for e in since if e.get("e") in ("new_follower", "new_mutual", "followed_back")]
    risks = sorted((D.get("bad") or []) + (D.get("quiet") or []), key=lambda r: -(r.get("sc") or 0))[:5]
    tiles = "".join(f'<div class="tile"><b>{E(str(v))}</b><span>{E(str(k))}</span></div>' for k, v, _ in
                    [(s[0], s[1], s[2]) if len(s) > 2 else (s[0], s[1], "") for s in D.get("stats") or []][:4])
    xt = ""
    if x_counts:
        xt = "".join(f'<div class="tile"><b>{v}</b><span>{E(k)}</span></div>' for k, v in x_counts.items())
    else:
        lost = len(unf) + len(gone)
        xt = (f'<div class="tile"><b>{lost}</b><span>followers lost</span></div>')

    def lst(rows, empty, say_hi=False):
        if not rows:
            return f'<p class="note">{E(empty)}</p>'
        return "".join(f'<div class="card row" data-h="{E(e["u"])}"><div class="grow"><a class="who" target="_blank" rel="noopener" '
                       f'href="https://x.com/{E(e["u"])}">@{E(e["u"])}</a> <span class="nm">{E(e.get("n", ""))}'
                       f'{" · " + E(e["note"]) if e.get("note") else ""} · {E(e.get("d", ""))}</span></div>'
                       + (f'<a class="btn" target="_blank" rel="noopener" href="{E(intent_post("@" + e["u"] + " "))}">Say hi</a>' if say_hi else "")
                       + "</div>" for e in rows)
    risk = "".join(f'<li><b>@{E(r["u"])}</b> score {r.get("sc", 0)}: {E(r.get("why") or r.get("t") or "")}</li>' for r in risks)
    return (f'<p class="note">Read only. It never follows or unfollows anyone.</p><div class="tiles">{tiles}{xt}</div>'
            + (f'<h2>Top risks</h2><ul class="plain">{risk}</ul>' if risk else "")
            + f'<h2>Unfollowed you ({len(unf)})</h2>' + lst(unf, "Nobody since the last scan.")
            + f'<h2>Account gone ({len(gone)})</h2><p class="note">Suspended, deactivated or not found, from this bot\'s own per-name lookup.</p>'
            + lst(gone, "None.")
            + f'<h2>New followers ({len(new)})</h2>' + lst(new, "None since the last scan.", say_hi=True))


# ---------------------------------------------------------------- Home

HOME_JS = r"""
(function(){var V=window.V11,P=JSON.parse(document.getElementById("home-people").textContent),grid=document.getElementById("panels");
var LK="v11-home-layout",lay={};try{lay=JSON.parse(localStorage.getItem(LK)||"{}")}catch(e){}
function apply(){var ps=[].slice.call(grid.querySelectorAll(".panel"));var ord=lay.order||[];
 ps.sort(function(a,b){var x=ord.indexOf(a.id),y=ord.indexOf(b.id);return (x<0?99:x)-(y<0?99:y)});ps.forEach(function(p){grid.appendChild(p);
 p.classList.toggle("off",(lay.off||[]).indexOf(p.id)>=0)})}
function save(){lay.order=[].map.call(grid.querySelectorAll(".panel"),function(p){return p.id});try{localStorage.setItem(LK,JSON.stringify(lay))}catch(e){}
 if(V.hosted&&!V.preview)fetch("/api/checks?page=layout-home",{method:"PUT",credentials:"same-origin",headers:{"content-type":"application/json"},body:JSON.stringify(lay)}).catch(function(){})}
if(V.hosted&&!V.preview)fetch("/api/checks?page=layout-home",{credentials:"same-origin",cache:"no-store"}).then(function(r){return r.ok?r.json():null}).then(function(s){if(s&&s.order){lay=s;apply()}}).catch(function(){});
apply();
document.getElementById("cust").onclick=function(){var on=document.body.classList.toggle("customizing");this.classList.toggle("on",on);this.textContent=on?"Done customizing":"Customize"};
grid.addEventListener("click",function(e){var b=e.target.closest("[data-mv]");if(!b)return;var p=b.closest(".panel"),k=b.getAttribute("data-mv");
 if(k==="up"&&p.previousElementSibling)grid.insertBefore(p,p.previousElementSibling);
 if(k==="down"&&p.nextElementSibling)grid.insertBefore(p.nextElementSibling,p);
 if(k==="hide"){lay.off=lay.off||[];var i=lay.off.indexOf(p.id);if(i>=0)lay.off.splice(i,1);else lay.off.push(p.id);p.classList.toggle("off")}save()});
function esc(t){var d=document.createElement("div");d.textContent=t;return d.innerHTML}
var dr=document.getElementById("drawer");
function openP(h){h=h.replace(/^@/,"").toLowerCase();var p=P[h]||{ev:[]};var st=V.m.stages[h],nt=(V.m.notes[h]||[]),fu=V.m.follow_ups[h];
 dr.innerHTML='<div class="row"><h3 class="grow">@'+esc(h)+'</h3><button type="button" id="dr-x">Close</button></div>'+
 '<div class="chips">'+(p.bots||[]).map(function(b){return '<span class="chip">'+esc(b)+'</span>'}).join("")+(st?'<span class="chip strong">stage: '+esc(st.stage)+'</span>':'')+'</div>'+
 '<h2>Timeline</h2>'+(p.ev.length?'<ul class="plain">'+p.ev.map(function(e){return '<li><span class="nm">'+esc(e.d||"")+' · '+esc(e.b)+'</span> '+esc(e.t)+'</li>'}).join("")+'</ul>':'<p class="note">Nothing saved yet.</p>')+
 '<h2>Notes</h2>'+nt.map(function(n){return '<p class="note">'+esc(n.ts.slice(0,10))+': '+esc(n.text)+'</p>'}).join("")+
 '<input type="text" id="dr-n" placeholder="Add a note" style="width:100%"><div class="btns"><button type="button" id="dr-add">Save note</button></div>'+
 '<h2>Follow-up</h2><input type="date" id="dr-d" value="'+(fu&&fu.on?esc(fu.due):'')+'"><div class="btns"><button type="button" id="dr-fu">Set follow-up</button>'+
 (fu&&fu.on?'<button type="button" id="dr-fx">Clear</button>':'')+'<a class="btn" target="_blank" rel="noopener" href="https://x.com/'+esc(h)+'">Open profile</a></div>';
 dr.classList.add("open");document.getElementById("dr-x").onclick=function(){dr.classList.remove("open")};
 document.getElementById("dr-add").onclick=function(){var v=document.getElementById("dr-n").value.trim();if(!v)return;(V.m.notes[h]=V.m.notes[h]||[]).push({ts:new Date().toISOString(),text:v});V.save();openP(h)};
 document.getElementById("dr-fu").onclick=function(){var v=document.getElementById("dr-d").value;if(v){V.set("follow_ups",h,{on:true,due:v,text:"follow up"});openP(h)}};
 var fx=document.getElementById("dr-fx");if(fx)fx.onclick=function(){V.set("follow_ups",h,{on:false});openP(h)}}
document.addEventListener("click",function(e){var a=e.target.closest("[data-person]");if(!a)return;e.preventDefault();openP(a.getAttribute("data-person"))});
function due(){var t=new Date().toISOString().slice(0,10),el=document.getElementById("fu-list");if(!el)return;
 var L=Object.keys(V.m.follow_ups).filter(function(h){var f=V.m.follow_ups[h];return f.on&&f.due<=t}).sort();
 el.innerHTML=L.map(function(h){var f=V.m.follow_ups[h];return '<li><a href="#" class="who" data-person="'+esc(h)+'">@'+esc(h)+'</a> <span class="nm">'+esc(f.text||"follow up")+', due '+esc(f.due)+'</span> <button type="button" data-fudone="'+esc(h)+'">Done</button></li>'}).join("")||'<li class="note">Nothing due.</li>'}
document.addEventListener("click",function(e){var b=e.target.closest("[data-fudone]");if(b)V.set("follow_ups",b.getAttribute("data-fudone"),{on:false})});
V.renderers.push(due);
})();
"""


def panel(pid, title, href, body):
    t = f'<a href="{E(href)}">{E(title)}</a>' if href else E(title)
    return (f'<div class="card panel" id="{E(pid)}"><div class="row"><h2 class="grow" style="margin:0 0 6px">{t}</h2>'
            f'<div class="ctl"><button type="button" data-mv="up" aria-label="Move up">↑</button>'
            f'<button type="button" data-mv="down" aria-label="Move down">↓</button>'
            f'<button type="button" data-mv="hide">Show / hide</button></div></div>{body}</div>')


def home(panels, people, top_fans, strip):
    """panels: [(id, title, href, body_html)]. people: {handle: {"bots":[..], "ev":[{d,b,t}]}}."""
    tf = ""
    if top_fans is not None:
        tf = panel("p-topfans", "Top fans", "", "<ul class='plain'>" + "".join(
            f'<li><a href="#" class="who" data-person="{E(h)}">@{E(h)}</a> <span class="nm">{E(w)}</span></li>'
            for h, w in top_fans) + "</ul>" if top_fans else '<p class="note">No fans counted yet.</p>')
    fu = panel("p-followups", "Follow-ups due", "", '<ul class="plain" id="fu-list"></ul>'
               '<p class="note">Tap any @name for their timeline, notes and follow-up.</p>')
    tiles = "".join(f'<div class="tile"><b>{E(str(v))}</b><span>{E(k)}</span></div>' for k, v in strip)
    return (f'<div class="tiles strip">{tiles}</div><div class="tools"><button type="button" id="cust">Customize</button>'
            f'<span class="note">Reorder or hide panels. Saved on this device and, when hosted, across devices.</span></div>'
            f'<div id="panels">{fu}{tf}' + "".join(panel(*p) for p in panels) + '</div><aside class="drawer" id="drawer"></aside>'
            + data_script("home-people", people) + f"<script>{HOME_JS}</script>")


# Home panels: real items with their buttons, not run summaries.

def _who(u):
    return f'<a class="who" href="https://x.com/{E(u)}" target="_blank" rel="noopener">@{E(u)}</a>'


def home_reply_queue(rows, n=5):
    """rows: Reply Queue DATA rows still waiting (done already removed). Top n, mentions first."""
    rows = sorted(rows, key=lambda x: (((x.get("chips") or [{}])[0].get("t") or "").lower() != "mention"))[:n]
    if not rows:
        return '<p class="note">Nothing waiting. Nice.</p>'
    return "".join(
        f'<div class="item">{_who(x.get("username", ""))} <span class="nm">{E(((x.get("chips") or [{}])[0].get("t") or "reply").lower())}'
        f'{" · " + E(x["chips"][1]["t"]) if len(x.get("chips") or []) > 1 else ""}</span>'
        f'<div class="txt">{RAW(snippet(x.get("text", ""), 14))}</div><div class="btns">'
        f'<a class="btn pri" target="_blank" rel="noopener" href="{RAW(intent_reply(x.get("key", "")))}">Reply</a>'
        f'<a class="btn" target="_blank" rel="noopener" href="{RAW(((x.get("links") or [{}])[0]).get("u", ""))}">Open</a></div></div>'
        for x in rows)


def home_fan_finder(rows, n=3):
    rows = rows[:n]
    if not rows:
        return '<p class="note">No new fans this run.</p>'
    return "".join(
        f'<div class="item">{_who(x.get("username", ""))} <span class="nm">{E(", ".join(c.get("t", "") for c in (x.get("chips") or [])[:1]))}</span>'
        f'<div class="chips"><span class="chip strong">Why: {E(" + ".join(c.get("t", "") for c in (x.get("chips") or [])[2:]) or "engaged with you")}</span></div>'
        f'<div class="btns"><a class="btn" target="_blank" rel="noopener" href="https://x.com/{E(x.get("username", ""))}">Open profile</a></div></div>'
        for x in rows)


def home_follow_finder(rows, n=3):
    rows = rows[:n]
    if not rows:
        return '<p class="note">No picks this run.</p>'
    return "".join(
        f'<div class="item">{_who(c.get("username", ""))} <span class="nm">{E(c.get("name", ""))} · {int(c.get("followers") or 0):,} followers</span>'
        f'<div class="txt">{RAW(snippet(c.get("bio", ""), 12))}</div></div>' for c in rows)


def home_reruns(rows, n=2):
    rows = rows[:n]
    if not rows:
        return '<p class="note">No picks this week.</p>'
    return "".join(
        f'<div class="item"><span class="chip strong">{E(str(r.get("ratio", "")))} vs typical</span> '
        f'<div class="txt">{RAW(snippet(r.get("text", ""), 12))}</div><div class="btns">'
        f'<a class="btn" target="_blank" rel="noopener" href="{RAW(r.get("url", ""))}">Open original</a></div></div>' for r in rows)


def home_shoutouts(rows, marks):
    """This week's picks with Done. Done saves to the Shoutout Picker page marks (same KV key)."""
    if not rows:
        return '<p class="note">No picks this week.</p>'
    items = [{"u": x.get("username", ""), "f": x.get("followers") or 0} for x in rows]
    return ('<div id="hso-list"></div>' + data_script("hso-data", items) + data_script("hso-marks", marks) + "<script>" + r"""
(function(){var D=JSON.parse(document.getElementById("hso-data").textContent),V=window.V11,LK="v11-marks-shoutout-picker",
API="/api/checks?page=marks-shoutout-picker",M={never:{},done:{},stages:{},notes:{},follow_ups:{}};
V.merge(M,JSON.parse(document.getElementById("hso-marks").textContent));try{V.merge(M,JSON.parse(localStorage.getItem(LK)||"null"))}catch(e){}
function esc(t){var d=document.createElement("div");d.textContent=t;return d.innerHTML}
function on(h){var e=M.done[h.toLowerCase()];return !!(e&&e.on)}
function render(){document.getElementById("hso-list").innerHTML=D.map(function(x){var o=on(x.u);
 return '<div class="item row'+(o?' done':'')+'"><div class="grow"><a class="who" target="_blank" rel="noopener" href="https://x.com/'+esc(x.u)+'">@'+esc(x.u)+
 '</a> <span class="nm">'+x.f.toLocaleString()+' followers</span></div><button type="button" class="'+(o?'on':'')+'" data-hso="'+esc(x.u)+'">'+(o?'Done ✓':'Done')+'</button></div>'}).join("")}
function save(){try{localStorage.setItem(LK,JSON.stringify(M))}catch(e){}
 if(V.hosted&&!V.preview)fetch(API,{method:"PUT",credentials:"same-origin",headers:{"content-type":"application/json"},body:JSON.stringify(M)}).catch(function(){V.offline()})}
if(V.hosted&&!V.preview)fetch(API,{credentials:"same-origin",cache:"no-store"}).then(function(r){if(!r.ok)throw 0;return r.json()}).then(function(s){if(s&&typeof s==="object"){V.merge(M,s);render()}}).catch(function(){});
document.getElementById("hso-list").addEventListener("click",function(e){var b=e.target.closest("[data-hso]");if(!b)return;var h=b.getAttribute("data-hso").toLowerCase(),was=on(h);
 M.done[h]={on:!was,ts:new Date().toISOString()};save();render();if(!was)V.toast("Marked @"+h+" done.",function(){M.done[h]={on:false,ts:new Date().toISOString()};save();render()})});
V.renderers.push(render);})();</script>""")


def home_unfollows(since, n=5):
    rows = sorted([e for e in since or [] if e.get("e") in ("unfollowed_you", "gone")], key=lambda e: e.get("d") or "", reverse=True)[:n]
    if not rows:
        return '<p class="note">Nobody since the last scan.</p>'
    return "".join(f'<div class="item">{_who(e["u"])} <span class="nm">{"unfollowed you" if e["e"] == "unfollowed_you" else "account gone"}'
                   f'{", " + E(e["note"]) if e.get("note") else ""} · {E(e.get("d", ""))}</span></div>' for e in rows)


def lines_html(lines):
    return "<ul class='plain'>" + "".join(f"<li>{E(str(x))}</li>" for x in lines) + "</ul>"


# ---------------------------------------------------------------- Analytics Log

def _n(x):
    try:
        return float(str(x).replace(",", "").strip())
    except (TypeError, ValueError):
        return 0.0


def _fmt(x):
    return f"{x:,.0f}"


def tiles_html(pairs, cls="tiles"):
    return f'<div class="{cls}">' + "".join(f'<div class="tile"><b>{E(str(v))}</b><span>{E(k)}</span></div>'
                                           for k, v in pairs) + "</div>"


def analytics_log(posts, followers, verified, monetized, sv=None, goal=500000, days=90):
    """posts: rows of posts_latest.csv. followers: rows of followers.csv (oldest first).
    verified: rows of verified_daily_latest.csv. The 500K chart shows only when monetized."""
    from datetime import datetime as _dt
    ps = []
    for r in posts:
        try:
            ts = _dt.fromisoformat((r.get("posted_at_et") or "").strip())
        except ValueError:
            continue
        ps.append({"ts": ts, "imp": _n(r.get("impressions")), "fol": _n(r.get("new_follows") or r.get("follows")),
                   "text": (r.get("text") or "").strip(), "link": r.get("link") or "", "id": r.get("post_id", "")})
    last = followers[-1] if followers else {}
    tiles = [("followers", _fmt(_n(last.get("followers_total")))) if last.get("followers_total") else None,
             ("posts tracked", len(ps)),
             ("impressions on those posts", _fmt(sum(p["imp"] for p in ps))),
             ("followers gained from posts", _fmt(sum(p["fol"] for p in ps)))]
    if last.get("new_follows_today"):
        tiles.append(("new follows today", _fmt(_n(last["new_follows_today"]))))
    out = tiles_html([t for t in tiles if t])
    # best time to post: day of week x hour, by average impressions
    by = {}
    for p in ps:
        k = (p["ts"].strftime("%a"), p["ts"].hour)
        by.setdefault(k, []).append(p)
    best = sorted(by.items(), key=lambda kv: -sum(x["imp"] for x in kv[1]) / len(kv[1]))[:6]
    rows = "".join(f'<tr><td>{E(d)} {(h % 12) or 12} {"AM" if h < 12 else "PM"}</td><td class="n">{len(v)}</td>'
                   f'<td class="n">{_fmt(sum(x["imp"] for x in v) / len(v))}</td>'
                   f'<td class="n">{sum(x["fol"] for x in v) / len(v):.1f}</td></tr>' for (d, h), v in best)
    bt = ('<div class="card"><h2 style="margin-top:0">Best time to post</h2>' + (
        '<table class="tbl"><tr><th>When (your time)</th><th class="n">Posts</th><th class="n">Avg impressions</th>'
        f'<th class="n">Avg follows</th></tr>{rows}</table>' if rows else '<p class="note">No posts pulled yet.</p>')
        + '<p class="note">From the posts Analytics Log has pulled. More posts make this steadier.</p></div>')
    top = sorted(ps, key=lambda p: (-p["fol"], -p["imp"]))[:10]
    rows = "".join(f'<tr><td>{(f"<a href=\"{E(p["link"])}\" target=\"_blank\" rel=\"noopener\">" if p["link"] else "")}'
                   f'{RAW(p["text"][:90] or p["id"])}{"</a>" if p["link"] else ""}<div class="nm">{E(p["ts"].strftime("%b %d"))}</div></td>'
                   f'<td class="n">{_fmt(p["fol"])}</td><td class="n">{_fmt(p["imp"])}</td></tr>' for p in top)
    fp = ('<div class="card"><h2 style="margin-top:0">Followers gained per post</h2>' + (
        f'<table class="tbl"><tr><th>Post</th><th class="n">Follows</th><th class="n">Impressions</th></tr>{rows}</table>'
        if rows else '<p class="note">No posts pulled yet.</p>') + '</div>')
    out += f'<div class="cols">{bt}{fp}</div>'
    if monetized:
        vs = [(r.get("date", ""), _n(r.get("impressions"))) for r in verified if r.get("date")][-days:]
        total = sum(v for _, v in vs)
        pct = min(100.0, 100.0 * total / goal) if goal else 0
        mx = max([v for _, v in vs] or [1]) or 1
        bars = "".join(f'<i style="height:{max(1, round(100 * v / mx))}%" title="{E(d)}: {_fmt(v)}"></i>' for d, v in vs)
        out += ('<div class="card"><h2 style="margin-top:0">500K verified impressions</h2>'
                f'<p>{_fmt(total)} of {_fmt(goal)} in the last {len(vs)} days ({pct:.0f}%).</p>'
                f'<div class="prog"><i style="width:{pct:.1f}%"></i></div>'
                + (f'<div class="chart" aria-label="Verified impressions per day">{bars}</div>'
                   f'<p class="note">Each bar is one day, {E(vs[0][0])} to {E(vs[-1][0])}.</p>' if vs else
                   '<p class="note">No verified impressions pulled yet.</p>') + '</div>')
    return out


# ---------------------------------------------------------------- Your week

_NUM = re.compile(r"^(?:(?P<lab>[A-Za-z][A-Za-z0-9 ()]+):\s*(?P<v1>[\d,.$]+(?:\s*(?:min|h))?)|(?:[A-Za-z]+ )?(?P<v2>\d[\d,]*)\s+(?P<lab2>[a-z][a-z ]{2,30}))")


def line_tiles(lines):
    """Pull 'Label: 12' and '12 things' pairs out of a bot's report lines. Returns (tiles, rest)."""
    tiles, rest = [], []
    for ln in lines:
        ln = str(ln)
        if ln.startswith("Today: about $"):
            tiles.append(("spend today (estimate)", ln.split("about ", 1)[1].split(" ")[0]))
            continue
        full = True
        for part in re.split(r"[;,] ", ln):
            part = part.strip()
            m = _NUM.match(part)
            if m and m.group("lab2") and (m.end() != len(part) or "(" in part or ")" in part):
                m = None
            if m and m.end() != len(part):
                m = None  # "Bench is low: 2 left for 4 slots" stays a line, not a "bench is low: 2" tile
            if m and len(tiles) < 8:
                lab = (m.group("lab") or m.group("lab2") or "").strip()
                val = m.group("v1") or m.group("v2")
                if lab and val and not lab.lower().startswith(("best", "most")):
                    tiles.append((lab.lower().split(" (")[0].split(" over ")[0][:28].rstrip(), val))
                    full = full and m.end() == len(part)
                    continue
            full = False
        if not full:
            rest.append(ln)
    return tiles, rest


def week_tiles(totals):
    """totals: [(label, value, secondary line)]. Clean number tiles, the full line under each."""
    return '<div class="tiles strip">' + "".join(
        f'<div class="tile"><b>{E(str(v))}</b><span>{E(k)}</span>' + (f'<div class="nm">{E(sub)}</div>' if sub else "") + "</div>"
        for k, v, sub in totals) + "</div>"


def week(sections, totals=None, label=""):
    """sections: [(bot, href, status, tiles [(label, value)], lines)]. One card per installed bot.
    totals: 7-day totals [(label, value, secondary)] shown first, under the date range label."""
    top = ""
    if totals:
        top = f'<h2>Last 7 days, {E(label)}</h2>' + week_tiles(totals) + '<h2>Each bot\'s last run</h2>'
    if not sections:
        return top + '<p class="note">No bot has run yet this week.</p>'
    cards = []
    for bot, href, status, tiles, lines in sections:
        t = f'<a href="{E(href)}">{E(bot)}</a>' if href else E(bot)
        cards.append(f'<div class="card"><h2>{t}</h2><p class="note" style="margin:0 0 4px">{E(status)}</p>'
                     + (tiles_html(tiles) if tiles else "") + (lines_html(lines) if lines else "") + "</div>")
    return top + '<div class="wk">' + "".join(cards) + "</div>"


def redirect(to):
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Moved</title>'
            f'<meta http-equiv="refresh" content="0;url={E(to)}"><link rel="canonical" href="{E(to)}">'
            f'<script>location.replace({_j(to)}+location.search+location.hash)</script></head>'
            f'<body><p>This page moved to <a href="{E(to)}">{E(to)}</a>.</p></body></html>')
