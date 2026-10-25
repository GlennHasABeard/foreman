# Follow Audit alone: setup guide

Follow this only after the owner typed "start setup" and `sh fetch_release.sh v1.0.1 --bot follow-audit` said the checksum is OK. Stop if `/workspace/foreman/.template-master` exists.

## Install
Copy `follow-audit/follow_watch.py`, `x_prices.py` and `bot_spend.py` into `$BOTS_HOME/follow-watch`. Scripts only, never a sign-in or token file.

## Questions
Ask only these and save them in `$BOTS_HOME/follow-watch/config.json`: `inactive_days`, `dormant_days`. Never fill an answer from an example or from anyone else's setup. If the owner says "you pick", offer two or three choices with a short reason each.

## Follow Audit notes
Before any full scan, show its cost from the follower and following counts in the free account read (about $0.65 to $1.00 per 1,000 accounts). If it does not fit the cap, offer the one-day raise or skip it for later.

## Cap and ledger
Run `CREW_BOT="Follow Audit" python3 $BOTS_HOME/follow-watch/bot_spend.py individual`. It marks this bot as set up from its individual template, so it keeps its own cap and ledger even if a Foreman crew lives in this `$BOTS_HOME`, and prints the mode.
- standalone (expected): ask the owner for this bot's daily spend cap and timezone and save them as `daily_spend_cap` and `timezone` in `$BOTS_HOME/follow-watch/config.json`. The bot keeps its own ledger. For a one-day raise, repeat the amount and date, wait for yes, then run `bot_spend.py raise <amount> --yes`. It ends at midnight by itself.

## Sign in to X
All individual bots on this Grok Bot computer share one sign-in at `/workspace/x-signin/x_signin.json` (owner-only, renewed under a lock). If a Foreman crew is here, they use its `dispatch/x_signin.json` instead. Each bot keeps its own ledger and cap.
First run `CREW_BOT="Follow Audit" python3 $BOTS_HOME/follow-watch/follow_watch.py signin-check`. If it says "Reusing", the sign-in is done: it made one account read (GET /users/me, $0.010, booked to this bot's ledger). Never sign in again. If it says no sign-in was found, this is the first bot: do steps 1 to 4.
1. Ask the owner to add `X_CLIENT_ID` and `X_CLIENT_SECRET` as stored secrets. Never in chat.
2. Before you send or open the link, say: "You have about 30 seconds after you approve. If the page after Authorize does not load, copy the full address from the address bar and paste it here right away, before doing anything else."
3. Start `CREW_BOT="Follow Audit" python3 $BOTS_HOME/follow-watch/follow_watch.py auth` in the background. Open the address it prints in the bot's own browser. The owner clicks Authorize and it finishes by itself.
4. If the page does not load, the moment they paste the address run `CREW_BOT="Follow Audit" python3 $BOTS_HOME/follow-watch/follow_watch.py auth-paste '<address>'`. If X says the code expired, say so, start auth again, repeat the 30 second warning and send a new link.
5. One X app covers every bot on this Grok Bot. Signing in with the same app on a second Grok Bot or another computer logs this one out.

## Self-check
Run one free check: `CREW_BOT="Follow Audit" python3 $BOTS_HOME/follow-watch/bot_spend.py mode`, then `CREW_BOT="Follow Audit" python3 follow_watch.py report` (no X reads). Report anything FLAGGED. Never report a 0 for something that was not read.

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
- One hosted bot: its own page is its home, and follow-ups show there.
- Billing: say the one-time billed-check line from `v11.py billing-setup-note` during setup. Until console.x.com is signed in in the bot's browser, spend shows as labeled estimates.

What this bot got in v1.1:
- Follower and following tiles use the newest live profile counts with an as-of time (Analytics Log's last pull if installed, otherwise this bot's own account read).
- Plain wording: "Unfollowed you" for named people who left, "Account gone" for suspended, deactivated or not-found accounts (from the per-name lookup), and "followers lost" for the unnamed daily count.
- The daily check reads your newest followers. The size is a setting (`newest_check_size`, default 350) and its cost is shown first (`v11.newest_check_cost`).
- X's own unfollow count and "Removed by X" show only when Analytics Log is installed. Otherwise the tile says "followers lost".
- New followers tab (last 30 days), 4-week chart of gains, losses and new mutuals, and a 5-line Top risks box.
- Light-only nights skip rebuilding the full report and page when the full data has not changed.
