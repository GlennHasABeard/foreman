"""One bot's own spend, when it is installed alone (no Dispatch or Foreman).

  CREW_BOT="Reply Queue" python3 bot_spend.py show
  CREW_BOT="Reply Queue" python3 bot_spend.py raise 3.00          (asks to confirm)
  CREW_BOT="Reply Queue" python3 bot_spend.py raise 3.00 --yes
  CREW_BOT="Reply Queue" python3 bot_spend.py clear [--yes]

The cap and timezone come from the bot's own config.json. The ledger is the bot's own
file in its folder. A raise is saved under today's date in that ledger, so it ends at
midnight in the owner's timezone by itself. In a crew (Dispatch or Foreman installed)
this tool does nothing and points to Dispatch, which owns the shared ledger and cap.
It never sends anything to X.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import follow_watch as fw  # noqa: E402


def bot_config(name):
    p = os.path.join(fw.bot_dir(name), "config.json")
    if not os.path.exists(p):
        raise SystemExit(f"No config.json in {fw.bot_dir(name)}. Run this bot's setup first.")
    with open(p, encoding="utf-8") as f:
        cfg = json.load(f)
    for k in ("daily_spend_cap", "timezone"):
        if cfg.get(k) is None:
            raise SystemExit(f"{p} is missing {k}. Run this bot's setup first.")
    return cfg


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", nargs="?", default="show", choices=["show", "raise", "clear", "mode", "individual"])
    ap.add_argument("amount", nargs="?", type=float)
    ap.add_argument("--yes", action="store_true")
    a = ap.parse_args(argv)
    name = fw.crew_bot()
    if a.cmd == "individual":
        m = fw.individual_marker(name)
        os.makedirs(os.path.dirname(m), exist_ok=True)
        open(m, "w").close()
        print(f"{name}: set up from its individual template. Own ledger and cap; shared sign-in.")
    mode = fw.crew_mode()
    if a.cmd in ("mode", "individual"):
        kind, sp = fw.signin_source()
        print(f"{name}: {mode}{' (individual template)' if fw.is_individual() else ''}. Ledger {fw.ledger_path()}. "
              f"Sign-in: {kind} at {sp}" + (" (none yet, run auth once)" if kind == "none" else "") + ".")
        return 0
    if mode == "shared":
        print("Dispatch or Foreman is installed, so this bot uses the shared ledger and cap. "
              "Ask Dispatch to show spend or raise the cap for one day.")
        return 0
    cfg = bot_config(name)
    cap = float(cfg["daily_spend_cap"])
    tz = cfg["timezone"]
    day, book, path = fw.ledger_today(cfg)
    if a.cmd == "show":
        e = book.get(day) or {}
        print(f"{name} today ({day}, {tz}): ${e.get('total', 0.0):.3f} of ${fw.effective_cap(cfg):.2f}"
              + (" (raised for today)" if e.get("cap_raise") else "") + f". Ledger: {path}")
        return 0
    if a.cmd == "raise":
        if a.amount is None or a.amount <= cap:
            print(f"Give an amount above your normal cap of ${cap:.2f}.")
            return 2
        if not a.yes:
            print(f"Raise {name}'s X spend cap to ${a.amount:.2f} for {day} only? "
                  f"It goes back to ${cap:.2f} at midnight {tz}. Reply yes to confirm.")
            return 0
        with fw.file_lock(path):
            day, book, path = fw.ledger_today(cfg)
            e = book.setdefault(day, {"total": 0.0, "by_bot": {}})
            e["cap_raise"] = {"amount": round(a.amount, 2), "set_at": fw.crew_now(fw.ZoneInfo(tz)).isoformat(timespec="seconds")}
            fw.write_json(path, book)
        print(f"Done. {name}'s cap is ${a.amount:.2f} for {day}. Back to ${cap:.2f} at midnight {tz}.")
        return 0
    if a.cmd == "clear":
        if not (book.get(day) or {}).get("cap_raise"):
            print(f"No raise today. Cap is ${cap:.2f}.")
            return 0
        if not a.yes:
            print(f"Drop today's raise and go back to ${cap:.2f}? Reply yes to confirm.")
            return 0
        with fw.file_lock(path):
            day, book, path = fw.ledger_today(cfg)
            (book.get(day) or {}).pop("cap_raise", None)
            fw.write_json(path, book)
        print(f"Done. Cap is back to ${cap:.2f}.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
