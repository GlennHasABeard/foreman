# Follow Audit alone: setup guide

Follow this only after the owner typed "start setup" and `sh fetch_release.sh v1.0.0 --bot follow-audit` said the checksum is OK. Stop if `/workspace/foreman/.template-master` exists.

## Install
Copy `follow-audit/follow_watch.py`, `x_prices.py` and `bot_spend.py` into `$BOTS_HOME/follow-watch`. Scripts only, never a sign-in or token file.

## Questions
Ask only these and save them in `$BOTS_HOME/follow-watch/config.json`: `inactive_days`, `dormant_days`. Never fill an answer from an example or from anyone else's setup. If the owner says "you pick", offer two or three choices with a short reason each.

## Follow Audit notes
Before any full scan, show its cost from the follower and following counts in the free account read (about $0.65 to $1.00 per 1,000 accounts). If it does not fit the cap, offer the one-day raise or skip it for later.

## Cap and ledger
Run `CREW_BOT="Follow Audit" python3 $BOTS_HOME/follow-watch/bot_spend.py mode`.
- shared: a Foreman crew already lives in this `$BOTS_HOME`. STOP. This template sets itself up alone. Ask the owner for a separate `BOTS_HOME` and start again there.
- standalone (expected): ask the owner for this bot's daily spend cap and timezone and save them as `daily_spend_cap` and `timezone` in `$BOTS_HOME/follow-watch/config.json`. The bot keeps its own ledger. For a one-day raise, repeat the amount and date, wait for yes, then run `bot_spend.py raise <amount> --yes`. It ends at midnight by itself.

## Sign in to X
The bot signs in by itself and saves its own file at `$BOTS_HOME/follow-watch/x_signin.json` (owner-only, renewed under a lock).
1. Ask the owner to add `X_CLIENT_ID` and `X_CLIENT_SECRET` as stored secrets. Never in chat.
2. Before you send or open the link, say: "You have about 30 seconds after you approve. If the page after Authorize does not load, copy the full address from the address bar and paste it here right away, before doing anything else."
3. Start `CREW_BOT="Follow Audit" python3 $BOTS_HOME/follow-watch/follow_watch.py auth` in the background. Open the address it prints in the bot's own browser. The owner clicks Authorize and it finishes by itself.
4. If the page does not load, the moment they paste the address run `CREW_BOT="Follow Audit" python3 $BOTS_HOME/follow-watch/follow_watch.py auth-paste '<address>'`. If X says the code expired, say so, start auth again, repeat the 30 second warning and send a new link.
5. Two bots alone on the same X app cancel each other's sign-in. If the owner wants a second individual template, it needs its own X app.

## Self-check
Run one free check: `CREW_BOT="Follow Audit" python3 $BOTS_HOME/follow-watch/bot_spend.py mode`, then `CREW_BOT="Follow Audit" python3 follow_watch.py report` (no X reads). Report anything FLAGGED. Never report a 0 for something that was not read.

## Introduce yourself
Two or three lines: what you do, when you run (only if the owner asked for a schedule), what a run costs, and how to ask you things. Create a routine only if the owner asks for one.
