"""$0 re-filter of the already-built Scout page/csv/picks through nsfw.check (no X API)."""
import json, re, csv, os, sys, importlib
H=os.path.dirname(os.path.abspath(__file__)); R=os.path.join(H,"..","..")
sys.path.insert(0,H); import nsfw
pg=os.path.join(R,"reports","creator_scout.html"); s=open(pg,encoding="utf-8").read()
m=re.search(r"const DATA=(\[.*?\]);const KEY",s,re.S); data=json.loads(m.group(1).replace("<\\/","</"))
drop=[]; keep=[]
for c in data:
    r=nsfw.check(c["username"],c.get("name",""),c.get("bio","")," ".join(p.get("text","") for p in c.get("top_posts",[])))
    (drop.append((c["username"],r)) if r else keep.append(c))
s=s.replace(m.group(1),json.dumps(keep,ensure_ascii=False).replace("</","<\\/"))
s=re.sub(r"(<p class=\"sub\">)\d+ ",lambda x:x.group(1)+f"{len(keep)} ",s)
open(pg,"w",encoding="utf-8").write(s)
bad={u.lower() for u,_ in drop}
cp=os.path.join(R,"reports","candidates.csv"); rows=list(csv.reader(open(cp,encoding="utf-8")))
csv.writer(open(cp,"w",newline="",encoding="utf-8")).writerows([r for r in rows if not r or r[0].lower() not in bad])
pt=os.path.join(R,"picks.txt"); L=open(pt).read().splitlines()
open(pt,"w").write("\n".join(l for l in L if not any(f"x.com/{b}" in l.lower() for b in bad))+"\n")
print(json.dumps({"kept":len(keep),"dropped":drop}))
