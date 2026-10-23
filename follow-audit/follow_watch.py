#!/usr/bin/env python3
"""
follow_watch.py
Read-only tracker for an X account's followers and following.

Commands
  auth    One-time sign-in for the whole crew. Requests read-only scopes (tweet.read
          users.read follows.read offline.access, plus like.read with --likes) and
          saves one refreshable sign-in at $BOTS_HOME/dispatch/x_signin.json, owned by
          Dispatch and shared by every bot. Main path: approve in the bot's own browser,
          which comes back to the local listener. Backup: paste the address the browser
          landed on (`auth-paste '<address>'`, or stdin with --paste). The code is
          swapped the moment it arrives; X gives about 30 seconds.
  auth-paste  Hand a pasted address to the sign-in that is waiting.
  full    Pull the complete follower and following lists, compare with the last
          full scan, log who followed, unfollowed, followed back or disappeared,
          score every account for fake, spam and inactivity signals, write a report.
  light   Cheap daily check. Reads only the newest followers and follows until it
          reaches accounts it already knows, logs them, and estimates how many
          people unfollowed since the last run. Names arrive with the next full scan.
  recheck Confirm the accounts flagged inactive or dormant by reading their posts
          from the last inactive_days (90 by default). X's "most recent post"
          field on a profile can lag, often missing replies and reposts, so
          an active account can look idle. Accounts with a recent post are
          updated and drop out of the flags. Accounts you follow by default,
          add --followers for your followers too. --estimate shows the count
          and the worst-case cost without calling X.
  daily   The cheap nightly run: a light check with small pages, then the full report
          rebuilt from saved data, so follow-backs leave the Not following back list
          the next day. Unfollows are counted only. Names come with the monthly full scan.
  report  Rebuild the latest full report from saved data. No API calls.

Every run needs CREW_BOT set to the calling bot's name (for example
CREW_BOT="Follow Audit"). There is no default; without it nothing is sent.
Each request is booked to that bot in the shared spend ledger, under a file
lock, before the next request is made. A run the cap stops says
"stopped before <what>, cap reached" and never reports a made-up 0.

What it never does
  It sends no follow, unfollow, block, mute, like, post, reply, DM or list request.
  Every X API call is a GET, except the OAuth token exchange and refresh.
  The token it asks for has no write scopes, so X would refuse a write anyway.

Data lives in /workspace/follow-watch (override with --dir or FW_DIR).
Python 3.9+ standard library only.
"""

import argparse
import base64
import contextlib
import csv
import fcntl
import hashlib
import http.server
import json
import os
import queue
import re
import secrets
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import x_prices  # noqa: E402  the crew's one price table

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None

API = os.environ.get("X_API_BASE", "https://api.x.com/2").rstrip("/")
AUTHORIZE_URL = "https://x.com/i/oauth2/authorize"
TOKEN_URL = API + "/oauth2/token"
SCOPES = "tweet.read users.read follows.read offline.access"
USER_FIELDS = ",".join([
    "created_at", "description", "location", "name", "profile_image_url",
    "protected", "public_metrics", "url", "username", "verified",
    "verified_type", "most_recent_tweet_id",
])
TWITTER_EPOCH_MS = 1288834974657

# Where the bots live. Foreman sets BOTS_HOME for each bot. On Grok Bot that is /workspace.
BOTS_HOME = os.environ.get("BOTS_HOME", "/workspace").rstrip("/")

DEFAULT_CONFIG = {
    "timezone": None,
    "inactive_days": None,
    "dormant_days": None,
    "daily_spend_cap": None,
    "likely_fake_score": 50,
    "watch_score": 35,
    "max_resources_per_run": 30000,
    "light_page_size": 100,
    "daily_page_size": 20,
    "light_max_pages": 5,
    "light_stop_after_known": 5,
    "recheck_max_cost": 5.00,
    "recheck_skip_days": 7,
    "report_rows_per_section": 40,
    "redirect_uri": "http://127.0.0.1:8765/callback",
    "skip_followback": [],
    "never_flag": [],
    "spam_patterns": [
        r"dm (me )?for promo", r"\bpromo(tion)? (service|offer)s?\b", r"\bpaid promo",
        r"\bcrypto\b", r"\bforex\b", r"\bairdrop", r"\bgiveaway", r"\bnft drop",
        r"\btrading signals?\b", r"\bbinary options?\b", r"\binvest(ment|or)s?\b",
        r"\bonlyfans\b", r"\bof link\b", r"\b18\+", r"\bnsfw\b", r"\bsugar (daddy|baby)\b",
        r"\btelegram\b", r"t\.me/", r"\bwhatsapp\b", r"wa\.me/", r"\bcash ?app\b",
        r"make money", r"earn \$", r"\bpassive income\b",
        r"\bfollow ?back\b", r"\bf4f\b", r"\bifb\b", r"\bfollow ?for ?follow\b",
    ],
}

OPTIONAL_NONE = set()

def check_config(cfg, where):
    """Every setting left as None must come from the user's own config.json, written by Foreman."""
    missing = sorted(k for k, v in cfg.items() if v is None and k not in OPTIONAL_NONE)
    if missing:
        raise SystemExit(f"{where} is missing settings: {', '.join(missing)}. Run Foreman setup or add them to config.json.")
    return cfg


# ----------------------------------------------------------------------------
# Paths, config, state
# ----------------------------------------------------------------------------

class Store:
    def __init__(self, root):
        self.root = root
        self.data = os.path.join(root, "data")
        self.snapshots = os.path.join(root, "snapshots")
        self.reports = os.path.join(root, "reports")
        for d in (self.root, self.data, self.snapshots, self.reports):
            os.makedirs(d, exist_ok=True)
        self.config_path = os.path.join(root, "config.json")
        self.state_path = os.path.join(self.data, "state.json")
        self.events_path = os.path.join(self.data, "events.csv")

    def load_config(self):
        cfg = dict(DEFAULT_CONFIG)
        if os.path.exists(self.config_path):
            with open(self.config_path, encoding="utf-8") as f:
                cfg.update(json.load(f))
        else:
            raise SystemExit(f"No config.json in {self.root}. Run Foreman setup first.")
        return check_config(cfg, 'Follow Audit config')

    def load_state(self):
        if os.path.exists(self.state_path):
            with open(self.state_path, encoding="utf-8") as f:
                return json.load(f)
        return {"accounts": {}}

    def save_state(self, state):
        write_json(self.state_path, state)

    def append_events(self, events):
        if not events:
            return
        new = not os.path.exists(self.events_path)
        with open(self.events_path, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=EVENT_FIELDS)
            if new:
                w.writeheader()
            for e in events:
                w.writerow({k: e.get(k, "") for k in EVENT_FIELDS})

    def read_events(self):
        if not os.path.exists(self.events_path):
            return []
        with open(self.events_path, newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))


EVENT_FIELDS = ["ts", "date", "event", "id", "username", "name", "days", "days_min", "detail"]


def write_json(path, obj, private=False):
    tmp = path + ".tmp"
    if private:
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=1, ensure_ascii=False)
    else:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=1, ensure_ascii=False)
    os.replace(tmp, path)


def local_now(cfg):
    if ZoneInfo:
        try:
            return datetime.now(ZoneInfo(cfg["timezone"]))
        except Exception:
            pass
    return datetime.now()


def d(s):
    return date.fromisoformat(s) if s else None


# ----------------------------------------------------------------------------
# X API client (GET only, plus OAuth token calls)
# ----------------------------------------------------------------------------

class Meter:
    def __init__(self, cfg):
        self.cfg = cfg
        self.owned = 0
        self.lookup = 0
        self.posts = 0

    def add(self, kind, n):
        if kind == "owned":
            self.owned += n
        elif kind == "post":
            self.posts += n
        else:
            self.lookup += n
        if self.owned + self.lookup + self.posts > self.cfg["max_resources_per_run"]:
            raise SystemExit(
                f"Stopped: this run passed max_resources_per_run "
                f"({self.cfg['max_resources_per_run']}). Raise it in config.json if expected.")

    def cost(self):
        return x_prices.estimate(owned=self.owned, user=self.lookup, post=self.posts)


# ----------------------------------------------------------------------------
# Which bot is calling. Every X request is booked to it in the shared ledger.
# ----------------------------------------------------------------------------

CREW_BOTS = ("Dispatch", "Foreman", "Follow Audit", "Follow Finder", "Shoutout Picker",
             "Reply Queue", "Fan Finder", "Rerun Picker", "Analytics Log")


def crew_bot():
    """The calling bot's name, from CREW_BOT. There is no default: a missing or unknown name
    stops the run before anything is sent, so the ledger can never book one bot's reads to another."""
    name = (os.environ.get("CREW_BOT") or "").strip()
    if not name:
        raise SystemExit("CREW_BOT is not set, so this run can't be booked to the right bot. Nothing was sent "
                         "to X. Run it as, for example: CREW_BOT=\"Follow Audit\" python3 follow_watch.py daily")
    if name not in CREW_BOTS:
        raise SystemExit(f"CREW_BOT is set to {name!r}, which is not a crew bot. Nothing was sent to X. "
                         f"Use one of: {', '.join(CREW_BOTS)}.")
    return name


@contextlib.contextmanager
def file_lock(path):
    """Exclusive lock on path + '.lock' (fcntl.flock). Not re-entrant: never nest two locks on the same path."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    fd = os.open(path + ".lock", os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


# ----------------------------------------------------------------------------
# Daily spend cap. One ledger for the whole crew, so every bot shares the cap.
# Every request is reserved at its worst case under the ledger lock before it is
# sent, and settled to what it likely cost right after, so concurrent bots can't
# overrun the cap or lose each other's writes.
# ----------------------------------------------------------------------------

def ledger_path():
    return os.environ.get("SPEND_LEDGER", os.path.join(BOTS_HOME, "dispatch", "spend_ledger.json"))


def crew_now(tz):
    """Now in the owner's timezone. CREW_NOW (ISO time) is a test hook only."""
    fake = os.environ.get("CREW_NOW")
    if fake:
        t = datetime.fromisoformat(fake)
        return t.replace(tzinfo=tz) if t.tzinfo is None else t.astimezone(tz)
    return datetime.now(tz)


def ledger_today(cfg):
    """(today, ledger, path). Read only. Callers that write must hold file_lock(ledger_path())."""
    tz = ZoneInfo(cfg["timezone"]) if ZoneInfo and cfg.get("timezone") else timezone.utc
    day = crew_now(tz).date().isoformat()
    path = ledger_path()
    book = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            book = json.load(f)
    return day, book, path


def _book_into(book, day, amount, who, request=False):
    e = book.setdefault(day, {"total": 0.0, "by_bot": {}})
    e.setdefault("by_bot", {})
    e["total"] = round(max(0.0, e.get("total", 0.0) + amount), 4)
    e["by_bot"][who] = round(max(0.0, e["by_bot"].get(who, 0.0) + amount), 4)
    if request:
        reqs = e.setdefault("requests", {})
        reqs[who] = reqs.get(who, 0) + 1


def ledger_add(cfg, amount, who, day=None):
    """Book amount (may be negative to release a reservation) under the ledger lock."""
    if not amount:
        return
    with file_lock(ledger_path()):
        today, book, path = ledger_today(cfg)
        _book_into(book, day or today, amount, who)
        write_json(path, book)


def _cap_for(cfg, book, day):
    raise_ = (book.get(day) or {}).get("cap_raise") or {}
    amount = raise_.get("amount")
    if isinstance(amount, (int, float)) and amount > cfg["daily_spend_cap"]:
        return float(amount)
    return float(cfg["daily_spend_cap"])


def effective_cap(cfg):
    """Today's cap. A one-day raise confirmed through Dispatch (spend.py raise) is saved under
    today's date in the ledger, so it ends at midnight in the owner's timezone by itself."""
    day, book, _ = ledger_today(cfg)
    return _cap_for(cfg, book, day)


def spent_today(cfg):
    day, book, _ = ledger_today(cfg)
    return (book.get(day) or {}).get("total", 0.0)


def worst_case(cfg, path, params, owner_id=None, owned=None):
    """The most one request could cost, from the shared price table (x_prices.py).
    Attached author profiles are not in this worst case. The settle step books them right
    after, so a run can pass the cap by one page."""
    return x_prices.worst_case(path, params, owner_id, owned)


def response_cost(cfg, path, body, owner_id=None, owned=None):
    """What one response likely cost, from the shared price table (x_prices.py)."""
    return x_prices.response_cost(path, body, owner_id, owned)


def owner_path():
    return os.path.join(BOTS_HOME, "dispatch", "owner.json")


def read_owner_id():
    try:
        with open(owner_path(), encoding="utf-8") as f:
            return str(json.load(f).get("id") or "") or None
    except Exception:
        return None


def what_for(path):
    """Plain name for what a request reads, for 'stopped before ..., cap reached' messages."""
    p = path.split("?")[0]
    for end, label in (("/users/me", "the account check"), ("/followers", "followers"),
                       ("/following", "following"), ("/mentions", "mentions"),
                       ("/liked_tweets", "your likes"), ("/quote_tweets", "quote posts"),
                       ("/liking_users", "likers"), ("/tweets/search/recent", "search")):
        if p.endswith(end):
            return label
    if re.fullmatch(r"/users/[^/]+/tweets", p):
        return "posts"
    if p == "/tweets":
        return "post lookups"
    if p in ("/users", "/users/by"):
        return "profile lookups"
    return p


class CapReached(SystemExit):
    """A request was stopped before it was sent because it could pass today's cap.
    Subclass of SystemExit, so a bot that doesn't catch it still stops with this message."""

    def __init__(self, path, spent, worst, cap):
        self.path, self.label, self.spent, self.worst, self.cap = path, what_for(path), spent, worst, cap
        super().__init__(f"Stopped before {self.label}, cap reached. Today's spend is ${spent:.2f} and the next "
                         f"request could cost up to ${worst:.2f}, which would pass today's cap of ${cap:.2f}. "
                         "Nothing past this point was read.")


def stopped_line(bot, e):
    """The one-line honest result for a run the cap stopped."""
    return f"{bot} stopped before {e.label}, cap reached. {e}"


# ----------------------------------------------------------------------------
# Shared X sign-in. ONE file for the whole crew, owned by Dispatch:
#   $BOTS_HOME/dispatch/x_signin.json  (owner-only permissions)
# Renewal takes a file lock, so one bot renews while the others wait, then they
# re-read the new file. Nothing ever copies this file. A failed renewal stops the
# bot with SIGNIN_REDO. The app's client id and secret come only from stored
# secrets (X_CLIENT_ID, X_CLIENT_SECRET) and are never written to the file.
# ----------------------------------------------------------------------------

SIGNIN_REDO = "X sign-in needs to be redone"
SIGNIN_KEYS = ("access_token", "refresh_token", "expires_at", "scope", "saved_at")


def signin_path():
    return os.path.join(BOTS_HOME, "dispatch", "x_signin.json")


def read_signin():
    p = signin_path()
    if not os.path.exists(p):
        return {}
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def write_signin(tok):
    keep = {k: tok[k] for k in SIGNIN_KEYS if k in tok}
    os.makedirs(os.path.dirname(signin_path()), exist_ok=True)
    write_json(signin_path(), keep, private=True)


def expiring(tok, margin=120):
    return not tok.get("access_token") or time.time() > float(tok.get("expires_at", 0)) - margin


class XClient:
    def __init__(self, store, cfg, meter):
        self.who = crew_bot()  # fails closed before anything else
        self.store = store
        self.cfg = cfg
        self.meter = meter
        self.app = {k: os.environ.get(env) for k, env in (("client_id", "X_CLIENT_ID"),
                                                          ("client_secret", "X_CLIENT_SECRET"))}
        self.tok = read_signin()
        self.owner_id = read_owner_id()  # your account id, so reads of your own data bill as owned
        self._booked = 0.0
        self._charged = 0.0
        import atexit
        atexit.register(self._book)

    # --- spend ---------------------------------------------------------------

    def _target(self):
        # the larger of what the caller metered and what the responses held
        return max(self.meter.cost(), self._charged)

    def _book(self):
        """Book anything metered but not yet in the ledger. Runs before every request and at exit."""
        new = self._target() - self._booked
        if new > 1e-9:
            ledger_add(self.cfg, new, self.who)
            self._booked += new

    def _reserve(self, path, params, owned=None):
        """Under the ledger lock: book what's pending, check the cap, then reserve this request's
        worst case so a bot running at the same moment sees it. Returns (day, worst)."""
        worst = worst_case(self.cfg, path, params, self.owner_id, owned)
        with file_lock(ledger_path()):
            day, book, lpath = ledger_today(self.cfg)
            pending = self._target() - self._booked
            if pending > 1e-9:
                _book_into(book, day, pending, self.who)
                self._booked += pending
            cap = _cap_for(self.cfg, book, day)
            spent = (book.get(day) or {}).get("total", 0.0)
            if spent + worst > cap + 1e-9:
                if pending > 1e-9:
                    write_json(lpath, book)
                raise CapReached(path, spent, worst, cap)
            _book_into(book, day, worst, self.who, request=True)
            write_json(lpath, book)
        self._booked += worst
        return day, worst

    def _settle(self, day):
        """Right after a response (or a failed send): swap the reservation for the likely cost."""
        delta = self._target() - self._booked
        if abs(delta) > 1e-9:
            ledger_add(self.cfg, delta, self.who, day=day)
            self._booked += delta

    # --- sign-in -------------------------------------------------------------

    def _token_request(self, fields):
        """POST to the token endpoint. Returns the JSON body or raises urllib.error.HTTPError/URLError."""
        data = urllib.parse.urlencode(fields).encode()
        req = urllib.request.Request(TOKEN_URL, data=data, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        if self.app.get("client_secret"):
            basic = base64.b64encode(
                f"{self.app['client_id']}:{self.app['client_secret']}".encode()).decode()
            req.add_header("Authorization", "Basic " + basic)
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)

    def _keep(self, body, old_refresh=None):
        tok = {"access_token": body["access_token"],
               "refresh_token": body.get("refresh_token") or old_refresh,
               "expires_at": time.time() + int(body.get("expires_in", 7200)),
               "scope": body.get("scope", ""),
               "saved_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        write_signin(tok)
        self.tok = tok

    def renew(self, used=None, force=False):
        """Make sure self.tok holds a usable access token. Takes the sign-in lock. If another bot
        renewed while this one waited (the file's token differs from `used`), it just reads the new
        file. Otherwise it renews once and writes the file. Any failure: SIGNIN_REDO."""
        with file_lock(signin_path()):
            disk = read_signin()
            if not disk:
                raise SystemExit(f"{SIGNIN_REDO}. No sign-in found at {signin_path()}. "
                                 "Foreman runs `follow_watch.py auth` once for the whole crew.")
            fresh_from_other = disk.get("access_token") and disk.get("access_token") != used
            if not expiring(disk) and (fresh_from_other or not force):
                self.tok = disk
                return
            if not (disk.get("refresh_token") and self.app.get("client_id")):
                raise SystemExit(SIGNIN_REDO)
            try:
                body = self._token_request({"grant_type": "refresh_token",
                                            "refresh_token": disk["refresh_token"],
                                            "client_id": self.app["client_id"]})
                if not body.get("access_token"):
                    raise ValueError("no access_token in the renewal answer")
            except urllib.error.HTTPError as e:
                print(f"Sign-in renewal refused by X (HTTP {e.code}).", file=sys.stderr)
                raise SystemExit(SIGNIN_REDO)
            except Exception as e:  # network, bad JSON, missing field
                print(f"Sign-in renewal failed ({type(e).__name__}).", file=sys.stderr)
                raise SystemExit(SIGNIN_REDO)
            self._keep(body, old_refresh=disk.get("refresh_token"))

    def _auth_header(self):
        if expiring(self.tok):
            self.renew(used=self.tok.get("access_token"))
        return "Bearer " + self.tok["access_token"]

    # --- requests ------------------------------------------------------------

    def get(self, path, params=None, refused_ok=False, owned=None):
        """GET through the cap. refused_ok: return None instead of stopping when X refuses this one
        item (protected, suspended, gone). 402 (out of credits) always stops.
        owned: True when a /tweets?ids= lookup reads your own posts, so it bills as owned."""
        url = API + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        renewed = False
        for attempt in range(6):
            header = self._auth_header()
            day, _ = self._reserve(path, params, owned)
            req = urllib.request.Request(url, method="GET")
            req.add_header("Authorization", header)
            req.add_header("User-Agent", "follow-watch/1.0")
            try:
                try:
                    with urllib.request.urlopen(req, timeout=60) as r:
                        body = json.load(r)
                    if path.split("?")[0] == "/users/me":
                        self._learn_owner(body)
                    self._charged += response_cost(self.cfg, path, body, self.owner_id, owned)
                    return body
                finally:
                    self._settle(day)
            except urllib.error.HTTPError as e:
                text = e.read().decode(errors="replace")
                if e.code == 401 and not renewed:
                    renewed = True
                    self.renew(used=header[len("Bearer "):], force=True)
                    continue
                if e.code == 429:
                    reset = e.headers.get("x-rate-limit-reset")
                    wait = max(5, int(reset) - int(time.time()) + 2) if reset else 60
                    wait = min(wait, 960)
                    print(f"Rate limited, waiting {wait}s", file=sys.stderr)
                    time.sleep(wait)
                    continue
                if 500 <= e.code < 600 and attempt < 5:
                    time.sleep(2 ** attempt * 3)
                    continue
                if e.code == 402:
                    raise SystemExit("X API error 402: out of credits. Nothing else was changed.")
                if refused_ok and e.code in (400, 403, 404):
                    return None
                raise SystemExit(f"X API error {e.code} on {path}: {text}")
            except urllib.error.URLError as e:
                if attempt < 5:
                    time.sleep(2 ** attempt * 3)
                    continue
                if refused_ok:
                    return None
                raise SystemExit(f"Network error on {path}: {e}")
        raise SystemExit(f"Gave up on {path} after retries")

    def _learn_owner(self, body):
        uid = str(((body or {}).get("data") or {}).get("id") or "")
        if uid and uid != self.owner_id:
            self.owner_id = uid
            os.makedirs(os.path.dirname(owner_path()), exist_ok=True)
            write_json(owner_path(), {"id": uid})

    # --- endpoints -----------------------------------------------------------

    def me(self):
        body = self.get("/users/me", {"user.fields": USER_FIELDS})
        self.meter.add("lookup", 1)
        return body["data"]

    def list_all(self, uid, kind, limit=None):
        """Every account in the list, or only the first `limit` (newest first) for a partial scan."""
        users, token = [], None
        while True:
            want = 1000 if not limit else max(1, min(1000, limit - len(users)))
            params = {"max_results": want, "user.fields": USER_FIELDS}
            if token:
                params["pagination_token"] = token
            body = self.get(f"/users/{uid}/{kind}", params)
            page = body.get("data", []) or []
            self.meter.add("owned", len(page))
            users.extend(page)
            token = (body.get("meta") or {}).get("next_token")
            if limit and len(users) >= limit:
                return users[:limit]
            if not token:
                return users

    def list_newest(self, uid, kind, known_ids, page_size, max_pages, stop_after_known):
        """Newest-first read. Stops after a run of already-known accounts."""
        fresh, token, streak = [], None, 0
        for _ in range(max_pages):
            params = {"max_results": page_size, "user.fields": USER_FIELDS}
            if token:
                params["pagination_token"] = token
            body = self.get(f"/users/{uid}/{kind}", params)
            page = body.get("data", []) or []
            self.meter.add("owned", len(page))
            for u in page:
                if u["id"] in known_ids:
                    streak += 1
                    if streak >= stop_after_known:
                        return fresh, True
                else:
                    streak = 0
                    fresh.append(u)
            token = (body.get("meta") or {}).get("next_token")
            if not token:
                return fresh, True
        return fresh, False

    def recent_posts(self, uid, start_time):
        """Newest posts (replies and reposts included) since start_time. Goes through the cap like
        every other read. Returns a list, or None if X refuses (protected, suspended, gone)."""
        params = {"max_results": 5, "start_time": start_time, "tweet.fields": "created_at"}
        body = self.get(f"/users/{uid}/tweets", params, refused_ok=True)
        if body is None:
            return None
        page = body.get("data", []) or []
        self.meter.add("post", len(page))
        return page

    def lookup(self, ids):
        """Returns (found {id: user}, gone {id: reason})."""
        found, gone = {}, {}
        ids = list(ids)
        for i in range(0, len(ids), 100):
            chunk = ids[i:i + 100]
            body = self.get("/users", {"ids": ",".join(chunk), "user.fields": USER_FIELDS})
            for u in body.get("data", []) or []:
                found[u["id"]] = u
            for err in body.get("errors", []) or []:
                uid = str(err.get("value") or err.get("resource_id") or "")
                detail = (err.get("detail") or "") + " " + (err.get("title") or "")
                if uid:
                    gone[uid] = "suspended" if "suspend" in detail.lower() else "deactivated or not found"
            self.meter.add("lookup", len(chunk))
        for uid in ids:
            if uid not in found and uid not in gone:
                gone[uid] = "not returned"
        return found, gone


# ----------------------------------------------------------------------------
# Account assessment
# ----------------------------------------------------------------------------

def slim(u):
    keys = ("id", "username", "name", "description", "created_at", "profile_image_url",
            "protected", "verified", "verified_type", "url", "location",
            "public_metrics", "most_recent_tweet_id")
    return {k: u.get(k) for k in keys if k in u}


def is_verified(u):
    return bool(u.get("verified")) or (u.get("verified_type") or "none") in ("blue", "business", "government")


def last_post_date(u):
    tid = u.get("most_recent_tweet_id")
    if not tid:
        return None
    try:
        ms = (int(tid) >> 22) + TWITTER_EPOCH_MS
    except ValueError:
        return None
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).date()


def readable(pattern):
    out = re.sub(r"\\b", "", pattern)
    out = re.sub(r"\(([^()]*)\)\?", r"\1", out)
    out = out.replace(" ?", " ").replace("\\", "").replace("?", "")
    return re.sub(r"\s+", " ", out).strip()


def compile_spam(cfg):
    return [(p, re.compile(p, re.I)) for p in cfg["spam_patterns"]]


def base_activity(u, today, cfg):
    pm = u.get("public_metrics") or {}
    last = last_post_date(u)
    idle = (today - last).days if last else None
    if (pm.get("tweet_count", 0) or 0) == 0:
        activity = "never posted"
    elif idle is None:
        activity = "unknown"
    elif idle >= cfg["dormant_days"]:
        activity = "dormant"
    elif idle >= cfg["inactive_days"]:
        activity = "inactive"
    else:
        activity = "active"
    return last, idle, activity


def assess(u, today, cfg, spam_res):
    pm = u.get("public_metrics") or {}
    followers = pm.get("followers_count", 0) or 0
    following = pm.get("following_count", 0) or 0
    posts = pm.get("tweet_count", 0) or 0
    likes = pm.get("like_count", 0) or 0
    score, reasons = 0, []

    def add(points, why):
        nonlocal score
        score += points
        reasons.append(why)

    if "default_profile" in (u.get("profile_image_url") or ""):
        add(20, "default avatar")
    if not (u.get("description") or "").strip():
        add(10, "empty bio")
    if re.search(r"\d{5,}$", u.get("username") or ""):
        add(15, "auto-style handle")
    created = u.get("created_at")
    age = None
    if created:
        try:
            age = (today - datetime.fromisoformat(created.replace("Z", "+00:00")).date()).days
        except ValueError:
            age = None
    if age is not None and age < 30:
        add(15, f"account {age}d old")
    elif age is not None and age < 90:
        add(8, f"account {age}d old")
    if posts == 0:
        add(15, "never posted")
    elif posts < 10:
        add(8, f"{posts} posts total")
    if followers < 10:
        add(10, f"{followers} followers")
    if following >= 1000 and following > 10 * max(followers, 1):
        add(20, f"follows {following:,}, followed by {followers:,}")
    if likes > 1000 and posts < 5:
        add(10, "likes a lot, posts almost nothing")
    if is_verified(u):
        score -= 10
    score = max(0, min(100, score))

    text = " ".join([u.get("name") or "", u.get("description") or "", u.get("url") or ""])
    spam_hits = sorted({readable(p) for p, rx in spam_res if rx.search(text)})

    last, idle, activity = base_activity(u, today, cfg)
    # A protected account's "most recent post" field is often stale and its posts
    # can't be read publicly. Only call it idle once a recheck has read its posts.
    if u.get("protected") and activity in ("inactive", "dormant", "unknown") and not u.get("confirmed_idle"):
        activity = "private"

    tags = []
    if score >= cfg["likely_fake_score"]:
        tags.append("likely fake")
    elif score >= cfg["watch_score"]:
        tags.append("watch")
    if spam_hits:
        tags.append("spam signals")
    if activity in ("inactive", "dormant", "never posted"):
        tags.append(activity)

    if (u.get("username") or "").lower() in {x.lower().lstrip("@") for x in cfg["never_flag"]}:
        tags = []
    return {"score": score, "reasons": reasons, "spam_hits": spam_hits,
            "last_post": last.isoformat() if last else "", "idle_days": idle,
            "activity": activity, "tags": tags, "verified": is_verified(u)}


# ----------------------------------------------------------------------------
# Scans
# ----------------------------------------------------------------------------

def event(ts, today, kind, acc, days=None, days_min=False, detail=""):
    u = acc.get("user", {})
    return {"ts": ts, "date": today.isoformat(), "event": kind, "id": u.get("id", ""),
            "username": u.get("username", ""), "name": u.get("name", ""),
            "days": "" if days is None else days, "days_min": "yes" if days_min else "",
            "detail": detail}


def span(today, since, baseline):
    if not since:
        return None, False
    return (today - d(since)).days, bool(baseline)


def cmd_full(store, cfg, client, now, limit=None):
    """limit: read only the first N followers and first N following (newest first). The scan is
    saved as PARTIAL: it never becomes the baseline and never marks unseen accounts as unfollows."""
    today, ts = now.date(), now.astimezone(timezone.utc).isoformat(timespec="seconds")
    me = client.me()
    uid = me["id"]
    print(f"Reading followers of @{me['username']}" + (f" (first {limit} only)" if limit else "") + "...", file=sys.stderr)
    followers = client.list_all(uid, "followers", limit)
    print(f"Reading accounts @{me['username']} follows" + (f" (first {limit} only)" if limit else "") + "...", file=sys.stderr)
    following = client.list_all(uid, "following", limit)
    pm = me.get("public_metrics") or {}
    partial = bool(limit) and (len(followers) < pm.get("followers_count", 0)
                               or len(following) < pm.get("following_count", 0))

    state = store.load_state()
    accounts = state.setdefault("accounts", {})
    first = not state.get("baseline_date")
    if partial:
        prev_fol0 = {i for i, a in accounts.items() if a.get("follower_now")}
        prev_fing0 = {i for i, a in accounts.items() if a.get("following_now")}
    fol_ids = {u["id"] for u in followers}
    fing_ids = {u["id"] for u in following}
    prev_fol = {i for i, a in accounts.items() if a.get("follower_now")}
    prev_fing = {i for i, a in accounts.items() if a.get("following_now")}

    for u in followers + following:
        acc = accounts.setdefault(u["id"], {})
        acc["user"] = slim(u)
        acc["last_seen"] = today.isoformat()
        acc.pop("gone", None)

    events = []
    if partial:
        # Partial: record who was seen, add nothing as lost, start no clocks as a baseline.
        for i in {u["id"] for u in followers}:
            accounts[i].setdefault("follower_since", None)
        fol_ids = fol_ids | prev_fol0
        fing_ids = fing_ids | prev_fing0
        for i in {u["id"] for u in followers}:
            accounts[i]["follower_now"] = True
        for i in {u["id"] for u in following}:
            accounts[i]["following_now"] = True
    elif first:
        state["baseline_date"] = today.isoformat()
        for i in fol_ids:
            accounts[i].update(follower_now=True, follower_since=today.isoformat(), follower_baseline=True)
        for i in fing_ids:
            accounts[i].update(following_now=True, following_since=today.isoformat(), following_baseline=True)
    else:
        new_fing = fing_ids - prev_fing
        lost_fing = prev_fing - fing_ids
        new_fol = fol_ids - prev_fol
        lost_fol = prev_fol - fol_ids

        gone = {}
        check = sorted(lost_fol | lost_fing)
        if check:
            found, gone = client.lookup(check)
            for i, u in found.items():
                accounts.setdefault(i, {})["user"] = slim(u)

        for i in sorted(new_fing):
            acc = accounts[i]
            acc.update(following_now=True, following_since=today.isoformat(), following_baseline=False)
            events.append(event(ts, today, "you_followed", acc,
                                detail="already follows you" if i in fol_ids else ""))
        for i in sorted(lost_fing):
            acc = accounts.setdefault(i, {})
            days, mn = span(today, acc.get("following_since"), acc.get("following_baseline"))
            acc.update(following_now=False, following_since=None, following_baseline=False)
            if i in gone:
                continue
            events.append(event(ts, today, "you_unfollowed", acc, days, mn))
        for i in sorted(new_fol):
            acc = accounts[i]
            acc.update(follower_now=True, follower_since=today.isoformat(), follower_baseline=False)
            if i in fing_ids and i not in new_fing:
                days, mn = span(today, acc.get("following_since"), acc.get("following_baseline"))
                events.append(event(ts, today, "followed_back", acc, days, mn))
            elif i in new_fing:
                events.append(event(ts, today, "new_mutual", acc, detail="you both followed since last scan"))
            else:
                events.append(event(ts, today, "new_follower", acc))
        for i in sorted(lost_fol):
            acc = accounts.setdefault(i, {})
            days, mn = span(today, acc.get("follower_since"), acc.get("follower_baseline"))
            acc.update(follower_now=False, follower_since=None, follower_baseline=False)
            if i in gone:
                acc["gone"] = {"reason": gone[i], "date": today.isoformat()}
                events.append(event(ts, today, "gone", acc, days, mn, detail=gone[i]))
            else:
                events.append(event(ts, today, "unfollowed_you", acc, days, mn,
                                    detail="you still follow them" if i in fing_ids else ""))
        for i in sorted(lost_fing - lost_fol):
            if i in gone:
                acc = accounts[i]
                acc["gone"] = {"reason": gone[i], "date": today.isoformat()}
                events.append(event(ts, today, "gone", acc, detail=gone[i] + " (you followed them)"))

    for i, acc in accounts.items():
        acc["follower_now"] = i in fol_ids
        acc["following_now"] = i in fing_ids

    # prune accounts with no relationship that have been gone for a while
    for i in [i for i, a in accounts.items()
              if not a.get("follower_now") and not a.get("following_now")
              and a.get("last_seen") and (today - d(a["last_seen"])).days > 180]:
        del accounts[i]

    prev_full = state.get("last_full")
    state["prev_full"] = prev_full
    state["me"] = slim(me)
    summary = summarize(accounts, cfg, today)
    state["last_full"] = {"ts": ts, "date": today.isoformat(), "summary": summary}
    if partial:
        state["last_full"].update(partial=True, limit=limit, read={"followers": len(followers),
                                  "following": len(following)}, real_counts={"followers": pm.get("followers_count"),
                                  "following": pm.get("following_count")})
        print(f"PARTIAL scan: read the first {len(followers)} of {pm.get('followers_count')} followers and the "
              f"first {len(following)} of {pm.get('following_count')} following. Counts below cover only those. "
              "This is not a baseline and no unfollows were worked out from it.", file=sys.stderr)
    state["last_me_counts"] = (me.get("public_metrics") or {})
    state["last_run"] = {"ts": ts, "kind": "full"}
    store.save_state(state)
    store.append_events(events)
    write_json(os.path.join(store.snapshots, f"{today.isoformat()}_{now.strftime('%H%M')}" + ("_partial" if partial else "") + ".json"),
               {"followers": sorted(fol_ids), "following": sorted(fing_ids)})

    path = build_full_report(store, cfg, state, now, client.meter, first)
    print(path)


def cmd_light(store, cfg, client, now, page_size=None):
    today, ts = now.date(), now.astimezone(timezone.utc).isoformat(timespec="seconds")
    state = store.load_state()
    if not state.get("baseline_date"):
        raise SystemExit("No baseline yet. Run `full` first.")
    accounts = state["accounts"]
    me = client.me()
    uid = me["id"]
    known_fing = {i for i, a in accounts.items() if a.get("following_now")}
    known_fol = {i for i, a in accounts.items() if a.get("follower_now")}

    size = page_size or cfg["light_page_size"]
    new_f, complete_f = client.list_newest(uid, "following", known_fing, size,
                                           cfg["light_max_pages"], cfg["light_stop_after_known"])
    new_fol, complete_fol = client.list_newest(uid, "followers", known_fol, size,
                                               cfg["light_max_pages"], cfg["light_stop_after_known"])
    events = []
    for u in new_f:
        acc = accounts.setdefault(u["id"], {})
        acc["user"] = slim(u)
        acc["last_seen"] = today.isoformat()
        acc.update(following_now=True, following_since=today.isoformat(), following_baseline=False)
        events.append(event(ts, today, "you_followed", acc,
                            detail="already follows you" if acc.get("follower_now") else ""))
    new_f_ids = {u["id"] for u in new_f}
    for u in new_fol:
        acc = accounts.setdefault(u["id"], {})
        acc["user"] = slim(u)
        acc["last_seen"] = today.isoformat()
        acc.update(follower_now=True, follower_since=today.isoformat(), follower_baseline=False)
        if acc.get("following_now") and u["id"] not in new_f_ids:
            days, mn = span(today, acc.get("following_since"), acc.get("following_baseline"))
            events.append(event(ts, today, "followed_back", acc, days, mn))
        elif u["id"] in new_f_ids:
            events.append(event(ts, today, "new_mutual", acc, detail="you both followed today"))
        else:
            events.append(event(ts, today, "new_follower", acc))

    counts = me.get("public_metrics") or {}
    prev = state.get("last_me_counts") or {}
    est_lost = None
    if "followers_count" in prev and "followers_count" in counts:
        est_lost = max(0, prev["followers_count"] + len(new_fol) - counts["followers_count"])
    light = {"ts": ts, "followers_count": counts.get("followers_count"),
             "following_count": counts.get("following_count"),
             "new_followers": len(new_fol), "new_follows": len(new_f),
             "est_unfollows": est_lost, "complete": complete_f and complete_fol}
    state.setdefault("light_log", []).append(light)
    state["light_log"] = state["light_log"][-120:]
    state["last_me_counts"] = counts
    state["last_run"] = {"ts": ts, "kind": "light"}
    store.save_state(state)
    store.append_events(events)
    path = build_light_report(store, cfg, state, now, client.meter, events, light)
    print(path)
    return events, light


def cmd_daily(store, cfg, client, now):
    events, light = cmd_light(store, cfg, client, now, page_size=cfg["daily_page_size"])
    state = store.load_state()
    today = now.date()
    # bring the snapshot numbers up to date so the Follow Audit page reflects today
    state["last_full"]["summary"] = summarize(state["accounts"], cfg, today)
    state["last_full"]["refreshed_by_daily"] = now.astimezone(timezone.utc).isoformat(timespec="seconds")
    store.save_state(state)
    build_full_report(store, cfg, state, now, client.meter, first=not state.get("prev_full"))
    kinds = {}
    for e in events:
        kinds[e["event"]] = kinds.get(e["event"], 0) + 1
    s = state["last_full"]["summary"]
    print(f"Daily check {now.strftime('%a %b %d, %I:%M %p')}: {kinds.get('new_follower', 0)} new followers, "
          f"{kinds.get('followed_back', 0) + kinds.get('new_mutual', 0)} followed you back, "
          f"{kinds.get('you_followed', 0)} new follows by you, "
          f"about {light['est_unfollows'] if light['est_unfollows'] is not None else 'n/a'} unfollows (names come "
          f"with the monthly full scan). Not following back: {s['not_following_back']:,}. "
          f"Read {client.meter.owned + client.meter.lookup:,} records, about ${client.meter.cost():.2f}."
          + ("" if light["complete"] else " More new accounts than this check reads, the next run continues."))


# ----------------------------------------------------------------------------
# Reports
# ----------------------------------------------------------------------------

def summarize(accounts, cfg, today):
    fol = [a for a in accounts.values() if a.get("follower_now")]
    fing = [a for a in accounts.values() if a.get("following_now")]
    skip = {x.lower().lstrip("@") for x in cfg["skip_followback"]}
    nfb = [a for a in fing if not a.get("follower_now")
           and (a["user"].get("username") or "").lower() not in skip]
    return {"followers": len(fol), "following": len(fing),
            "mutuals": sum(1 for a in fing if a.get("follower_now")),
            "verified_followers": sum(1 for a in fol if is_verified(a["user"])),
            "not_following_back": len(nfb)}


def link(u):
    name = u.get("username") or u.get("id", "?")
    return f"[@{name}](https://x.com/{name})"


def fmt_days(days, mn):
    if days in (None, ""):
        return "n/a"
    return f"{days}+ days" if mn in (True, "yes") else f"{days} days"


def md_table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(c).replace("|", "/").replace("\n", " ") for c in r) + " |")
    return "\n".join(out)


def delta(now_v, prev_v):
    if prev_v is None:
        return ""
    diff = now_v - prev_v
    return f"+{diff:,}" if diff > 0 else (f"{diff:,}" if diff < 0 else "0")


def build_full_report(store, cfg, state, now, meter, first):
    today = now.date()
    spam_res = compile_spam(cfg)
    accounts = state["accounts"]
    s = state["last_full"]["summary"]
    prev = (state.get("prev_full") or {}).get("summary") or {}
    prev_ts = (state.get("prev_full") or {}).get("ts")
    n = cfg["report_rows_per_section"]
    skip = {x.lower().lstrip("@") for x in cfg["skip_followback"]}
    me = state.get("me", {})

    L = [f"# Follow Audit: full scan for @{me.get('username', '')}, {now.strftime('%a %b %d, %Y %I:%M %p')}",
         "", "Read-only run. Nothing was followed, unfollowed, blocked, muted or removed.", ""]
    lf = state.get("last_full") or {}
    if lf.get("partial"):
        r, rc = lf.get("read") or {}, lf.get("real_counts") or {}
        L += [f"**PARTIAL SCAN (--limit {lf.get('limit')}).** Read only the first {r.get('followers')} of "
              f"{rc.get('followers')} followers and the first {r.get('following')} of {rc.get('following')} following. "
              "Every count and list below covers only those accounts. It is not a baseline and no unfollows "
              "were worked out from it.", ""]
    elif first:
        L += [f"This is the baseline. Follow-back clocks start today ({today.isoformat()}) for every account "
              "you already follow, so their waiting time shows as a minimum (for example 30+ days). "
              "Unfollow tracking starts with the next full scan.", ""]

    L += ["## Snapshot", "", md_table(["", "Now", "Change since last full scan"], [
        ["Followers", f"{s['followers']:,}", delta(s["followers"], prev.get("followers"))],
        ["Following", f"{s['following']:,}", delta(s["following"], prev.get("following"))],
        ["Mutuals", f"{s['mutuals']:,}", delta(s["mutuals"], prev.get("mutuals"))],
        ["Verified followers", f"{s['verified_followers']:,}",
         delta(s["verified_followers"], prev.get("verified_followers"))],
        ["You follow, they don't follow back", f"{s['not_following_back']:,}",
         delta(s["not_following_back"], prev.get("not_following_back"))],
    ]), ""]

    evs = [e for e in store.read_events() if prev_ts and e["ts"] > prev_ts]
    by = {}
    for e in evs:
        by.setdefault(e["event"], []).append(e)

    if not first:
        since = d(prev_ts[:10]).strftime("%b %d") if prev_ts else "the last scan"
        fb = by.get("followed_back", [])
        fb_days = [int(e["days"]) for e in fb if e["days"] not in ("", None) and not e["days_min"]]
        avg = (f", average {sum(fb_days) / len(fb_days):.0f} days for accounts you followed after tracking began"
               if fb_days else "")
        L += [f"## Since {since}", "",
              f"- New followers: {len(by.get('new_follower', []))}",
              f"- Followed you back: {len(fb)}{avg}",
              f"- New mutuals from both sides at once: {len(by.get('new_mutual', []))}",
              f"- Unfollowed you: {len(by.get('unfollowed_you', []))}",
              f"- Gone (suspended or deactivated): {len(by.get('gone', []))}",
              f"- You followed: {len(by.get('you_followed', []))}",
              f"- You unfollowed: {len(by.get('you_unfollowed', []))}", ""]

        uf = by.get("unfollowed_you", [])
        if uf:
            rows = []
            for e in uf:
                u = (accounts.get(e["id"]) or {}).get("user", {"username": e["username"]})
                rows.append([link(u), fmt_days(e["days"], e["days_min"]),
                             "yes" if e["detail"] else "no", "yes" if is_verified(u) else ""])
            L += ["## Unfollowed you", "",
                  "A soft block (they removed you) looks the same as an unfollow from the API.", "",
                  md_table(["Account", "Followed you for", "You still follow them", "Verified"], rows), ""]

        newm = fb + by.get("new_mutual", [])
        if newm:
            rows = []
            for e in newm:
                u = (accounts.get(e["id"]) or {}).get("user", {"username": e["username"]})
                rows.append([link(u), fmt_days(e["days"], e["days_min"]) if e["event"] == "followed_back"
                             else "same period", "yes" if is_verified(u) else ""])
            L += ["## New mutuals", "", "Candidates for your New Connections list. Add them by hand if you want them there.", "",
                  md_table(["Account", "Took to follow back", "Verified"], rows), ""]

        nf = by.get("new_follower", [])
        if nf:
            rows = []
            for e in nf:
                u = (accounts.get(e["id"]) or {}).get("user", {"username": e["username"]})
                a = assess(u, today, cfg, spam_res)
                pm = u.get("public_metrics") or {}
                rows.append([link(u), "yes" if a["verified"] else "", f"{pm.get('followers_count', 0):,}",
                             ", ".join(a["tags"]) or "clean"])
            rows.sort(key=lambda r: (r[3] != "clean", r[1] != "yes"))
            L += ["## New followers you don't follow yet", "",
                  md_table(["Account", "Verified", "Their followers", "Flags"], rows[:n]), ""]
            if len(rows) > n:
                L += [f"{len(rows) - n} more in events.csv.", ""]

        gone = by.get("gone", [])
        if gone:
            L += ["## Gone", "", md_table(["Account", "Status"], [[f"@{e['username']}", e["detail"]] for e in gone]), ""]

    # not following back
    nfb_rows = []
    for i, a in accounts.items():
        if not a.get("following_now") or a.get("follower_now"):
            continue
        u = a["user"]
        if (u.get("username") or "").lower() in skip:
            continue
        days, mn = span(today, a.get("following_since"), a.get("following_baseline"))
        info = assess(u, today, cfg, spam_res)
        pm = u.get("public_metrics") or {}
        nfb_rows.append({"id": i, "username": u.get("username", ""), "name": u.get("name", ""),
                         "days_waiting": days, "minimum": "yes" if mn else "",
                         "verified": "yes" if info["verified"] else "",
                         "followers": pm.get("followers_count", 0), "following": pm.get("following_count", 0),
                         "last_post": info["last_post"], "activity": info["activity"],
                         "flags": "; ".join(info["tags"]), "url": f"https://x.com/{u.get('username', '')}"})
    nfb_rows.sort(key=lambda r: -(r["days_waiting"] or 0))
    write_csv(os.path.join(store.reports, "not_following_back.csv"), nfb_rows)

    buckets = [("Over 90 days", 91, 10 ** 6), ("31 to 90 days", 31, 90),
               ("8 to 30 days", 8, 30), ("7 days or less", 0, 7)]
    L += ["## You follow, they don't follow back", "",
          f"{len(nfb_rows):,} accounts. Full list in not_following_back.csv. "
          "Accounts in skip_followback in config.json are left out.", ""]
    for title, lo, hi in buckets:
        rows = [r for r in nfb_rows if r["days_waiting"] is not None and lo <= r["days_waiting"] <= hi]
        if not rows:
            continue
        L += [f"### {title} ({len(rows):,})", "",
              md_table(["Account", "Waiting", "Verified", "Their followers", "Last post", "Flags"],
                       [[f"[@{r['username']}]({r['url']})", fmt_days(r["days_waiting"], r["minimum"]),
                         r["verified"], f"{r['followers']:,}", r["last_post"] or "unknown",
                         r["flags"] or ""] for r in rows[:n]]), ""]
        if len(rows) > n:
            L += [f"{len(rows) - n:,} more in the CSV.", ""]

    # flagged
    for side, key, fname, title in (("followers", "follower_now", "flagged_followers.csv", "Flagged followers"),
                                    ("following", "following_now", "flagged_following.csv",
                                     "Flagged accounts you follow")):
        rows = []
        for i, a in accounts.items():
            if not a.get(key):
                continue
            info = assess(a["user"], today, cfg, spam_res)
            if not info["tags"]:
                continue
            u = a["user"]
            pm = u.get("public_metrics") or {}
            rows.append({"id": i, "username": u.get("username", ""), "name": u.get("name", ""),
                         "score": info["score"], "tags": "; ".join(info["tags"]),
                         "reasons": "; ".join(info["reasons"]),
                         "spam_matches": "; ".join(info["spam_hits"]),
                         "last_post": info["last_post"], "idle_days": info["idle_days"] or "",
                         "followers": pm.get("followers_count", 0), "following": pm.get("following_count", 0),
                         "posts": pm.get("tweet_count", 0), "verified": "yes" if info["verified"] else "",
                         "mutual": "yes" if a.get("follower_now") and a.get("following_now") else "",
                         "url": f"https://x.com/{u.get('username', '')}"})
        rows.sort(key=lambda r: (-r["score"], r["username"].lower()))
        write_csv(os.path.join(store.reports, fname), rows)
        counts = {}
        for r in rows:
            for t in r["tags"].split("; "):
                counts[t] = counts.get(t, 0) + 1
        order = ["likely fake", "watch", "spam signals", "never posted", "dormant", "inactive"]
        L += [f"## {title}", "",
              ", ".join(f"{t}: {counts[t]:,}" for t in order if t in counts) or "Nothing flagged.", "",
              f"Inactive means no post in {cfg['inactive_days']} days. Dormant means {cfg['dormant_days']}+. "
              f"Full list in {fname}.", ""]
        top = [r for r in rows if "likely fake" in r["tags"] or "spam signals" in r["tags"]][:n]
        if top:
            L += [md_table(["Account", "Score", "Flags", "Why"],
                           [[f"[@{r['username']}]({r['url']})", r["score"], r["tags"],
                             "; ".join(x for x in (r["reasons"], r["spam_matches"]) if x)] for r in top]), ""]

    L += ["## Run cost", "",
          f"Read {meter.owned:,} follower and following records and {meter.lookup:,} profile lookups. "
          f"Estimated ${meter.cost():.2f} at the rates in x_prices.py. "
          "Check the X developer console for the billed amount.", ""]

    name = f"{today.isoformat()}_full.md"
    path = os.path.join(store.reports, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    with open(os.path.join(store.reports, "latest_full.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    return path


def recheck_targets(state, cfg, today, followers_too):
    spam_res = compile_spam(cfg)
    skip_days = cfg["recheck_skip_days"]
    out = []
    for i, a in state.get("accounts", {}).items():
        if not (a.get("following_now") or (followers_too and a.get("follower_now"))):
            continue
        u = a["user"]
        if u.get("protected"):
            # readable only if you follow them, and only worth reading if X's date says idle
            if not a.get("following_now"):
                continue
            if base_activity(u, today, cfg)[2] not in ("inactive", "dormant", "unknown"):
                continue
            info = assess(u, today, cfg, spam_res)
            if u.get("confirmed_idle") and info["activity"] not in ("inactive", "dormant", "unknown"):
                continue
        else:
            info = assess(u, today, cfg, spam_res)
            if info["activity"] not in ("inactive", "dormant", "unknown"):
                continue
        last = a.get("activity_checked")
        if last and (today - d(last)).days < skip_days:
            continue
        out.append((i, a, info))
    # accounts you follow first, then longest idle first
    out.sort(key=lambda t: (not t[1].get("following_now"), -(t[2]["idle_days"] or 10 ** 6)))
    return out


def cmd_recheck(store, cfg, client, now, followers_too, estimate):
    today = now.date()
    state = store.load_state()
    if not state.get("last_full"):
        raise SystemExit("No full scan saved yet.")
    targets = recheck_targets(state, cfg, today, followers_too)
    worst = len(targets) * 5 * x_prices.RATES["post"]
    side = "accounts you follow and your followers" if followers_too else "accounts you follow"
    print(f"Flagged inactive or dormant, not checked in the last {cfg['recheck_skip_days']} days: "
          f"{len(targets):,} ({side}).")
    print(f"Worst case ${worst:.2f} if every one has 5 recent posts. Truly idle accounts return no posts. "
          f"Cap for this run: ${cfg['recheck_max_cost']:.2f}.")
    if estimate or not targets:
        return
    start = (datetime.now(timezone.utc) - timedelta(days=cfg["inactive_days"])).strftime("%Y-%m-%dT%H:%M:%SZ")
    checked = active = refused = 0
    stopped = False
    cap_stop = None
    revived = []
    for i, a, info in targets:
        if client.meter.cost() + 5 * x_prices.RATES["post"] > cfg["recheck_max_cost"]:
            stopped = True
            break
        try:
            posts = client.recent_posts(i, start)
        except CapReached as e:
            cap_stop = e
            break
        checked += 1
        a["activity_checked"] = today.isoformat()
        if posts is None:
            refused += 1
            continue
        if not posts:
            a["user"]["confirmed_idle"] = today.isoformat()
        if posts:
            a["user"].pop("confirmed_idle", None)
            newest = max(int(p["id"]) for p in posts)
            cur = a["user"].get("most_recent_tweet_id")
            if not cur or newest > int(cur):
                a["user"]["most_recent_tweet_id"] = str(newest)
            active += 1
            revived.append(a["user"].get("username", ""))
        time.sleep(0.2)
    state["last_recheck"] = {"ts": now.astimezone(timezone.utc).isoformat(timespec="seconds"),
                             "checked": checked, "active": active}
    store.save_state(state)
    path = build_full_report(store, cfg, state, now, client.meter, first=not state.get("prev_full"))
    print(f"Checked {checked:,}. Posted in the last {cfg['inactive_days']} days: {active:,}, "
          f"now unflagged. Still idle: {checked - active - refused:,}. Skipped by X (protected or gone): {refused:,}.")
    print(f"Read {client.meter.posts:,} posts. Estimated ${client.meter.cost():.2f}.")
    if stopped:
        print(f"Stopped at the ${cfg['recheck_max_cost']:.2f} cap with {len(targets) - checked:,} left. "
              "Run recheck again to continue. Checked accounts are skipped.")
    if cap_stop:
        print(f"{stopped_line(client.who, cap_stop)} {len(targets) - checked:,} accounts were not checked. "
              "Run recheck again after midnight or after a one-day raise. Checked accounts are skipped.")
    print(f"Report rebuilt: {path}")


def build_light_report(store, cfg, state, now, meter, events, light):
    today = now.date()
    spam_res = compile_spam(cfg)
    accounts = state["accounts"]
    L = [f"# Follow Audit: daily check, {now.strftime('%a %b %d, %Y %I:%M %p')}", "",
         "Read-only run. Nothing was followed, unfollowed, blocked, muted or removed.", "",
         f"- Followers: {light['followers_count']:,}" if light["followers_count"] is not None else "- Followers: n/a",
         f"- Following: {light['following_count']:,}" if light["following_count"] is not None else "- Following: n/a",
         f"- New followers: {light['new_followers']}",
         f"- New follows by you (clock started): {light['new_follows']}"]
    if light["est_unfollows"] is not None:
        L.append(f"- Unfollows since last check: about {light['est_unfollows']} "
                 "(count only. Names come with the weekly full scan.)")
    if not light["complete"]:
        L.append("- More new accounts than this check reads. The next full scan picks up the rest.")
    L.append("")
    fb = [e for e in events if e["event"] in ("followed_back", "new_mutual")]
    if fb:
        L += ["## Followed you back", "",
              md_table(["Account", "Took"], [[link(accounts[e["id"]]["user"]),
                                              fmt_days(e["days"], e["days_min"]) if e["event"] == "followed_back"
                                              else "same day"] for e in fb]), ""]
    nf = [e for e in events if e["event"] == "new_follower"]
    if nf:
        rows = []
        for e in nf:
            u = accounts[e["id"]]["user"]
            a = assess(u, today, cfg, spam_res)
            rows.append([link(u), "yes" if a["verified"] else "", ", ".join(a["tags"]) or "clean"])
        L += ["## New followers", "", md_table(["Account", "Verified", "Flags"], rows), ""]
    L += [f"Run cost: {meter.owned + meter.lookup:,} records read, about ${meter.cost():.2f}.", ""]
    path = os.path.join(store.reports, f"{today.isoformat()}_daily.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    return path


def write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        if not rows:
            f.write("")
            return
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


# ----------------------------------------------------------------------------
# One-time OAuth 2.0 sign-in (PKCE) for the whole crew
#
# Main path: the owner approves in the bot's own browser (on this computer). X sends
# that browser back to redirect_uri, where this script is already listening, and the
# code is swapped for a sign-in the moment it arrives.
# Backup: if that page can't load, the owner copies the full address from the address
# bar and pastes it to Foreman, who hands it to this same waiting script with
#   python3 follow_watch.py auth-paste '<address>'
# (or types it on stdin with --paste). The waiting script swaps it at once. X's code
# only lives about 30 seconds, so the swap can't wait for anything else.
# ----------------------------------------------------------------------------

PASTE_WAIT_SECONDS = 600


def paste_inbox():
    """Named pipe the waiting sign-in reads pasted addresses from. Exists only while auth waits."""
    return os.path.join(BOTS_HOME, "dispatch", ".signin_paste")


def cmd_auth_paste(address):
    """Hand a pasted redirect address to the sign-in that is waiting. Never stores it."""
    p = paste_inbox()
    try:
        fd = os.open(p, os.O_WRONLY | os.O_NONBLOCK)
    except (FileNotFoundError, OSError):
        raise SystemExit("No sign-in is waiting for an address. Start `follow_watch.py auth` again, approve, "
                         "and paste the new address within about 30 seconds.")
    with os.fdopen(fd, "w") as f:
        f.write(address.strip() + "\n")
    print("Handed to the waiting sign-in.")


def wait_for_redirect(redirect, st, stdin_paste, timeout=PASTE_WAIT_SECONDS, ready=None):
    """Wait on every path at once and return the first query (dict of lists) that carries our state.
    Paths: the local listener on redirect_uri, the paste pipe, and stdin when stdin_paste is set."""
    got = queue.Queue()

    def offer(address, source):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(address.strip()).query)
        if (q.get("state") or [""])[0] == st and ("code" in q or "error" in q):
            got.put((q, source))
            return True
        if address.strip():
            print(f"Ignored an address from {source} that isn't this sign-in's answer.", file=sys.stderr)
        return False

    stops = []
    parsed = urllib.parse.urlparse(redirect)

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            ok = offer("http://x" + self.path, "the browser")
            self.send_response(200 if ok else 404)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Signed in. You can close this tab." if ok else b"Not the sign-in answer.")

        def log_message(self, *a):
            pass

    try:
        srv = http.server.ThreadingHTTPServer((parsed.hostname, parsed.port or 80), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        stops.append(lambda: (srv.shutdown(), srv.server_close()))
        print(f"Listening on {redirect} for the browser to come back after Authorize.", flush=True)
    except OSError as e:
        print(f"Can't listen on {redirect} ({e}). Use the paste backup.", file=sys.stderr)

    pipe = paste_inbox()
    os.makedirs(os.path.dirname(pipe), exist_ok=True)
    if os.path.exists(pipe):
        os.remove(pipe)
    os.mkfifo(pipe, 0o600)
    done = threading.Event()

    def read_pipe():
        while not done.is_set():
            fd = os.open(pipe, os.O_RDONLY | os.O_NONBLOCK)
            try:
                buf = b""
                while not done.is_set():
                    try:
                        chunk = os.read(fd, 65536)
                    except BlockingIOError:
                        chunk = None
                    if chunk:
                        buf += chunk
                        while b"\n" in buf:
                            line, buf = buf.split(b"\n", 1)
                            offer(line.decode(errors="replace"), "a pasted address")
                    elif chunk == b"" and buf:
                        offer(buf.decode(errors="replace"), "a pasted address")
                        buf = b""
                    time.sleep(0.05)
            finally:
                os.close(fd)
    threading.Thread(target=read_pipe, daemon=True).start()
    stops.append(lambda: os.path.exists(pipe) and os.remove(pipe))

    if stdin_paste:
        def read_stdin():
            for line in sys.stdin:
                if offer(line, "a pasted address"):
                    return
        threading.Thread(target=read_stdin, daemon=True).start()

    if ready:
        ready()
    try:
        return got.get(timeout=timeout)
    except queue.Empty:
        return None, None
    finally:
        done.set()
        for s in stops:
            try:
                s()
            except Exception:
                pass


def cmd_auth(store, cfg, client, paste, handle=None):
    if not client.app.get("client_id"):
        raise SystemExit("Set X_CLIENT_ID (and X_CLIENT_SECRET) as stored secrets first.")
    verifier = secrets.token_urlsafe(64)[:96]
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    st = secrets.token_urlsafe(16)
    redirect = cfg["redirect_uri"]
    url = AUTHORIZE_URL + "?" + urllib.parse.urlencode({
        "response_type": "code", "client_id": client.app["client_id"], "redirect_uri": redirect,
        "scope": SCOPES, "state": st, "code_challenge": challenge, "code_challenge_method": "S256"})
    who = f" as {handle}" if handle else ""
    print(f"1. Open this address in the bot's own browser, sign in to X{who} if asked, and click Authorize:\n")
    print(url + "\n")
    print("   X sends that browser back here and the sign-in finishes by itself.")
    print("2. Backup, only if the page after Authorize doesn't load: copy the full address from the address bar "
          "and paste it right away. You have about 30 seconds before X's one-time code expires. "
          "It is swapped for the sign-in the moment it is pasted. The bot hands it over with:\n"
          f"   CREW_BOT=\"Foreman\" python3 {os.path.abspath(__file__)} auth-paste \"<the full address>\"\n",
          flush=True)

    def ready():
        print("Waiting for X (up to 10 minutes). Both ways are open now.", flush=True)

    q, source = wait_for_redirect(redirect, st, paste, ready=ready)
    if q is None:
        raise SystemExit("No answer from X within 10 minutes. Nothing was saved. Run auth again.")
    if "error" in q:
        raise SystemExit(f"Sign-in refused: {q['error'][0]}")
    # swap at once: X's code expires in about 30 seconds
    try:
        with file_lock(signin_path()):
            body = client._token_request({"grant_type": "authorization_code", "code": q["code"][0],
                                          "redirect_uri": redirect, "code_verifier": verifier,
                                          "client_id": client.app["client_id"]})
            client._keep(body)
    except urllib.error.HTTPError as e:
        raise SystemExit(f"X refused the code (HTTP {e.code}). It most likely expired (about 30 seconds). "
                         "Run auth again and approve in the bot's browser, or paste faster.")
    print(f"Code from {source} swapped for a sign-in. Saved to {signin_path()} (owner-only permissions), "
          "the one sign-in the whole crew shares.")
    me = client.me()
    pm = me.get("public_metrics") or {}
    print(f"Signed in as @{me['username']}. Scopes: {client.tok.get('scope')}. "
          f"Followers {pm.get('followers_count', 'n/a')}, following {pm.get('following_count', 'n/a')}.")


# ----------------------------------------------------------------------------

def main(argv=None):
    p = argparse.ArgumentParser(description="Read-only X follower and following tracker.")
    p.add_argument("command", choices=["auth", "auth-paste", "full", "light", "daily", "recheck", "report"])
    p.add_argument("address", nargs="?", help="auth-paste: the full address the browser landed on after Authorize")
    p.add_argument("--dir", default=os.environ.get("FW_DIR", BOTS_HOME + "/follow-watch"))
    p.add_argument("--paste", action="store_true", help="auth: also accept the pasted address on stdin")
    p.add_argument("--likes", action="store_true", help="auth: add like.read (Reply Queue or Fan Finder chosen)")
    p.add_argument("--followers", action="store_true", help="recheck: include your followers, not only accounts you follow")
    p.add_argument("--limit", type=int, help="full: read only the first N followers and N following (a partial scan, for testing)")
    p.add_argument("--estimate", action="store_true", help="recheck: count and price it without calling X")
    args = p.parse_args(argv)

    if args.command == "auth-paste":
        if not args.address:
            raise SystemExit("auth-paste needs the full address, in quotes.")
        cmd_auth_paste(args.address)
        return

    store = Store(args.dir)
    cfg = store.load_config()
    now = local_now(cfg)
    meter = Meter(cfg)

    if args.command == "report":
        state = store.load_state()
        if not state.get("last_full"):
            raise SystemExit("No full scan saved yet.")
        print(build_full_report(store, cfg, state, now, meter, first=not state.get("prev_full")))
        return
    if args.command == "recheck" and args.estimate:
        cmd_recheck(store, cfg, None, now, args.followers, True)
        return
    client = XClient(store, cfg, meter)
    if args.command == "recheck":
        cmd_recheck(store, cfg, client, now, args.followers, False)
        return
    if args.command == "auth":
        global SCOPES
        if args.likes and "like.read" not in SCOPES:
            SCOPES = SCOPES + " like.read"
        cmd_auth(store, cfg, client, args.paste)
        return
    try:
        if args.command == "full":
            cmd_full(store, cfg, client, now, args.limit)
        elif args.command == "light":
            cmd_light(store, cfg, client, now)
        elif args.command == "daily":
            cmd_daily(store, cfg, client, now)
    except CapReached as e:
        # nothing from this run is saved, so the last report's numbers stay as they were
        print(stopped_line(client.who, e) + f" Nothing from this {args.command} run was saved, so no new counts "
              "were written. The last saved report is unchanged.")
        sys.exit(3)


if __name__ == "__main__":
    main()
