#!/usr/bin/env python3
"""Foreman's cost check. Adds up each weekday on its own (Sunday included) and judges the
plan by its most expensive day, not the average. No X calls.

  python3 costcheck.py plan.json

plan.json:
  {"cap": 0.50,
   "runs": [{"slug": "reply-queue", "days": "daily", "times_per_day": 2, "time": "08:00"},
            {"slug": "shoutout-picker", "days": ["sun"], "time": "09:00"},
            {"slug": "follow-finder", "days": "daily", "cost": 0.10}]}

"cost" overrides the catalog cost for one run (for example after a lower per-run limit).
Exit 0 when every day fits, 1 when any day is over the cap. Setup must not finish on 1.
"""
import json, os, sys

DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
NAMES = dict(zip(DAYS, ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]))
HERE = os.path.dirname(os.path.abspath(__file__))


def catalog():
    with open(os.path.join(HERE, "bots.json"), encoding="utf-8") as f:
        return {b["slug"]: b for b in json.load(f)["bots"]}


def run_days(r):
    d = r.get("days", "daily")
    return list(DAYS) if d == "daily" else [x.lower()[:3] for x in d]


def run_cost(r, cat):
    return float(r["cost"]) if "cost" in r else float(cat[r["slug"]]["cost_per_run"])


def per_day(plan, cat):
    out = {d: [] for d in DAYS}
    for r in plan["runs"]:
        c = run_cost(r, cat) * int(r.get("times_per_day", 1))
        for d in run_days(r):
            out[d].append((cat[r["slug"]]["name"], round(c, 2), r))
    return out


def check(plan, cat=None, show=print):
    cat = cat or catalog()
    cap = float(plan["cap"])
    days = per_day(plan, cat)
    totals = {d: round(sum(c for _, c, _ in days[d]), 2) for d in DAYS}
    show(f"Cap ${cap:.2f} a day. Cost per day, judged by the worst day:")
    for d in DAYS:
        mark = "  OVER" if totals[d] > cap + 1e-9 else ""
        parts = ", ".join(f"{n} ${c:.2f}" for n, c, _ in days[d] if c > 0) or "nothing that costs"
        show(f"  {NAMES[d]:<9} ${totals[d]:.2f}  ({parts}){mark}")
    worst = max(DAYS, key=lambda d: totals[d])
    show(f"Worst day: {NAMES[worst]} at ${totals[worst]:.2f}.")
    over = [d for d in DAYS if totals[d] > cap + 1e-9]
    if not over:
        show(f"Every day fits under ${cap:.2f}.")
        return {"ok": True, "totals": totals, "worst": worst, "fixes": []}

    show(f"{', '.join(NAMES[d] for d in over)} would go over the cap, so the last runs that day would be stopped.")
    fixes = []
    fixes.append(f"Raise the daily cap to ${totals[worst]:.2f} or more.")
    weekly = [r for r in plan["runs"] if run_days(r) != DAYS]
    light = min(DAYS, key=lambda d: totals[d])
    for r in weekly:
        if any(d in over for d in run_days(r)):
            c = run_cost(r, cat) * int(r.get("times_per_day", 1))
            fits = totals[light] + c <= cap + 1e-9
            fixes.append(f"Move {cat[r['slug']]['name']} to {NAMES[light]} (${totals[light]:.2f} that day now, "
                         f"${totals[light] + c:.2f} after){'' if fits else ', still over on its own'}.")
    if weekly:
        fixes.append("Run the weekly bots before the daily bots on that day, so if the cap is hit it is a "
                     "daily run that waits, not the weekly list. This does not lower the total, so pair it "
                     "with one of the other fixes.")
    biggest = max((x for d in over for x in days[d]), key=lambda x: x[1])
    gap = round(totals[worst] - cap, 2)
    fixes.append(f"Lower a per-run limit, for example {biggest[0]} (${biggest[1]:.2f} on {NAMES[worst]}) "
                 f"by at least ${gap:.2f}.")
    show("Pick one:")
    for i, f in enumerate(fixes, 1):
        show(f"  {i}. {f}")
    show("Setup does not finish until every day fits.")
    return {"ok": False, "totals": totals, "worst": worst, "fixes": fixes}


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        print(__doc__)
        return 2
    with open(argv[0], encoding="utf-8") as f:
        plan = json.load(f)
    return 0 if check(plan)["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
