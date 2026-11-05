#!/usr/bin/env python3
"""The crew's one X price table. The spend ledger (the shared client in follow_watch.py)
and every bot's own estimate read their rates from here, so they always agree.

  python3 x_prices.py            prints the table

Kinds:
  owned          reads of your own data: your posts, mentions, likes, followers,
                 following, likers of your posts, lookups of your own posts
  post           other people's posts: search, quote posts, someone else's timeline
  user           profile lookups (/users/me, /users/by, /users)
  attached_user  profiles that ride along on a post read (expansions=author_id)

The billing check on the X developer console confirms the table. It does not set it.
"""
import json
import os
import re

# v1.1: profiles attached to post reads are priced at $0.00 (X did not bill them in testing).
# The nightly billing check (foreman/v11.py) writes the switch file and puts $0.010 back only if
# X billed more user lookups than the bots logged.
OLD_ATTACHED = 0.010


def _switch():
    p = os.environ.get("X_PRICE_SWITCH", os.path.join(os.environ.get("BOTS_HOME", "/workspace/bots"),
                                                      ".shared", "x_price_switch.json"))
    try:
        with open(p, encoding="utf-8") as f:
            return bool(json.load(f).get("attached_user_billed"))
    except Exception:
        return False


RATES = {"owned": 0.001, "post": 0.005, "user": 0.010, "attached_user": OLD_ATTACHED if _switch() else 0.0}

TABLE = [
    ("owned", "GET /users/:me/tweets (your posts)", "owned read"),
    ("owned", "GET /users/:me/mentions (your mentions)", "owned read"),
    ("owned", "GET /users/:me/liked_tweets (your likes)", "owned read, was $0.005 in the ledger before v0.2.0"),
    ("owned", "GET /users/:me/followers and /following", "owned read"),
    ("owned", "GET /tweets/:id/liking_users (likers of your posts)", "owned read, was $0.005 in the ledger before v0.2.0"),
    ("owned", "GET /tweets?ids= (your own posts, caller says owned)", "owned read, was $0.005 in the ledger before v0.2.0"),
    ("post", "GET /tweets/search/recent", "post read"),
    ("post", "GET /tweets/:id/quote_tweets", "post read"),
    ("post", "GET /users/:other/tweets and /tweets?ids= (other people's posts)", "post read"),
    ("user", "GET /users/me, /users/by, /users", "user read"),
    ("attached_user", "each profile in includes.users", "$0 since v1.1, switch puts $0.010 back"),
]

_OWNABLE = re.compile(r"/users/([^/]+)/(tweets|mentions|liked_tweets)$")


def kind_of(path, owner_id=None, owned=None):
    """Which rate one request bills at. owned=True/False lets the caller say whose posts a
    /tweets?ids= lookup reads. Unknown ownership bills at the post rate, the higher one."""
    p = path.split("?")[0]
    if p.startswith("/users/me") or p.startswith("/users/by") or p == "/users":
        return "user"
    if p.endswith("/followers") or p.endswith("/following") or p.endswith("/liking_users"):
        return "owned"
    m = _OWNABLE.fullmatch(p)
    if m:
        if owned is not None:
            return "owned" if owned else "post"
        return "owned" if owner_id and m.group(1) == str(owner_id) else "post"
    if p == "/tweets" and owned:
        return "owned"
    return "post"


def items_in(params):
    params = params or {}
    n = int(params.get("max_results") or 0)
    for key in ("ids", "usernames"):
        if key in params:
            n = len(str(params[key]).split(","))
    return max(n, 1)


def worst_case(path, params, owner_id=None, owned=None):
    """The most one request could cost before attached profiles."""
    return items_in(params) * RATES[kind_of(path, owner_id, owned)]


def response_cost(path, body, owner_id=None, owned=None):
    """What one response likely cost: items returned at their rate, plus attached profiles."""
    if not isinstance(body, dict):
        return 0.0
    data = body.get("data")
    n = len(data) if isinstance(data, list) else (1 if data else 0)
    users = len(((body.get("includes") or {}).get("users")) or [])
    return n * RATES[kind_of(path, owner_id, owned)] + users * RATES["attached_user"]


def estimate(**counts):
    """estimate(owned=10, post=3, user=1, attached_user=2) in dollars.
    Unscaled. Spend caps use this, never the scaled display estimate."""
    return sum(RATES[k] * n for k, n in counts.items())


# Owned-read display estimates are scaled by the last 7 days' billed/logged ratio.
# The ratio is capped so a thin week cannot swing the estimate. Caps stay unscaled.
OWNED_RATIO_MIN = 0.3
OWNED_RATIO_MAX = 1.5


def owned_ratio(billed=None, logged=None):
    """billed/logged over the last 7 days, capped from 0.3 to 1.5. No history means 1."""
    try:
        logged = float(logged or 0)
        billed = float(billed or 0)
    except (TypeError, ValueError):
        return 1.0
    if logged <= 0:
        return 1.0
    return max(OWNED_RATIO_MIN, min(OWNED_RATIO_MAX, billed / logged))


def counts(owned=0, post=0, user=0, attached_user=0, ratio=None, billed=None, logged=None):
    """Scaled display estimate for owned reads. Keeps est_cost_raw.

    Spend caps still use estimate() and worst_case(), which are unscaled.
    Only the owned portion is multiplied by the billed/logged ratio.
    """
    raw = estimate(owned=owned, post=post, user=user, attached_user=attached_user)
    if ratio is None:
        ratio = owned_ratio(billed, logged)
    ratio = max(OWNED_RATIO_MIN, min(OWNED_RATIO_MAX, float(ratio)))
    owned_raw = RATES["owned"] * owned
    return {"est_cost": raw - owned_raw + owned_raw * ratio, "est_cost_raw": raw, "owned_ratio": ratio}


def table_lines():
    return [f"${RATES[k]:.3f}  {k:<13}  {what}  ({src})" for k, what, src in TABLE]


if __name__ == "__main__":
    print("\n".join(table_lines()))
