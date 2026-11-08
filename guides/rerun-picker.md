# Rerun Picker alone: setup guide

Follow this only after the owner typed "start setup" and `sh /workspace/foreman/foreman/fetch_release.sh v1.2.2 --bot rerun-picker` said the checksum is OK. Stop if `/workspace/foreman/.template-master` exists. If `/workspace/foreman` already exists, ask before replacing it.

## Rules (always)

1. Read only on X: never post, reply, like, follow, unfollow, DM, block or mute. Stay out of X Chat.
2. Never go over the daily spend cap. Book every request in the ledger before the next. If the cap stops a run, say what was not read.
3. Secrets only in stored secrets. Never ask for, print or write a key, token or password in chat or files.
4. Flag anything missing or failed. Never report a fake 0 or empty list for something not read.
5. Never overwrite raw files or pulls; new runs write new dated files.

No memory, routines or secrets until setup is finished.


## Install
Copy `follow-audit/follow_watch.py`, `x_prices.py`, `bot_spend.py` and `weekly_rollup.py` into `$BOTS_HOME/follow-watch` and `rerun-picker/rerun_picker.py` plus `qol_rerun.py` into `$BOTS_HOME/reruns`. Scripts only, never a sign-in or token file.

## Questions
Ask only these and save them in `$BOTS_HOME/reruns/config.json`: `picks`, `min_age_days`, `min_ratio`, `media_only`, `skip_media_types`, `skip_terms`, `max_cost_per_pull`, and `brand_handles`: "Which brands or partners do you post for (their X handles)? Posts that tag them won't be suggested." `brand_handles` ships empty, and "none" is a fine answer. Never fill an answer from an example or from anyone else's setup. If the owner says "you pick", offer two or three choices with a short reason each.

## Rerun Picker notes
`python3 $BOTS_HOME/reruns/rerun_picker.py pull --tally-night` skips for $0 unless it is Sunday or the last pull is 6 or more days old. A same-day self-quote does not start the rerun cooldown. `max_per_tool` (default 2, 0 turns it off) is a soft cap per tool or series. `python3 $BOTS_HOME/reruns/rerun_picker.py media-list` lists videos left after rejects and downloads nothing before the build. The weekly "Stale review nudge" is offered in Routines. It runs `nudge`, which writes one line when a review is `stale_review_days` old (default 3) and no rejects are synced. It never builds. Create that routine only after the owner says yes.

A one-time backfill of post history costs about $0.001 per post. Show that before the first pull.

## Cap and ledger
Run `CREW_BOT="Rerun Picker" python3 $BOTS_HOME/follow-watch/bot_spend.py individual`. It marks this bot as set up from its individual template, so it keeps its own cap and ledger even if a Foreman crew lives in this `$BOTS_HOME`, and prints the mode.
- standalone (expected): ask the owner for this bot's daily spend cap and timezone and save them as `daily_spend_cap` and `timezone` in `$BOTS_HOME/reruns/config.json`. The bot keeps its own ledger. For a one-day raise, repeat the amount and date, wait for yes, then run `CREW_BOT="Rerun Picker" python3 $BOTS_HOME/follow-watch/bot_spend.py raise <amount> --yes`. It ends at midnight by itself.

## Sign in to X
All individual bots on this Grok Bot computer share one sign-in at `/workspace/x-signin/x_signin.json` (owner-only, renewed under a lock). If a Foreman crew is here, they use its `dispatch/x_signin.json` instead. Each bot keeps its own ledger and cap.
First run `CREW_BOT="Rerun Picker" python3 $BOTS_HOME/follow-watch/follow_watch.py signin-check`. If it says "Reusing", the sign-in is done: it made one account read (GET /users/me, $0.010, booked to this bot's ledger). Never sign in again. If it says no sign-in was found, this is the first bot: do steps 1 to 4.
1. Ask the owner to add `X_CLIENT_ID` and `X_CLIENT_SECRET` as stored secrets. Never in chat.
2. Before you send or open the link, say: "You have about 30 seconds after you approve. If the page after Authorize does not load, copy the full address from the address bar and paste it here right away, before doing anything else."
3. Start `CREW_BOT="Rerun Picker" python3 $BOTS_HOME/follow-watch/follow_watch.py auth` in the background. Open the address it prints in the bot's own browser. The owner clicks Authorize and it finishes by itself.
4. If the page does not load, the moment they paste the address run `CREW_BOT="Rerun Picker" python3 $BOTS_HOME/follow-watch/follow_watch.py auth-paste '<address>'`. If X says the code expired, say so, start auth again, repeat the 30 second warning and send a new link.
5. One X app covers every bot on this Grok Bot. Signing in with the same app on a second Grok Bot or another computer logs this one out. Do not run `auth --force` unless the owner says yes. That command logs the other bots on this X app out.

## Self-check
Run one free check: `CREW_BOT="Rerun Picker" python3 $BOTS_HOME/follow-watch/bot_spend.py mode`, then `python3 $BOTS_HOME/reruns/rerun_picker.py --help` (no X reads). Report anything FLAGGED. Never report a 0 for something that was not read.

## Routines

Offer each routine below. Say what it is for and what it costs. Create it only after the owner says yes to that routine. Never create a routine they did not accept.

- Weekly reruns. One picks run. About $0.02 a week, plus a one-time backfill at about $0.001 per post. Show the backfill cost before the first pull.
- Stale review nudge. `python3 $BOTS_HOME/reruns/rerun_picker.py nudge` writes one line when a review is `stale_review_days` old (default 3) and no rejects are synced. It never builds. $0, no X calls.
- Update check. Once a day, `python3 /workspace/foreman/foreman/update_check.py check`. $0. It does not download a release.

## Introduce yourself
Two or three lines: what you do, when you run (only the routines the owner accepted), what a run costs, and how to ask you things.

## Updates

Before any version change, run `python3 /workspace/foreman/foreman/update_check.py check`. It reads GitHub's public release list, costs $0, and does not touch X. If it prints UPDATE AVAILABLE, show the owner the version and the release notes, then ask. Do not download yet. Only after the owner says yes to that exact version, run `python3 /workspace/foreman/foreman/update_check.py fetch <tag> --yes`. That downloads the zip and SHA256SUMS and checks one against the other. If it says STOP, tell the owner and stop. A no, or no answer, means stay on this version. Never download from main. The zip does not carry its own digest. The check uses the SHA256SUMS file published beside that release.

## New in v1.1
`foreman/v11.py` and `foreman/v11_wire.py` stay in `/workspace/foreman/foreman` (like `update_check.py`). Never copy them elsewhere. `python3 /workspace/foreman/foreman/v11_wire.py` rebuilds a bot's saved panel and does not call the X API.
- If your lists are hosted, marks you make on the page (never show, show again, done, stages, notes, follow-ups) are pulled into the bot before every run, so the page and chat always agree. The newest mark wins, and two devices saving at once keep both. The previous full report stays linked at the bottom of each page.
- No hosting needed: every saved mark works by chat and lives in this bot's own files.
  - `note @name ...` saves a note
  - `show me everything from @name` shows the per-person timeline and notes
  - `follow up @name on YYYY-MM-DD` sets a follow-up that shows on Home, on this bot's own page if it is the only hosted bot, or in chat if not hosted
- One hosted bot: its own page is its home, and follow-ups show there.
- Billing: say the one-time billed-check line from `python3 /workspace/foreman/foreman/v11.py billing-setup-note` during setup. Until console.x.com is signed in in the bot's browser, spend shows as labeled estimates.

What this bot got in v1.1:
- Each pick shows post date, original stats and last rerun date.
- "similar to #N" chip for near-duplicate picks.
- Sponsor flag from the owner's own sponsor list (`sponsor_terms`, empty by default). With an empty list nothing is flagged.
- Angles fold into each pick. Chat gets the link and a pick count when hosted.
- New video picks are reviewed before the build. Rejected picks are skipped that week.

## New in v1.1.1
- Picks skip personal updates, partner or #ad posts, posts tagging a partner in `brand_handles`, shoutout posts, time-bound posts ("ends today", "tonight", "ends soon", words inside quotes are ignored) and posts under 5 words. The word lists are in `config.json` and can be edited.
- Angles and drafts are written after watching the video (or looking at the image), not from the post text alone.
