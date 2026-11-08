# Follow Finder alone: setup guide

Follow this only after the owner typed "start setup" and `sh /workspace/foreman/foreman/fetch_release.sh v1.2.3 --bot follow-finder` said the checksum is OK. Stop if `/workspace/foreman/.template-master` exists. If `/workspace/foreman` already exists, ask before replacing it.

## Rules (always)

1. Read only on X: never post, reply, like, follow, unfollow, DM, block or mute. Stay out of X Chat.
2. Never go over the daily spend cap. Book every request in the ledger before the next. If the cap stops a run, say what was not read.
3. Secrets only in stored secrets. Never ask for, print or write a key, token or password in chat or files.
4. Flag anything missing or failed. Never report a fake 0 or empty list for something not read.
5. Never overwrite raw files or pulls; new runs write new dated files.

No memory, routines or secrets until setup is finished.


## Install
Copy `follow-audit/follow_watch.py`, `x_prices.py`, `bot_spend.py` and `weekly_rollup.py` into `$BOTS_HOME/follow-watch` and `follow-finder/creator_scout.py` plus `qol_scout.py` into `$BOTS_HOME/creator-scout`. Also copy the Game files into `$BOTS_HOME/creator-scout/game` (and `game/nsfw`): `follow-finder/game/CHAT_COMMANDS.md`, `daily_game.sh`, `game_tab.py`, `game_ui.js`, `nsfw/daily_vision.py`, `nsfw/nsfw.py`, `nsfw/refilter_today.py`. Leave the Game off until the owner says "turn on Game". Scripts only, never a sign-in or token file. Chat commands from that guide run as `python3 $BOTS_HOME/creator-scout/game/game_tab.py chat "<the owner's words>"`.

## Questions
Ask only these and save them in `$BOTS_HOME/creator-scout/config.json`: `niche_queries`, `min_followers`, `max_followers`, `verified_only`, `adult_filter`, `exclude_terms`, `shortlist_size`, `max_cost_per_run`. Never fill an answer from an example or from anyone else's setup. If the owner says "you pick", offer two or three choices with a short reason each.

## Follow Finder notes
Suggest a follower range with `python3 $BOTS_HOME/creator-scout/creator_scout.py suggest-range <their follower count>` and let the owner pick. The report lists how many creators each filter dropped.

## Cap and ledger
Run `CREW_BOT="Follow Finder" python3 $BOTS_HOME/follow-watch/bot_spend.py individual`. It marks this bot as set up from its individual template, so it keeps its own cap and ledger even if a Foreman crew lives in this `$BOTS_HOME`, and prints the mode.
- standalone (expected): ask the owner for this bot's daily spend cap and timezone and save them as `daily_spend_cap` and `timezone` in `$BOTS_HOME/creator-scout/config.json`. The bot keeps its own ledger. For a one-day raise, repeat the amount and date, wait for yes, then run `CREW_BOT="Follow Finder" python3 $BOTS_HOME/follow-watch/bot_spend.py raise <amount> --yes`. It ends at midnight by itself.

## Sign in to X
All individual bots on this Grok Bot computer share one sign-in at `/workspace/x-signin/x_signin.json` (owner-only, renewed under a lock). If a Foreman crew is here, they use its `dispatch/x_signin.json` instead. Each bot keeps its own ledger and cap.
First run `CREW_BOT="Follow Finder" python3 $BOTS_HOME/follow-watch/follow_watch.py signin-check`. If it says "Reusing", the sign-in is done: it made one account read (GET /users/me, $0.010, booked to this bot's ledger). Never sign in again. If it says no sign-in was found, this is the first bot: do steps 1 to 4.
1. Ask the owner to add `X_CLIENT_ID` and `X_CLIENT_SECRET` as stored secrets. Never in chat.
2. Before you send or open the link, tell the owner the sign-in finishes in this bot's own browser. If it does not, stop. Never ask for the callback address, the code, or a token in chat.
3. Start `CREW_BOT="Follow Finder" python3 $BOTS_HOME/follow-watch/follow_watch.py auth` in the background. Open the address it prints in the bot's own browser. The owner clicks Authorize and it finishes by itself.
4. If the page after Authorize does not finish the sign-in, stop. Do not ask the owner to copy the address bar, and do not put a callback address, code, or token into a command, a log, or this chat. If the script prints a backup that asks for that address, do not use it. The owner approves again in this bot's own browser, or finishes on the sign-in screen or terminal the script already opened. If X says the code expired, start auth again and send a new link. Do not ask them to send the old address.
5. One X app covers every bot on this Grok Bot. Signing in with the same app on a second Grok Bot or another computer logs this one out. Do not run `auth --force` unless the owner says yes. That command logs the other bots on this X app out.

## Self-check
Run one free check: `CREW_BOT="Follow Finder" python3 $BOTS_HOME/follow-watch/bot_spend.py mode`, then `python3 $BOTS_HOME/creator-scout/creator_scout.py suggest-range 1000` (no X reads). Report anything FLAGGED. Never report a 0 for something that was not read.

## Routines

Offer each routine below. Say what it is for and what it costs. Create it only after the owner says yes to that routine. Never create a routine they did not accept.

- Daily search. One creator search. About $0.45 a run. The Game stays off until the owner says "turn on Game".
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
  - `never show @name` and `show @name again` (Never show tab with undo when hosted. Returning soon lists people back from the 60-day rest)
- One hosted bot: its own page is its home, and follow-ups show there.
- Billing: say the one-time billed-check line from `python3 /workspace/foreman/foreman/v11.py billing-setup-note` during setup. Until console.x.com is signed in in the bot's browser, spend shows as labeled estimates.

What this bot got in v1.1:
- Stats strip: kept, dropped free, paid checks skipped.
- Free pre-screen drops out-of-range, already followed, already shown, never-show and filtered accounts before any paid check.
- Language and size quotas are the owner's own settings (`language_quota`, `size_quota`), off by default. Never set one unless the owner asks.
- The language floor is off until setup. Ask which languages to favor and what minimum share each one should get. Save only that answer in `lang_balance`. Blank stays `{}`. A listed share is a floor, not a cap. Never copy a language mix from another account. `lang_balance_slack` is unused and kept so older configs still load. `size_bands` are floors filled after the language floor. They never push a language under its floor.
- After `sensitive_rest.fails` (3) sensitive-media fails, that account rests `sensitive_rest.days` (30) and is skipped before any paid lookup.
- The free pre-screen also drops casino or betting, AI tool or product, promo or giveaway, and glamour, plus any `offtopic_terms` you add. Matches are whole words.
- Engagement-per-follower chip and sort by engagement. The follows-you chip shows only when Follow Audit is installed.
- Never show tab with undo, and Returning soon from the 60-day rest.

## Game tab (off by default)
Say "turn on Game" to add a daily Game tab to the Follow Finder page: a Daily Pack of 5, a Blind Taste Test, Not like this rules with Undo, and a score that counts only follows Follow Audit confirms. Notes on rules that can only be partly checked stay on Rules learned. Daily Pack cards do not show them. It costs $0 unless you turn on the optional image check. The NSFW filter is always on. Say `not like @name because ...`, `undo rule ...` or `already following @name` in chat any time.
**Embeds and images:** the Game stays off until you say "turn on Game". The Daily Pack uses only X's official embed widget (`platform.twitter.com/widgets.js`). If an embed does not load, the card shows the saved post text. Unrated picks stay blurred. The optional image check (`game_image_check`, **off by default**) uses official media expansions, shows its cost first, and reads nothing without `--yes`.
