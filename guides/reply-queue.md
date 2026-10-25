# Reply Queue alone: setup guide

Follow this only after the owner typed "start setup" and `sh fetch_release.sh v1.0.1 --bot reply-queue` said the checksum is OK. Stop if `/workspace/foreman/.template-master` exists.

## Install
Copy `follow-audit/follow_watch.py`, `x_prices.py` and `bot_spend.py` into `$BOTS_HOME/follow-watch` and `reply-queue/engagement.py` into `$BOTS_HOME/engagement`. Scripts only, never a sign-in or token file.

## Questions
Ask only these and save them in `$BOTS_HOME/engagement/config.json`: `skip_handles`, `max_cost_per_run`. Never fill an answer from an example or from anyone else's setup. If the owner says "you pick", offer two or three choices with a short reason each.

## Reply Queue notes
It reads mentions and quotes first and your likes last. If the likes do not finish, items are kept and marked "may already be liked" and the report says so.

## Cap and ledger
Run `CREW_BOT="Reply Queue" python3 $BOTS_HOME/follow-watch/bot_spend.py individual`. It marks this bot as set up from its individual template, so it keeps its own cap and ledger even if a Foreman crew lives in this `$BOTS_HOME`, and prints the mode.
- standalone (expected): ask the owner for this bot's daily spend cap and timezone and save them as `daily_spend_cap` and `timezone` in `$BOTS_HOME/engagement/config.json`. The bot keeps its own ledger. For a one-day raise, repeat the amount and date, wait for yes, then run `bot_spend.py raise <amount> --yes`. It ends at midnight by itself.

## Sign in to X
All individual bots on this Grok Bot computer share one sign-in at `/workspace/x-signin/x_signin.json` (owner-only, renewed under a lock). If a Foreman crew is here, they use its `dispatch/x_signin.json` instead. Each bot keeps its own ledger and cap.
First run `CREW_BOT="Reply Queue" python3 $BOTS_HOME/follow-watch/follow_watch.py signin-check`. If it says "Reusing", the sign-in is done: it made one account read (GET /users/me, $0.010, booked to this bot's ledger). Never sign in again. If it says no sign-in was found, this is the first bot: do steps 1 to 4.
1. Ask the owner to add `X_CLIENT_ID` and `X_CLIENT_SECRET` as stored secrets. Never in chat.
2. Before you send or open the link, say: "You have about 30 seconds after you approve. If the page after Authorize does not load, copy the full address from the address bar and paste it here right away, before doing anything else."
3. Start `CREW_BOT="Reply Queue" python3 $BOTS_HOME/follow-watch/follow_watch.py auth --likes` in the background. Open the address it prints in the bot's own browser. The owner clicks Authorize and it finishes by itself.
4. If the page does not load, the moment they paste the address run `CREW_BOT="Reply Queue" python3 $BOTS_HOME/follow-watch/follow_watch.py auth-paste '<address>'`. If X says the code expired, say so, start auth again, repeat the 30 second warning and send a new link.
5. One X app covers every bot on this Grok Bot. Signing in with the same app on a second Grok Bot or another computer logs this one out.

## Self-check
Run one free check: `CREW_BOT="Reply Queue" python3 $BOTS_HOME/follow-watch/bot_spend.py mode`, then `python3 engagement.py --help` (no X reads). Report anything FLAGGED. Never report a 0 for something that was not read.

## Introduce yourself
Two or three lines: what you do, when you run (only if the owner asked for a schedule), what a run costs, and how to ask you things. Create a routine only if the owner asks for one.

## Updates

Once a day, the first time it works that day, the bot checks GitHub (free, no X reads) for a newer Foreman release. If there is one, it shows you the release notes and asks first. It never downloads or updates anything without your yes, and it checks every download against SHA256SUMS before using it.

## New in v1.1
`foreman/v11.py` stays in `/workspace/foreman/foreman` (like `update_check.py`). Never copy it elsewhere.
- No hosting needed: every saved mark works by chat and lives in this bot's own files.
  - `note @name ...` saves a note
  - `show me everything from @name` shows the per-person timeline and notes
  - `follow up @name on YYYY-MM-DD` sets a follow-up that shows on Home, on this bot's own page if it is the only hosted bot, or in chat if not hosted
  - `mark @name done` marks an item answered. `median` gives median time to reply over 7 and 30 days from those done marks, chat or page
- One hosted bot: its own page is its home, and follow-ups show there.
- Billing: say the one-time billed-check line from `v11.py billing-setup-note` during setup. Until console.x.com is signed in in the bot's browser, spend shows as labeled estimates.

What this bot got in v1.1:
- Reply, Like and Open buttons on each row, and a reply draft box prefilled with the @name.
- Regulars chip and filter by distinct conversations this month (shows up to 9, then 10+ this month).
- Drowning posts: your posts with the most unanswered items.
- Median time to reply over 7 and 30 days, from done marks (page checkmarks or chat).
- Filters and sort, mentions first.
- Runs per day is a setting (`runs_per_day`, default 3). The window stays 72 hours.
