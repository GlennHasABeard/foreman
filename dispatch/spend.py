#!/usr/bin/env python3
"""Shared crew spend ledger. No X calls.

  python3 spend.py                 today
  python3 spend.py --days 7        last 7 days
  python3 spend.py raise 2         print the confirmation for a one-day cap raise, changes nothing
  python3 spend.py raise 2 --yes   save it, after the owner said yes to that exact amount and date
  python3 spend.py clear --yes     drop today's raise and go back to the normal cap

Every bot books each X request here (reserved at its worst case before it is sent, settled
right after) under an fcntl lock on spend_ledger.json.lock. This script takes the same lock.
A raise is saved under today's date (owner's timezone) in the ledger. The shared X client
reads it from there, so it stops at midnight with no clean up needed.
"""
import argparse, contextlib, fcntl, json, os, sys
from datetime import datetime, timezone
try:
    from zoneinfo import ZoneInfo
except ImportError:  # noqa
    ZoneInfo = None

BOTS_HOME = os.environ.get("BOTS_HOME", "/workspace").rstrip("/")

_PRICES = None


def P():
    """The crew's shared price table (x_prices.py, next to follow_watch.py)."""
    global _PRICES
    if _PRICES is None:
        here = os.path.dirname(os.path.abspath(__file__))
        for d in (os.environ.get("FW_DIR"), os.path.join(BOTS_HOME, "follow-watch"),
                  os.path.join(here, "..", "follow-audit"), os.path.join(here, "..", "follow-watch")):
            if d and os.path.exists(os.path.join(d, "x_prices.py")):
                if d not in sys.path:
                    sys.path.insert(0, d)
                import x_prices
                _PRICES = x_prices
                break
        else:
            raise SystemExit("x_prices.py not found. It ships next to follow_watch.py in the Follow Audit folder.")
    return _PRICES

LEDGER = os.environ.get("SPEND_LEDGER", os.path.join(BOTS_HOME, "dispatch", "spend_ledger.json"))


def now_local(tzname):
    tz = ZoneInfo(tzname) if ZoneInfo and tzname else timezone.utc
    fake = os.environ.get("CREW_NOW")  # test hook only
    if fake:
        t = datetime.fromisoformat(fake)
        return t.replace(tzinfo=tz) if t.tzinfo is None else t.astimezone(tz)
    return datetime.now(tz)


@contextlib.contextmanager
def ledger_lock():
    """Same lock the shared X client takes (LEDGER + '.lock', fcntl.flock), so a raise or clear
    can never overwrite a request a bot is booking at the same moment."""
    os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
    fd = os.open(LEDGER + ".lock", os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def load_ledger():
    if not os.path.exists(LEDGER):
        return {}
    with open(LEDGER, encoding="utf-8") as f:
        return json.load(f)


def save_ledger(led):
    os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
    tmp = LEDGER + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(led, f, indent=2, sort_keys=True)
    os.replace(tmp, LEDGER)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", nargs="?", default="show", choices=["show", "raise", "clear", "prices"])
    ap.add_argument("amount", nargs="?", type=float)
    ap.add_argument("--yes", action="store_true")
    ap.add_argument("--days", type=int, default=1)
    a = ap.parse_args(argv)
    with open(os.path.join(BOTS_HOME, "dispatch", "crew.json"), encoding="utf-8") as f:
        crew = json.load(f)
    cap = float(crew["daily_spend_cap"])
    tzname = crew.get("timezone")
    now = now_local(tzname)
    today = now.date().isoformat()
    nice = now.strftime("%A %b %d, %Y")
    led = load_ledger()

    if a.cmd == "prices":
        print("X prices the crew uses (the ledger and every bot's estimate read this one table):")
        print("\n".join(P().table_lines()))
        return 0
    if a.cmd == "raise":
        if a.amount is None or a.amount <= cap:
            print(f"Give an amount above your normal cap of ${cap:.2f}.")
            return 2
        if not a.yes:
            print(f"Raise today's X spend cap to ${a.amount:.2f} for {nice} only? "
                  f"It goes back to ${cap:.2f} at midnight {tzname or 'UTC'}. Reply yes to confirm.")
            return 0
        with ledger_lock():
            led = load_ledger()  # re-read under the lock
            e = led.setdefault(today, {"total": 0.0, "by_bot": {}})
            e["cap_raise"] = {"amount": round(a.amount, 2), "set_at": now.isoformat(timespec="seconds")}
            save_ledger(led)
        print(f"Done. Cap is ${a.amount:.2f} for {nice}. Back to ${cap:.2f} at midnight {tzname or 'UTC'}.")
        return 0

    if a.cmd == "clear":
        e = led.get(today) or {}
        if "cap_raise" not in e:
            print(f"No raise today. Cap is ${cap:.2f}.")
            return 0
        if not a.yes:
            print(f"Drop today's raise and go back to ${cap:.2f}? Reply yes to confirm.")
            return 0
        with ledger_lock():
            led = load_ledger()  # re-read under the lock
            (led.get(today) or {}).pop("cap_raise", None)
            save_ledger(led)
        print(f"Done. Cap is back to ${cap:.2f}.")
        return 0

    with ledger_lock():
        led = load_ledger()  # a consistent read, never half a write
    if not led:
        if os.path.exists(LEDGER):
            print("No spend booked yet. The ledger is empty, which is normal before the first run.")
        else:
            print("No spend booked yet. Ledger file not found, which is normal before the first run.")
        return 0
    for day in sorted(led)[-a.days:]:
        e = led[day]
        r = (e.get("cap_raise") or {}).get("amount")
        day_cap = r if r and r > cap else cap
        extra = f" (raised for this day only, normal ${cap:.2f})" if day_cap != cap else ""
        reqs = e.get("requests", {})
        parts = ", ".join(f"{k} ${v:.2f}" + (f" in {reqs[k]} requests" if k in reqs else "")
                          for k, v in sorted(e.get("by_bot", {}).items()))
        print(f"{day}: ${e.get('total', 0):.2f} of ${day_cap:.2f} cap{extra} ({parts or 'no runs'}). "
              "Estimated, check the X console for billed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
