# Shoutout Picker alone: setup guide

Follow this only after the owner typed "start setup" and `sh fetch_release.sh v1.1.1 --bot shoutout-picker` said the checksum is OK. Stop if `/workspace/foreman/.template-master` exists.

## Install
Copy `follow-audit/follow_watch.py`, `x_prices.py` and `bot_spend.py` into `$BOTS_HOME/follow-watch` and `shoutout-picker/shoutout_desk.py` into `$BOTS_HOME/shoutouts`. Scripts only, never a sign-in or token file.

## Questions
Ask only these and save them in `$BOTS_HOME/shoutouts/config.json`: `account_kinds`, `labels`, `min_followers`, `max_followers`, `list_size`, `weekly_goal` (how many shoutout posts a week they aim for, blank is fine). Never fill an answer from an example or from anyone else's setup. If the owner says "you pick", offer two or three choices with a short reason each.

## Shoutout Picker notes
Shoutout Picker needs a follower list. If Follow Audit is installed (`$BOTS_HOME/follow-watch/data/state.json` exists), use it. If not, offer two choices and let the owner pick:
- Its own follower scan. Show the cost first from the free account read (about $0.65 to $1.00 per 1,000 followers plus following). If it does not fit the cap, offer the one-day raise. Then write `$BOTS_HOME/follow-watch/config.json` (inactive_days and dormant_days, with defaults the owner agrees to) and run `CREW_BOT="Shoutout Picker" python3 $BOTS_HOME/follow-watch/follow_watch.py full`. It is booked to Shoutout Picker.
- Install Follow Audit (`sh fetch_release.sh v1.1.1 --bot follow-audit`), which keeps the list fresh every day.

## Cap and ledger
Run `CREW_BOT="Shoutout Picker" python3 $BOTS_HOME/follow-watch/bot_spend.py individual`. It marks this bot as set up from its individual template, so it keeps its own cap and ledger even if a Foreman crew lives in this `$BOTS_HOME`, and prints the mode.
- standalone (expected): ask the owner for this bot's daily spend cap and timezone and save them as `daily_spend_cap` and `timezone` in `$BOTS_HOME/shoutouts/config.json`. The bot keeps its own ledger. For a one-day raise, repeat the amount and date, wait for yes, then run `bot_spend.py raise <amount> --yes`. It ends at midnight by itself.

## Sign in to X
All individual bots on this Grok Bot computer share one sign-in at `/workspace/x-signin/x_signin.json` (owner-only, renewed under a lock). If a Foreman crew is here, they use its `dispatch/x_signin.json` instead. Each bot keeps its own ledger and cap.
First run `CREW_BOT="Shoutout Picker" python3 $BOTS_HOME/follow-watch/follow_watch.py signin-check`. If it says "Reusing", the sign-in is done: it made one account read (GET /users/me, $0.010, booked to this bot's ledger). Never sign in again. If it says no sign-in was found, this is the first bot: do steps 1 to 4.
1. Ask the owner to add `X_CLIENT_ID` and `X_CLIENT_SECRET` as stored secrets. Never in chat.
2. Before you send or open the link, say: "You have about 30 seconds after you approve. If the page after Authorize does not load, copy the full address from the address bar and paste it here right away, before doing anything else."
3. Start `CREW_BOT="Shoutout Picker" python3 $BOTS_HOME/follow-watch/follow_watch.py auth` in the background. Open the address it prints in the bot's own browser. The owner clicks Authorize and it finishes by itself.
4. If the page does not load, the moment they paste the address run `CREW_BOT="Shoutout Picker" python3 $BOTS_HOME/follow-watch/follow_watch.py auth-paste '<address>'`. If X says the code expired, say so, start auth again, repeat the 30 second warning and send a new link.
5. One X app covers every bot on this Grok Bot. Signing in with the same app on a second Grok Bot or another computer logs this one out.

## Self-check
Run one free check: `CREW_BOT="Shoutout Picker" python3 $BOTS_HOME/follow-watch/bot_spend.py mode`, then `python3 shoutout_desk.py status` (no X reads). Report anything FLAGGED. Never report a 0 for something that was not read.

## Introduce yourself
Two or three lines: what you do, when you run (only if the owner asked for a schedule), what a run costs, and how to ask you things. Create a routine only if the owner asks for one.

## Updates

Once a day, the first time it works that day, the bot checks GitHub (free, no X reads) for a newer Foreman release. If there is one, it shows you the release notes and asks first. It never downloads or updates anything without your yes, and it checks every download against SHA256SUMS before using it.

## New in v1.1
`foreman/v11.py` stays in `/workspace/foreman/foreman` (like `update_check.py`). Never copy it elsewhere.
- If your lists are hosted, marks you make on the page (never show, show again, done, stages, notes, follow-ups) are pulled into the bot before every run, so the page and chat always agree. The newest mark wins, and two devices saving at once keep both. The previous full report stays linked at the bottom of each page.
- No hosting needed: every saved mark works by chat and lives in this bot's own files.
  - `note @name ...` saves a note
  - `show me everything from @name` shows the per-person timeline and notes
  - `follow up @name on YYYY-MM-DD` sets a follow-up that shows on Home, on this bot's own page if it is the only hosted bot, or in chat if not hosted
  - `mark @name done` and `mark @name pending` (Done and Pending)
- One hosted bot: its own page is its home, and follow-ups show there.
- Billing: say the one-time billed-check line from `v11.py billing-setup-note` during setup. Until console.x.com is signed in in the bot's browser, spend shows as labeled estimates.

What this bot got in v1.1:
- Done and Pending from your checkmarks (page) or `mark @name done` (chat).
- Bench warning when the bench cannot fill every slot.
- Skip reasons grouped with counts, an "Art type" label and a "runner-up promoted" chip.
- Reuses Follow Audit's follower check from the last 24 hours when installed. Otherwise it runs its own follower scan and shows the cost first.
- Top fans and Write shoutout show only when Reply Queue or Fan Finder is installed.
