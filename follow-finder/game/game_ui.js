(function(){
if(window.__game)return;window.__game=1;
var G=null,API="/api/checks?page=",S={rules:{},taste:{},binder:{},never:{},af:{}},PG={rules:"game-rules",taste:"game-taste",binder:"game-binder",never:"never-scout",af:"game-following"};
var esc=function(s){return String(s==null?"":s).replace(/[&<>"]/g,function(c){return{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]})};
function ld(k){try{return JSON.parse(localStorage.getItem("g_"+k)||"{}")||{}}catch(e){return{}}}
function sv(k){try{localStorage.setItem("g_"+k,JSON.stringify(S[k]))}catch(e){}
 fetch(API+PG[k],{method:"PUT",credentials:"same-origin",headers:{"content-type":"application/json"},body:JSON.stringify(S[k])}).catch(function(){})}
for(var k in PG)S[k]=ld(k);
var css=`
.gtabs{display:flex;gap:6px;margin:0 0 14px;border-bottom:1px solid var(--line)}
.gtabs button{background:none;border:0;border-bottom:2px solid transparent;color:var(--mute);font:inherit;font-weight:600;padding:8px 12px;cursor:pointer}
.gtabs button.on{color:var(--ink);border-color:var(--acc)}
#game{display:none}#game.on{display:block}
.gstrip{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px}
.gstrip div{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:8px 12px;font-size:13px;color:var(--mute)}
.gstrip b{display:block;color:var(--ink);font-size:17px}
.gsec{margin:18px 0 8px;font-size:15px;font-weight:700}.gsub{color:var(--mute);font-size:13px;margin:-4px 0 10px}
.gseg{display:inline-flex;border:1px solid var(--line);border-radius:9px;overflow:hidden;margin-bottom:12px}
.gseg button{background:var(--card);border:0;color:var(--mute);font:inherit;font-size:13px;padding:7px 12px;cursor:pointer}
.gseg button.on{background:var(--acc);color:#fff}
.gpack{display:grid;gap:10px;grid-template-columns:1fr}
@media(min-width:900px){.gpack{grid-template-columns:repeat(auto-fill,minmax(260px,1fr))}}
.gc{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px;display:flex;flex-direction:column;gap:8px;border-top:3px solid var(--line)}
.gc.Rare{border-top-color:#3c7dd9}.gc.Legendary{border-top-color:#c99a2e}
.gr{font-size:11px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--mute)}
.gc.Rare .gr{color:#3c7dd9}.gc.Legendary .gr{color:#c99a2e}
.gtop{display:flex;gap:10px;align-items:center}.gtop img{width:40px;height:40px;border-radius:50%;background:var(--chip);object-fit:cover}
.gpost{font-size:13px;border-left:2px solid var(--line);padding:2px 0 2px 8px;color:var(--ink)}
.gwhy{font-size:13px;color:var(--mute)}.gcav{font-size:12px;color:var(--mute);background:var(--chip);border-radius:8px;padding:6px 8px}
.gbtns{display:flex;gap:8px;flex-wrap:wrap;margin-top:auto}
.gb{border:1px solid var(--line);background:none;color:var(--ink);border-radius:8px;padding:7px 12px;font:inherit;font-size:13px;cursor:pointer;text-decoration:none}
.gb.p{background:var(--acc);border-color:var(--acc);color:#fff}
.gtaste{max-width:520px}.gtaste .gc{min-height:200px}.gmask{display:flex;gap:10px;align-items:center;color:var(--mute);font-size:13px}
.gmask i{width:40px;height:40px;border-radius:50%;background:var(--chip);display:inline-block}
.gtable{width:100%;border-collapse:collapse;font-size:13px;background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden}
.gtable td,.gtable th{padding:9px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}.gtable th{color:var(--mute);font-weight:600}
.gtable tr.off td{opacity:.5}
.gbind{display:grid;gap:6px;grid-template-columns:repeat(auto-fill,minmax(200px,1fr))}
.gbind div{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:8px 10px;font-size:13px}
.gbind span{color:var(--mute)}
.gmod{position:fixed;inset:0;background:rgba(0,0,0,.45);display:none;align-items:flex-end;justify-content:center;z-index:70}
.gmod.on{display:flex}@media(min-width:700px){.gmod{align-items:center}}
.gsheet{background:var(--card);color:var(--ink);border-radius:14px 14px 0 0;padding:16px;width:100%;max-width:520px}
@media(min-width:700px){.gsheet{border-radius:14px}}
.gchips{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0}
.gchips button{border:1px solid var(--line);background:var(--chip);color:var(--ink);border-radius:999px;padding:7px 12px;font:inherit;font-size:13px;cursor:pointer}
.gchips button.on{background:var(--acc);border-color:var(--acc);color:#fff}
.gsheet textarea{width:100%;min-height:70px;border:1px solid var(--line);border-radius:8px;background:var(--bg);color:var(--ink);font:inherit;padding:8px}
.gnote{font-size:12px;color:var(--mute);margin-top:6px}
.wrap.gwide{max-width:1400px}
.gemb .gembx{min-height:0}.gemb.ok .gpost{display:none}.gemb .ggone{display:none}.gemb.gone .ggone{display:block}
.gemb .twitter-tweet{margin:0!important}.gemb.cov{position:relative;min-height:140px}.gemb.cov>*:not(.gcover){filter:blur(22px);pointer-events:none}.gcover{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:6px;background:rgba(0,0,0,.35);color:#fff;border:0;border-radius:12px;font:600 15px system-ui;cursor:pointer;z-index:2}.gcover small{font-weight:400;opacity:.85}.gc .gtop img.cov{filter:blur(10px)}.gc{min-width:0}
.ghid i{width:40px;height:40px;border-radius:50%;background:#8b8f96;display:inline-block;flex:none}.ghid b{color:var(--mute)}
.gbtxt{font-size:15px;white-space:pre-wrap;word-break:break-word}
.gbmed{display:grid;gap:4px;border-radius:14px;overflow:hidden;border:1px solid var(--line)}.gbmed.n2,.gbmed.n4{grid-template-columns:1fr 1fr}.gbmed.n3{grid-template-columns:1fr 1fr}
.gbvid{width:100%;border:0;display:block;max-height:520px;background:#000}.gbmed img,.gbmed video{width:100%;display:block;max-height:520px;object-fit:cover;background:#000}.gbmed.n1 img,.gbmed.n1 video{object-fit:contain}
.gbfall{position:relative}.gbfall .gbcov{position:absolute;left:0;right:0;background:var(--card);z-index:3;display:flex;align-items:center;padding:0 12px}
.gbfall .gbcov.t{top:0;height:66px}.gbfall .gbcov.b{bottom:0;height:96px}.gbfall .gbblock{position:absolute;inset:0;z-index:4}
.gbfall:not(.ok) .gbcov,.gbfall:not(.ok) .gbblock{display:none}`;
var st=document.createElement("style");st.textContent=css;document.head.appendChild(st);
var wrap=document.querySelector(".wrap"),list=document.getElementById("list");
var tabs=document.createElement("div");tabs.className="gtabs";tabs.innerHTML='<button data-t="picks" class="on">Picks</button><button data-t="game">Game</button>';
var h1=wrap.querySelector("h1"),top=h1;while(top&&top.parentNode!==wrap)top=top.parentNode;
// the redesigned page nests the h1 inside .hdr; anchor on wrap's own child that holds the h1
var head=(top===h1)?null:top,anchor=head?head.nextSibling:(h1.nextSibling&&h1.nextSibling.nextSibling);
if(anchor&&anchor.parentNode===wrap)wrap.insertBefore(tabs,anchor);else wrap.appendChild(tabs);
var picksEls=[].slice.call(wrap.children).filter(function(e){return e!==tabs&&e!==head&&e.tagName!=="H1"&&!e.classList.contains("rb-over")});
var game=document.createElement("div");game.id="game";wrap.appendChild(game);
var mod=document.createElement("div");mod.className="gmod";mod.innerHTML='<div class="gsheet"></div>';document.body.appendChild(mod);
var view="pack";
function tab(t){tabs.querySelectorAll("button").forEach(function(b){b.classList.toggle("on",b.dataset.t===t)});
 picksEls.forEach(function(e){e.style.display=t==="game"?"none":""});game.classList.toggle("on",t==="game");wrap.classList.toggle("gwide",t==="game")}
tabs.addEventListener("click",function(e){var b=e.target.closest("button");if(!b)return;tab(b.dataset.t);if(b.dataset.t==="game")history.replaceState(null,"","#game");else history.replaceState(null,"",location.pathname)});
function pts(){var s=G.score;return '<div class="gstrip"><div><b>'+s.streak+' day'+(s.streak===1?"":"s")+'</b>streak</div><div><b>Level '+s.level+'</b>'+s.week+' of '+s.next_level+' points this week</div><div><b>'+s.follows_today+' of '+s.follow_cap+'</b>follows counted today</div></div>'}
function card(c){var n=S.never[c.h.toLowerCase()],p=c.post;
 return '<div class="gc '+c.rarity+'"><div class="gr">'+c.rarity+'</div><div class="gtop"><img'+(c.checked===false?' class="cov"':'')+' src="'+esc(c.avatar)+'" alt="" onerror="this.style.visibility=\'hidden\'"><div><b>@'+esc(c.h)+'</b><div class="gwhy">'+esc(c.name)+' · '+(c.followers||0).toLocaleString()+' followers</div></div></div>'+
 (p?emb(p,c.h,c.checked!==false):'')+
 '<div class="gwhy">'+esc(c.why)+'</div>'+
 (n?'<div class="gcav">On your never-scout list</div>':'')+
 '<div class="gbtns"><a class="gb p" target="_blank" rel="noopener" href="https://x.com/'+encodeURIComponent(c.h)+(p?'/status/'+p.id:'')+'" data-open="'+esc(c.h)+'">Open on X</a><button class="gb" data-nl="'+esc(c.h)+'">Not like this</button>'+(c.spare===undefined?'':'<button class="gb" data-af="'+esc(c.h)+'" data-uid="'+esc(c.uid||"")+'">Already following</button>')+'</div></div>'}
function packNow(){var af=S.af,out=[],seen={};function ok(c){var k=c.h.toLowerCase();return !(af[k]&&!af[k].undone)&&!seen[k]}
 G.pack.forEach(function(c){if(ok(c)){seen[c.h.toLowerCase()]=1;out.push(Object.assign({spare:false},c))}});
 (G.spares||[]).forEach(function(c){if(out.length<G.pack.length&&ok(c)&&!S.never[c.h.toLowerCase()]){seen[c.h.toLowerCase()]=1;out.push(Object.assign({spare:true},c))}});return out}
var deckI=0,revealed=null;
var WJS=null;function widgets(){if(WJS)return WJS;WJS=new Promise(function(ok,no){var sc=document.createElement("script");sc.src="https://platform.twitter.com/widgets.js";sc.async=true;sc.charset="utf-8";
 sc.onload=function(){window.twttr&&twttr.ready?twttr.ready(function(){ok(twttr)}):no()};sc.onerror=no;document.head.appendChild(sc)});return WJS}
function theme(){return matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light"}
function embedOne(el){if(el.dataset.done)return;el.dataset.done=1;
 widgets().then(function(t){var box=el.querySelector(".gembx");return t.widgets.createTweet(el.dataset.id,box,{theme:theme(),dnt:true,conversation:"none",align:"center"}).then(function(w){
  if(w){el.classList.add("ok")}else{el.classList.add("gone")}})}).catch(function(){el.classList.add("gone")})}
var IO="IntersectionObserver" in window?new IntersectionObserver(function(es){es.forEach(function(e){if(e.isIntersecting){IO.unobserve(e.target);embedOne(e.target)}})},{rootMargin:"300px"}):null;
function lazy(){game.querySelectorAll(".gemb:not([data-done])").forEach(function(el){IO?IO.observe(el):embedOne(el)})}
function emb(p,h,ck){return '<div class="gemb'+(ck?'':' cov')+'" data-id="'+esc(p.id)+'">'+(ck?'':'<button class="gcover" data-show><span>Tap to show</span><small>Not image-checked yet</small></button>')+'<div class="gembx"></div><div class="gpost">'+esc(p.text)+'<div class="gwhy">'+(p.likes||0)+' likes'+(p.created?' · '+esc(p.created):'')+'</div></div><div class="ggone gnote">This post is deleted or protected, so here is the saved text.</div></div>'}
function taste(){var d=G.deck.filter(function(x){return !S.taste[x.k]});
 if(revealed)return '<div class="gtaste">'+card({h:revealed.h,name:revealed.name,avatar:revealed.avatar,followers:revealed.followers,rarity:revealed.pick==="keep"?"Kept":"Passed",why:revealed.pick==="keep"?"Moves to the top of your next pack":"Counts as a light signal against "+revealed.styles.join(", ")+" posts",post:{id:revealed.id,text:revealed.text,likes:revealed.likes,created:""}})+'<div class="gbtns" style="margin-top:10px"><button class="gb p" data-next>Next post</button></div></div>';
 if(!d.length)return '<p class="gsub">No more posts today. New ones come with tomorrow\'s pack.</p>';
 var x=d[0];return '<div class="gtaste"><div class="gc gblind"><div class="gr">Hidden until you pick · '+d.length+' left</div>'+blind(x)+'<div class="gbtns"><button class="gb p" data-tk="keep" data-k="'+x.k+'">Keep</button><button class="gb" data-tk="pass" data-k="'+x.k+'">Pass</button></div></div></div>'}
// Daily Pack uses only X's official embed widget (platform.twitter.com/widgets.js).
function bdate(s){if(!s)return"";var d=new Date(s+"T12:00:00");return isNaN(d)?s:d.toLocaleDateString(undefined,{month:"short",day:"numeric",year:"numeric"})}
// video.twimg.com refuses requests that carry another site's Referer, so each video plays inside a
// no-referrer srcdoc frame (real file, real browser controls, nothing links to X)
function vid(v){var m=/\/(\d+)x(\d+)\//.exec(v.mp4||""),ar=m?m[1]+"/"+m[2]:"16/9",d='<!doctype html><meta name="referrer" content="no-referrer"><style>html,body{margin:0;height:100%;background:#000}video{width:100%;height:100%;display:block;object-fit:contain}</style><video src="'+esc(v.mp4)+'" poster="'+esc(v.img)+'" controls playsinline preload="metadata"></video>';
 return '<iframe class="gbvid" style="aspect-ratio:'+ar+'" referrerpolicy="no-referrer" sandbox="allow-scripts allow-same-origin" allow="autoplay; fullscreen; picture-in-picture" allowfullscreen srcdoc="'+esc(d)+'"></iframe>'}
function blind(x){var hid='<div class="gtop ghid"><i></i><div><b>Hidden creator</b></div></div>';
 if(x.bmedia&&x.bmedia.length){var m=x.bmedia,n=m.length;
  return hid+'<div class="gbtxt">'+esc(x.blind||"")+'</div><div class="gbmed n'+Math.min(n,4)+'">'+m.map(function(v){return v.type==="photo"?'<img src="'+esc(v.img)+'" alt="" referrerpolicy="no-referrer" draggable="false">':vid(v)}).join("")+'</div><div class="gwhy">'+esc(bdate(x.bdate))+(x.likes?' · '+x.likes+' likes':'')+'</div>'}
 return '<div class="gemb gbfall" data-id="'+esc(x.id)+'"><div class="gembx"></div><div class="gbcov t">'+hid.replace("gtop ghid","gtop ghid in")+'</div><div class="gbcov b"></div><div class="gbblock"></div><div class="gpost">'+esc(x.blind||"(No text, image-only post)")+'</div><div class="ggone gnote">Embed did not load, so here is the saved text.</div></div>'}
function rules(){var rs=G.rules.map(function(r){var u=S.rules[r.id]&&S.rules[r.id].undone;return Object.assign({},r,{active:r.active&&!u})});
 for(var id in S.rules){var x=S.rules[id];if(!x.undone&&!rs.some(function(r){return r.id===id}))rs.unshift({id:id,what:x.what||x.reason,chip:x.reason,active:true,reliable:x.reliable,note:x.note,blocked_week:null,pending:1})}
 if(!rs.length)return '<p class="gsub">No rules yet. Use Not like this on a card, or say "not like @x because ..." in chat.</p>';
 return '<table class="gtable"><tr><th>Rule</th><th>Blocked this week</th><th></th></tr>'+rs.map(function(r){return '<tr class="'+(r.active?"":"off")+'"><td><b>'+esc(r.what)+'</b>'+(r.free&&r.chip!==r.free?'<div class="gnote">You said: '+esc(r.free)+'</div>':'')+(r.reliable===false?'<div class="gnote">'+esc(r.note||"Not a reliable rule. Saved as a note only.")+'</div>':'')+(r.pending?'<div class="gnote">Applies from the next pack</div>':'')+'</td><td>'+(r.blocked_week==null?"–":r.blocked_week)+'</td><td>'+(r.active?'<button class="gb" data-undo="'+esc(r.id)+'">Undo</button>':'<span class="gnote">Undone</span>')+'</td></tr>'}).join("")+'</table>'}
function binder(){var b=G.binder;if(!b.length)return '';return '<div class="gbind">'+b.map(function(x){return '<div><b>@'+esc(x.h)+'</b> <span>'+x.rarity+'</span><br><span>'+(x.followed?"Followed":"Not followed")+' · since '+esc(x.first)+'</span></div>'}).join("")+'</div>'}
function draw(){if(!G){game.innerHTML='<p class="gsub">Game data not built yet.</p>';return}
 game.innerHTML=pts()+'<div class="gseg">'+[["pack","Daily pack"],["taste","Taste test"],["rules","Rules learned"],["binder","Binder"]].map(function(v){return '<button data-v="'+v[0]+'"'+(view===v[0]?' class="on"':'')+'>'+v[1]+'</button>'}).join("")+'</div>'+
 (view==="pack"?'<div class="gsec">Today\'s pack</div><p class="gsub">'+G.pack.length+' creators from this morning\'s Follow Finder picks. Opening X is all the game does.</p><div class="gpack">'+packNow().map(card).join("")+'</div>':
  view==="taste"?'<div class="gsec">Blind taste test</div><p class="gsub">Judge the post on its own. The creator shows after you pick.</p>'+taste():
  view==="rules"?'<div class="gsec">Rules learned</div><p class="gsub">Follow Finder applies these before building the next pack.</p>'+rules():
  '<div class="gsec">Collection binder</div><p class="gsub">'+G.binder.length+' cards opened. Followed is checked against Follow Audit\'s nightly list.</p>'+binder());lazy()}
game.addEventListener("click",function(e){var t=e.target.closest("[data-v],[data-af],[data-nl],[data-tk],[data-next],[data-undo],[data-open]");if(!t)return;
 if(t.dataset.v){view=t.dataset.v;revealed=null;draw();return}
 if(t.dataset.open){S.binder[t.dataset.open.toLowerCase()]={opened:true,at:new Date().toISOString()};sv("binder");return}
 if(t.dataset.af){S.af[t.dataset.af.toLowerCase()]={id:t.dataset.uid||null,at:new Date().toISOString()};sv("af");draw();return}
 if(t.dataset.nl){nl(t.dataset.nl);return}
 if(t.dataset.tk){var x=G.deck.filter(function(d){return d.k===t.dataset.k})[0];S.taste[x.k]={pick:t.dataset.tk,styles:x.styles,at:new Date().toISOString()};sv("taste");revealed=Object.assign({pick:t.dataset.tk},x);draw();return}
 if(t.hasAttribute("data-next")){revealed=null;draw();return}
 if(t.dataset.undo){S.rules[t.dataset.undo]=Object.assign({},S.rules[t.dataset.undo]||{},{undone:true,at:new Date().toISOString()});sv("rules");draw()}});
var sheet=mod.firstChild,CH=null;
function close(){mod.classList.remove("on")}
mod.addEventListener("click",function(e){if(e.target===mod)close()});
function nl(h){sheet.innerHTML='<div class="gsec" style="margin-top:0">Not like @'+esc(h)+'</div><div class="gbtns" style="flex-direction:column"><button class="gb" data-a="person">Not this person<div class="gnote">Adds them to never-scout</div></button><button class="gb" data-a="like">Not creators like this<div class="gnote">Tell me why, and Follow Finder learns a rule</div></button><button class="gb" data-a="x">Cancel</button></div>';
 mod.classList.add("on");sheet.onclick=function(e){var b=e.target.closest("[data-a]");if(!b)return;
  if(b.dataset.a==="person"){S.never[h.toLowerCase()]=new Date().toISOString().slice(0,10);sv("never");close();draw()}
  else if(b.dataset.a==="like")why(h);else close()}}
var WEAK={"reposts other people's work":1,"low effort or spammy ai":1};
function why(h,pre){var sel={};
 sheet.innerHTML='<div class="gsec" style="margin-top:0">Why not creators like @'+esc(h)+'?</div><p class="gsub">Pick any that fit. Each one becomes a rule.</p><div class="gchips">'+G.chips.map(function(c){return '<button data-c="'+esc(c)+'">'+esc(({"nsfw":"NSFW","low effort or spammy ai":"Low effort or spammy AI"})[c]||c.charAt(0).toUpperCase()+c.slice(1))+'</button>'}).join("")+'</div><textarea placeholder="Or say it in your words, e.g. no posts about &quot;crypto&quot;"></textarea><div class="gnote" id="gw"></div><div class="gbtns" style="margin-top:10px"><button class="gb p" data-s>Save rules</button><button class="gb" data-x>Cancel</button></div>';
 mod.classList.add("on");var gw=sheet.querySelector("#gw");
 function note(){var w=Object.keys(sel).filter(function(c){return WEAK[c]});gw.textContent=(sel.nsfw?"NSFW also adds @"+h+" to never-scout. ":"")+(w.length?"Heads up: "+w.join(", ")+" can only be partly checked from saved data. Rules learned will say so.":"")}
 sheet.onclick=function(e){var c=e.target.closest("[data-c]");if(c){var k=c.dataset.c;if(sel[k])delete sel[k];else sel[k]=1;c.classList.toggle("on");note();return}
  if(e.target.closest("[data-x]")){close();return}
  if(e.target.closest("[data-s]")){var now=new Date().toISOString(),n=0,txt=sheet.querySelector("textarea").value.trim();
   if(sel.nsfw){S.never[h.toLowerCase()]=new Date().toISOString().slice(0,10);sv("never")}Object.keys(sel).forEach(function(c){S.rules["w"+Date.now().toString(36)+(n++)]={reason:c,handle:h,at:now,what:c,reliable:!WEAK[c]}});
   if(txt)S.rules["w"+Date.now().toString(36)+(n++)]={reason:txt,free:txt,handle:h,at:now,what:"Your words: "+txt};
   if(n){sv("rules");view="rules"}close();draw()}}}
function load(){fetch("game.json",{cache:"no-store"}).then(function(r){return r.json()}).then(function(g){G=g;if(location.hash==="#game-reveal"&&G.deck[0]){view="taste";revealed=Object.assign({pick:"keep"},G.deck[0])}draw();if(location.hash==="#game-why"&&G.pack[0])why(G.pack[0].h)}).catch(function(){draw()});
 Object.keys(PG).forEach(function(k){fetch(API+PG[k],{credentials:"same-origin",cache:"no-store"}).then(function(r){if(!r.ok)throw 0;return r.json()}).then(function(s){if(s&&typeof s==="object"){for(var x in s)S[k][x]=s[x];try{localStorage.setItem("g_"+k,JSON.stringify(S[k]))}catch(e){}draw()}}).catch(function(){})})}
var hv=location.hash.replace("#","");if(hv.indexOf("game")===0){tab("game");var v=hv.split("-")[1];if(v&&v!=="why")view=v}
load();
})();
document.addEventListener("click",function(e){var b=e.target.closest&&e.target.closest("[data-show]");if(!b)return;e.preventDefault();e.stopPropagation();var g=b.closest(".gemb");g.classList.remove("cov");b.remove();var c=g.closest(".gc");c&&c.querySelectorAll("img.cov").forEach(function(i){i.classList.remove("cov")})},true);
