#!/usr/bin/env python3
"""Self-check for one bot in the crew. Read only.

  python3 selfcheck.py --bot reply-queue            (includes the ~$0.01 X read)
  python3 selfcheck.py --bot reply-queue --offline  (no X request at all)

Checks three things and prints a plain report, then the bot's intro:
  1. Secrets: the stored secrets this bot needs are present. Values are never printed.
  2. X read: one test read (GET /users/me, about $0.01) through the shared client,
     so it counts against the daily spend cap like any other request.
  3. Folders: every folder the bot writes to exists and is writable.
Anything missing or failed is flagged by name. Nothing is left blank.
"""
import argparse, json, os, sys, tempfile

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

HERE = os.path.dirname(os.path.abspath(__file__))

SUBDIRS = {
    "follow-watch": ["data", "reports"],
    "creator-scout": ["data", "reports"],
    "shoutouts": ["data", "weeks"],
    "engagement": ["data", "reports"],
    "reruns": ["data", "picks"],
    "x-analytics": ["data", "logs"],
    "dispatch": ["."],
}


def load_crew():
    path = os.path.join(BOTS_HOME, "dispatch", "crew.json")
    if not os.path.exists(path):
        raise SystemExit("FLAG: crew.json not found. Run Foreman setup first.")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def check_secrets(crew, bot):
    rows, ok = [], True
    x_needed = bot["slug"] not in ("analytics-log",)
    if x_needed:
        has_app = bool(os.environ.get("X_CLIENT_ID")) and bool(os.environ.get("X_CLIENT_SECRET"))
        signin = os.path.join(BOTS_HOME, "dispatch", "x_signin.json")
        if has_app:
            rows.append("X app secrets: found (X_CLIENT_ID and X_CLIENT_SECRET)")
        else:
            rows.append("X app secrets: MISSING. Add X_CLIENT_ID and X_CLIENT_SECRET as stored secrets.")
            ok = False
        if os.path.exists(signin):
            mode = os.stat(signin).st_mode & 0o777
            if mode & 0o077:
                rows.append(f"Shared X sign in: found at {signin} but readable by others ({oct(mode)}). FLAG.")
                ok = False
            else:
                rows.append(f"Shared X sign in: found at {signin} (owner-only, owned by Dispatch)")
        else:
            rows.append(f"Shared X sign in: MISSING at {signin}. X sign-in needs to be redone "
                        "(Foreman runs follow_watch.py auth once for the whole crew).")
            ok = False
    if crew.get("hosting") and bot["slug"] in ("dispatch", "follow-finder"):
        for k in ("CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ACCOUNT_ID"):
            if os.environ.get(k):
                rows.append(f"{k}: found")
            else:
                rows.append(f"{k}: MISSING. Add it as a stored secret, or turn hosting off.")
                ok = False
    if not rows:
        rows.append("No secrets needed by this bot.")
    return ok, rows


def check_read(bot, offline=False):
    if bot["slug"] == "analytics-log":
        return True, "X read: skipped. This bot uses the browser, not the API. First real run will confirm sign in."
    if offline:
        return True, "X read: skipped (--offline). Nothing was sent to X."
    sys.path.insert(0, os.path.join(BOTS_HOME, "follow-watch"))
    os.environ["CREW_BOT"] = bot["name"]  # book the test read to this bot, never a default
    try:
        import follow_watch as fw
        store = fw.Store(os.path.join(BOTS_HOME, "follow-watch"))
        cfg = store.load_config()
        client = fw.XClient(store, cfg, fw.Meter(cfg))
        me = client.me()
        client._book()
        return True, f"X read: OK, signed in as @{me.get('username')} (about ${P().RATES['user']:.3f}, booked to the spend ledger)"
    except SystemExit as e:
        return False, f"X read: FAILED. {e}"
    except Exception as e:  # noqa
        return False, f"X read: FAILED. {type(e).__name__}: {e}"


def check_folders(bot):
    rows, ok = [], True
    folder = os.path.join(BOTS_HOME, bot["folder"])
    for sub in SUBDIRS.get(bot["folder"], ["."]):
        d = os.path.normpath(os.path.join(folder, sub))
        try:
            os.makedirs(d, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=d, prefix=".selfcheck_")
            os.close(fd)
            os.remove(tmp)
            rows.append(f"{d}: writable")
        except Exception as e:  # noqa
            rows.append(f"{d}: NOT WRITABLE ({e})")
            ok = False
    return ok, rows


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--bot", required=True)
    ap.add_argument("--offline", action="store_true", help="skip the paid X read")
    a = ap.parse_args(argv)
    crew = load_crew()
    bot = next((b for b in crew["bots"] if b["slug"] == a.bot), None)
    if not bot:
        raise SystemExit(f"FLAG: {a.bot} is not in this crew.")
    print(f"== Self-check: {bot['name']} ==")
    s_ok, s_rows = check_secrets(crew, bot)
    r_ok, r_row = check_read(bot, a.offline)
    f_ok, f_rows = check_folders(bot)
    for r in s_rows + [r_row] + f_rows:
        print("  - " + r)
    status = "PASS" if (s_ok and r_ok and f_ok) else "FLAGGED"
    print(f"  Result: {status}")
    print()
    print(bot.get("intro", f"Hi, I am {bot['name']}."))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
