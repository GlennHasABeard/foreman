# Follow Finder alone: setup guide

Follow this only after the owner typed "start setup" and `sh fetch_release.sh v0.3.0 --bot follow-finder` said the checksum is OK. Stop if `/workspace/foreman/.template-master` exists.

## Install
Copy `follow-audit/follow_watch.py`, `x_prices.py` and `bot_spend.py` into `$BOTS_HOME/follow-watch` and `follow-finder/creator_scout.py` into `$BOTS_HOME/creator-scout`. Scripts only, never a sign-in or token file.

## Questions
Ask only these and save them in `$BOTS_HOME/creator-scout/config.json`: `niche_queries`, `min_followers`, `max_followers`, `verified_only`, `adult_filter`, `exclude_terms`, `shortlist_size`, `max_cost_per_run`. Never fill an answer from an example or from anyone else's setup. If the owner says "you pick", offer two or three choices with a short reason each.

## Follow Finder notes
Suggest a follower range with `python3 creator_scout.py suggest-range <their follower count>` and let the owner pick. The report lists how many creators each filter dropped.

## Cap and ledger
Run `CREW_BOT="Follow Finder" python3 $BOTS_HOME/follow-watch/bot_spend.py mode`.
- shared: Dispatch or Foreman is installed. Do not write a cap into config.json. The crew's cap and ledger in `$BOTS_HOME/dispatch` apply. Raises go through Dispatch.
- standalone: ask the owner for this bot's daily spend cap and timezone and save them as `daily_spend_cap` and `timezone` in `$BOTS_HOME/creator-scout/config.json`. The bot keeps its own ledger. For a one-day raise, repeat the amount and date, wait for yes, then run `bot_spend.py raise <amount> --yes`. It ends at midnight by itself.

## Sign in to X
If Dispatch or Foreman is installed, skip this. The bot uses the crew's one sign-in at `$BOTS_HOME/dispatch/x_signin.json`.
Alone, the bot signs in by itself and saves its own file at `$BOTS_HOME/creator-scout/x_signin.json` (owner-only, renewed under a lock like the crew file).
1. Ask the owner to add `X_CLIENT_ID` and `X_CLIENT_SECRET` as stored secrets. Never in chat.
2. Before you send or open the link, say: "You have about 30 seconds after you approve. If the page after Authorize does not load, copy the full address from the address bar and paste it here right away, before doing anything else."
3. Start `CREW_BOT="Follow Finder" python3 $BOTS_HOME/follow-watch/follow_watch.py auth` in the background. Open the address it prints in the bot's own browser. The owner clicks Authorize and it finishes by itself.
4. If the page does not load, the moment they paste the address run `CREW_BOT="Follow Finder" python3 $BOTS_HOME/follow-watch/follow_watch.py auth-paste '<address>'`. If X says the code expired, say so, start auth again, repeat the 30 second warning and send a new link.
5. Two bots alone on the same X app cancel each other's sign-in. If the owner wants a second bot, suggest Dispatch (one shared sign-in) or a second X app.

## Self-check
Run one free check: `CREW_BOT="Follow Finder" python3 $BOTS_HOME/follow-watch/bot_spend.py mode`, then `python3 creator_scout.py suggest-range 1000` (no X reads). Report anything FLAGGED. Never report a 0 for something that was not read.

## Introduce yourself
Two or three lines: what you do, when you run (only if the owner asked for a schedule), what a run costs, and how to ask you things. Create a routine only if the owner asks for one.
