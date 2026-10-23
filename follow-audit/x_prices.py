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
import re

RATES = {"owned": 0.001, "post": 0.005, "user": 0.010, "attached_user": 0.010}

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
    ("attached_user", "each profile in includes.users", "user read"),
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
    """estimate(owned=10, post=3, user=1, attached_user=2) in dollars."""
    return sum(RATES[k] * n for k, n in counts.items())


def table_lines():
    return [f"${RATES[k]:.3f}  {k:<13}  {what}  ({src})" for k, what, src in TABLE]


if __name__ == "__main__":
    print("\n".join(table_lines()))
