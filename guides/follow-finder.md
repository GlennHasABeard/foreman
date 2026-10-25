# Follow Finder alone: setup guide

Follow this only after the owner typed "start setup" and `sh fetch_release.sh v1.0.1 --bot follow-finder` said the checksum is OK. Stop if `/workspace/foreman/.template-master` exists.

## Install
Copy `follow-audit/follow_watch.py`, `x_prices.py` and `bot_spend.py` into `$BOTS_HOME/follow-watch` and `follow-finder/creator_scout.py` into `$BOTS_HOME/creator-scout`. Scripts only, never a sign-in or token file.

## Questions
Ask only these and save them in `$BOTS_HOME/creator-scout/config.json`: `niche_queries`, `min_followers`, `max_followers`, `verified_only`, `adult_filter`, `exclude_terms`, `shortlist_size`, `max_cost_per_run`. Never fill an answer from an example or from anyone else's setup. If the owner says "you pick", offer two or three choices with a short reason each.

## Follow Finder notes
Suggest a follower range with `python3 creator_scout.py suggest-range <their follower count>` and let the owner pick. The report lists how many creators each filter dropped.

## Cap and ledger
Run `CREW_BOT="Follow Finder" python3 $BOTS_HOME/follow-watch/bot_spend.py individual`. It marks this bot as set up from its individual template, so it keeps its own cap and ledger even if a Foreman crew lives in this `$BOTS_HOME`, and prints the mode.
- standalone (expected): ask the owner for this bot's daily spend cap and timezone and save them as `daily_spend_cap` and `timezone` in `$BOTS_HOME/creator-scout/config.json`. The bot keeps its own ledger. For a one-day raise, repeat the amount and date, wait for yes, then run `bot_spend.py raise <amount> --yes`. It ends at midnight by itself.

## Sign in to X
All individual bots on this Grok Bot computer share one sign-in at `/workspace/x-signin/x_signin.json` (owner-only, renewed under a lock). If a Foreman crew is here, they use its `dispatch/x_signin.json` instead. Each bot keeps its own ledger and cap.
First run `CREW_BOT="Follow Finder" python3 $BOTS_HOME/follow-watch/follow_watch.py signin-check`. If it says "Reusing", the sign-in is done: it made one account read (GET /users/me, $0.010, booked to this bot's ledger). Never sign in again. If it says no sign-in was found, this is the first bot: do steps 1 to 4.
1. Ask the owner to add `X_CLIENT_ID` and `X_CLIENT_SECRET` as stored secrets. Never in chat.
2. Before you send or open the link, say: "You have about 30 seconds after you approve. If the page after Authorize does not load, copy the full address from the address bar and paste it here right away, before doing anything else."
3. Start `CREW_BOT="Follow Finder" python3 $BOTS_HOME/follow-watch/follow_watch.py auth` in the background. Open the address it prints in the bot's own browser. The owner clicks Authorize and it finishes by itself.
4. If the page does not load, the moment they paste the address run `CREW_BOT="Follow Finder" python3 $BOTS_HOME/follow-watch/follow_watch.py auth-paste '<address>'`. If X says the code expired, say so, start auth again, repeat the 30 second warning and send a new link.
5. One X app covers every bot on this Grok Bot. Signing in with the same app on a second Grok Bot or another computer logs this one out.

## Self-check
Run one free check: `CREW_BOT="Follow Finder" python3 $BOTS_HOME/follow-watch/bot_spend.py mode`, then `python3 creator_scout.py suggest-range 1000` (no X reads). Report anything FLAGGED. Never report a 0 for something that was not read.

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
  - `never show @name` and `show @name again` (Never show tab with undo when hosted. Returning soon lists people back from the 60-day rest)
- One hosted bot: its own page is its home, and follow-ups show there.
- Billing: say the one-time billed-check line from `v11.py billing-setup-note` during setup. Until console.x.com is signed in in the bot's browser, spend shows as labeled estimates.

What this bot got in v1.1:
- Stats strip: kept, dropped free, paid checks skipped.
- Free pre-screen drops out-of-range, already followed, already shown, never-show and filtered accounts before any paid check.
- Language and size quotas are the owner's own settings (`language_quota`, `size_quota`), off by default. Never set one unless the owner asks.
- Engagement-per-follower chip and sort by engagement. The follows-you chip shows only when Follow Audit is installed.
- Never show tab with undo, and Returning soon from the 60-day rest.
